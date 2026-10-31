"""Junie adapter."""

import os
import sys
from pathlib import Path

from agent_skills.project import find_project_root
from agent_skills.manifest import load_manifest, selected_ids, validate_manifest
from agent_skills.config import resolve_library_root
from agent_skills.discovery import discover_skills, DiscoveryError
from agent_skills.links import generate_project_skills_dir, read_marker
from agent_skills.lock import AdvisoryLock, LockError


def _junie_exe(cfg):
    if isinstance(cfg, dict):
        p = (cfg.get("agent_paths") or {}).get("junie")
        if p:
            return p
    return "junie"


def _generated_dir(cfg, root):
    generated_root = cfg.get("generated_root") if isinstance(cfg, dict) else None
    if not generated_root:
        generated_root = str(Path.home() / ".local" / "share" / "agent-skills" / "projects")
    import hashlib
    key = "%s-%s" % (root.name, hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:12])
    return Path(generated_root) / key, key


def launch_junie(args, cfg):
    prepare = getattr(args, "prepare", False)
    passthrough = getattr(args, "args", []) or []
    # Filter leading '--'
    if passthrough and passthrough[0] == "--":
        passthrough = passthrough[1:]

    # Refuse conflicting flags.
    for a in passthrough:
        if a.startswith("--skill-location") or a.startswith("--skill-default-locations"):
            print("error: user-supplied skill flags would defeat managed policy", file=sys.stderr)
            return 4

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

    gen_dir, key = _generated_dir(cfg, root)
    gen_dir.parent.mkdir(parents=True, exist_ok=True)
    lock_path = gen_dir.parent / ".lock"
    try:
        with AdvisoryLock(lock_path):
            generate_project_skills_dir(
                gen_dir, selected_records, resolve_library_root(cfg),
                allowed_roots=cfg.get("allowed_roots", []) if isinstance(cfg, dict) else [],
                project_key=key,
            )
    except LockError as e:
        print("error: %s" % e, file=sys.stderr)
        return 1

    # Validate generated dir.
    marker = read_marker(gen_dir)
    if marker is None:
        print("error: generated directory marker missing", file=sys.stderr)
        return 1
    for name in marker.get("managed_entries", []):
        link = gen_dir / name
        if not link.is_symlink() or not link.exists():
            print("error: broken generated link: %s" % link, file=sys.stderr)
            return 1

    if prepare:
        print("prepared: %s (%d skills)" % (gen_dir, len(selected_records)))
        return 0

    # Build argv.
    argv = [_junie_exe(cfg), "--skill-default-locations", "false",
            "--skill-location", str(gen_dir)]
    # Shared rules delivery via --ide-guidelines if rules file exists.
    rules_path = cfg.get("rules_path") if isinstance(cfg, dict) else None
    if rules_path and Path(rules_path).expanduser().is_file():
        argv += ["--ide-guidelines", str(Path(rules_path).expanduser())]
    argv += passthrough

    if not selected_records:
        print("notice: empty selection; no skills loaded", file=sys.stderr)

    os.execvp(argv[0], argv)
    return 0