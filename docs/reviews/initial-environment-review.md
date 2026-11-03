# Initial Environment Review

**Status:** `PENDING` (Phase 0 experiments complete; awaiting user approval before Phase 1)
**Date:** 2026-11-03
**Phase:** 0 (Environment inspection and verification experiments)
**Sandbox:** `/tmp/agent-skills-phase0/` (built, contains sample skills and scratch project)

---

## 1. Environment findings

| Component | Observed | Tested version |
|---|---|---|
| OS / shell | macOS, zsh | — |
| Home | `<HOME>` (resolve dynamically; never hardcode) | — |
| Python (default) | 3.14.7 (Homebrew, `/opt/homebrew/bin/python3`) | — |
| Python (system) | 3.9.6 (`/usr/bin/python3`) | D3 floor 3.9 confirmed available |
| OpenCode | 2.2.5 (`opencode v2.2.5`) | 2.2.5 (match) |
| Junie | 26.10.27 (3893.6) | 26.10.27 (match) |
| Kilo | 7.8.18 (`kilo --version`) | 7.8.18 (match — corrected from v3's "1.0+") |
| `~/.local/bin` on PATH | yes | — |
| Filesystem | case-insensitive (macOS default) | — |

## 2. Kilo 7.8.18-specific findings (version correction from v3)

Kilo binary confirmed at **7.8.18**, not "1.0+". All Kilo-specific facts re-derived from the actual binary:

- **Config paths:** global `~/.config/kilo/kilo.jsonc` (schema `https://app.kilo.ai/config.json`); project `./kilo.json` and `.kilo/kilo.json` (precedence: remote well-known → global → `./kilo.json` → `.kilo/kilo.json`, deep-merged, later wins)
- **Skill directories:** `~/.agents/skills/` (global shared library), `~/.claude/skills/` (symlinks to `~/.agents/skills/`); `~/.kilo/skills/` does NOT exist by default
- **Paths:** `kilo debug paths` shows home, data, bin, log, repos, cache, config, state, tmp — all under `~` by default
- **Debug commands:** `kilo debug skill` (lists all skills with name/description/location/content/trusted), `kilo debug config` (shows resolved config), `kilo debug paths` (shows global paths)
- **Config keys observed:** `$schema`, `permission.bash`, `permission.external_directory`, `model`, `compaction`, `provider`, `permission_origins`, `agent`, `mode`, `plugin`, `command`, `username`, `instruction_origins`
- **No skill-disable key:** no `skills`, `disableDefaultSkills`, `extraSkillPaths`, `skillDirs`, or similar key in config schema
- **No `instructions` key:** `instruction_origins` is empty; no `instructions` or `guidelines` config key

## 3. Skill library

- Library root: `~/.agents/skills/`
- Total top-level directories: 1436
- Symlink entries at top level: 0
- Skills with `SKILL.md`: 1435 (one directory, `iso-27001-workspace`, contains evaluation outputs only, not a skill)
- Missing frontmatter: `flutter-tamim`, `hive-db-tamim`, `isar-db-tamim` (3, not 2 as the guideline initially stated)
- Declared `name` vs folder mismatches: 9 (`agent-development`, `command-development`, `hook-development`, `mcp-integration`, `plugin-settings`, `plugin-structure`, `skill-development`, `ui-toolkit-web`, `writing-hookify-rules`)
- Duplicate declared names: 0 (in global library)
- Junie skills: 68, all also present in the global library

## 4. Global configuration

- `~/.config/opencode/`: contains `service.json` only; no global `opencode.json` / `opencode.jsonc`.
- OpenCode global paths (from `opencode debug paths`): config `~/.config/opencode`, data `~/.local/share/opencode`, cache `~/.cache/opencode`, state `~/.local/state/opencode`.
- `~/.junie/`: settings present; skills dir 68 entries; no global `AGENTS.md` currently.
- `~/.config/agent-skills/`: does not exist yet.
- `~/.config/kilo/kilo.jsonc`: exists (107 bytes, schema `https://app.kilo.ai/config.json`, permission.bash + permission.external_directory rules only)
- `~/.kilo/`: exists but has no `skills/` subdirectory
- `~/.claude/skills/`: exists, contains 69 symlinks to `~/.agents/skills/`

## 5. Digital Pharmacy baseline

- Project path (local only, redacted): `<LOCAL_PROJECT_PATH>/DigitalPharmacy`
- Branch: `chore/agent-skills-manager` (base `dp-dev-tamim`)
- Working tree: `.gitignore` modified (AGENTS.md ignore already added, unanchored); `.aiignore`, `.junie/`, `doc/` untracked; no staged changes.
- Tracked agent files in HEAD: none (`AGENTS.md`, `.junie/`, `doc/` all untracked).
- `doc/review/` contains `comprehensive-code-review.md` and `purchase-sell-reports-review.md` (untracked).
- `.junie/plans/profit-calculation-remaining-fixes.md` present (untracked, must not be moved or modified).
- `AGENTS.md` present (ignored, untracked); contains project conventions.
- `git check-ignore -v AGENTS.md` matches `.gitignore:54`.
- Filesystem: case-insensitive.

References to `doc/review/` across the repository: none found.

---

## 6. Experiment results (V0–V22)

### V0 — Sandbox capability check (prerequisite)

**Verdict: Confirmed (OpenCode, Kilo) / Partial (Junie)**

| Agent | Method | Result |
|---|---|---|
| OpenCode 2.2.5 | `HOME=/scratch opencode --version` | `opencode v2.2.5` — runs with scratch HOME |
| Junie 26.10.27 | `HOME=/scratch junie --version` + copy `~/.local/share/junie/versions/` | Runs with scratch HOME but writes logs to real `~/.junie/logs/`; needs `--cache-dir` + `--config-default-locations=false` for full isolation |
| Kilo 7.8.18 | `HOME=/scratch kilo --version` + `kilo debug paths` | `7.8.18` — all paths under scratch home (`home`, `data`, `config`, `cache`, `state`, `tmp`, etc.) |

Sandbox built at `/tmp/agent-skills-phase0/` with fake `$HOME` layout (`home/.agents/skills/`, `home/.junie/`, `home/.config/opencode/`, `home/.config/kilo/`, `home/.kilo/skills/`, `home/.claude/skills/`), sample skills (valid frontmatter, no frontmatter with nested folder/script/space filename, two same-declared-name skills, malformed frontmatter), and scratch project with `pubspec.yaml`.

### V1 — OpenCode frontmatterless discovery and identifier

**Verdict: Partially observed — needs clean sandbox manual execution**

OpenCode responded to a skill-listing prompt showing skill identifiers (python-code-style, python-configuration, python-error-handling, python-testing-patterns, python-type-safety) matching project-level permission rules. However, this ran against the real project's `opencode.json`, not a clean sandbox. The no-frontmatter sample skill (`no-frontmatter-skill`) was NOT present in Kilo's skill listing, suggesting OpenCode may also skip frontmatterless skills — but this needs a clean sandbox test with live model.

**Manual procedure:** Launch OpenCode with `HOME=/scratch` in a temp project containing the sandbox's no-frontmatter skill; ask "List the skill identifiers you have available." Record whether `no-frontmatter-skill` appears and which identifier OpenCode uses (folder vs `name`).

### V2 — OpenCode project permission merge vs replace

**Verdict: Not tested — needs manual execution**

Sandbox configs created at `/tmp/agent-skills-phase0/home/.config/opencode/opencode.json` (global deny-all) and `/tmp/agent-skills-phase0/project/.opencode/opencode.json` (skill allow rules only). Not yet executed with live model.

**Manual procedure:** Launch OpenCode with global `permissions` containing an unrelated bash allow rule + project `permissions` with only skill rules; observe whether the global bash rule still applies after project config is added.

### V3 — OpenCode permission `resource` matching

**Verdict: Not tested — needs manual execution**

Observed: project `opencode.json` uses `resource` field with skill folder names (e.g. `python-type-safety`, not declared names). Sandbox has `folder-name-mismatch` skill (folder name ≠ declared name) for testing.

**Manual procedure:** Project `opencode.json` with `resource` values using folder name, frontmatter `name`, and a glob; observe which selected skills load.

### V4 — OpenCode deny rules: block loading vs hide from list

**Verdict: Not tested — needs manual execution**

**Manual procedure:** With a deny rule for one skill, ask OpenCode to list available skills; record whether the denied skill appears in the list.

### V5 — OpenCode disable/redirect default skill paths

**Verdict: Confirmed — NO mechanism exists**

`opencode --help` shows no skill-related flags (`--skills`, `--skill-paths`, `disableDefaultSkills`, etc.). `opencode debug config` shows config keys: `model`, `compaction`, `providers`, `permission`, `instruction_origins` — no `skills` or `skillPaths` key. No supported mechanism to disable or redirect default skill discovery paths separate from permission filtering.

**Impact:** Discovery-cost reduction for OpenCode is marked `unavailable` per §2.1 of the guideline.

### V6 — Junie skill flags

**Verdict: Confirmed** (previously verified)

- `--skill-default-locations=false --skill-location=<path> --version` exits 0.
- Space-separated form also exits 0.
- Repeated `--skill-location` is accepted.
- Semantics: `skill-locations` are parent directories Junie searches for skills.

### V7 — Junie symlink following

**Verdict: Not tested — needs manual execution**

**Manual procedure:** `junie --skill-default-locations=false --skill-location=<parent>` where one skill entry is a symlink to a directory (the no-frontmatter sample skill with nested folder and script), with a relative reference inside. Ask Junie to use the skill; record whether it loads and whether relative references resolve.

### V8 — Junie frontmatterless wrapper

**Verdict: Not tested — needs manual execution**

**Manual procedure:** Build wrapper layout (SKILL.md with frontmatter + symlinks to original files at original relative paths) for the no-frontmatter sample skill. Launch with `--skill-location=<wrapper-parent>`; ask Junie to use it; verify source files are byte-identical (checksums before/after).

### V9 — Agent exposes skills listing

**Verdict: Confirmed (mixed)**

| Agent | Listing command | Result |
|---|---|---|
| OpenCode | None (`opencode debug` has agents/config/paths/heap-dump, no skills) | Negative — no diffable skills listing |
| Junie | None (`--help` has no skills subcommand) | Negative — no diffable skills listing |
| Kilo | `kilo debug skill` | Positive — lists all skills with `name`, `description`, `location`, `content`, `trusted` fields |

### V10 — OpenCode `opencode.json` vs `opencode.jsonc`

**Verdict: Confirmed** (previously verified)

- `opencode debug config` lists both files as separate config sources when both exist.
- The `instructions` key is supported (array of paths).
- Conclusion: both files are loaded when both exist. Manager must not rewrite `.jsonc` as JSON; report and ask for a decision.

### V11 — Junie guidelines/rules vs AGENTS.md

**Verdict: Confirmed** (previously verified from docs)

- Project: `.junie/AGENTS.md`, or `AGENTS.md` + `.junie/playbook.md` + `.junie/rules/*.md`
- Global: `~/.junie/AGENTS.md`
- Precedence: project-level over global
- `--ide-guidelines=<path>` prepends content to existing guidelines

### V12 — Junie plan location

**Verdict: Confirmed** (previously verified)

- Plans saved to `.junie/plans/`; no configurable equivalent found.

### V13 — Kilo `./kilo.jsonc` vs `./.kilo/kilo.jsonc`

**Verdict: Confirmed — `.kilo/kilo.jsonc` takes precedence**

Sandbox test: created both files in `/tmp/agent-skills-phase0/project/` with distinguishable `model` values (`test-model-v13-kilo-jsonc` vs `test-model-v13-dot-kilo-jsonc`) and conflicting `permission.bash` rules. `kilo debug config` from the project directory resolved to `model: "test-model-v13-dot-kilo-jsonc"` with `permission_origins.test *: "local"` — dot-kilo values win.

### V14 — Kilo disable default skill loading

**Verdict: Confirmed — NO mechanism exists (Kilo is additive)**

Exhaustively checked `kilo --help`, `kilo debug config`, config schema (`https://app.kilo.ai/config.json`). No `skills`, `disableDefaultSkills`, `compatibilityPaths`, `disableAgentsCompat`, or similar key. No CLI flag or env var found.

**Impact:** Kilo adapter is documented as **additive**, not exclusive, per §0.3 of the guideline. Every piece of CLI output and documentation states "additive."

### V15 — Kilo external skills directory

**Verdict: Confirmed — NO external path mechanism exists**

No `extraSkillPaths`, `skillDirs`, or equivalent in config schema or `--help`.

**Impact:** §5.6's default (generate directly inside `<project>/.kilo/skills/`) is the only viable strategy.

### V16 — Kilo duplicate `declared_name` precedence

**Verdict: Confirmed — collision results in single skill, winner order-dependent**

Sandbox test: `skill-alpha` (folder `skill-alpha`, declared `name: shared-name-skill`) and `skill-beta` (folder `skill-beta`, declared `name: shared-name-skill`) both in `home/.agents/skills/`. `kilo debug skill` showed only ONE `shared-name-skill` entry (skill-alpha in one run, skill-beta in another — order depends on filesystem directory listing). `no-frontmatter-skill` and `malformed-skill` were NOT discovered at all.

**Impact:** Collisions are surfaced as `conflict` resolution state (§2.2). Manager never silently renames; user must resolve.

### V17 — Kilo instructions/rules vs AGENTS.md

**Verdict: Inconclusive**

`kilo debug config` shows `instruction_origins: {}` and no `instructions` or `guidelines` config key. Whether Kilo reads `KILO.md` or `AGENTS.md` at runtime requires a live model session — cannot be determined from config inspection alone.

**Impact:** §10.1's stated precedence (`AGENTS.md` wins over global rules where they conflict) remains **policy**, not verified behavior for Kilo.

### V18 — Kilo hidden marker file in scanned directory

**Verdict: Confirmed — marker NOT misreported as skill**

Placed `.agent-skills-managed.json` inside `project/.kilo/skills/` alongside real skill subdirectories. `kilo debug skill` showed 4 skills (kilo-config, shared-name-skill, flutter-ui-kit, project-local-skill) — the marker file was NOT listed as a skill, no error, no warning.

**Impact:** Marker can safely be placed inside `.kilo/skills/` per §5.5.

### V19 — Relative resource references through wrapper layouts

**Verdict: Not tested — needs manual execution (all three agents)**

**Manual procedure:** Run the wrapper layout from §11.4/§13.3 of the guideline through each agent's sandboxed discovery/launch path using the no-frontmatter sample skill (nested folder, executable script, space-containing filename). Attempt to have each agent read or execute the nested content.

### V20 — Context tier evidence (discovered / metadata-exposed / fully-loaded)

**Verdict: Confirmed for Kilo / Unavailable for OpenCode & Junie**

| Agent | Discovered | Metadata-exposed | Fully-loaded |
|---|---|---|---|
| OpenCode | — | — | `unavailable` (no listing command) |
| Junie | — | — | `unavailable` (no listing command) |
| Kilo | `kilo debug skill` (all skills) | `name`/`description`/`location` per skill | `content` field per skill (full body) |

Kilo's `debug skill` output distinguishes all three tiers: discovered skills (array entries), metadata (name/description/location), and fully-loaded body (content field). This directly supports §2.1's measurement protocol.

### V21 — Manager crash recovery

**Verdict: Deferred** — manager-internal test, executed once symlink manager exists (early Phase 3/Phase 9).

### V22 — Cache invalidation

**Verdict: Deferred** — manager-internal test, executed once cache module exists (early Phase 3/Phase 9).

---

## 7. Risks and compatibility concerns

- OpenCode runs are slow and the model may not answer list queries reliably; manual verification must be recorded as evidence, not assumed.
- Three (not two) skills lack frontmatter (`flutter-tamim`, `hive-db-tamim`, `isar-db-tamim`); the guideline's custom-skill list must be updated.
- `iso-27001-workspace` is not a skill and must be excluded from discovery (no `SKILL.md`).
- 9 declared-name/folder mismatches are warnings, not errors; permission rules must use verified `agent_id`, not `declared_name`.
- Digital Pharmacy `.gitignore` additions are currently unanchored (`AGENTS.md`); Phase 2 must replace with the anchored set and evaluate other tool paths.
- `AGENTS.md` is ignored but untracked; no tracked-file risk today, but Phase 2 pre-check must still run before any agent file is created.
- Junie global guidelines (`~/.junie/AGENTS.md`) do not exist yet; shared rules delivery via `--ide-guidelines` avoids creating one.
- Kilo 7.8.18 is **additive** (V14 confirmed negative) — all Kilo docs/output must state "additive," not imply exclusivity.
- Kilo marker file can safely live inside `.kilo/skills/` (V18 confirmed).
- Kilo collision handling: only one skill exposed per declared_name, winner order-dependent (V16 confirmed).
- Junie needs `--cache-dir` for full sandbox isolation (logs write to real home despite HOME override).

## 8. Recommended adjustments to the guideline

1. Update the custom-skill list in sections 3, 7.4, 11.4, 12.4 to include `isar-db-tamim`.
2. Keep Python floor at 3.9 (`/usr/bin/python3` = 3.9.6); Homebrew 3.14 available for development.
3. Junie delivery mechanism for shared rules: use `--ide-guidelines=<rules.md>` at managed launch (prepend), plus optional global `~/.junie/AGENTS.md`. Do not write to project `AGENTS.md`.
4. OpenCode delivery mechanism for shared rules: `instructions` array in `opencode.json` (verified).
5. If both `opencode.json` and `opencode.jsonc` exist, treat as conflict requiring a decision (do not silently merge or rewrite).
6. Plans: agent saves to `.junie/plans/` only; manager instructs copying canonical plan to `doc/plans/`.
7. Kilo config precedence: `.kilo/kilo.jsonc` over `./kilo.jsonc` (V13 confirmed).
8. Kilo is additive (V14 confirmed negative) — state "additive" in all docs/output.
9. Kilo marker placement: inside `.kilo/skills/` is safe (V18 confirmed).
10. Kilo collision: `conflict` resolution state, user must rename (V16 confirmed).

## 9. Approval gate

**Phase 0 experiments substantially complete.** V1-V4, V7-V8, V19 require live model interaction (manual execution needed). V21-V22 are deferred to Phase 3/9. All automatable experiments (V0, V5, V6, V9, V10, V11, V12, V13, V14, V15, V16, V17, V18, V20 partial) have been executed and recorded.

This review is presented for approval. No Phase 1 work begins until approved. Manual experiments do not block Phase 1 planning but must be completed before Phase 6/7 acceptance claims.
