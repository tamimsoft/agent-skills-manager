"""OpenCode adapter."""

import json
import os
import sys
from pathlib import Path

from agent_skills.adapter_common import apply_context_budget
from agent_skills.project import find_project_root
from agent_skills.manifest import load_manifest, selected_ids
from agent_skills.config import resolve_library_root
from agent_skills.discovery import discover_skills
from agent_skills.lock import AdvisoryLock, LockError
from agent_skills.detection import detect_technologies


def _opencode_exe(cfg):
    if isinstance(cfg, dict):
        p = (cfg.get("agent_paths") or {}).get("opencode")
        if p:
            return p
    return "opencode"


def _permission_rules(selected_agent_ids):
    # V2 permissions array (execution-time): blocks loading unselected skills.
    rules = [{"action": "skill", "resource": "*", "effect": "deny"}]
    for aid in selected_agent_ids:
        rules.append({"action": "skill", "resource": aid, "effect": "allow"})
    return rules


def _policy_rules(selected_agent_ids):
    # Policies (binary) actually remove denied skills from the catalog.
    rules = [{"action": "skill.use", "resource": "*", "effect": "deny"}]
    for aid in selected_agent_ids:
        rules.append({"action": "skill.use", "resource": aid, "effect": "allow"})
    return rules


def _sidecar_path(opencode_json_path):
    # Store sidecar inside the ignored .agents/ directory.
    root = Path(opencode_json_path).parent
    return root / ".agents" / "opencode-owned-rules.json"


def _load_json(path):
    if not Path(path).exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _agent_ids_for_selected(cfg, sel):
    records, warnings, errors = discover_skills(
        library_root=resolve_library_root(cfg),
        allowed_roots=cfg.get("allowed_roots", []) if isinstance(cfg, dict) else [],
        overrides=cfg.get("skill_overrides", {}) if isinstance(cfg, dict) else {},
        no_cache=True,
        cache_file=None,
    )
    rec_map = {r["dir_name"]: r for r in records}
    ids = []
    for sid in sel:
        rec = rec_map.get(sid)
        if rec is None:
            raise ValueError("selected skill missing from library: %s" % sid)
        aid = (rec.get("agent_id") or {}).get("opencode")
        # Default: use dir_name as agent_id until V1/V3 verified.
        if not aid:
            aid = rec["dir_name"]
        ids.append(aid)
    return ids, warnings, rec_map


def _apply_rules_to_config(cfg_obj, new_rules, new_policies=None):
    """Return (new_config, changed) preserving unrelated settings."""
    cfg_obj = dict(cfg_obj) if isinstance(cfg_obj, dict) else {}
    perms = cfg_obj.get("permissions")
    if not isinstance(perms, list):
        perms = []
    # Remove previously owned rules (exact match) then append new.
    sidecar = None
    # Caller handles sidecar; here just append new rules.
    # We'll store owned rules separately; merge by removing exact owned matches.
    owned = []
    # The caller passes owned via closure? We'll handle in apply function.
    # Simplest: replace permissions list's skill rules? Instead, append deny+allows at end.
    # To avoid duplicates, remove any prior rules identical to new_rules.
    kept = [r for r in perms if not (isinstance(r, dict) and r.get("action") == "skill")]
    kept.extend(new_rules)
    cfg_obj["permissions"] = kept
    if new_policies is not None:
        pols = cfg_obj.get("policies")
        if not isinstance(pols, list):
            pols = []
        kept_p = [r for r in pols if not (isinstance(r, dict) and r.get("action") == "skill.use")]
        kept_p.extend(new_policies)
        cfg_obj["policies"] = kept_p
    return cfg_obj


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
    # Apply context budget filtering for display.
    selected_records = [rec_map[sid] for sid in sel if sid in rec_map]
    filtered_records, skipped, total_tokens, _ = apply_context_budget(
        selected_records, sel, techs, cfg,
    )
    # Derive display agent_ids from the filtered set so output matches rules.
    filtered_ids = [(r.get("agent_id") or {}).get("opencode") or r["dir_name"] for r in filtered_records]
    rules = _permission_rules(filtered_ids)
    oc_path = root / "opencode.json"
    oc_jsonc = root / "opencode.jsonc"
    lines = []
    lines.append("Project root: %s" % root)
    if oc_jsonc.exists():
        lines.append("WARNING: opencode.jsonc exists; manager will not rewrite it. Resolve manually.")
    lines.append("Selected skills: %s" % (", ".join(sel) if sel else "(none)"))
    lines.append("Context budget: %d tokens, max %d skills" % (budget_tokens, max_skills))
    lines.append("Estimated context tokens: %d" % total_tokens)
    if skipped:
        lines.append("Skills excluded by budget: %d" % skipped)
    lines.append("OpenCode agent_ids: %s" % (", ".join(filtered_ids) if filtered_ids else "(none)"))
    lines.append("Permission rules to apply (filtered set):")
    for r in rules:
        lines.append("  %s" % json.dumps(r))
    lines.append("Policy rules to apply (removes denied skills from catalog):")
    for r in _policy_rules(filtered_ids):
        lines.append("  %s" % json.dumps(r))
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
    sel = selected_ids(man)
    try:
        ids, warnings, rec_map = _agent_ids_for_selected(cfg, sel)
    except ValueError as e:
        return 1, str(e)
    # Detect technologies for relevance-based budget filtering.
    techs = detect_technologies(root)
    # Apply context budget filtering: only allow rules for skills that fit in context.
    selected_records = [rec_map[sid] for sid in sel if sid in rec_map]
    filtered_records, skipped, _, _ = apply_context_budget(
        selected_records, sel, techs, cfg,
    )
    filtered_ids = [(r.get("agent_id") or {}).get("opencode") or r["dir_name"] for r in filtered_records]
    rules = _permission_rules(filtered_ids)
    policies = _policy_rules(filtered_ids)

    existing = {}
    if oc_path.exists():
        try:
            existing = _load_json(oc_path)
        except (OSError, ValueError) as e:
            return 1, "invalid existing JSON: %s" % e

    new_config = _apply_rules_to_config(existing, rules, policies)

    if dry_run:
        msg = "would write %s with %d permission rules" % (oc_path, len(rules))
        if skipped:
            msg += " (%d skills excluded by context budget)" % skipped
        return 0, msg

    # Confirm.
    if not (yes or sys.stdin.isatty()):
        return 4, "confirmation required (non-TTY); use --yes"
    if not yes:
        ans = input("Apply OpenCode config? [y/N] ").strip().lower()
        if ans not in ("y", "yes"):
            return 0, "aborted"

    # Atomic write.
    import tempfile
    tmp = oc_path.with_suffix(oc_path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(new_config, f, indent=2)
        f.write("\n")
    # Validate JSON round-trip.
    with tmp.open("r", encoding="utf-8") as f:
        json.load(f)
    os.replace(tmp, oc_path)

    # Sidecar owned rules.
    sidecar = _sidecar_path(oc_path)
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    with sidecar.open("w", encoding="utf-8") as f:
        json.dump({"rules": rules, "policies": policies}, f, indent=2)
        f.write("\n")

    return 0, "applied: %s (%d permission rules%s)" % (
        oc_path, len(rules), " (%d skills excluded by context budget)" % skipped if skipped else "")


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
    os.execvp(argv[0], argv)
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
        extra = getattr(args, "args", []) or []
        if extra and extra[0] == "--":
            extra = extra[1:]
        return run(cfg, extra)
    print("unknown opencode subcommand", file=sys.stderr)
    return 2