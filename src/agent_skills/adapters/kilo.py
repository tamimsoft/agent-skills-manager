"""Kilo adapter; project skill discovery and permissions were tested on 7.8.18.

Kilo discovers project skills from ``.kilo/skills/``, but does not follow
project links whose targets are outside the worktree. The adapter therefore
copies selected skills into the managed project directory. Kilo also
continues to catalog ``~/.agents/skills/`` entries; permission rules do not
remove those entries from its debug catalog, so this adapter is additive.
"""

import hashlib
import json
import os
import sys
from pathlib import Path

from agent_skills.adapter_common import (
    apply_context_budget,
    backup_config_file,
    build_skill_copy,
    build_skills_dir_atomic,
    write_json_atomic,
)
from agent_skills.config import resolve_library_root
from agent_skills.detection import detect_technologies
from agent_skills.discovery import discover_skills, DiscoveryError
from agent_skills.frontmatter import parse_frontmatter
from agent_skills.identity import permission_ids_for_records
from agent_skills.links import MARKER_FILENAME, read_marker
from agent_skills.lock import AdvisoryLock, LockError
from agent_skills.manifest import load_manifest, selected_ids
from agent_skills.project import find_project_root
from agent_skills.recommend import filter_skills_for_context
from agent_skills.resolution import (
    AVAILABLE, CONFLICT, UNAVAILABLE, UNRESOLVED,
    resolve_resolutions, resolution_summary,
)

MARKER_FILENAME_KILO = ".agent-skills-managed.json"
KILO_JSON_FILENAME = "kilo.json"
KILO_OWNED_RULES_FILENAME = "kilo-owned-rules.json"
SKILLS_DIR_NAME = "skills"
ADDITIVE_NOTICE = (
    "notice: Kilo 7.8.18 remains additive: project-selected skills are copied "
    "to .kilo/skills/, but ~/.agents/skills/ entries remain in Kilo's catalog. "
    "permission.skill rules do not remove global entries from that catalog."
)


def _kilo_exe(cfg):
    if isinstance(cfg, dict):
        p = (cfg.get("agent_paths") or {}).get("kilo")
        if p:
            return p
    return "kilo"


def _project_kilo_dir(root):
    return Path(root) / ".kilo"


def _project_skills_dir(root):
    return _project_kilo_dir(root) / SKILLS_DIR_NAME


def _project_kilo_json(root):
    return _project_kilo_dir(root) / KILO_JSON_FILENAME


def _project_kilo_jsonc(root):
    return _project_kilo_dir(root) / "kilo.jsonc"


def _project_kilo_owned_rules(root):
    return Path(root) / ".agents" / KILO_OWNED_RULES_FILENAME


def _generated_dir_key(root):
    return "%s-%s" % (root.name,
                      hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:12])


def _kilo_permission_rules(selected_agent_ids):
    """Build Kilo permission.skill rules (dict format per Kilo schema)."""
    rules = {}
    rules["*"] = "deny"
    for aid in selected_agent_ids:
        rules[aid] = "allow"
    return rules


def _load_kilo_json(path):
    if not Path(path).exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Kilo config must contain a JSON object")
    return data


def _load_owned_rules(path):
        if not Path(path).exists():
            return {}
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or data.get("schema_version") != 1:
            raise ValueError("invalid Kilo owned-rules sidecar")
        return data


def _apply_kilo_rules(existing, new_rules, owned_rules=None):
    """Merge skill permission rules into Kilo config, preserving unrelated keys.

    Manager-owned rules are recorded in a sidecar, never in Kilo's config.
    """
    cfg = dict(existing) if isinstance(existing, dict) else {}
    perms = cfg.get("permission")
    if perms is None:
        perms = {}
    if not isinstance(perms, dict):
        raise ValueError("Kilo permission config must be an object")
    perms = dict(perms)
    if owned_rules is not None and not isinstance(owned_rules, dict):
        raise ValueError("Kilo owned-rules sidecar must contain a JSON object")
    legacy_keys = perms.pop("_agent_skills_managed", [])
    if not isinstance(legacy_keys, list):
        legacy_keys = []

    skill_rules = perms.get("skill")
    if skill_rules is None:
        skill_rules = {}
    if not isinstance(skill_rules, dict):
        raise ValueError("Kilo permission.skill config must be an object")
    skill_rules = dict(skill_rules)
    warnings = []
    previous_rules = (owned_rules or {}).get("rules", {})
    if not isinstance(previous_rules, dict):
        raise ValueError("Kilo owned-rules sidecar has an invalid rules object")

    for key, value in previous_rules.items():
        if skill_rules.get(key) == value:
            skill_rules.pop(key)
        else:
            warnings.append(
                "preserving user-edited Kilo permission.skill rule for %s" % key
            )

    for key in legacy_keys:
        expected = "deny" if key == "*" else "allow"
        if perms.get(key) == expected:
            perms.pop(key)
        elif key in perms:
            warnings.append("preserving conflicting legacy Kilo permission rule for %s" % key)

    manager_rules = {}
    for key, value in new_rules.items():
        if key in skill_rules:
            if skill_rules[key] != value:
                warnings.append(
                    "preserving user Kilo permission.skill rule for %s" % key
                )
            continue
        skill_rules[key] = value
        manager_rules[key] = value

    # Keep the wildcard first and selected-name rules last so they override it.
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
        perms["skill"] = ordered_rules
    else:
        perms.pop("skill", None)
    cfg["permission"] = perms
    return cfg, {"schema_version": 1, "rules": manager_rules}, warnings


def _compute_kilo_agent_ids(records, sel):
    """Kilo uses declared_name as its skill identifier (§2.2, V16)."""
    rec_map = {r["dir_name"]: r for r in records}
    selected_records = []
    for sid in sel:
        rec = rec_map.get(sid)
        if rec is None:
            selected_records.append({"dir_name": sid})
        else:
            selected_records.append(rec)
    ids = permission_ids_for_records(selected_records, "kilo")
    return ids, rec_map


def _kilo_permission_rules_for_records(records):
    """Build permission rules only for skills included in the generated directory."""
    selected = [record["dir_name"] for record in records]
    ids, _ = _compute_kilo_agent_ids(records, selected)
    return _kilo_permission_rules(ids)


def launch_kilo(args, cfg):
    passthrough = getattr(args, "args", []) or []
    if passthrough and passthrough[0] == "--":
        passthrough = passthrough[1:]

    try:
        root = find_project_root()
    except ValueError as e:
        print("error: %s" % e, file=sys.stderr)
        return 1
    man, errs = load_manifest(root)
    if man is None:
        print("error: %s" % "; ".join(errs), file=sys.stderr)
        return 1
    if errs:
        print("error: invalid manifest: %s" % "; ".join(errs), file=sys.stderr)
        return 1

    sel = selected_ids(man)
    records, warnings, errors = discover_skills(
        library_root=resolve_library_root(cfg),
        allowed_roots=cfg.get("allowed_roots", []) if isinstance(cfg, dict) else [],
        overrides=cfg.get("skill_overrides", {}) if isinstance(cfg, dict) else {},
        no_cache=bool(getattr(args, "dry_run", False)),
        cache_file=None,
    )
    rec_map = {r["dir_name"]: r for r in records}
    selected_records = []
    for sid in sel:
        if sid not in rec_map:
            print("error: selected skill missing from library: %s" % sid, file=sys.stderr)
            return 1
        selected_records.append(rec_map[sid])

    # Per-agent resolution against Kilo (§2.2, V16 collisions).
    agents_block = man.get("agents") or {}
    enabled = [a for a, v in agents_block.items()
               if isinstance(v, dict) and v.get("enabled", True)]
    res = resolve_resolutions(rec_map.values(), sel, ["kilo"] if "kilo" in enabled else [])

    # Detect technologies for relevance-based budget filtering.
    techs = detect_technologies(root)
    # Context budget filtering: only symlink skills that fit in context.
    filtered_records, skipped, _, cwarnings = apply_context_budget(
        selected_records, sel, techs, cfg,
    )
    if cwarnings:
        for w in cwarnings:
            print("notice: %s" % w, file=sys.stderr)

    skills_dir = _project_skills_dir(root)
    kilo_json = _project_kilo_json(root)
    kilo_jsonc = _project_kilo_jsonc(root)
    owned_rules_path = _project_kilo_owned_rules(root)
    if kilo_jsonc.exists():
        print("error: .kilo/kilo.jsonc exists; refusing to rewrite it as JSON", file=sys.stderr)
        return 4

    try:
        existing = _load_kilo_json(kilo_json)
        owned_rules = _load_owned_rules(owned_rules_path)
        new_rules = _kilo_permission_rules_for_records(filtered_records)
        new_config, new_owned_rules, rule_warnings = _apply_kilo_rules(
            existing, new_rules, owned_rules,
        )
    except (OSError, ValueError) as e:
        print("error: unable to read Kilo config: %s" % e, file=sys.stderr)
        return 1
    if rule_warnings:
        for warning in rule_warnings:
            print("notice: %s" % warning, file=sys.stderr)
    permission = existing.get("permission", {})
    legacy_migration = isinstance(permission, dict) and isinstance(
        permission.get("_agent_skills_managed"), list,
    )

    key = _generated_dir_key(root)
    lock_path = skills_dir.parent / ".lock"

    dry = getattr(args, "dry_run", False)
    if dry:
        print("would generate %s with %d selected skills" % (skills_dir, len(filtered_records)))
        print("would write %s with %d skill permission rules" % (kilo_json, len(new_rules)))
        if getattr(args, "run_kilo", False):
            print("dry-run: would run Kilo in %s with args: %s" % (
                root, " ".join(passthrough),
            ))
        print(ADDITIVE_NOTICE)
        print("\nPer-agent resolution (kilo):")
        print(resolution_summary(res))
        return 0

    if not getattr(args, "yes", False) and not sys.stdin.isatty():
        print("confirmation required (non-TTY); use --yes", file=sys.stderr)
        return 4
    if not getattr(args, "yes", False):
        ans = input("Apply Kilo config? [y/N] ").strip().lower()
        if ans not in ("y", "yes"):
            print("aborted", file=sys.stderr)
            return 0

    try:
        if legacy_migration and kilo_json.exists() and not owned_rules_path.exists():
            backup = backup_config_file(root, kilo_json, "kilo.json")
            print("backed up legacy Kilo config: %s" % backup)
    except OSError as e:
        print("error: unable to back up legacy Kilo config: %s" % e, file=sys.stderr)
        return 1

    from agent_skills.cli import generate_agents_md
    wrote_agents, msg_agents, agents_md_content = generate_agents_md(root, techs, cfg)
    if msg_agents:
        print("notice: %s" % msg_agents)
    if agents_md_content is None:
        print("error: %s" % msg_agents, file=sys.stderr)
        return 1

    skills_dir.parent.mkdir(parents=True, exist_ok=True)
    try:
        with AdvisoryLock(lock_path):
            build_skills_dir_atomic(
                parent=skills_dir.parent,
                dest_dir=skills_dir,
                records=filtered_records,
                agent_name="kilo",
                key=key,
                build_entry_fn=build_skill_copy,
                tmp_prefix=".kilo-skills-tmp-",
                marker_filename=MARKER_FILENAME_KILO,
                agents_md_content=agents_md_content,
            )
    except LockError as e:
        print("error: %s" % e, file=sys.stderr)
        return 1
    except (OSError, RuntimeError) as e:
        print("error: failed to generate Kilo skills: %s" % e, file=sys.stderr)
        return 1

    try:
        write_json_atomic(kilo_json, new_config)
        write_json_atomic(owned_rules_path, new_owned_rules)
    except OSError as e:
        print("error: failed to write Kilo config: %s" % e, file=sys.stderr)
        return 1

    print("applied: %s (%d skills, %d skill rules)" % (
        kilo_json, len(filtered_records), len(new_rules)))
    if skipped:
        print("notice: %d skills excluded by context budget" % skipped)
    print(ADDITIVE_NOTICE)
    print("\nPer-agent resolution (kilo):")
    print(resolution_summary(res))

    # For `run`: launch kilo.
    dry = getattr(args, "dry_run", False)
    if getattr(args, "run_kilo", False):
        argv = [_kilo_exe(cfg), "run", "--dir", str(root)]
        argv += passthrough
        sys.stdout.flush()
        sys.stderr.flush()
        os.execvp(argv[0], argv)
    return 0


def kilo_plan(cfg):
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
    records, warnings, errors = discover_skills(
        library_root=resolve_library_root(cfg),
        allowed_roots=cfg.get("allowed_roots", []) if isinstance(cfg, dict) else [],
        overrides=cfg.get("skill_overrides", {}) if isinstance(cfg, dict) else {},
        no_cache=True,
        cache_file=None,
    )
    rec_map = {r["dir_name"]: r for r in records}
    agents_block = man.get("agents") or {}
    enabled = [a for a, v in agents_block.items()
               if isinstance(v, dict) and v.get("enabled", True)]
    res = resolve_resolutions(rec_map.values(), sel, ["kilo"] if "kilo" in enabled else [])
    lines = []
    lines.append("Project root: %s" % root)
    if _project_kilo_jsonc(root).exists():
        lines.append("WARNING: .kilo/kilo.jsonc exists; manager will not rewrite it.")
    lines.append("Selected skills: %s" % (", ".join(sel) if sel else "(none)"))
    lines.append(ADDITIVE_NOTICE)
    lines.append("\nPer-agent resolution (kilo):")
    lines.append(resolution_summary(res))
    return 0, "\n".join(lines)


def kilo_validate(cfg):
    try:
        root = find_project_root()
    except ValueError as e:
        return 1, str(e)
    man, errs = load_manifest(root)
    if man is None:
        return 1, "; ".join(errs)
    if errs:
        return 1, "; ".join(errs)
    if _project_kilo_jsonc(root).exists():
        return 1, ".kilo/kilo.jsonc exists; manager will not rewrite it as JSON"
    kilo_json = _project_kilo_json(root)
    if kilo_json.exists():
        try:
            data = _load_kilo_json(kilo_json)
            permission = data.get("permission", {})
            if not isinstance(permission, dict):
                return 1, "Kilo permission config must be an object"
            skill_rules = permission.get("skill", {})
            if not isinstance(skill_rules, dict):
                return 1, "Kilo permission.skill config must be an object"
            _load_owned_rules(_project_kilo_owned_rules(root))
        except (OSError, ValueError) as e:
            return 1, "invalid Kilo config: %s" % e
        if "_agent_skills_managed" in permission:
            return 1, "legacy Kilo rules found; run 'agent-skills kilo apply' to migrate"
    sel = selected_ids(man)
    records, warnings, errors = discover_skills(
        library_root=resolve_library_root(cfg),
        allowed_roots=cfg.get("allowed_roots", []) if isinstance(cfg, dict) else [],
        overrides=cfg.get("skill_overrides", {}) if isinstance(cfg, dict) else {},
        no_cache=True,
        cache_file=None,
    )
    rec_map = {r["dir_name"]: r for r in records}
    for sid in sel:
        if sid not in rec_map:
            return 1, "manifest references missing skill: %s" % sid
    agents_block = man.get("agents") or {}
    enabled = [a for a, v in agents_block.items()
               if isinstance(v, dict) and v.get("enabled", True)]
    res = resolve_resolutions(rec_map.values(), sel, ["kilo"] if "kilo" in enabled else [])
    lines = []
    lines.append("manifest: %s (selected=%d)" % (
        Path(root) / ".agents" / "skills.json", len(sel)))
    lines.append(ADDITIVE_NOTICE)
    lines.append("\nPer-agent resolution (kilo):")
    lines.append(resolution_summary(res))
    if errors:
        for e in errors:
            lines.append("discovery error: %s" % e)
        return 1, "\n".join(lines)
    return 0, "\n".join(lines)
