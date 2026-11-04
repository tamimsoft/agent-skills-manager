"""Symlink management for generated project skill directories."""

import json
from pathlib import Path

MARKER_FILENAME = ".agent-skills-managed.json"
OWNED_RULES_FILENAME = "opencode-owned-rules.json"


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