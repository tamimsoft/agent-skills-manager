"""Cross-component validation helpers (Phase 1: basic)."""

from pathlib import Path


def validate_library_root(path):
    p = Path(path).expanduser()
    if not p.exists():
        return False, "library root does not exist: %s" % p
    if not p.is_dir():
        return False, "library root is not a directory: %s" % p
    return True, "ok"


def validate_safe_id(value):
    from agent_skills.identity import is_safe_id
    if is_safe_id(value):
        return True, "ok"
    return False, "invalid skill id: %r" % value


def validate_config(cfg):
    from agent_skills.config import _validate
    errs = _validate(cfg)
    if errs:
        return False, errs
    return True, []