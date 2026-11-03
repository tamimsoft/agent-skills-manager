"""Per-agent skill resolution model (guideline v4 §2.2 / R-03).

The manifest keeps one shared ``skills.selected`` list. On top of that single
list, the manager computes a **resolution result per selected skill per
enabled agent**:

State        Meaning
----------   -------------------------------------------------------------------
available    The skill is selected, its agent identifier resolves cleanly, and
             it is actually exposed to that agent.
unavailable  The skill is selected but cannot be exposed to that agent at all
             (e.g. OpenCode rejects a skill with no frontmatter).
unresolved   The skill's identifier cannot be determined for that agent yet
             (verification pending, or a parsing ambiguity).
conflict     The skill's identifier collides with another skill already visible
             to that agent (e.g. a declared_name collision between two skills
             for Kilo).

Rules:
- validate and list --selected show this per-agent breakdown with a reason
  string, not just pass/fail.
- A skill unavailable in one adapter must never silently become available
  under a different identity in another adapter without that being visible in
  the resolution output.
- No per-agent selection override — only per-agent resolution reporting.
- Collisions are surfaced as `conflict` with both colliding sources named.
  The manager never silently renames a skill to resolve a collision.
"""

from agent_skills.identity import is_safe_id

# Resolution states.
AVAILABLE = "available"
UNAVAILABLE = "unavailable"
UNRESOLVED = "unresolved"
CONFLICT = "conflict"

ALL_STATES = (AVAILABLE, UNAVAILABLE, UNRESOLVED, CONFLICT)


def _agent_id_for(record, agent_name):
    """Return the resolved agent identifier for a skill, or None."""
    agent_ids = record.get("agent_id") or {}
    aid = agent_ids.get(agent_name)
    if aid:
        return aid
    # Fallback: OpenCode and Junie use dir_name; Kilo uses declared_name.
    if agent_name == "kilo":
        return record.get("declared_name")
    return record.get("dir_name")


def resolve_resolutions(records, selected_ids, enabled_agents):
    """Compute per-agent resolution state for every selected skill.

    Returns a dict mapping dir_name -> {agent_name: (state, reason)}.
    """
    rec_map = {r["dir_name"]: r for r in records if isinstance(r, dict)}
    result = {}

    for sid in selected_ids:
        rec = rec_map.get(sid)
        if rec is None:
            result[sid] = {}
            for agent in enabled_agents:
                result[sid][agent] = (UNAVAILABLE, "selected skill missing from library")
            continue

        agent_states = {}
        for agent in enabled_agents:
            agent_states[agent] = _resolve_one(rec, agent, rec_map)
        result[sid] = agent_states

    return result


def _resolve_one(record, agent_name, rec_map):
    """Resolve a single skill for a single agent."""
    dir_name = record.get("dir_name")
    declared_name = record.get("declared_name")
    frontmatter_status = record.get("frontmatter_status")

    # Identifier resolution: can we determine this agent's identifier?
    agent_id = _agent_id_for(record, agent_name)

    if agent_id is None:
        return UNRESOLVED, "no %s identifier resolved" % agent_name

    # Safe-ID check: an identifier the agent cannot select by CLI id is
    # treated as unresolved rather than available.
    if not is_safe_id(agent_id):
        return UNRESOLVED, "%s identifier %r is not a safe skill id" % (agent_name, agent_id)

    # Frontmatter-less skills: unavailable for agents that require frontmatter.
    # OpenCode requires frontmatter (V1 pending verification); treat missing
    # frontmatter as unavailable until V1 confirms otherwise.
    if frontmatter_status == "missing" and agent_name == "opencode":
        return UNAVAILABLE, "no frontmatter; OpenCode requires frontmatter (V1 pending verification)"

    # Collision detection: another selected skill with the same agent_id for
    # this agent is a conflict.
    for other_sid, other in rec_map.items():
        if other_sid == dir_name:
            continue
        other_aid = _agent_id_for(other, agent_name)
        if other_aid == agent_id and other_aid is not None:
            return CONFLICT, "collides with %r on %s identifier %r" % (
                other_sid, agent_name, agent_id)

    return AVAILABLE, "ok"


def resolution_summary(resolutions):
    """Return a human-readable summary string for resolution output."""
    lines = []
    for sid in sorted(resolutions):
        states = resolutions[sid]
        if not states:
            lines.append("%s: (no agents enabled)" % sid)
            continue
        parts = []
        for agent in sorted(states):
            state, reason = states[agent]
            parts.append("%s=%s(%s)" % (agent, state, reason))
        lines.append("%s: %s" % (sid, "; ".join(parts)))
    return "\n".join(lines)
