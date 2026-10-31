"""Project root resolution."""

import os
import subprocess
from pathlib import Path


def find_project_root(start=None, for_init=False):
    """Resolve project root per guideline 5.7."""
    cur = Path(start or os.getcwd()).resolve()
    # 1. Nearest ancestor containing .agents/skills.json
    p = cur
    while True:
        if (p / ".agents" / "skills.json").is_file():
            return p
        if p.parent == p:
            break
        p = p.parent
    # 2. For init only: git top-level
    if for_init:
        try:
            out = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=str(cur), capture_output=True, text=True, check=True,
            )
            top = out.stdout.strip()
            if top:
                return Path(top).resolve()
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
    # 3. Fail
    raise ValueError("could not resolve project root (no .agents/skills.json and not in a git repo)")