"""Identifier model for skills.

Three distinct values per skill record:
- dir_name: folder name inside the library (stable manifest reference).
- declared_name: frontmatter ``name`` if present, else None.
- agent_id: per-agent identifier (dict keyed by agent name).
"""

import re

SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def is_safe_id(value):
    if not value or not isinstance(value, str):
        return False
    if "/" in value or "\\" in value or "\x00" in value:
        return False
    if value.startswith("."):
        return False
    if ".." in value:
        return False
    return bool(SAFE_ID_RE.match(value))


def permission_ids_for_skill(record, agent_name):
    """Return safe folder/declared aliases for an agent's skill permission rule."""
    dir_name = record.get("dir_name")
    declared_name = record.get("declared_name")
    agent_ids = record.get("agent_id") or {}
    primary = agent_ids.get(agent_name)
    if not primary:
        primary = declared_name if agent_name == "kilo" else dir_name
    candidates = [primary, dir_name, declared_name]
    ids = []
    for candidate in candidates:
        if candidate and is_safe_id(candidate) and candidate not in ids:
            ids.append(candidate)
    if not ids:
        raise ValueError("no safe permission identifier for skill %r" % dir_name)
    return ids


def permission_ids_for_records(records, agent_name):
    """Resolve permission IDs and reject aliases shared by distinct skills."""
    ids = []
    owners = {}
    for record in records:
        for identifier in permission_ids_for_skill(record, agent_name):
            owner = owners.get(identifier)
            if owner is not None and owner != record.get("dir_name"):
                raise ValueError(
                    "ambiguous %s permission identifier %r for %s and %s"
                    % (agent_name, identifier, owner, record.get("dir_name"))
                )
            owners[identifier] = record.get("dir_name")
            if identifier not in ids:
                ids.append(identifier)
    return ids


def make_skill_record(dir_name, real_path, is_symlink, frontmatter_result, overrides=None):
    overrides = overrides or {}
    declared_name = None
    description = None
    if isinstance(frontmatter_result, dict):
        data = frontmatter_result.get("data") or {}
        declared_name = data.get("name")
        description = data.get("description")
        if declared_name is not None and not isinstance(declared_name, str):
            declared_name = str(declared_name)
        if description is not None and not isinstance(description, str):
            description = str(description)

    # User-authored overrides (for skills lacking frontmatter).
    override = overrides.get(dir_name) if isinstance(overrides, dict) else None
    if override and isinstance(override, dict):
        if "name" in override and override.get("name") is not None:
            declared_name = override["name"]
        if "description" in override and override.get("description") is not None:
            description = override["description"]

    fm_status = "missing"
    if isinstance(frontmatter_result, dict):
        fm_status = frontmatter_result.get("status", "missing")

    record = {
        "dir_name": dir_name,
        "real_path": real_path,
        "is_symlink": bool(is_symlink),
        "declared_name": declared_name,
        "description": description,
        "frontmatter_status": fm_status,
        "agent_id": {},  # filled per agent by adapters/identity resolution
        "warnings": list(frontmatter_result.get("warnings", [])) if isinstance(frontmatter_result, dict) else [],
    }
    return record


def resolve_agent_ids(record, agent_name, resolver):
    """Resolve agent_id[agent_name] using a resolver callable.

    resolver(record, agent_name) -> str or None. If None, mark unresolved.
    """
    try:
        value = resolver(record, agent_name)
    except Exception:
        value = None
    if value is None:
        record["agent_id"][agent_name] = None
        record.setdefault("unresolved_agents", []).append(agent_name)
    else:
        record["agent_id"][agent_name] = value
    return record


def check_duplicate_declared_names(records):
    """Return list of (dir_name_a, dir_name_b, name) for duplicate declared names."""
    seen = {}
    dups = []
    for r in records:
        name = r.get("declared_name")
        if not name:
            continue
        if name in seen:
            dups.append((seen[name], r["dir_name"], name))
        else:
            seen[name] = r["dir_name"]
    return dups


def check_name_folder_mismatch(records):
    """Return list of (dir_name, declared_name) where they differ."""
    out = []
    for r in records:
        dn = r.get("declared_name")
        if dn and dn != r["dir_name"]:
            out.append((r["dir_name"], dn))
    return out