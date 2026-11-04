"""Safe management of the agent-skills block in project AGENTS.md files."""

import os
import shutil
import stat
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from agent_skills.config import home_dir

BEGIN_MARKER = "<!-- agent-skills:begin -->"
END_MARKER = "<!-- agent-skills:end -->"
BASE_TEMPLATE_FILENAME = "AGENTS.base.md"
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


class AgentsMdError(ValueError):
    """Raised when the managed instruction block cannot be safely updated."""


def _global_template_path():
    return home_dir() / ".config" / "agent-skills" / "templates" / BASE_TEMPLATE_FILENAME


def ensure_global_template():
    """Copy the bundled default template only when no user copy exists."""
    global_tpl = _global_template_path()
    if not global_tpl.exists():
        global_tpl.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(TEMPLATES_DIR / BASE_TEMPLATE_FILENAME), str(global_tpl))
    return global_tpl


def _tech_section(tech):
    name = tech.get("name", "unknown")
    evidence = ", ".join(e.get("file", "") for e in tech.get("evidence", []))
    return "### %s\nDetected via: %s\n" % (name, evidence)


def render_agents_block(techs, cfg, create_global_template=True):
    global_tpl = _global_template_path()
    if create_global_template:
        global_tpl = ensure_global_template()
    elif not global_tpl.exists():
        global_tpl = TEMPLATES_DIR / BASE_TEMPLATE_FILENAME
    template = global_tpl.read_text(encoding="utf-8")
    if BEGIN_MARKER in template or END_MARKER in template:
        raise AgentsMdError("base template must not contain AGENTS.md block markers")
    parts = [template.rstrip()]
    if techs:
        parts.append("## Project-specific technology guidance\n")
        parts.extend(_tech_section(tech) for tech in techs)
    parts.append("## Agent skills\nSee .agents/skills.json for the selected skill set.\n")
    body = "\n".join(parts).strip()
    return "%s\n%s\n%s" % (BEGIN_MARKER, body, END_MARKER)


def extract_agents_block(text):
    starts = [i for i in range(len(text)) if text.startswith(BEGIN_MARKER, i)]
    ends = [i for i in range(len(text)) if text.startswith(END_MARKER, i)]
    if not starts and not ends:
        return None
    if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
        raise AgentsMdError("AGENTS.md contains malformed or duplicate agent-skills markers")
    end = ends[0] + len(END_MARKER)
    if text.find(BEGIN_MARKER, starts[0] + len(BEGIN_MARKER), end) != -1:
        raise AgentsMdError("AGENTS.md contains nested agent-skills markers")
    return text[starts[0]:end]


def _merge(existing, block):
    current = extract_agents_block(existing)
    if current is None:
        separator = "" if not existing else ("" if existing.endswith("\n\n") else "\n" if existing.endswith("\n") else "\n\n")
        return existing + separator + block + "\n"
    start = existing.index(BEGIN_MARKER)
    end = existing.index(END_MARKER, start) + len(END_MARKER)
    return existing[:start] + block + existing[end:]


def _backup_unmarked(path):
    backup_dir = path.parent / ".agents" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    backup = backup_dir / ("AGENTS.md." + stamp)
    shutil.copy2(str(path), str(backup))
    return backup


def _atomic_write(path, text):
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
    fd, temp_name = tempfile.mkstemp(prefix=".AGENTS.md-", dir=str(path.parent))
    try:
        os.chmod(temp_name, mode)
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, str(path))
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def generate_agents_md(root, techs, cfg, force=False, write=True):
    """Merge a rendered manager block into AGENTS.md without replacing user text.

    The ``force`` argument remains accepted for callers from older installed
    versions, but all writes now update only the marked manager-owned block.
    Returns ``(wrote, message, merged_content)``.
    """
    del force
    root = Path(root)
    path = root / "AGENTS.md"
    try:
        block = render_agents_block(techs, cfg, create_global_template=write)
        existed = path.exists()
        existing = path.read_text(encoding="utf-8") if existed else ""
        merged = _merge(existing, block)
        if not write:
            return False, "AGENTS.md content computed (not written).", merged
        if existed and merged == existing:
            return False, "Managed block in %s is already current." % path, merged
        if existed and extract_agents_block(existing) is None:
            _backup_unmarked(path)
        _atomic_write(path, merged)
        return merged != existing, "Updated managed block in %s" % path, merged
    except (OSError, AgentsMdError) as exc:
        return False, "Failed to update AGENTS.md: %s" % exc, None
