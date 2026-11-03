# agent-skills-manager

Global agent skill manager for OpenCode, Junie, and Kilo. Python 3 (>=3.9), standard library only.

Installs, discovers, validates, and syncs agent skills (SKILL.md frontmatter files) into per-project generated skill directories that OpenCode, Junie, and Kilo can consume.

## Install

```bash
./install.sh
```

Installs the `agent-skills` launcher to `~/.local/bin/agent-skills`, copies the package to `~/.local/lib/agent-skills`, and sets PYTHONPATH in the wrapper. Ensure `~/.local/bin` is on PATH.

## Usage

```bash
# Manifest
agent-skills init              # create .agents/skills.json (detects techs, recommends skills)
agent-skills select            # interactively select skills (TTY or --yes)
agent-skills add SKILL [...]   # add skills by dir_name (validates safe IDs)
agent-skills remove SKILL [...]# remove skills from manifest

# Inspection
agent-skills list [--selected] [--filter STR] [--tech STR] [--json]
agent-skills detect            # show detected technologies for project root
agent-skills recommend [--all] [--limit N]

# Validation & sync
agent-skills validate          # validate config, manifest, library (exit 3 on failure)
agent-skills sync [--dry-run]  # regenerate generated project skills dir from manifest

# Managed launches (context-budget enforced)
agent-skills junie [--prepare] [args...]
agent-skills kilo [args...]
agent-skills opencode plan|apply|validate|run [args...]

# Maintenance
agent-skills doctor            # environment checks
agent-skills clean [--dry-run] # list/remove orphaned generated directories
```

## Context budget

Managed launches (`agent-skills junie`, `agent-skills kilo`, `agent-skills opencode apply|run`, `agent-skills sync`) limit which skills enter the agent context window:

- Only skills listed in the project manifest `selected` array are eligible.
- Eligible skills are scored by `recommend.score_skill()` (+5 tech match, +1 keyword overlap, +min(3) instruction overlap), sorted by score then dir_name, and truncated to fit the budget.
- `skill_context_budget_tokens` (default 32768): estimated max tokens for all skill context. Set 0 for unlimited.
- `max_skills_in_context` (default 50): hard cap on skill count. Set 0 for unlimited.
- Skills excluded by the budget are reported as warnings; selection is unchanged in the manifest.
- Unmanaged launches (plain `opencode` or `junie`, not through the manager) load all skills in the global library — this asymmetry is by design.

Config fields live in `~/.config/agent-skills/config.json` (schema v1). Override via `AGENT_SKILLS_HOME` / `AGENT_SKILLS_CONFIG` env vars for tests.

## Safe skill IDs

Skill IDs (folder names) must match `^[A-Za-z0-9][A-Za-z0-9._-]*$`. Names with spaces, slashes, or leading dots are discovered but flagged as unsafe and cannot be selected or added to the manifest.

## Tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

## Architecture

- `src/agent_skills/cli.py` — all subcommands (validate/sync implemented inline)
- `src/agent_skills/discovery.py` — skill discovery, frontmatter parsing, caching, identity checks
- `src/agent_skills/frontmatter.py` — restricted YAML-subset parser
- `src/agent_skills/identity.py` — safe ID validation, skill records, duplicate/mismatch checks
- `src/agent_skills/recommend.py` — scoring and context-budget filtering
- `src/agent_skills/manifest.py` — `.agents/skills.json` load/save/validate
- `src/agent_skills/config.py` — config load/save/validate, env var overrides
- `src/agent_skills/cache.py` — discovery cache with stat + content-hash invalidation
- `src/agent_skills/lock.py` — fcntl.flock advisory lock (10s timeout)
- `src/agent_skills/links.py` — atomic build-then-swap project skills dir generation
- `src/agent_skills/detection.py` — technology marker scanning
- `src/agent_skills/resolution.py` — per-agent resolution states
- `src/agent_skills/adapter_common.py` — shared wrapper/build/budget helpers
- `src/agent_skills/adapters/{junie,kilo,opencode}.py` — agent-specific launchers

Generated project dirs contain `.agent-skills-managed.json` marker and `opencode-owned-rules.json`; `sync` regenerates them atomically.
