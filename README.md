# agent-skills-manager

Global agent skill manager for OpenCode and Junie. Python 3, standard library only.

## Install

```bash
./install.sh
```

Ensures `~/.local/bin` is on PATH.

## Usage

```bash
agent-skills init
agent-skills list
agent-skills detect
agent-skills recommend
agent-skills add flutter-tamim
agent-skills validate
agent-skills sync
agent-skills junie
agent-skills kilo
agent-skills opencode plan
agent-skills opencode apply
```

## Context budget (Kilo-ready)

Managed launches limit which skills enter the agent context window:

- Only skills listed in the project manifest `selected` array are eligible.
- Eligible skills are scored by relevance (+5 tech match, +1 keyword overlap, +min(3) instruction overlap), sorted by score then dir_name, and truncated to fit the budget.
- `skill_context_budget_tokens` (default 32768): estimated max tokens for all skill context. Set 0 for unlimited.
- `max_skills_in_context` (default 50): hard cap on skill count. Set 0 for unlimited.
- Skills excluded by the budget are reported as warnings; selection is unchanged in the manifest.
- Unmanaged launches (plain `opencode` or `junie`, not through the manager) load all skills in the global library — this asymmetry is by design.

Config fields live in `~/.config/agent-skills/config.json` (schema v1). Override via `AGENT_SKILLS_HOME` / `AGENT_SKILLS_CONFIG` env vars for tests.

## Tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```
