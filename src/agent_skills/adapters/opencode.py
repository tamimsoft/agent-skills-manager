"""OpenCode adapter."""

import json
import os
import sys
from pathlib import Path

from agent_skills.adapter_common import (
    apply_context_budget,
    backup_config_file,
    write_json_atomic,
)
from agent_skills.project import find_project_root
from agent_skills.manifest import load_manifest, selected_ids
from agent_skills.config import resolve_library_root
from agent_skills.discovery import discover_skills
from agent_skills.lock import AdvisoryLock, LockError
from agent_skills.detection import detect_technologies
from agent_skills.identity import permission_ids_for_records
from agent_skills.manifest import agent_is_enabled


def _opencode_exe(cfg):
    if isinstance(cfg, dict):
        p = (cfg.get("agent_paths") or {}).get("opencode")
        if p:
            return p
    return "opencode"


def _permission_rules(selected_agent_ids):
    rules = {"*": "deny"}
    for aid in selected_agent_ids:
        rules[aid] = "allow"
    return rules


def _sidecar_path(opencode_json_path):
    # Store sidecar inside the ignored .agents/ directory.
    root = Path(opencode_json_path).parent
    return root / ".agents" / "opencode-owned-rules.json"


def _load_json(path):
    if not Path(path).exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("OpenCode config must contain a JSON object")
    return data


def _load_owned_rules(path):
    if not Path(path).exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("OpenCode owned-rules sidecar must contain a JSON object")
    if data.get("schema_version") == 1 and isinstance(data.get("rules"), dict):
        return data
    if isinstance(data.get("rules"), list):
        return {"schema_version": 0, "rules": {}}
    raise ValueError("invalid OpenCode owned-rules sidecar")


def _agent_ids_for_selected(cfg, sel):
    records, warnings, errors = discover_skills(
        library_root=resolve_library_root(cfg),
        allowed_roots=cfg.get("allowed_roots", []) if isinstance(cfg, dict) else [],
        overrides=cfg.get("skill_overrides", {}) if isinstance(cfg, dict) else {},
        no_cache=True,
        cache_file=None,
    )
    rec_map = {r["dir_name"]: r for r in records}
    selected_records = []
    for sid in sel:
        rec = rec_map.get(sid)
        if rec is None:
            raise ValueError("selected skill missing from library: %s" % sid)
        selected_records.append(rec)
    ids = permission_ids_for_records(selected_records, "opencode")
    return ids, warnings, rec_map


def _apply_rules_to_config(cfg_obj, new_rules, owned_rules=None):
    """Apply nested skill permissions and preserve all user-authored rules."""
    if not isinstance(cfg_obj, dict):
        raise ValueError("OpenCode config must contain a JSON object")
    if owned_rules is not None and not isinstance(owned_rules, dict):
        raise ValueError("OpenCode owned-rules sidecar must contain a JSON object")
    cfg_obj = dict(cfg_obj)
    warnings = []

    for legacy_name in ("permissions", "policies"):
        legacy = cfg_obj.get(legacy_name)
        if isinstance(legacy, list):
            kept = [
                rule for rule in legacy
                if not (
                    isinstance(rule, dict)
                    and rule.get("source") == "agent-skills-manager"
                )
            ]
            if kept:
                cfg_obj[legacy_name] = kept
            else:
                cfg_obj.pop(legacy_name, None)

    permission = cfg_obj.get("permission")
    if permission is None:
        permission = {}
    if not isinstance(permission, dict):
        raise ValueError("OpenCode permission config must be an object")
    permission = dict(permission)
    skill_rules = permission.get("skill")
    if skill_rules is None:
        skill_rules = {}
    if not isinstance(skill_rules, dict):
        raise ValueError("OpenCode permission.skill config must be an object")
    skill_rules = dict(skill_rules)

    previous_rules = (owned_rules or {}).get("rules", {})
    if not isinstance(previous_rules, dict):
        raise ValueError("OpenCode owned-rules sidecar has an invalid rules object")
    for key, value in previous_rules.items():
        if skill_rules.get(key) == value:
            skill_rules.pop(key)
        else:
            warnings.append("preserving user-edited OpenCode skill rule for %s" % key)

    manager_rules = {}
    for key, value in new_rules.items():
        if key in skill_rules:
            if skill_rules[key] != value:
                warnings.append("preserving user OpenCode skill rule for %s" % key)
            continue
        skill_rules[key] = value
        manager_rules[key] = value

    ordered_rules = {}
    if "*" in skill_rules:
        ordered_rules["*"] = skill_rules.pop("*")
    selected_keys = [key for key in new_rules if key != "*"]
    for key, value in skill_rules.items():
        if key not in selected_keys:
            ordered_rules[key] = value
    for key in selected_keys:
        if key in skill_rules:
            ordered_rules[key] = skill_rules[key]
    if ordered_rules:
        permission["skill"] = ordered_rules
    else:
        permission.pop("skill", None)
    cfg_obj["permission"] = permission
    return cfg_obj, {"schema_version": 1, "rules": manager_rules}, warnings


def plan(cfg):
    try:
        root = find_project_root()
    except ValueError as e:
        return 1, str(e)
    man, errs = load_manifest(root)
    if man is None:
        return 1, "; ".join(errs)
    if errs:
        return 1, "; ".join(errs)
    sel = selected_ids(man)
    try:
        ids, warnings, rec_map = _agent_ids_for_selected(cfg, sel)
    except ValueError as e:
        return 1, str(e)
    # Detect technologies for relevance-based budget filtering.
    techs = detect_technologies(root)
    lines = []
    # Apply context budget filtering for display.
    selected_records = [rec_map[sid] for sid in sel if sid in rec_map]
    filtered_records, skipped, total_tokens, _ = apply_context_budget(
        selected_records, sel, techs, cfg,
    )
    # Derive display agent_ids from the filtered set so output matches rules.
    try:
        filtered_ids = permission_ids_for_records(filtered_records, "opencode")
    except ValueError as e:
        return 1, str(e)
    rules = _permission_rules(filtered_ids)
    oc_path = root / "opencode.json"
    oc_jsonc = root / "opencode.jsonc"
    lines.append("Project root: %s" % root)
    if oc_jsonc.exists():
        lines.append("WARNING: opencode.jsonc exists; manager will not rewrite it. Resolve manually.")
    lines.append("Selected skills: %s" % (", ".join(sel) if sel else "(none)"))
    budget_tokens = cfg.get("skill_context_budget_tokens") if isinstance(cfg, dict) else 32768
    max_skills = cfg.get("max_skills_in_context") if isinstance(cfg, dict) else 50
    lines.append("Context budget: %d tokens, max %d skills" % (budget_tokens, max_skills))
    lines.append("Estimated context tokens: %d" % total_tokens)
    if skipped:
        lines.append("Skills excluded by budget: %d" % skipped)
    lines.append("OpenCode agent_ids: %s" % (", ".join(filtered_ids) if filtered_ids else "(none)"))
    lines.append("Permission rules to apply (filtered set):")
    lines.append("  %s" % json.dumps({"permission": {"skill": rules}}))
    if oc_path.exists():
        lines.append("Existing opencode.json will be preserved (unrelated settings kept).")
    else:
        lines.append("opencode.json will be created.")
    return 0, "\n".join(lines)


def validate(cfg):
    try:
        root = find_project_root()
    except ValueError as e:
        return 1, str(e)
    oc_path = root / "opencode.json"
    oc_jsonc = root / "opencode.jsonc"
    msgs = []
    if oc_jsonc.exists():
        msgs.append("opencode.jsonc present (manager does not rewrite it)")
    if not oc_path.exists():
        msgs.append("opencode.json missing")
        return 1, "\n".join(msgs)
    try:
        data = _load_json(oc_path)
    except (OSError, ValueError) as e:
        return 1, "invalid JSON: %s" % e
    permission = data.get("permission", {})
    if not isinstance(permission, dict):
        return 1, "OpenCode permission config must be an object"
    skill_rules = permission.get("skill", {})
    if not isinstance(skill_rules, dict):
        return 1, "OpenCode permission.skill config must be an object"
    try:
        _load_owned_rules(_sidecar_path(oc_path))
    except (OSError, ValueError) as e:
        return 1, "invalid OpenCode owned-rules sidecar: %s" % e
    msgs.append("opencode.json valid JSON")
    man, errs = load_manifest(root)
    if errs:
        msgs.append("manifest errors: %s" % "; ".join(errs))
        return 1, "\n".join(msgs)
    sel = selected_ids(man)
    msgs.append("manifest selected: %s" % (", ".join(sel) if sel else "(none)"))
    return 0, "\n".join(msgs)


def apply(cfg, dry_run=False, yes=False):
    try:
        root = find_project_root()
    except ValueError as e:
        return 1, str(e)
    oc_path = root / "opencode.json"
    oc_jsonc = root / "opencode.jsonc"
    if oc_jsonc.exists():
        return 4, "opencode.jsonc exists; refusing to rewrite as JSON. Resolve manually."
    man, errs = load_manifest(root)
    if man is None or errs:
        return 1, "; ".join(errs) if errs else "manifest missing"
    if not agent_is_enabled(man, "opencode"):
        return 4, "OpenCode is disabled in .agents/skills.json; enable it before managed OpenCode operations"
    sel = selected_ids(man)
    try:
        ids, warnings, rec_map = _agent_ids_for_selected(cfg, sel)
    except ValueError as e:
        return 1, str(e)
    # Detect technologies for relevance-based budget filtering.
    techs = detect_technologies(root)
    # Compute the managed instructions without writing before the dry-run and
    # confirmation gates.
    from agent_skills.cli import generate_agents_md
    wrote_agents, msg_agents, agents_md_content = generate_agents_md(
        root, techs, cfg, write=False,
    )
    if agents_md_content is None:
        return 1, msg_agents
    # Apply context budget filtering: only allow rules for skills that fit in context.
    selected_records = [rec_map[sid] for sid in sel if sid in rec_map]
    filtered_records, skipped, _, _ = apply_context_budget(
        selected_records, sel, techs, cfg,
    )
    try:
        filtered_ids = permission_ids_for_records(filtered_records, "opencode")
    except ValueError as e:
        return 1, str(e)
    rules = _permission_rules(filtered_ids)

    existing = {}
    if oc_path.exists():
        try:
            existing = _load_json(oc_path)
        except (OSError, ValueError) as e:
            return 1, "invalid existing JSON: %s" % e
    sidecar = _sidecar_path(oc_path)
    try:
        owned_rules = _load_owned_rules(sidecar)
        new_config, new_owned_rules, rule_warnings = _apply_rules_to_config(
            existing, rules, owned_rules,
        )
    except (OSError, ValueError) as e:
        return 1, "unable to prepare OpenCode config: %s" % e
    legacy_migration = any(
        isinstance(existing.get(key), list)
        and any(
            isinstance(rule, dict) and rule.get("source") == "agent-skills-manager"
            for rule in existing[key]
        )
        for key in ("permissions", "policies")
    )

    if dry_run:
        msg = "would write %s with %d permission rules" % (oc_path, len(rules))
        if skipped:
            msg += " (%d skills excluded by context budget)" % skipped
        if rule_warnings:
            msg += "\n" + "\n".join("notice: " + warning for warning in rule_warnings)
        return 0, msg

    # Confirm.
    if not (yes or sys.stdin.isatty()):
        return 4, "confirmation required (non-TTY); use --yes"
    if not yes:
        ans = input("Apply OpenCode config? [y/N] ").strip().lower()
        if ans not in ("y", "yes"):
            return 0, "aborted"

    try:
        if (
            legacy_migration
            and owned_rules.get("schema_version") != 1
            and oc_path.exists()
        ):
            backup = backup_config_file(root, oc_path, "opencode.json")
            print("backed up legacy OpenCode config: %s" % backup)
    except OSError as e:
        return 1, "unable to back up legacy OpenCode config: %s" % e

    wrote_agents, msg_agents, agents_md_content = generate_agents_md(root, techs, cfg)
    if msg_agents:
        print("notice: %s" % msg_agents)
    if agents_md_content is None:
        return 1, msg_agents

    try:
        write_json_atomic(oc_path, new_config)
        write_json_atomic(sidecar, new_owned_rules)
    except (OSError, ValueError) as e:
        return 1, "failed to write OpenCode config: %s" % e

    msg = "applied: %s (%d permission rules%s)" % (
        oc_path, len(rules),
        " (%d skills excluded by context budget)" % skipped if skipped else "",
    )
    if rule_warnings:
        msg += "\n" + "\n".join("notice: " + warning for warning in rule_warnings)
    return 0, msg


def run(cfg, extra=None):
    extra = extra or []
    # Apply permissions implicitly so managed launch restricts skills in one command.
    rc, msg = apply(cfg, dry_run=False, yes=True)
    if rc != 0:
        print(msg, file=sys.stderr)
        return rc
    rc, msg = validate(cfg)
    if rc != 0:
        print(msg, file=sys.stderr)
        return rc
    argv = [_opencode_exe(cfg), "run"] + (extra or [])
    sys.stdout.flush()
    sys.stderr.flush()
    try:
        os.execvp(argv[0], argv)
    except OSError as exc:
        print(
            "error: unable to launch OpenCode using %r; check PATH or agent_paths.opencode: %s"
            % (argv[0], exc),
            file=sys.stderr,
        )
        return 127
    return 0


def run_opencode_subcommand(args, cfg):
    sub = getattr(args, "oc_sub", None)
    if sub == "plan":
        rc, msg = plan(cfg)
        print(msg)
        return rc
    if sub == "apply":
        dry = getattr(args, "dry_run", False)
        yes = getattr(args, "yes", False)
        rc, msg = apply(cfg, dry_run=dry, yes=yes)
        print(msg)
        return rc
    if sub == "validate":
        rc, msg = validate(cfg)
        print(msg)
        return rc
    if sub == "run":
        dry = getattr(args, "dry_run", False)
        extra = getattr(args, "args", []) or []
        if extra and extra[0] == "--":
            extra = extra[1:]
        if dry:
            print("dry-run: would apply opencode config and run opencode with args: %s" % extra)
            return 0
        return run(cfg, extra)
    print("unknown opencode subcommand", file=sys.stderr)
    return 2