"""Skill discovery for the shared library."""

import os
from pathlib import Path

from agent_skills.frontmatter import parse_frontmatter
from agent_skills.identity import (
    make_skill_record,
    is_safe_id,
    check_duplicate_declared_names,
    check_name_folder_mismatch,
)
from agent_skills.cache import (
    cache_key_for_skill,
    load_cache,
    save_cache,
    is_cache_valid,
    OVERRIDES_VERSION,
    CACHE_SCHEMA_VERSION,
)


class DiscoveryError(Exception):
    pass


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


def _is_symlink_entry(path):
    return os.path.islink(path)


def discover_skills(library_root, allowed_roots=None, overrides=None, no_cache=False, cache_file=None):
    """Discover skills in library_root.

    Returns (records_list, warnings_list, errors_list).
    Raises DiscoveryError for missing/unreadable library root.
    """
    lr = Path(library_root).expanduser()
    if not lr.exists():
        raise DiscoveryError("library root does not exist: %s" % lr)
    if not lr.is_dir():
        raise DiscoveryError("library root is not a directory: %s" % lr)

    roots = _real_roots(lr, allowed_roots)
    overrides = overrides or {}

    # Collect candidate skill directories.
    candidates = []
    try:
        entries = sorted(os.listdir(lr))
    except OSError as e:
        raise DiscoveryError("cannot list library root %s: %s" % (lr, e))

    for name in entries:
        if name.startswith("."):
            continue
        full = lr / name
        if not full.is_dir():
            continue
        skill_md = full / "SKILL.md"
        if not skill_md.is_file():
            # Not a skill directory; skip (but report? info only)
            continue
        candidates.append((name, full, skill_md))

    # Cache handling.
    cache = None
    cache_path = cache_file
    if (not no_cache) and cache_path is not None:
        cache = load_cache(cache_path)

    # Build skill_md path list for cache validation.
    skill_entries = [(name, str(sm)) for name, _, sm in candidates]
    use_cache = (not no_cache) and cache is not None and is_cache_valid(cache, lr, skill_entries, OVERRIDES_VERSION)

    records = []
    warnings = []
    errors = []
    fm_by_name = {}

    # Case-insensitive collision tracking.
    case_map = {}

    for name, full, skill_md in candidates:
        # Safe ID check.
        if not _safe_name(name):
            warnings.append("unsafe-skill-id: %r cannot be selected by CLI id until a safe form is defined" % name)

        # Resolve real path and allow-list.
        try:
            real = os.path.realpath(str(full))
        except OSError as e:
            errors.append("cannot resolve path for %s: %s" % (name, e))
            continue
        if not _inside_allowed(real, roots):
            errors.append("symlink-escape: %s resolves outside allowed roots (%s)" % (name, real))
            continue

        is_link = _is_symlink_entry(str(full))

        # Case collision.
        low = name.lower()
        if low in case_map:
            warnings.append("case-insensitive-collision: %r and %r" % (case_map[low], name))
        else:
            case_map[low] = name

        # Cache hit for this skill.
        cached_rec = None
        if use_cache:
            cached_rec = (cache.get("skills") or {}).get(name)

        skill_key = cache_key_for_skill(skill_md)
        if cached_rec is not None and cached_rec.get("key") == (list(skill_key) if skill_key else None):
            fm_result = cached_rec.get("frontmatter")
            if not isinstance(fm_result, dict):
                fm_result = {"status": cached_rec.get("frontmatter_status", "missing"),
                            "data": {}, "warnings": [], "error": None}
                # Reconstruct declared name/description from cache if possible.
                if cached_rec.get("declared_name") is not None:
                    fm_result.setdefault("data", {})["name"] = cached_rec["declared_name"]
                if cached_rec.get("description") is not None:
                    fm_result.setdefault("data", {})["description"] = cached_rec["description"]
            rec = make_skill_record(name, real, is_link, fm_result, overrides)
            fm_by_name[name] = fm_result
            records.append(rec)
            continue

        # Bounded read of SKILL.md (first 64 KB).
        try:
            with skill_md.open("r", encoding="utf-8", errors="replace") as f:
                text = f.read(65536)
        except OSError as e:
            errors.append("cannot read %s: %s" % (skill_md, e))
            continue

        fm_result = parse_frontmatter(text)

        # Unsupported YAML warnings already in fm_result["warnings"].
        for w in fm_result.get("warnings", []):
            warnings.append("%s: %s" % (name, w))

        if fm_result.get("error"):
            warnings.append("%s: %s" % (name, fm_result["error"]))

        rec = make_skill_record(name, real, is_link, fm_result, overrides)
        fm_by_name[name] = fm_result
        records.append(rec)

    # Post-discovery identity checks.
    dups = check_duplicate_declared_names(records)
    for a, b, nm in dups:
        warnings.append("duplicate-declared-name: %r in %s and %s" % (nm, a, b))
    mismatches = check_name_folder_mismatch(records)
    for dn, decl in mismatches:
        warnings.append("name-folder-mismatch: dir=%r declared=%r" % (dn, decl))

    # Save cache.
    if (not no_cache) and cache_path is not None:
        try:
            skills_cache = {}
            for rec in records:
                sm = Path(rec["real_path"]) / "SKILL.md"
                key = cache_key_for_skill(sm)
                fm = fm_by_name.get(rec["dir_name"], {"status": rec["frontmatter_status"], "data": {}, "warnings": [], "error": None})
                skills_cache[rec["dir_name"]] = {
                    "key": list(key) if key else None,
                    "frontmatter_status": rec["frontmatter_status"],
                    "declared_name": rec["declared_name"],
                    "description": rec["description"],
                    "frontmatter": fm,
                }
            save_cache(cache_path, {
                "library_root": str(Path(library_root).resolve()),
                "schema_version": CACHE_SCHEMA_VERSION,
                "overrides_version": OVERRIDES_VERSION,
                "skills": skills_cache,
            })
        except OSError:
            pass

    return records, warnings, errors


def _safe_name(name):
    # Per 5.4: accept unicode/spaces but report; here we treat as selectable only if safe id.
    # We reuse is_safe_id from identity but import lazily to avoid cycle.
    from agent_skills.identity import is_safe_id
    return is_safe_id(name)