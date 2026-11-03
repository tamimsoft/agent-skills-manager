"""Global configuration for the agent skill manager."""

import json
import os
import shutil
from pathlib import Path

SCHEMA_VERSION = 1
DEFAULT_CONFIG_REL = ".config/agent-skills/config.json"
DEFAULT_RULES_REL = ".config/agent-skills/rules.md"
DEFAULT_LIBRARY_REL = ".agents/skills"
DEFAULT_GENERATED_REL = ".local/share/agent-skills/projects"

TESTED_AGENT_VERSIONS = {
    "opencode": "2.2.5",
    "junie": "26.10.27",
    "kilo": "7.8.18",
}


def home_dir():
    override = os.environ.get("AGENT_SKILLS_HOME")
    if override:
        return Path(override).expanduser().resolve()
    return Path.home()


def config_path():
    override = os.environ.get("AGENT_SKILLS_CONFIG")
    if override:
        return Path(override).expanduser().resolve()
    return home_dir() / ".config" / "agent-skills" / "config.json"


def default_config():
    h = home_dir()
    return {
        "schema_version": SCHEMA_VERSION,
        "manager_version": "0.1.0",
        "library_root": str(h / ".agents" / "skills"),
        "allowed_roots": [],
        "generated_root": str(h / ".local" / "share" / "agent-skills" / "projects"),
        "rules_path": str(h / ".config" / "agent-skills" / "rules.md"),
        "agent_paths": {},
        "skill_overrides": {},
        "skill_context_budget_tokens": 32768,
        "max_skills_in_context": 50,
        "tested_agent_versions": dict(TESTED_AGENT_VERSIONS),
    }


def _validate(cfg):
    errors = []
    if not isinstance(cfg, dict):
        return ["config must be a JSON object"]
    if cfg.get("schema_version") != SCHEMA_VERSION:
        # Allow migration handled elsewhere; here just note.
        if "schema_version" in cfg and cfg.get("schema_version") is not None:
            if not isinstance(cfg.get("schema_version"), int):
                errors.append("schema_version must be an integer")
    # library_root
    lr = cfg.get("library_root")
    if lr is not None and not isinstance(lr, str):
        errors.append("library_root must be a string")
    # allowed_roots
    ar = cfg.get("allowed_roots")
    if ar is not None and not (isinstance(ar, list) and all(isinstance(x, str) for x in ar)):
        errors.append("allowed_roots must be a list of strings")
    # skill_overrides
    so = cfg.get("skill_overrides")
    if so is not None and not isinstance(so, dict):
        errors.append("skill_overrides must be an object")
    elif isinstance(so, dict):
        for k, v in so.items():
            if not isinstance(v, dict):
                errors.append("skill_overrides[%s] must be an object" % k)
    # skill_context_budget_tokens
    bgt = cfg.get("skill_context_budget_tokens")
    if bgt is not None and not (isinstance(bgt, int) and bgt >= 0):
        errors.append("skill_context_budget_tokens must be a non-negative integer")
    # max_skills_in_context
    msc = cfg.get("max_skills_in_context")
    if msc is not None and not (isinstance(msc, int) and msc >= 0):
        errors.append("max_skills_in_context must be a non-negative integer")
    return errors


def load_config():
    p = config_path()
    if not p.exists():
        return default_config(), []
    try:
        with p.open("r", encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError) as e:
        return None, ["failed to read config %s: %s" % (p, e)]
    if not isinstance(cfg, dict):
        return None, ["config root must be a JSON object"]
    # Merge defaults for missing keys (preserve unknown keys).
    base = default_config()
    for k, v in base.items():
        if k not in cfg:
            cfg[k] = v
    errs = _validate(cfg)
    if errs:
        return cfg, errs
    return cfg, []


def save_config(cfg):
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    # Backup previous version.
    if p.exists():
        backup = p.with_suffix(p.suffix + ".bak")
        try:
            shutil.copy2(p, backup)
        except OSError:
            pass
    # Validate.
    errs = _validate(cfg)
    if errs:
        raise ValueError("config validation failed: " + "; ".join(errs))
    tmp = p.with_suffix(p.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, sort_keys=False)
        f.write("\n")
    os.replace(tmp, p)
    return p


def resolve_library_root(cfg=None):
    if cfg is None:
        cfg, _ = load_config()
    if cfg is None:
        cfg = default_config()
    lr = cfg.get("library_root")
    if lr:
        return Path(lr).expanduser()
    return home_dir() / ".agents" / "skills"