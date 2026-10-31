"""Mtime-keyed discovery cache."""

import json
import os
from pathlib import Path

CACHE_FILENAME = "discovery-cache.json"


def cache_path(generated_root=None):
    if generated_root is None:
        # Use a cache dir under home.
        base = Path(os.environ.get("AGENT_SKILLS_CACHE", "")).expanduser() if os.environ.get("AGENT_SKILLS_CACHE") else None
        if base:
            return base / CACHE_FILENAME
        return Path.home() / ".cache" / "agent-skills" / CACHE_FILENAME
    return Path(generated_root) / CACHE_FILENAME


def load_cache(path):
    p = Path(path)
    if not p.exists():
        return None
    try:
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def save_cache(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, p)


def cache_key_for_skill(skill_md_path):
    try:
        st = Path(skill_md_path).stat()
        return (int(st.st_mtime), int(st.st_size))
    except OSError:
        return None


def is_cache_valid(cache, library_root, skill_entries):
    """skill_entries: list of (dir_name, skill_md_path)."""
    if not isinstance(cache, dict):
        return False
    if cache.get("library_root") != str(Path(library_root).resolve()):
        return False
    cached = cache.get("skills")
    if not isinstance(cached, dict):
        return False
    for dn, p in skill_entries:
        key = cache_key_for_skill(p)
        if key is None:
            return False
        ck = cached.get(dn)
        if not isinstance(ck, dict) or tuple(ck.get("key", ())) != tuple(key):
            return False
    # Ensure no stale extra entries.
    if set(cached.keys()) != set(d for d, _ in skill_entries):
        return False
    return True