"""Shared helpers for agent adapters (junie, kilo, opencode).

Extracts copy-pasted logic (_build_wrapper, _build_skill_entry,
context-budget boilerplate) so fixes don't drift between adapters.
"""

import hashlib
import json
import os
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from agent_skills.frontmatter import parse_frontmatter
from agent_skills.links import MARKER_FILENAME
from agent_skills.recommend import filter_skills_for_context


def backup_config_file(root, path, prefix):
    """Create a timestamped backup of a config before a one-time migration."""
    root = Path(root)
    path = Path(path)
    backup_dir = root / ".agents" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    backup = backup_dir / ("%s.%s" % (prefix, stamp))
    shutil.copy2(str(path), str(backup))
    return backup


def write_json_atomic(path, data):
    """Write JSON through a same-directory temporary file and atomic replace."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".%s-" % path.name, dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


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

    src_real = src_root.resolve()

    def _link_target_safe(path):
        """Return True if the symlink target of `path` resolves inside src_real."""
        try:
            target = Path(os.path.realpath(str(path)))
            target.relative_to(src_real)
            return True
        except ValueError:
            return False

    linked = []
    for entry in sorted(src_root.iterdir()):
        if entry.name == "SKILL.md":
            continue
        # Skip macOS metadata files that are not part of the skill.
        if entry.name == ".DS_Store" or entry.name.startswith("._"):
            continue
        rel = entry.relative_to(src_root)
        dest_entry = dest_root / rel
        if entry.is_symlink():
            # Symlink: only replicate if target is inside the library root.
            if not _link_target_safe(entry):
                continue
            target = os.path.realpath(str(entry))
            if not os.path.exists(target):
                continue
            dest_entry.parent.mkdir(parents=True, exist_ok=True)
            if dest_entry.exists() or dest_entry.is_symlink():
                dest_entry.unlink()
            os.symlink(target, dest_entry)
            linked.append(str(rel))
        elif entry.is_dir():
            dest_entry.mkdir(parents=True, exist_ok=True)
            for sub in entry.rglob("*"):
                sub_rel = sub.relative_to(src_root)
                sub_dest = dest_root / sub_rel
                if sub.name == ".DS_Store" or sub.name.startswith("._"):
                    continue
                if sub.is_symlink():
                    if not _link_target_safe(sub):
                        continue
                    target = os.path.realpath(str(sub))
                    if not os.path.exists(target):
                        continue
                    sub_dest.parent.mkdir(parents=True, exist_ok=True)
                    if sub_dest.exists() or sub_dest.is_symlink():
                        sub_dest.unlink()
                    os.symlink(target, sub_dest)
                    linked.append(str(sub_rel))
                elif sub.is_dir():
                    sub_dest.mkdir(parents=True, exist_ok=True)
                else:
                    target = os.path.realpath(str(sub))
                    if not os.path.exists(target):
                        continue
                    sub_dest.parent.mkdir(parents=True, exist_ok=True)
                    if sub_dest.exists() or sub_dest.is_symlink():
                        sub_dest.unlink()
                    os.symlink(target, sub_dest)
                    linked.append(str(sub_rel))
        else:
            target = os.path.realpath(str(entry))
            if not os.path.exists(target):
                continue
            dest_entry.parent.mkdir(parents=True, exist_ok=True)
            if dest_entry.exists() or dest_entry.is_symlink():
                dest_entry.unlink()
            os.symlink(target, dest_entry)
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
        return linked
    else:
        # Direct symlink for skills with valid frontmatter.
        if dest_entry.exists() or dest_entry.is_symlink():
            dest_entry.unlink()
        os.symlink(os.path.realpath(src_root), dest_entry)
        return []


def build_skill_copy(src_root, dest_root, rec):
    """Copy one selected skill, rejecting bundle links that escape its root."""
    src_root = Path(src_root).resolve()
    dest_entry = Path(dest_root) / rec["dir_name"]

    def copy_item(source, destination, ancestors):
        try:
            resolved = source.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise RuntimeError("cannot resolve skill content %s: %s" % (source, exc))
        try:
            resolved.relative_to(src_root)
        except ValueError:
            raise RuntimeError("skill content symlink escapes skill root: %s" % source)

        if resolved.is_dir():
            if resolved in ancestors:
                raise RuntimeError("skill content contains a directory cycle: %s" % source)
            destination.mkdir(parents=True, exist_ok=True)
            next_ancestors = ancestors | {resolved}
            for child in sorted(resolved.iterdir()):
                if child.name == ".DS_Store" or child.name.startswith("._"):
                    continue
                copy_item(child, destination / child.name, next_ancestors)
        elif resolved.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(resolved), str(destination))
        else:
            raise RuntimeError("unsupported skill content type: %s" % source)

    copy_item(src_root, dest_entry, set())
    return []


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
                            marker_filename=None, extra_marker_fields=None,
                            agents_md_content=None, owned_rules_filename=None):
    """Build-then-swap crash recovery pattern (§5.5).

    Builds skill entries in a temp sibling directory under `parent`, writes
    a marker, verifies symlinks, then atomically swaps into `dest_dir` with
    old-aside cleanup. The caller is responsible for holding the advisory
    lock before invoking this.
    """
    parent.mkdir(parents=True, exist_ok=True)
    parent = Path(parent)
    dest_dir = Path(dest_dir)
    old_prefix = tmp_prefix + "old-"
    legacy_old_prefix = tmp_prefix.rstrip("-") + ".old-"
    marker_path = Path(marker_filename) if marker_filename else Path(MARKER_FILENAME)
    build_marker_name = ".agent-skills-build.json"

    def remove_path(path):
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        elif path.exists() or path.is_symlink():
            path.unlink()

    def valid_managed_tree(path):
        if not path.is_dir() or path.is_symlink():
            return False
        try:
            with (path / marker_path).open("r", encoding="utf-8") as stream:
                marker = json.load(stream)
        except (OSError, ValueError):
            return False
        return (
            isinstance(marker, dict)
            and marker.get("schema_version") == 1
            and marker.get("project_key") == key
            and marker.get("agent") in (agent_name, None)
            and isinstance(marker.get("managed_entries"), list)
        )

    def valid_build_temp(path):
        if not path.is_dir() or path.is_symlink():
            return False
        try:
            with (path / build_marker_name).open("r", encoding="utf-8") as stream:
                marker = json.load(stream)
        except (OSError, ValueError):
            return False
        return (
            isinstance(marker, dict)
            and marker.get("project_key") == key
            and marker.get("agent") == agent_name
        )

    # Remove only abandoned build directories. Restore a marked old tree first
    # if a prior process crashed after moving the destination aside.
    for entry in os.listdir(parent):
        path = parent / entry
        if (
            entry.startswith(tmp_prefix)
            and not entry.startswith(old_prefix)
            and not entry.startswith(legacy_old_prefix)
        ) and valid_build_temp(path):
            remove_path(path)

    old_dirs = sorted(
        (
            parent / name for name in os.listdir(parent)
            if name.startswith(old_prefix) or name.startswith(legacy_old_prefix)
        ),
        key=lambda path: path.stat().st_mtime_ns if path.exists() else 0,
        reverse=True,
    )
    if not dest_dir.exists() and not dest_dir.is_symlink():
        recovery = next((path for path in old_dirs if valid_managed_tree(path)), None)
        if recovery is not None:
            os.replace(recovery, dest_dir)

    tmp = Path(tempfile.mkdtemp(prefix=tmp_prefix, dir=str(parent)))
    try:
        with (tmp / build_marker_name).open("w", encoding="utf-8") as stream:
            json.dump({"project_key": key, "agent": agent_name}, stream)

        managed_entries = []
        for rec in records:
            # rec["real_path"] is the skill directory; use it directly as src_root.
            src_root = Path(rec["real_path"])
            linked = build_entry_fn(src_root, tmp, rec)
            if linked:
                for l in linked:
                    managed_entries.append("%s/%s" % (rec["dir_name"], l))
            else:
                managed_entries.append(rec["dir_name"])

        if agents_md_content is not None:
            with (tmp / "AGENTS.md").open("w", encoding="utf-8") as f:
                f.write(agents_md_content)
                f.write("\n")
            managed_entries.append("AGENTS.md")

        marker = {
            "manager_version": "0.1.0",
            "schema_version": 1,
            "project_key": key,
            "agent": agent_name,
            "managed_entries": managed_entries,
        }
        if extra_marker_fields:
            marker.update(extra_marker_fields)
        with (tmp / marker_path).open("w", encoding="utf-8") as f:
            json.dump(marker, f, indent=2)
            f.write("\n")
        if owned_rules_filename:
            owned_rules = {
                "schema_version": 1,
                "project_key": key,
                "managed_entries": managed_entries,
            }
            with (tmp / owned_rules_filename).open("w", encoding="utf-8") as f:
                json.dump(owned_rules, f, indent=2)
                f.write("\n")
        # Verify symlinks resolve.
        for name in managed_entries:
            link = tmp / name
            if link.is_symlink():
                if not link.exists():
                    raise RuntimeError("broken generated link: %s" % link)
            elif link.is_file():
                continue
            elif link.is_dir():
                continue
            else:
                raise RuntimeError("broken generated link: %s" % link)

        old_aside = parent / (old_prefix + uuid.uuid4().hex)
        if dest_dir.exists() or dest_dir.is_symlink():
            if not valid_managed_tree(dest_dir):
                raise RuntimeError(
                    "refusing to replace unmarked generated directory: %s" % dest_dir
                )
            os.replace(dest_dir, old_aside)
        try:
            os.replace(tmp, dest_dir)
        except OSError:
            if old_aside.exists() and not dest_dir.exists():
                os.replace(old_aside, dest_dir)
            raise
        tmp = None
        (dest_dir / build_marker_name).unlink()

        if old_aside.exists():
            remove_path(old_aside)
        for stale_old in old_dirs:
            if stale_old.exists() and valid_managed_tree(stale_old):
                remove_path(stale_old)

    finally:
        if tmp is not None and Path(tmp).exists():
            shutil.rmtree(tmp, ignore_errors=True)
