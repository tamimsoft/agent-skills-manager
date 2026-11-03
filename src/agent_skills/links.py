"""Symlink management for generated project skill directories."""

import json
import os
import shutil
import tempfile
from pathlib import Path

MARKER_FILENAME = ".agent-skills-managed.json"
OWNED_RULES_FILENAME = "opencode-owned-rules.json"


def _real_roots(library_root, allowed_roots):
    roots = [Path(library_root).resolve()]
    for r in (allowed_roots or []):
        try:
            roots.append(Path(r).expanduser().resolve())
        except Exception:
            pass
    return roots


def _inside_allowed(real_path, roots):
    rp = Path(real_path).resolve()
    for root in roots:
        try:
            rp.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def _make_symlink(src_real, dest):
    # Remove existing dest if it is a symlink we can replace; never overwrite real files.
    if dest.exists() or dest.is_symlink():
        if dest.is_symlink() or dest.is_file():
            dest.unlink()
        else:
            raise RuntimeError("refusing to overwrite non-file path: %s" % dest)
    os.symlink(src_real, dest)


def generate_project_skills_dir(generated_dir, selected_records, library_root, allowed_roots=None, manager_version="0.1.0", schema_version=1, project_key=""):
    """Atomically (re)build generated_dir with symlinks to selected skills.

    selected_records: list of skill record dicts.
    Returns path to generated_dir.
    """
    generated_dir = Path(generated_dir)
    roots = _real_roots(library_root, allowed_roots)

    # Build in a temp sibling directory.
    parent = generated_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    # Clean up leftover .tmp-* / .old-* from a crashed run (§5.5).
    import shutil as _shutil
    for entry in os.listdir(parent):
        name = entry
        if name.startswith(".gen-tmp-") or name.startswith(".gen-old-"):
            leftover = parent / name
            if leftover.is_dir() and not leftover.is_symlink():
                _shutil.rmtree(leftover, ignore_errors=True)
            else:
                try:
                    leftover.unlink()
                except OSError:
                    pass
    tmp = Path(tempfile.mkdtemp(prefix=".gen-", dir=str(parent)))
    try:
        managed_entries = []
        for rec in selected_records:
            src_real = os.path.realpath(rec["real_path"])
            if not _inside_allowed(src_real, roots):
                raise RuntimeError("symlink escape for %s: %s" % (rec["dir_name"], src_real))
            dest = tmp / rec["dir_name"]
            _make_symlink(src_real, dest)
            managed_entries.append(rec["dir_name"])

        marker = {
            "manager_version": manager_version,
            "schema_version": schema_version,
            "project_key": project_key,
            "managed_entries": managed_entries,
        }
        with (tmp / MARKER_FILENAME).open("w", encoding="utf-8") as f:
            json.dump(marker, f, indent=2)
            f.write("\n")

        # Verify all symlinks resolve.
        for name in managed_entries:
            link = tmp / name
            if not link.is_symlink():
                raise RuntimeError("expected symlink: %s" % link)
            if not link.exists():
                raise RuntimeError("broken symlink: %s" % link)

        # Atomic rename into place.
        if generated_dir.exists() or generated_dir.is_symlink():
            # Remove only managed entries from old dir, then replace.
            old_marker_path = generated_dir / MARKER_FILENAME
            if old_marker_path.is_file():
                try:
                    with old_marker_path.open("r", encoding="utf-8") as f:
                        old_marker = json.load(f)
                except (OSError, ValueError):
                    old_marker = {}
                old_entries = old_marker.get("managed_entries", [])
                # Remove old managed entries whose target still matches.
                for oe in old_entries:
                    old_link = generated_dir / oe
                    if old_link.is_symlink():
                        old_link.unlink()
            # Move tmp to a staging final then swap.
            # Use rename with replace (atomic on same filesystem).
            if generated_dir.is_dir() and not generated_dir.is_symlink():
                shutil.rmtree(generated_dir)
            else:
                generated_dir.unlink()
        os.replace(tmp, generated_dir)
        tmp = None
    finally:
        if tmp is not None and Path(tmp).exists():
            shutil.rmtree(tmp, ignore_errors=True)

    return generated_dir


def read_marker(generated_dir):
    p = Path(generated_dir) / MARKER_FILENAME
    if not p.is_file():
        return None
    try:
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def remove_managed_entries(generated_dir):
    """Remove only entries listed in the marker whose target still matches creation."""
    gd = Path(generated_dir)
    marker = read_marker(gd)
    if not marker:
        return []
    removed = []
    for name in marker.get("managed_entries", []):
        link = gd / name
        if link.is_symlink():
            link.unlink()
            removed.append(name)
    return removed