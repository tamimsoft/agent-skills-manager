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
import stat
import sys
import tempfile
from pathlib import Path

from agent_skills.config import resolve_library_root
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


def _build_wrapper(src_root, dest_root, rec):
    """Build a wrapper for a skill, preserving original relative structure.

    Only the top-level SKILL.md is regenerated (frontmatter added, original
    body copied verbatim). Every other file/subfolder is symlinked at the
    same relative path it occupied in the source (§11.4 / §13.3).
    """
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
    override = None
    # No overrides passed here; wrapper uses existing frontmatter if present.

    # Regenerate top-level SKILL.md: frontmatter + verbatim original body.
    if fm_result.get("status") in ("missing", "malformed"):
        # Add frontmatter; keep body verbatim.
        name_val = declared or rec.get("dir_name")
        desc_val = description or rec.get("description") or ""
        body = text
        # Strip any existing frontmatter delimiters from body if present.
        if body.startswith("---"):
            lines = body.splitlines()
            end_idx = None
            for i in range(1, len(lines)):
                if lines[i].strip() == "---":
                    end_idx = i
                    break
            if end_idx is not None:
                body = "\n".join(lines[end_idx + 1:])
        new_md = "---\nname: %s\ndescription: %s\n---\n%s" % (
            name_val, desc_val, body.lstrip("\n"))
    else:
        new_md = text

    dest_skill_md = dest_root / "SKILL.md"
    dest_skill_md.write_text(new_md, encoding="utf-8")

    # Symlink everything else at original relative path.
    linked = []
    for entry in sorted(src_root.iterdir()):
        if entry.name == "SKILL.md":
            continue
        rel = entry.relative_to(src_root)
        dest_entry = dest_root / rel
        if entry.is_dir():
            dest_entry.parent.mkdir(parents=True, exist_ok=True)
            # Create directory symlink structure: symlink files inside.
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
    """Copy or wrapper a single skill into dest_root/<dir_name>/. Returns
    list of managed relative entry names."""
    src_root = Path(src_root)
    skill_md = src_root / "SKILL.md"
    fm_result = parse_frontmatter(
        skill_md.read_text(encoding="utf-8", errors="replace")
        if skill_md.is_file() else "")
    dest_entry = dest_root / rec["dir_name"]
    if fm_result.get("status") == "missing":
        # Wrapper layout for frontmatter-less skill (§13.3): create a
        # subdirectory named after the skill, regenerate only SKILL.md,
        # symlink everything else at original relative path.
        dest_entry.mkdir(parents=True, exist_ok=True)
        linked = _build_wrapper(src_root, dest_entry, rec)
        return [rec["dir_name"] + "/" + l for l in linked]
    else:
        # Direct symlink for skills with valid frontmatter.
        if dest_entry.exists() or dest_entry.is_symlink():
            dest_entry.unlink()
        os.symlink(os.path.realpath(src_root), dest_entry)
        return [rec["dir_name"]]


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
    """Merge skill permission rules into Kilo config, preserving unrelated keys."""
    cfg = dict(existing) if isinstance(existing, dict) else {}
    perms = cfg.get("permission")
    if not isinstance(perms, dict):
        perms = {}
    perms = dict(perms)
    # Remove prior owned skill rules, add new.
    skill_perms = {k: v for k, v in perms.items()
                   if not (k.startswith("skill:") or k == "skill")}
    skill_perms.update(new_rules)
    perms = skill_perms
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

    # Context budget filtering for reporting.
    budget_tokens = cfg.get("skill_context_budget_tokens") if isinstance(cfg, dict) else 32768
    max_skills = cfg.get("max_skills_in_context") if isinstance(cfg, dict) else 50
    filtered_records, skipped, total_tokens, cwarnings = filter_skills_for_context(
        selected_records, sel, [], budget_tokens, max_skills,
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
            # Build in a temp sibling.
            parent = skills_dir.parent
            parent.mkdir(parents=True, exist_ok=True)
            # Clean up leftover .tmp-* / .old-* from a crashed run (§5.5).
            import shutil as _shutil
            for entry in os.listdir(parent):
                name = entry
                if name.startswith(".kilo-skills-tmp-") or name.startswith(".kilo-skills-old-"):
                    leftover = parent / name
                    if leftover.is_dir() and not leftover.is_symlink():
                        _shutil.rmtree(leftover, ignore_errors=True)
                    else:
                        try:
                            leftover.unlink()
                        except OSError:
                            pass
            tmp = Path(tempfile.mkdtemp(prefix=".kilo-skills-", dir=str(parent)))
            try:
                managed_entries = []
                for rec in selected_records:
                    src_root = Path(rec["real_path"]).parent
                    dest_name = rec["dir_name"]
                    dest_entry = tmp / dest_name
                    linked = _build_skill_entry(src_root, tmp, rec)
                    if linked:
                        for l in linked:
                            managed_entries.append("%s/%s" % (dest_name, l))
                    else:
                        managed_entries.append(dest_name)

                marker = {
                    "manager_version": "0.1.0",
                    "schema_version": 1,
                    "project_key": key,
                    "agent": "kilo",
                    "managed_entries": managed_entries,
                }
                with (tmp / MARKER_FILENAME_KILO).open("w", encoding="utf-8") as f:
                    json.dump(marker, f, indent=2)
                    f.write("\n")

                # Verify symlinks resolve.
                for name in managed_entries:
                    link = tmp / name
                    if not link.exists():
                        raise RuntimeError("broken generated link: %s" % link)

                # Build-then-swap (§5.5).
                old_marker_path = skills_dir / MARKER_FILENAME_KILO
                old_entries = []
                if old_marker_path.is_file():
                    try:
                        with old_marker_path.open("r", encoding="utf-8") as f:
                            old_marker = json.load(f)
                    except (OSError, ValueError):
                        old_marker = {}
                    old_entries = old_marker.get("managed_entries", [])

                # Rename old aside, move tmp into place, remove old.
                old_aside = parent / (".kilo-skills.old-%d" % os.getpid())
                if skills_dir.exists() or skills_dir.is_symlink():
                    if skills_dir.is_dir() and not skills_dir.is_symlink():
                        os.rename(str(skills_dir), str(old_aside))
                    else:
                        skills_dir.unlink()
                os.replace(tmp, skills_dir)
                tmp = None

                # Remove old aside.
                if old_aside.exists():
                    shutil.rmtree(old_aside, ignore_errors=True)

            finally:
                if tmp is not None and Path(tmp).exists():
                    shutil.rmtree(tmp, ignore_errors=True)

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
