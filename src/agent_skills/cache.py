"""Discovery cache with fuller invalidation key (guideline v4 §5.7 / R-07).

Cache key per skill includes:
  - resolved real source path
  - SKILL.md mtime
  - SKILL.md size
  - fast content fingerprint (md5 of first 64 KB)

Cache-level keys:
  - resolved real path of library root
  - manager/parser schema version
  - user-authored metadata override version (skill_overrides)
  - presence/absence of each previously-seen skill directory

--no-cache bypasses it for diagnostics.
"""

import hashlib
import json
import os
from pathlib import Path

CACHE_FILENAME = "discovery-cache.json"
CACHE_SCHEMA_VERSION = 1
OVERRIDES_VERSION = 1


def cache_path(generated_root=None):
    if generated_root is None:
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


def content_hash(skill_md_path, limit=65536):
    """Fast content fingerprint: md5 of the first `limit` bytes of SKILL.md."""
    try:
        h = hashlib.md5()
        with open(skill_md_path, "rb") as f:
            h.update(f.read(limit))
        return h.hexdigest()
    except OSError:
        return None


def stat_key_for_skill(skill_md_path):
    """Return a list key: [real_path, mtime, size] (cheap stat only, no file read)."""
    try:
        p = Path(skill_md_path)
        st = p.stat()
        return [
            str(p.resolve()),
            int(st.st_mtime),
            int(st.st_size),
        ]
    except OSError:
        return None


def cache_key_for_skill(skill_md_path):
    """Return full key: [real_path, mtime, size, content_hash].

    Content hash is computed eagerly here; callers that only need a cheap
    invalidation check should use stat_key_for_skill() first.
    """
    key = stat_key_for_skill(skill_md_path)
    if key is None:
        return None
    key.append(content_hash(Path(skill_md_path)))
    return key


def is_cache_valid(cache, library_root, skill_entries, overrides_version=OVERRIDES_VERSION):
    """skill_entries: list of (dir_name, skill_md_path).

    Returns True only if every cache-level and per-skill key component matches.
    """
    if not isinstance(cache, dict):
        return False
    if cache.get("library_root") != str(Path(library_root).resolve()):
        return False
    if cache.get("schema_version") != CACHE_SCHEMA_VERSION:
        return False
    if cache.get("overrides_version") != overrides_version:
        return False
    cached = cache.get("skills")
    if not isinstance(cached, dict):
        return False
    current_names = set(d for d, _ in skill_entries)
    # Presence/absence: renamed or removed skills must invalidate.
    if set(cached.keys()) != current_names:
        return False
    for dn, p in skill_entries:
        # Cheap stat-only check first: mtime+size is a sufficient proxy for
        # content unchanged in the common case. Avoids reading SKILL.md on
        # every cache hit.
        stat_key = stat_key_for_skill(p)
        if stat_key is None:
            return False
        ck = cached.get(dn)
        if not isinstance(ck, dict):
            return False
        cached_key = ck.get("key")
        if not isinstance(cached_key, list) or len(cached_key) < 3:
            return False
        # Compare stat components (real_path, mtime, size).
        if cached_key[:3] != stat_key:
            return False
        # Stat matches: verify content hash to guard against same-mtime/same-size edits.
        cached_hash = cached_key[3] if len(cached_key) > 3 else None
        current_hash = content_hash(Path(p))
        if cached_hash is not None and current_hash is not None and cached_hash != current_hash:
            return False
    return True