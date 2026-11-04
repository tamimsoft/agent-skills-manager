"""Project manifest (.agents/skills.json)."""

import json
import os
import shutil
from pathlib import Path

SCHEMA_VERSION = 1


def manifest_path(project_root):
    return Path(project_root) / ".agents" / "skills.json"


def default_manifest(project_name=None):
    return {
        "schema_version": SCHEMA_VERSION,
        "project": {"name": project_name or ""},
        "skills": {"selected": []},
        "agents": {
            "junie": {"enabled": True},
            "opencode": {"enabled": True},
            "kilo": {"enabled": True},
        },
    }


def load_manifest(project_root):
    p = manifest_path(project_root)
    if not p.exists():
        return None, ["manifest not found: %s" % p]
    try:
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        return None, ["failed to read manifest: %s" % e]
    errs = validate_manifest(data)
    if errs:
        return data, errs
    return data, []


def validate_manifest(data):
    errs = []
    if not isinstance(data, dict):
        return ["manifest must be a JSON object"]
    if data.get("schema_version") != SCHEMA_VERSION:
        sv = data.get("schema_version")
        if sv is None:
            errs.append("missing schema_version")
        elif sv > SCHEMA_VERSION:
            errs.append("manifest schema_version %s is newer than supported %s" % (sv, SCHEMA_VERSION))
        elif sv < SCHEMA_VERSION:
            # migration would handle; for now accept older? We'll require exact for Phase 3.
            errs.append("manifest schema_version %s requires migration (not implemented)" % sv)
    proj = data.get("project")
    if not isinstance(proj, dict):
        errs.append("project must be an object")
    skills = data.get("skills")
    if not isinstance(skills, dict):
        errs.append("skills must be an object")
    else:
        sel = skills.get("selected")
        if not isinstance(sel, list):
            errs.append("skills.selected must be a list")
        else:
            seen = set()
            for sid in sel:
                if not isinstance(sid, str):
                    errs.append("skill id must be string: %r" % sid)
                    continue
                from agent_skills.identity import is_safe_id
                if not is_safe_id(sid):
                    errs.append("invalid skill id: %r" % sid)
                if sid in seen:
                    errs.append("duplicate skill id: %r" % sid)
                seen.add(sid)
    agents = data.get("agents")
    if agents is not None and not isinstance(agents, dict):
        errs.append("agents must be an object")
    elif isinstance(agents, dict):
        for agent_id, settings in agents.items():
            if not isinstance(agent_id, str) or not isinstance(settings, dict):
                errs.append("each agents entry must map an agent id to an object")
                continue
            if "enabled" in settings and not isinstance(settings["enabled"], bool):
                errs.append("agents.%s.enabled must be a boolean" % agent_id)
    return errs


def save_manifest(project_root, data):
    p = manifest_path(project_root)
    p.parent.mkdir(parents=True, exist_ok=True)
    errs = validate_manifest(data)
    if errs:
        raise ValueError("manifest validation failed: " + "; ".join(errs))
    if p.exists():
        backup = p.with_suffix(p.suffix + ".bak")
        try:
            shutil.copy2(p, backup)
        except OSError:
            pass
    tmp = p.with_suffix(p.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    os.replace(tmp, p)
    return p


def selected_ids(manifest):
    if not isinstance(manifest, dict):
        return []
    skills = manifest.get("skills") or {}
    sel = skills.get("selected") or []
    return [s for s in sel if isinstance(s, str)]


def agent_is_enabled(manifest, agent_id):
    """Return whether a manager-supported target is enabled in the manifest.

    Older manifests without an agent entry retain the historical enabled
    behavior. An explicit ``enabled: false`` opts out of managed operations.
    """
    agents = manifest.get("agents") if isinstance(manifest, dict) else None
    settings = agents.get(agent_id) if isinstance(agents, dict) else None
    if not isinstance(settings, dict):
        return True
    return settings.get("enabled", True)