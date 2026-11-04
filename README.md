# agent-skills-manager

**Global agent skill manager for OpenCode, Junie, and Kilo.** Python 3 (>=3.9), standard library only.

Discover, validate, select, and sync agent skills (SKILL.md frontmatter files) into per-project agent configurations — with launch-time context limits, safe generated directories, and a protected manager-owned instructions block.

---

## The Problem

Some coding agents discover skills from global directories as well as project directories. A large shared library can create three problems:

1. **Context bloat** — Every skill in your library is injected into the agent's context window, regardless of whether it's relevant to the current project. A Flutter project shouldn't load .NET or Laravel skills, but without a manager, it does.
2. **No per-project control** — There's no way to say "this project should only use these 10 skills" without manually editing agent config files in every project.
3. **No hard enforcement** — Project-level instructions (AGENTS.md) are advisory. Agents can ignore them, and they go stale as your tech stack changes.

`agent-skills-manager` manages a shared library and project-specific selections. It applies context limits to managed launches and creates a project skill directory. Discovery behavior differs by agent: Kilo continues to catalog global skills, so complete isolation requires moving the library outside its default scan path.

---

## Why Use This Project

| Problem | Without agent-skills-manager | With agent-skills-manager |
|---------|------------------------------|---------------------------|
| Context bloat | Global discovery may expose the full library | Managed launches use selected skills subject to configured context limits |
| Per-project control | Manual edits to `opencode.json`, `.kilo/kilo.json`, Junie flags in every project | One manifest (`.agents/skills.json`) per project; one command syncs it everywhere |
| Stale instructions | `AGENTS.md` drifts from your actual stack | Only the marked manager-owned block is refreshed; surrounding user content is preserved |
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

# 2. Create the manifest and run the guided agent/skill setup.
agent-skills init --interactive

# Or create the manifest non-interactively with the existing default agent set.
agent-skills init

# 3. Change the selected skill set later (requires a TTY).
agent-skills select

# 4. Or add specific skills by dir_name.
agent-skills add flutter-tamim code-reviewer

# 5. Validate the manifest against the library.
agent-skills validate

# 6. Preview, then generate the project skills directory.
agent-skills sync --dry-run
agent-skills sync

# 7. Launch an agent with managed skills.
agent-skills junie --prepare
agent-skills opencode plan
agent-skills kilo plan
```

**First-time behavior:**
- `init --interactive` asks which supported agents to manage, displays whether their configured executable is available, then lets you select recommended skills or search/browse the full library. Existing manifest selections and unrelated project metadata are preserved when editing.
- In the text skill picker, enter `s <text>` (or `/text`) to search the full catalog, `a` to browse all skills, and `r` to return to recommendations. In the curses picker, type to search the full catalog.
- Agent availability is informational: you may select a supported agent that is not currently installed or configured. Managed launch/apply commands refuse to run for agents disabled in `.agents/skills.json`.
- Interactive selection requires a TTY; `--yes` confirms writes but never supplies agent or skill choices. Plain `init` remains non-interactive and preserves the existing default agent set with no skills auto-selected.
- Successful initialization ensures local `docs/plans/` and `docs/reviews/` directories exist; empty directories are not tracked by Git.
- `init` merges a marked manager-owned block into `AGENTS.md`. Existing unmarked content is backed up under `.agents/backups/` and preserved.
- Use subcommand flags such as `select --yes`, `sync --dry-run`, `kilo apply --yes`, and `opencode apply --yes`; these flags are not global.

---

## Usage

```bash
# Manifest
agent-skills init [--interactive] [--yes] [--dry-run]
agent-skills select [--yes] [--dry-run]
agent-skills add SKILL [...] [--yes] [--dry-run]
agent-skills remove SKILL [...] [--yes] [--dry-run]

# Inspection
agent-skills list [--selected] [--filter STR] [--tech STR] [--json]
agent-skills detect            # show detected technologies for project root
agent-skills recommend [--all] [--limit N]

# Validation & sync
agent-skills validate          # validate config, manifest, library (exit 3 on failure)
agent-skills sync [--dry-run]  # regenerate generated project skills dir from manifest

# Managed launches (context-budget enforced)
agent-skills junie [--prepare] [--dry-run] [args...]
agent-skills kilo plan|validate
agent-skills kilo apply|run [--yes] [--dry-run] [args...]
agent-skills opencode plan|validate
agent-skills opencode apply [--yes] [--dry-run]
agent-skills opencode run [--dry-run] [args...]

# Maintenance
agent-skills doctor            # environment checks
agent-skills clean [--yes] [--dry-run] # list/remove orphaned generated directories
```

---

## Context Budget

Managed launches (`agent-skills junie`, `agent-skills kilo`, `agent-skills opencode apply|run`, `agent-skills sync`) limit which skills enter the agent context window:

- Only skills listed in the project manifest `selected` array are eligible.
- Eligible skills are scored by `recommend.score_skill()` (+5 tech match, +1 keyword overlap, +min(3) instruction overlap), sorted by score then dir_name, and filtered to fit the configured limits.
- The estimate covers catalog metadata (skill name and description), not full skill bodies; it is a rough estimate, not the agent's complete prompt-token count.
- `skill_context_budget_tokens` (default 32768): estimated maximum catalog tokens. Set 0 for unlimited.
- `max_skills_in_context` (default 50): hard cap on skill count. Set 0 for unlimited.
- Skills excluded by the budget are reported as warnings; selection is unchanged in the manifest.
- The manifest's `selected` list is unchanged when limits exclude skills. `sync` and managed launches report exclusions.
- Plain `opencode` or `junie` launches bypass manager filtering. Kilo 7.8.18 catalogs global `~/.agents/skills/` entries even during managed launches; its permission rules do not remove them from the catalog. Exclusive Kilo discovery requires moving the library outside that path and pointing `library_root` to the new location.

Config fields live in `~/.config/agent-skills/config.json` (schema v1). Override via `AGENT_SKILLS_HOME` / `AGENT_SKILLS_CONFIG` env vars for tests.

---

## Managed AGENTS.md block

Unlike a static `AGENTS.md` that agents can ignore, `agent-skills-manager` treats it as a live artifact:

- `init`, `sync`, and managed launches update only the `<!-- agent-skills:begin -->` / `<!-- agent-skills:end -->` block.
- Existing text outside the block is preserved. An unmarked existing file is backed up once before the block is appended.
- `plan` and `validate` are read-only; `validate` reports a missing, malformed, or stale block.
- The manager does not set or clear filesystem immutable flags. If an older version marked the file immutable, remove that flag manually before the first update (`chflags nouchg AGENTS.md` on macOS or `chattr -i AGENTS.md` on Linux).

This keeps generated project guidance current without replacing user-authored instructions. Instructions remain advisory to the agent.

---

## Safe Skill IDs

Skill IDs (folder names) must match `^[A-Za-z0-9][A-Za-z0-9._-]*$`. Names with spaces, slashes, or leading dots are discovered but flagged as unsafe and cannot be selected or added to the manifest.

---

## How It Works

```
┌─────────────────┐     ┌──────────────────────────┐     ┌─────────────────────┐
│   Library root  │     │   Project manifest       │     │   Generated skills    │
│ ~/.agents/skills│────▶│  .agents/skills.json     │────▶│   dir (agent-specific)│
│  SKILL.md files │     │   (selected skill IDs)   │     │   + AGENTS.md + marker│
└─────────────────┘     └──────────────────────────┘     └─────────────────────┘
                                                         │
                    ┌───────────────────────────────────┼──────────────────────┐
                    ▼                                   ▼                      ▼
            ┌─────────────┐                      ┌───────────┐         ┌──────────┐
            │   OpenCode  │                      │   Junie   │         │   Kilo   │
            │   (apply)   │                      │   launch  │         │  (apply) │
            │ permission  │                      │ --skill-location   permission rules
            │   .skill    │                      │   generated dir    in kilo.json
            └─────────────┘                      └───────────┘         └──────────┘
```

- **Discovery**: `discover_skills()` scans the library root, parses SKILL.md frontmatter, validates safe IDs, allow-lists symlinks (targets must resolve inside the library root), and caches results.
- **Manifest**: `.agents/skills.json` lists selected skill IDs; `init` detects technologies and recommends skills; `generate_agents_md()` safely refreshes only its marked `AGENTS.md` block.
- **Sync/build**: `sync` (and managed launches) apply the context budget (tech-match scoring + token/max-skill caps), then atomically build-then-swap the generated skills dir via `AdvisoryLock` (fcntl.flock, 10s timeout).
- **Adapter behavior**:
  - **OpenCode** — writes `permission.skill` rules into `opencode.json`; manager ownership is tracked in `.agents/opencode-owned-rules.json`, and tagged legacy rules are migrated with a backup.
  - **Junie** — launches with `--skill-default-locations=false --skill-location=<generated dir>`; additive library loading remains for unmanaged Junie.
  - **Kilo** — writes `permission.skill` rules to `.kilo/kilo.json` and copies only budget-filtered selected skills into `.kilo/skills/` because Kilo does not discover project links outside the worktree. Global skills remain in its catalog.
- **Context budget**: Only `selected` skills are eligible; they are scored (+5 tech match, +1 keyword overlap, +min(3) instruction overlap), sorted by score then dir_name, and truncated to `skill_context_budget_tokens` / `max_skills_in_context`. Excluded skills are reported as warnings; manifest selection is unchanged.

---

## Tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

Tests cover discovery, frontmatter parsing, identity/safe-ID validation, context-budget filtering, CLI flags, adapter config migration, crash recovery, generated-directory safety, resolution, and managed AGENTS.md behavior.

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
| `src/agent_skills/links.py` | Managed-directory marker reading and cleanup |
| `src/agent_skills/detection.py` | Technology marker scanning |
| `src/agent_skills/resolution.py` | Per-agent resolution states |
| `src/agent_skills/adapter_common.py` | Shared wrapper/build/budget helpers |
| `src/agent_skills/adapters/{junie,kilo,opencode}.py` | Agent-specific launchers |

Generated project directories are rebuilt atomically with a `.agent-skills-managed.json` marker and `AGENTS.md`. The OpenCode rules sidecar is stored in the project's `.agents/` directory.

---

## License

MIT

---

**No external dependencies.** Standard library only. No lint, typecheck, or formatter configured — verification is the test suite.
