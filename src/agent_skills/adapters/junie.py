"""Junie adapter (Phase 5).

Junie supports `--skill-default-locations=false --skill-location=<dir>` (V6
confirmed) which provides a plausible path to **exclusive** guarantee level
(pending V7-V9 verification). Managed launch validates the manifest,
generates the project skills directory (symlinks with wrapper layout for
frontmatter-less skills per §11.4/R-08), and launches junie with the
generated dir as `--skill-location`.

Wrapper layout (§11.4): for skills with no frontmatter (e.g. `flutter-tamim`,
`hive-db-tamim`, `isar-db-tamim`), only the top-level SKILL.md is regenerated
(frontmatter added, original body copied verbatim beneath it); every other
file/subfolder is symlinked at the same relative path it occupied in the
source, not flattened or re-arranged. Checksums are not computed here (the
manager never reads skill content beyond frontmatter parsing per §2.3).
"""

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

from agent_skills.adapter_common import (
    apply_context_budget,
    build_skills_dir_atomic,
    build_wrapper,
    build_skill_entry,
)
from agent_skills.frontmatter import parse_frontmatter
from agent_skills.links import MARKER_FILENAME, read_marker
from agent_skills.lock import AdvisoryLock, LockError
from agent_skills.manifest import load_manifest, selected_ids, validate_manifest
from agent_skills.config import resolve_library_root
from agent_skills.discovery import discover_skills, DiscoveryError


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
    key = "%s-%s" % (root.name,
                     hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:12])
    return Path(generated_root) / key, key


def launch_junie(args, cfg):
    prepare = getattr(args, "prepare", False)
    passthrough = getattr(args, "args", []) or []
    if passthrough and passthrough[0] == "--":
        passthrough = passthrough[1:]

    # Refuse conflicting flags.
    for a in passthrough:
        if a.startswith("--skill-location") or a.startswith("--skill-default-locations"):
            print("error: user-supplied skill flags would defeat managed policy",
                  file=sys.stderr)
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
            print("error: selected skill missing from library: %s" % sid,
                  file=sys.stderr)
            return 1
        selected_records.append(rec_map[sid])

    # Apply context budget filtering: only symlink skills that fit in context.
    filtered_records, skipped, _, cwarnings = apply_context_budget(
        selected_records, sel, [], cfg,
    )
    if cwarnings:
        for w in cwarnings:
            print("notice: %s" % w, file=sys.stderr)

    gen_dir, key = _generated_dir(cfg, root)
    gen_dir.parent.mkdir(parents=True, exist_ok=True)
    lock_path = gen_dir.parent / ".lock"

    try:
        with AdvisoryLock(lock_path):
            build_skills_dir_atomic(
                parent=gen_dir.parent,
                dest_dir=gen_dir,
                records=filtered_records,
                agent_name="junie",
                key=key,
                build_entry_fn=build_skill_entry,
                tmp_prefix=".junie-skills-tmp-",
                marker_filename=MARKER_FILENAME,
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
        if not link.exists():
            print("error: broken generated link: %s" % link, file=sys.stderr)
            return 1

    if prepare:
        print("prepared: %s (%d skills%s)" % (
            gen_dir, len(filtered_records),
            " (%d excluded by context budget)" % skipped if skipped else ""))
        return 0

    # Build argv.
    argv = [_junie_exe(cfg), "--skill-default-locations", "false",
            "--skill-location", str(gen_dir)]
    # Shared rules delivery via --ide-guidelines if rules file exists.
    rules_path = cfg.get("rules_path") if isinstance(cfg, dict) else None
    if rules_path and Path(rules_path).expanduser().is_file():
        argv += ["--ide-guidelines", str(Path(rules_path).expanduser())]
    argv += passthrough

    if not filtered_records:
        print("notice: empty selection; no skills loaded", file=sys.stderr)

    sys.stdout.flush()
    sys.stderr.flush()
    os.execvp(argv[0], argv)
    return 0
