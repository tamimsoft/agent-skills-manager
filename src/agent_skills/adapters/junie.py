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

from agent_skills.frontmatter import parse_frontmatter
from agent_skills.links import MARKER_FILENAME, read_marker
from agent_skills.lock import AdvisoryLock, LockError
from agent_skills.manifest import load_manifest, selected_ids, validate_manifest
from agent_skills.config import resolve_library_root
from agent_skills.discovery import discover_skills, DiscoveryError
from agent_skills.recommend import filter_skills_for_context


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


def _build_wrapper(src_root, dest_root, rec):
    """Build a wrapper for a frontmatter-less skill, preserving relative
    structure (§11.4). Only SKILL.md is regenerated; everything else is
    symlinked at its original relative path."""
    src_root = Path(src_root)
    dest_root = Path(dest_root)
    skill_md = src_root / "SKILL.md"

    text = ""
    if skill_md.is_file():
        try:
            with skill_md.open("r", encoding="utf-8", errors="replace") as f:
                text = f.read(65536)
        except OSError:
            text = ""

    fm_result = parse_frontmatter(text)
    declared = None
    description = None
    if isinstance(fm_result, dict):
        data = fm_result.get("data") or {}
        declared = data.get("name")
        description = data.get("description")

    # Strip any existing frontmatter from body.
    body = text
    if body.startswith("---"):
        lines = body.splitlines()
        end_idx = None
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end_idx = i
                break
        if end_idx is not None:
            body = "\n".join(lines[end_idx + 1:])

    name_val = declared or rec.get("dir_name")
    desc_val = description or rec.get("description") or ""
    new_md = "---\nname: %s\ndescription: %s\n---\n%s" % (
        name_val, desc_val, body.lstrip("\n"))

    dest_skill_md = dest_root / "SKILL.md"
    dest_skill_md.write_text(new_md, encoding="utf-8")

    linked = []
    for entry in sorted(src_root.iterdir()):
        if entry.name == "SKILL.md":
            continue
        rel = entry.relative_to(src_root)
        dest_entry = dest_root / rel
        if entry.is_dir():
            for sub in entry.rglob("*"):
                sub_rel = sub.relative_to(src_root)
                sub_dest = dest_root / sub_rel
                if sub.is_dir():
                    sub_dest.mkdir(parents=True, exist_ok=True)
                else:
                    sub_dest.parent.mkdir(parents=True, exist_ok=True)
                    if sub_dest.exists() or sub_dest.is_symlink():
                        sub_dest.unlink()
                    os.symlink(os.path.realpath(sub), sub_dest)
                    linked.append(str(sub_rel))
        else:
            dest_entry.parent.mkdir(parents=True, exist_ok=True)
            if dest_entry.exists() or dest_entry.is_symlink():
                dest_entry.unlink()
            os.symlink(os.path.realpath(entry), dest_entry)
            linked.append(str(rel))

    return linked


def _build_skill_entry(src_root, dest_root, rec):
    """Copy or wrapper a single skill into dest_root. Returns list of
    managed relative entry names."""
    skill_md = src_root / "SKILL.md"
    fm_result = parse_frontmatter(
        skill_md.read_text(encoding="utf-8", errors="replace")
        if skill_md.is_file() else "")
    if fm_result.get("status") == "missing":
        return _build_wrapper(src_root, dest_root, rec)
    else:
        dest_link = dest_root / rec["dir_name"]
        if dest_link.exists() or dest_link.is_symlink():
            dest_link.unlink()
        os.symlink(os.path.realpath(src_root), dest_link)
        return [rec["dir_name"]]


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
    budget_tokens = cfg.get("skill_context_budget_tokens") if isinstance(cfg, dict) else 32768
    max_skills = cfg.get("max_skills_in_context") if isinstance(cfg, dict) else 50
    filtered_records, skipped, total_tokens, cwarnings = filter_skills_for_context(
        selected_records, sel, [], budget_tokens, max_skills,
    )
    if cwarnings:
        for w in cwarnings:
            print("notice: %s" % w, file=sys.stderr)

    gen_dir, key = _generated_dir(cfg, root)
    gen_dir.parent.mkdir(parents=True, exist_ok=True)
    lock_path = gen_dir.parent / ".lock"

    try:
        with AdvisoryLock(lock_path):
            # Build in a temp sibling.
            parent = gen_dir.parent
            parent.mkdir(parents=True, exist_ok=True)
            tmp = Path(tempfile.mkdtemp(prefix=".junie-skills-", dir=str(parent)))
            try:
                managed_entries = []
                for rec in filtered_records:
                    src_root = Path(rec["real_path"]).parent
                    dest_entry = tmp / rec["dir_name"]
                    linked = _build_skill_entry(src_root, tmp, rec)
                    if linked:
                        for l in linked:
                            managed_entries.append("%s/%s" % (rec["dir_name"], l))
                    else:
                        managed_entries.append(rec["dir_name"])

                marker = {
                    "manager_version": "0.1.0",
                    "schema_version": 1,
                    "project_key": key,
                    "agent": "junie",
                    "managed_entries": managed_entries,
                }
                with (tmp / MARKER_FILENAME).open("w", encoding="utf-8") as f:
                    json.dump(marker, f, indent=2)
                    f.write("\n")

                # Verify symlinks resolve.
                for name in managed_entries:
                    link = tmp / name
                    if not link.exists():
                        raise RuntimeError("broken generated link: %s" % link)

                # Build-then-swap (§5.5).
                old_marker_path = gen_dir / MARKER_FILENAME
                old_aside = parent / (".junie-skills.old-%d" % os.getpid())
                if gen_dir.exists() or gen_dir.is_symlink():
                    if gen_dir.is_dir() and not gen_dir.is_symlink():
                        os.rename(str(gen_dir), str(old_aside))
                    else:
                        gen_dir.unlink()
                os.replace(tmp, gen_dir)
                tmp = None

                if old_aside.exists():
                    import shutil
                    shutil.rmtree(old_aside, ignore_errors=True)

            finally:
                if tmp is not None and Path(tmp).exists():
                    import shutil
                    shutil.rmtree(tmp, ignore_errors=True)

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
