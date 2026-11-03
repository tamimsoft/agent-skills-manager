# agent-skills-manager

Global agent skill manager for OpenCode, Junie, and Kilo. Python 3 (>=3.9), standard library only.

Installs, discovers, validates, and syncs agent skills (SKILL.md frontmatter files) into per-project generated skill directories that OpenCode, Junie, and Kilo can consume.

## Install

```bash
./install.sh
```

Installs the `agent-skills` launcher to `~/.local/bin/agent-skills`, copies the package to `~/.local/lib/agent-skills`, and sets PYTHONPATH in the wrapper. Ensure `~/.local/bin` is on PATH.

## Getting started with a new project

```bash
# 1. Enter your project root (must contain or be under a git repo).
cd /path/to/your-project

# 2. Create the manifest — detects technologies and recommends skills.
agent-skills init

# 3. Select skills interactively (requires TTY or --yes).
agent-skills select

# 4. Or add specific skills by dir_name.
agent-skills add flutter-tamim code-reviewer

# 5. Validate the manifest against the library.
agent-skills validate

# 6. Generate the project skills directory (respects context budget).
agent-skills sync

# 7. Launch an agent with managed skills.
agent-skills junie --prepare
agent-skills opencode plan
agent-skills kilo plan
```

**First-time behavior:**
- `init` creates `.agents/skills.json` with an empty `selected` array and writes `AGENTS.md` (combining the global rules template + detected technology guidance). An existing `AGENTS.md` is **never overwritten**.
- Detected technologies are printed; recommended skills are shown but **not auto-selected**.
- Use `--yes` to skip confirmations in non-TTY environments (CI, scripts).

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

## How it works

```
┌─────────────────┐     ┌──────────────────────────┐     ┌─────────────────────┐
│   Library root  │     │   Project manifest       │     │   Generated skills    │
│ ~/.agents/skills│────▶│  .agents/skills.json     │────▶│   dir (symlinks)      │
│  SKILL.md files │     │   (selected skill IDs)   │     │   + managed marker    │
└─────────────────┘     └──────────────────────────┘     └─────────────────────┘
                                                        │
                    ┌───────────────────────────────────┼──────────────────────┐
                    ▼                                   ▼                      ▼
            ┌─────────────┐                      ┌───────────┐         ┌──────────┐
            │   OpenCode  │                      │   Junie   │         │   Kilo   │
            │   (apply)   │                      │   launch  │         │  (apply) │
            │ permissions │                      │ --skill-location   permission rules
            │   + policies│                      │   generated dir    in kilo.json
            └─────────────┘                      └───────────┘         └──────────┘
```

- **Discovery**: `discover_skills()` scans the library root, parses SKILL.md frontmatter, validates safe IDs, allow-lists symlinks, and caches results.
- **Manifest**: `.agents/skills.json` lists selected skill IDs; `init` detects technologies and recommends skills; `generate_agents_md()` creates `AGENTS.md` (safe merge — never overwrites).
- **Sync/build**: `sync` (and managed launches) apply the context budget (tech-match scoring + token/max-skill caps), then atomically build-then-swap the generated skills dir via `AdvisoryLock`.
- **Adapter behavior**:
  - **OpenCode** — writes permission rules + `skill.use` policies into `opencode.json` plus an `opencode-owned-rules.json` sidecar; user-authored rules are preserved (tagged `source: agent-skills-manager`).
  - **Junie** — launches with `--skill-default-locations=false --skill-location=<generated dir>`; additive library loading remains for unmanaged Junie.
  - **Kilo** — additive (no exclusive skill-path mechanism); writes permission rules into `.kilo/kilo.json` and generates `.kilo/skills/` with marker.
- **Context budget**: Only `selected` skills are eligible; they are scored (+5 tech match, +1 keyword overlap, +min(3) instruction overlap), sorted by score then dir_name, and truncated to `skill_context_budget_tokens` / `max_skills_in_context`. Excluded skills are reported as warnings; manifest selection is unchanged.

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
