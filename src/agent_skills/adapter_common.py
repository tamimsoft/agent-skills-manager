"""Shared helpers for agent adapters (junie, kilo, opencode).

Extracts copy-pasted logic (_build_wrapper, _build_skill_entry,
context-budget boilerplate) so fixes don't drift between adapters.
"""

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from agent_skills.frontmatter import parse_frontmatter
from agent_skills.links import MARKER_FILENAME
from agent_skills.recommend import filter_skills_for_context


def build_wrapper(src_root, dest_root, rec):
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
            dest_entry.parent.mkdir(parents=True, exist_ok=True)
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


def build_skill_entry(src_root, dest_root, rec):
    """Copy or wrapper a single skill into dest_root/<dir_name>/.

    Returns list of managed relative entry names.
    """
    src_root = Path(src_root)
    dest_root = Path(dest_root)
    skill_md = src_root / "SKILL.md"
    fm_result = parse_frontmatter(
        skill_md.read_text(encoding="utf-8", errors="replace")
        if skill_md.is_file() else "")
    dest_entry = dest_root / rec["dir_name"]
    if fm_result.get("status") == "missing":
        # Wrapper layout for frontmatter-less skill (§11.4).
        dest_entry.mkdir(parents=True, exist_ok=True)
        linked = build_wrapper(src_root, dest_entry, rec)
        return [rec["dir_name"] + "/" + l for l in linked]
    else:
        # Direct symlink for skills with valid frontmatter.
        if dest_entry.exists() or dest_entry.is_symlink():
            dest_entry.unlink()
        os.symlink(os.path.realpath(src_root), dest_entry)
        return [rec["dir_name"]]


def apply_context_budget(selected_records, sel, techs, cfg):
    """Apply context budget filtering with common defaults.

    Returns (filtered_records, skipped, total_tokens, warnings).
    """
    budget_tokens = cfg.get("skill_context_budget_tokens") if isinstance(cfg, dict) else 32768
    max_skills = cfg.get("max_skills_in_context") if isinstance(cfg, dict) else 50
    return filter_skills_for_context(
        selected_records, sel, techs, budget_tokens, max_skills,
    )


def build_skills_dir_atomic(parent, dest_dir, records, agent_name, key,
                            build_entry_fn, tmp_prefix=".gen-tmp-",
                            marker_filename=None, extra_marker_fields=None):
    """Build-then-swap crash recovery pattern (§5.5).

    Builds skill entries in a temp sibling directory under `parent`, writes
    a marker, verifies symlinks, then atomically swaps into `dest_dir` with
    old-aside cleanup. The caller is responsible for holding the advisory
    lock before invoking this.
    """
    parent.mkdir(parents=True, exist_ok=True)
    # Clean up leftover .tmp-* / .old-* from a crashed run.
    base_prefix = tmp_prefix.rstrip("-")
    for entry in os.listdir(parent):
        name = entry
        if name.startswith(base_prefix + "-tmp-") or name.startswith(base_prefix + "-old-"):
            leftover = parent / name
            if leftover.is_dir() and not leftover.is_symlink():
                shutil.rmtree(leftover, ignore_errors=True)
            else:
                try:
                    leftover.unlink()
                except OSError:
                    pass
    tmp = Path(tempfile.mkdtemp(prefix=tmp_prefix, dir=str(parent)))
    try:
        managed_entries = []
        for rec in records:
            src_root = Path(rec["real_path"]).parent
            dest_entry = tmp / rec["dir_name"]
            linked = build_entry_fn(src_root, tmp, rec)
            if linked:
                for l in linked:
                    managed_entries.append("%s/%s" % (rec["dir_name"], l))
            else:
                managed_entries.append(rec["dir_name"])

        marker = {
            "manager_version": "0.1.0",
            "schema_version": 1,
            "project_key": key,
            "agent": agent_name,
            "managed_entries": managed_entries,
        }
        if extra_marker_fields:
            marker.update(extra_marker_fields)
        mk_path = Path(marker_filename) if marker_filename else Path(MARKER_FILENAME)
        with (tmp / mk_path).open("w", encoding="utf-8") as f:
            json.dump(marker, f, indent=2)
            f.write("\n")

        # Verify symlinks resolve.
        for name in managed_entries:
            link = tmp / name
            if not link.exists():
                raise RuntimeError("broken generated link: %s" % link)

        # Build-then-swap: rename old aside, move tmp into place, remove old.
        old_aside = parent / (base_prefix + ".old-%d" % os.getpid())
        if dest_dir.exists() or dest_dir.is_symlink():
            if dest_dir.is_dir() and not dest_dir.is_symlink():
                os.rename(str(dest_dir), str(old_aside))
            else:
                dest_dir.unlink()
        os.replace(tmp, dest_dir)
        tmp = None

        if old_aside.exists():
            shutil.rmtree(old_aside, ignore_errors=True)

    finally:
        if tmp is not None and Path(tmp).exists():
            shutil.rmtree(tmp, ignore_errors=True)
