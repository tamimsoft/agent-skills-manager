"""Kilo adapter (Phase 7).

Kilo 7.8.18 confirmed via ``kilo --version``. Per Phase 0 (V14), Kilo has no
mechanism to disable its default loading of ``~/.agents/skills/`` and
``.agents/skills/`` — the adapter is therefore **additive**, not exclusive.
Every user-facing plan/apply/validate/run prints the additive limitation
notice unless V14 is later resolved.

Generation strategy (guideline §5.6, §13):
- In-place generation inside ``<project>/.kilo/skills/`` (V15 confirmed: no
  external skill-path mechanism).
- Symlinks to selected skills; marker file ``.agent-skills-managed.json``
  inside ``.kilo/skills/`` (V18 confirmed: Kilo does not misreport it).
- ``.kilo/kilo.json`` permission rules documenting managed skills.
- Build-then-swap with crash recovery (§5.5).
- Wrapper layout for frontmatter-less skills (§13.3 / §11.4): regenerate only
  the top-level SKILL.md, symlink everything else at original relative path.
"""

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from agent_skills.adapter_common import (
    apply_context_budget,
    build_skills_dir_atomic,
    build_wrapper,
    build_skill_entry,
)
from agent_skills.config import resolve_library_root
from agent_skills.detection import detect_technologies
from agent_skills.discovery import discover_skills, DiscoveryError
from agent_skills.frontmatter import parse_frontmatter
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
SKILLS_DIR_NAME = "skills"
ADDITIVE_NOTICE = (
    "notice: Kilo (7.8.18) adapter is ADDITIVE, not exclusive. "
    "Kilo loads all skills from ~/.agents/skills/ by default and has no "
    "supported mechanism to disable that (V14 confirmed negative). "
    "This manager only adds project-selected skills to .kilo/skills/; "
    "it does not restrict what Kilo discovers globally."
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
        return json.load(f)


def _apply_kilo_rules(existing, new_rules):
    """Merge skill permission rules into Kilo config, preserving unrelated keys.

    Manager-owned keys are tracked via the ``_agent_skills_managed`` key so
    re-apply removes only our own rules and preserves user-authored ones.
    """
    cfg = dict(existing) if isinstance(existing, dict) else {}
    perms = cfg.get("permission")
    if not isinstance(perms, dict):
        perms = {}
    perms = dict(perms)
    # Remove prior owned skill rules (tracked via _agent_skills_managed key).
    managed_keys = perms.get("_agent_skills_managed", [])
    if not isinstance(managed_keys, list):
        managed_keys = []
    for mk in managed_keys:
        perms.pop(mk, None)
    perms.pop("_agent_skills_managed", None)
    # Remove the wildcard deny we manage.
    perms.pop("*", None)
    # Add new rules, tracking managed keys.
    new_keys = []
    for aid, effect in new_rules.items():
        perms[aid] = effect
        new_keys.append(aid)
    perms["_agent_skills_managed"] = new_keys
    cfg["permission"] = perms
    return cfg


def _compute_kilo_agent_ids(records, sel):
    """Kilo uses declared_name as its skill identifier (§2.2, V16)."""
    rec_map = {r["dir_name"]: r for r in records}
    ids = []
    for sid in sel:
        rec = rec_map.get(sid)
        if rec is None:
            ids.append(None)
        else:
            aid = rec.get("declared_name") or sid
            ids.append(aid)
    return ids, rec_map


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
        no_cache=False,
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
    skills_dir.parent.mkdir(parents=True, exist_ok=True)

    key = _generated_dir_key(root)
    lock_path = skills_dir.parent / ".lock"

    try:
        with AdvisoryLock(lock_path):
            build_skills_dir_atomic(
                parent=skills_dir.parent,
                dest_dir=skills_dir,
                records=filtered_records,
                agent_name="kilo",
                key=key,
                build_entry_fn=build_skill_entry,
                tmp_prefix=".kilo-skills-tmp-",
                marker_filename=MARKER_FILENAME_KILO,
            )
    except LockError as e:
        print("error: %s" % e, file=sys.stderr)
        return 1

    # Write .kilo/kilo.json permission rules.
    kilo_ids, _ = _compute_kilo_agent_ids(records, sel)
    new_rules = _kilo_permission_rules(kilo_ids)
    existing = _load_kilo_json(kilo_json)
    new_config = _apply_kilo_rules(existing, new_rules)

    dry = getattr(args, "dry_run", False)
    if dry:
        print("would write %s with %d skill rules" % (kilo_json, len(new_rules)))
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

    tmp_json = kilo_json.with_suffix(kilo_json.suffix + ".tmp")
    with tmp_json.open("w", encoding="utf-8") as f:
        json.dump(new_config, f, indent=2)
        f.write("\n")
    with tmp_json.open("r", encoding="utf-8") as f:
        json.load(f)
    os.replace(tmp_json, kilo_json)

    print("applied: %s (%d skills, %d skill rules)" % (
        kilo_json, len(selected_records), len(new_rules)))
    if skipped:
        print("notice: %d skills excluded by context budget" % skipped)
    print(ADDITIVE_NOTICE)
    print("\nPer-agent resolution (kilo):")
    print(resolution_summary(res))

    # For `run`: launch kilo.
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
