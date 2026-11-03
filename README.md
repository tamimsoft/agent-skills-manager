# agent-skills-manager

**Global agent skill manager for OpenCode, Junie, and Kilo.** Python 3 (>=3.9), standard library only.

Discover, validate, select, and sync agent skills (SKILL.md frontmatter files) into per-project generated skill directories that AI coding agents can consume — with enforced context budgets, safe symlink handling, and hard-enforced project instructions.

---

## The Problem

AI coding agents (OpenCode, Junie, Kilo) load **all** skills from a shared global library by default. This creates three problems:

1. **Context bloat** — Every skill in your library is injected into the agent's context window, regardless of whether it's relevant to the current project. A Flutter project shouldn't load .NET or Laravel skills, but without a manager, it does.
2. **No per-project control** — There's no way to say "this project should only use these 10 skills" without manually editing agent config files in every project.
3. **No hard enforcement** — Project-level instructions (AGENTS.md) are advisory. Agents can ignore them, and they go stale as your tech stack changes.

`agent-skills-manager` solves all three. It maintains a shared skill library, lets you select a subset per project, enforces a context budget (tokens + max skills), generates per-project skill directories, and keeps `AGENTS.md` in sync across every managed launch.

---

## Why Use This Project

| Problem | Without agent-skills-manager | With agent-skills-manager |
|---------|------------------------------|---------------------------|
| Context bloat | All ~1,400+ library skills load into every agent session | Only your selected skills (typically 5–15) are injected |
| Per-project control | Manual edits to `opencode.json`, `.kilo/kilo.json`, Junie flags in every project | One manifest (`.agents/skills.json`) per project; one command syncs it everywhere |
| Stale instructions | `AGENTS.md` drifts from your actual stack | Auto-regenerated on `sync` and every managed launch — never out of date |
| Unsafe symlinks | Library symlinks can escape to arbitrary filesystem paths | Allow-listed symlink resolution — targets must resolve inside the library root |
| Context budget | No budget; every skill consumes tokens | Enforced token + max-skills budget with relevance-based truncation |

---

## Install

```bash
./install.sh
```

Installs the `agent-skills` launcher to `~/.local/bin/agent-skills`, copies the package to `~/.local/lib/agent-skills`, and sets PYTHONPATH in the wrapper. Ensure `~/.local/bin` is on PATH.

Verify with:

```bash
agent-skills doctor
```

---

## Getting Started with a New Project

```bash
# 1. Enter your project root.
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

---

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

---

## Context Budget

Managed launches (`agent-skills junie`, `agent-skills kilo`, `agent-skills opencode apply|run`, `agent-skills sync`) limit which skills enter the agent context window:

- Only skills listed in the project manifest `selected` array are eligible.
- Eligible skills are scored by `recommend.score_skill()` (+5 tech match, +1 keyword overlap, +min(3) instruction overlap), sorted by score then dir_name, and truncated to fit the budget.
- `skill_context_budget_tokens` (default 32768): estimated max tokens for all skill context. Set 0 for unlimited.
- `max_skills_in_context` (default 50): hard cap on skill count. Set 0 for unlimited.
- Skills excluded by the budget are reported as warnings; selection is unchanged in the manifest.
- Unmanaged launches (plain `opencode` or `junie`, not through the manager) load all skills in the global library — this asymmetry is by design.

Config fields live in `~/.config/agent-skills/config.json` (schema v1). Override via `AGENT_SKILLS_HOME` / `AGENT_SKILLS_CONFIG` env vars for tests.

---

## Hard-Enforced AGENTS.md

Unlike a static `AGENTS.md` that agents can ignore, `agent-skills-manager` treats it as a live artifact:

- **`init`** generates it once (safe merge — never overwrites an existing file).
- **`sync`** and every managed launch (`junie`, `opencode apply|run`, `kilo apply|run`) regenerate it from the global rules template + your detected technologies.
- **`validate`** fails (exit 3) if `AGENTS.md` is missing or stale.

This keeps the global engineering rules in front of the agent on every session, and keeps them current as your stack evolves.

---

## Safe Skill IDs

Skill IDs (folder names) must match `^[A-Za-z0-9][A-Za-z0-9._-]*$`. Names with spaces, slashes, or leading dots are discovered but flagged as unsafe and cannot be selected or added to the manifest.

---

## How It Works

```
┌─────────────────┐     ┌──────────────────────────┐     ┌─────────────────────┐
│   Library root  │     │   Project manifest       │     │   Generated skills    │
│ ~/.agents/skills│────▶│  .agents/skills.json     │────▶│   dir (symlinks)      │
│  SKILL.md files │     │   (selected skill IDs)   │     │   + AGENTS.md + marker│
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

- **Discovery**: `discover_skills()` scans the library root, parses SKILL.md frontmatter, validates safe IDs, allow-lists symlinks (targets must resolve inside the library root), and caches results.
- **Manifest**: `.agents/skills.json` lists selected skill IDs; `init` detects technologies and recommends skills; `generate_agents_md()` creates `AGENTS.md` (safe merge — never overwrites).
- **Sync/build**: `sync` (and managed launches) apply the context budget (tech-match scoring + token/max-skill caps), then atomically build-then-swap the generated skills dir via `AdvisoryLock` (fcntl.flock, 10s timeout).
- **Adapter behavior**:
  - **OpenCode** — writes permission rules + `skill.use` policies into `opencode.json` plus an `opencode-owned-rules.json` sidecar; user-authored rules are preserved (tagged `source: agent-skills-manager`).
  - **Junie** — launches with `--skill-default-locations=false --skill-location=<generated dir>`; additive library loading remains for unmanaged Junie.
  - **Kilo** — additive (no exclusive skill-path mechanism); writes permission rules into `.kilo/kilo.json` and generates `.kilo/skills/` with marker.
- **Context budget**: Only `selected` skills are eligible; they are scored (+5 tech match, +1 keyword overlap, +min(3) instruction overlap), sorted by score then dir_name, and truncated to `skill_context_budget_tokens` / `max_skills_in_context`. Excluded skills are reported as warnings; manifest selection is unchanged.

---

## Tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

66 tests covering discovery, frontmatter parsing, identity/safe-ID validation, context budget filtering, cache invalidation, crash recovery, link generation, resolution, and AGENTS.md hard enforcement.

---

## Architecture

| Module | Purpose |
|--------|---------|
| `src/agent_skills/cli.py` | All subcommands (validate/sync implemented inline) |
| `src/agent_skills/discovery.py` | Skill discovery, frontmatter parsing, caching, identity checks |
| `src/agent_skills/frontmatter.py` | Restricted YAML-subset parser |
| `src/agent_skills/identity.py` | Safe ID validation, skill records, duplicate/mismatch checks |
| `src/agent_skills/recommend.py` | Scoring and context-budget filtering |
| `src/agent_skills/manifest.py` | `.agents/skills.json` load/save/validate |
| `src/agent_skills/config.py` | Config load/save/validate, env var overrides |
| `src/agent_skills/cache.py` | Discovery cache with stat + content-hash invalidation |
| `src/agent_skills/lock.py` | fcntl.flock advisory lock (10s timeout) |
| `src/agent_skills/links.py` | Atomic build-then-swap project skills dir generation |
| `src/agent_skills/detection.py` | Technology marker scanning |
| `src/agent_skills/resolution.py` | Per-agent resolution states |
| `src/agent_skills/adapter_common.py` | Shared wrapper/build/budget helpers |
| `src/agent_skills/adapters/{junie,kilo,opencode}.py` | Agent-specific launchers |

Generated project dirs contain `.agent-skills-managed.json` marker, `opencode-owned-rules.json`, and `AGENTS.md`; `sync` regenerates them atomically.

---

## License

MIT

---

**No external dependencies.** Standard library only. No lint, typecheck, or formatter configured — verification is the test suite.
