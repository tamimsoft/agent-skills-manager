# Global Agent Skill Manager
## Implementation Guideline for OpenCode and Junie (v2)

**Project:** Global Agent Skill Manager
**Platform:** macOS (zsh)
**Supported agents:** OpenCode CLI 2.2.5, Junie CLI 26.10.27 (tested versions; see 4.6)
**Implementation language:** Python 3, standard library only
**Shared skill library:** `~/.agents/skills/`
**First integration target:** Digital Pharmacy (Flutter)
**Digital Pharmacy branch:** `chore/agent-skills-manager` (base: `dp-dev-tamim`)
**Document status:** `AWAITING_APPROVAL`

---

# 0. Revision Notes (v1 -> v2)

This version resolves contradictions and gaps found in review of v1. Main changes:

1. Added **Phase 0 verification experiments**. Every behavior of OpenCode or Junie that the design depends on is now tested before it is relied upon.
2. **Git protection moved before project integration**, and a "already tracked?" check is mandatory first.
3. **Manager source now has its own repository.** Digital Pharmacy receives only integration artifacts.
4. Introduced an explicit **identifier model** (directory name vs frontmatter name vs per-agent identifier).
5. Defined a **custom-skill strategy** that does not conflict with "do not modify" and "no duplicate identifiers".
6. Added a **delivery mechanism for shared rules**.
7. Defined **project root**, **ownership markers**, **atomic generation**, **locking**, and **path-hash keying**.
8. Fixed **technology detection** so Flutter's `android/` folder is not reported as a separate Android/Java project.
9. Added CLI semantics (`--dry-run`, `--json`, `--yes`, non-TTY behavior) and missing commands (`sync`, `doctor`, `clean`).
10. Added **test isolation**, performance budgets, and a manual verification procedure where automation is impossible.
11. Phase 0 no longer contradicts itself (see 6).

---

# 1. Open Decisions (confirm before Phase 1)

Each decision has a recommended default. If you do not override a default, it is used, and the choice is recorded in the plan.

| ID | Decision | Recommended default | Why |
|---|---|---|---|
| D1 | Custom skills (`flutter-tamim`, `hive-db-tamim`) lack frontmatter. How to expose them? | Store **user-authored** `name` and `description` overrides in manager config. Junie: generate a wrapper directory (generated `SKILL.md` + symlinks to original files). OpenCode: decided by experiment V1; if OpenCode skips them, they are reported as `unavailable-in-opencode` and left unfiltered-by-design, never auto-fixed. | Keeps originals untouched, avoids fabricated descriptions, avoids duplicate identifiers in OpenCode (which scans the shared library itself). |
| D2 | Where does manager source live? | Separate Git repository (for example `~/Projects/agent-skills-manager`), installed to `~/.local/` by an install script. | `~/.local/lib` is not a repo. Manager code, tests, plans, reviews need a tracked home. |
| D3 | Minimum Python version | 3.9 (macOS system Python), no newer syntax (`X | Y` types, `match`). Verified in Phase 0. | Avoids a Homebrew dependency. If Phase 0 shows a newer Python is standard on this machine, raise the floor. |
| D4 | Ignore mechanism in projects | `.gitignore` (team-wide protection), with anchored patterns. | `.git/info/exclude` is not shared and does not protect teammates. Editing `.gitignore` creates a tracked change that must be committed with approval. |

---

# 2. Project Objective

Build a reusable global skill management system so OpenCode and Junie use the same centralized skill library while loading only the skills relevant to each project.

The system must:

1. Maintain one centralized skill library.
2. Discover available skills automatically.
3. Recommend skills from project technologies (deterministic, offline, explainable).
4. Let users select skills per project, always with explicit confirmation.
5. Integrate with OpenCode and Junie through independent adapters.
6. Never duplicate or modify original skill content.
7. Apply consistent engineering rules to both agents (delivery mechanism defined in Phase 4).
8. Keep AI and agent configuration out of Git.
9. Keep engineering plans and reviews in Git.
10. Provide reliable validation, error handling, and diagnostics.

**Do not build a Digital Pharmacy-specific solution.** Digital Pharmacy is the first validation target. The manager must work for Flutter, Java, .NET, Laravel, React, Android, and other projects.

**Known asymmetry (must be documented to users):** Junie is restricted only when launched through `agent-skills junie`; running plain `junie` still loads everything. OpenCode is restricted on every run through the project `opencode.json`. Document this and recommend a shell alias if the user wants managed launch to be the default.

---

# 3. Existing Environment (to verify, not assume)

| Component | Expected configuration |
|---|---|
| OS / shell | macOS, zsh |
| Home | `/Users/tamimhasan` (resolve dynamically in code; never hardcode) |
| OpenCode | 2.2.5 |
| Junie | 26.10.27 |
| Python | Verify version (see D3) |
| Shared skills | `~/.agents/skills/` |
| Junie skills | `~/.junie/skills/` |
| OpenCode config | `~/.config/opencode/` |

Reported inventory (re-verify in Phase 0):

- About 1,435 global skills; 68 Junie skills, all also present in the global library.
- Folder names: no duplicates found. **Frontmatter `name` duplicates were never checked and must be.**
- OpenCode discovers skills from `~/.agents/skills/`.

Custom skills requiring special handling: `flutter-tamim`, `hive-db-tamim`. Their missing frontmatter is intentional. Their files and directory structure must remain byte-identical. Never inject generated frontmatter into them.

Note: disabling default locations for Junie also removes the 68 skills in `~/.junie/skills/` from managed launches. This is intended and must be documented.

---

# 4. Non-Negotiable Engineering Rules

## 4.1 Requirement analysis (per phase)

1. Understand the phase requirements.
2. Inspect the existing implementation.
3. Identify missing requirements and loopholes.
4. Challenge incorrect assumptions.
5. Identify security, compatibility, and performance risks.
6. Present the phase plan.
7. **Approval gate:** every phase ends its planning step with an explicit approval request. No file is modified before approval of that phase's plan. (v1's "if a new material decision" condition was subjective and is removed.)

In non-interactive runs (no TTY, scheduled, or headless), an agent must stop at the gate and write the pending plan to disk; it must never self-approve.

## 4.2 Existing files and user data

- Never overwrite an existing file without inspecting it.
- Never modify original shared skill files.
- Never delete existing skills.
- Never replace agent configuration without preserving unrelated settings.
- Never discard uncommitted changes.
- Never use destructive Git commands.
- Never silently untrack files.
- Never print secrets, API keys, tokens, or private config values in logs, reports, or tracked documents.

## 4.3 Implementation discipline

- Implement only approved scope; follow existing conventions.
- Clear names, small testable modules, no unnecessary dependencies.
- No unrelated refactoring.
- Stop and ask when implementation-critical information is missing.

## 4.4 Git policy

Never commit without explicit authorization. When authorized:

1. Inspect staged files.
2. Identify unrelated changes.
3. Prepare a Conventional Commit message.
4. Present the exact message.
5. Wait for approval of that exact message.
6. Commit only after approval.

No AI or agent configuration may be committed. Plans and reviews must be tracked.

## 4.5 Tracked-document hygiene

Documents under `doc/plans/` and `doc/reviews/` are committed. Before writing them:

- Redact absolute home paths (use `~` or `<HOME>`), usernames, tokens, and config values.
- Record versions and counts, not private configuration contents.

## 4.6 Version policy

The manager records the tested agent versions (OpenCode 2.2.5, Junie 26.10.27). At runtime it compares installed versions and **warns** (not fails) on mismatch, with a note that behavior is unverified.

---

# 5. Target Architecture

## 5.1 Repositories and install layout

**Manager source repository (D2)**

```text
agent-skills-manager/
├── pyproject.toml            # metadata only; no runtime dependencies
├── install.sh                # idempotent install/upgrade; see Phase 8
├── src/agent_skills/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py                # argument parsing, output formatting only
│   ├── config.py             # global config load/validate/migrate
│   ├── discovery.py          # scan library, build skill records (incl. metadata parse)
│   ├── frontmatter.py        # restricted YAML-subset parser
│   ├── identity.py           # identifier model (see 5.3)
│   ├── detection.py          # technology detection
│   ├── recommend.py          # scoring and recommendations
│   ├── manifest.py           # project manifest load/validate/migrate
│   ├── project.py            # project root resolution
│   ├── links.py              # symlink manager, ownership markers, atomic refresh
│   ├── lock.py               # advisory locking
│   ├── validation.py         # cross-component validation and doctor checks
│   ├── cache.py              # mtime-keyed discovery cache
│   └── adapters/
│       ├── base.py
│       ├── junie.py
│       └── opencode.py
├── tests/
│   ├── fixtures/
│   └── ...
└── doc/
    ├── plans/
    └── reviews/
```

**Installed layout (outside any repo)**

```text
~/.local/bin/agent-skills                   # thin launcher script
~/.local/lib/agent-skills/                  # installed copy or link of src/agent_skills
~/.local/share/agent-skills/projects/<key>/ # generated per-project artifacts
~/.config/agent-skills/config.json
~/.config/agent-skills/rules.md
```

Rules for the structure:

- `agent_skills` is a real Python package (a directory named `agent-skills` is not importable).
- The launcher sets `sys.path` or uses `python3 -m agent_skills`. The mechanism is fixed in Phase 1.
- `~/.local/bin` must be on `PATH`; `doctor` checks this and prints the exact `~/.zshrc` line if missing (it does not edit `~/.zshrc`).
- `templates/` and "default project configuration" from v1 are **removed** unless a phase gives them a concrete purpose. They must never be used to generate or replace `AGENTS.md`.

**Digital Pharmacy receives only:** `.agents/skills.json`, `opencode.json` (local-only), `doc/plans/`, `doc/reviews/`, and `.gitignore` additions.

## 5.2 Responsibilities

| Component | Responsibility |
|---|---|
| Discovery | Scan library, produce skill records |
| Frontmatter | Parse the supported YAML subset |
| Identity | Map directory name, frontmatter name, per-agent identifiers |
| Detection | Identify technologies and frameworks |
| Recommend | Score and explain recommendations |
| Manifest | Project selections and schema migration |
| Project | Resolve project root |
| Links | Create, verify, and remove managed symlinks safely |
| Lock | Prevent concurrent writes to generated state |
| Validation | Verify configs, references, and generated state |
| Adapters | Agent-specific configuration and launch |
| CLI | Unified user interface; no business logic |

Business logic must not depend on adapters. Adapters depend on core modules, never the reverse.

## 5.3 Identifier model

v1 conflated directory names and skill identifiers. Define three distinct values per skill record:

| Field | Meaning |
|---|---|
| `dir_name` | Folder name inside the library. Used in the manifest as the stable reference. |
| `declared_name` | Frontmatter `name` if present, else `null`. |
| `agent_id[agent]` | The identifier a specific agent uses (for permissions or discovery). Derived per agent from verified behavior (V1, V3). |

Rules:

- The manifest stores `dir_name`.
- OpenCode permission `resource` values use `agent_id["opencode"]`, never assumed to equal `dir_name`.
- `validate` reports: duplicate `declared_name` across different directories, `declared_name != dir_name` (warning), and any collision of `agent_id` within one agent.
- Skills where the agent identifier cannot be determined are marked `unresolved` and cannot be selected for that agent until resolved.

## 5.4 Symlink and path policy

Entries in the library may themselves be symlinks (installed by tooling). v1's "reject links outside the library" would reject legitimate setups. New policy:

1. Resolve every source with `realpath`.
2. The real path must be inside an **allow-list of roots** (default: the library root's real path, plus any roots explicitly listed in `config.json`).
3. Reject path traversal (`..`, absolute-path injection in IDs), names with path separators, NUL, or leading `.`.
4. Skill IDs accepted by the CLI must match `^[A-Za-z0-9][A-Za-z0-9._-]*$` (unicode and spaces in on-disk names are reported and handled, but cannot be selected by CLI ID until a safe form is defined; report clearly).
5. Detect case-insensitive collisions (macOS default filesystem).
6. Never overwrite a path the manager does not own.

## 5.5 Ownership of generated artifacts

- Every generated directory contains `.agent-skills-managed.json` with: manager version, schema version, project key, creation time, list of managed entries.
- The manager removes only entries listed in that marker whose current target still matches what it created.
- For `opencode.json`, JSON has no comments, so manager-owned permission rules are tracked in a **sidecar record** (`<generated-dir>/opencode-owned-rules.json`) holding the exact rule objects the manager added. Only those exact rules are modified or removed.
- If `opencode.jsonc` exists, the manager must not rewrite it as JSON (comments would be lost). It reports the situation and asks for a decision (Phase 3).

## 5.6 Generated directory keying and refresh

- Key: `<sanitized-project-name>-<first 12 hex of sha256(realpath(project_root))>`. Name alone collides.
- Refresh is **atomic**: build in a sibling temp directory, verify, then rename into place. Never leave a half-built directory visible.
- Concurrency: acquire an advisory lock (`fcntl.flock` on a lock file) around any write. A second writer waits briefly, then fails with a clear message.
- `clean` removes generated directories for projects whose root no longer exists (with confirmation and `--dry-run`).

## 5.7 Project root

Resolution order:

1. Nearest ancestor directory (starting at the current directory) containing `.agents/skills.json`.
2. Otherwise, the Git top-level directory (`git rev-parse --show-toplevel`), for `init` only.
3. Otherwise, fail with a clear message (no silent fallback to the current directory).

Define behavior for Git worktrees (each worktree is its own root, with its own manifest) and monorepos (the manifest at the nearest ancestor wins; nested manifests are allowed). The manifest does not store `root`.

---

# 6. Phase 0: Environment Inspection and Verification Experiments

**Objective:** Establish a safe baseline and replace every assumption with a verified fact.

## 6.1 Constraint reconciliation

v1 said "do not modify anything" but required a new file in `doc/reviews/`. Resolution:

- Inspection is read-only with respect to the project, agent configs, and skill library.
- The Phase 0 review is first written **outside any repository** (for example `~/agent-skills-phase0/initial-environment-review.md`), then, after redaction (4.5) and your approval, copied to `doc/reviews/` in the manager repo.
- Experiments run only in a **scratch sandbox** (temporary `HOME`-like directories and copies/symlinks of a few sample skills), never against the real library or real configs.

## 6.2 Inspection tasks

1. Verify Python version and `python3` availability; list other installed Pythons.
2. Verify OpenCode and Junie versions; read their `--help` output.
3. Inspect the skill library: count, symlink entries, frontmatter presence, duplicate `name` values (not only folder names).
4. Inspect global configs (without printing secret values).
5. Check `PATH` for `~/.local/bin`.
6. Inspect Digital Pharmacy: branch, `git status --short --branch`, tracked agent files (`git ls-files` filtered for `AGENTS.md`, `.aiignore`, `.agents`, `.junie`, `opencode.json`, `.opencode`), existing `.gitignore`.
7. Identify existing engineering documents and references to `doc/review/` (grep) so the later migration cannot break links.
8. Check filesystem case sensitivity.

Required commands (read-only):

```bash
python3 --version
opencode --version
junie --version
git status --short --branch
git branch --show-current
git ls-files
git check-ignore -v AGENTS.md .agents/skills.json opencode.json
```

## 6.3 Verification experiments

Each experiment records: question, method, result, conclusion, and how the design depends on it. Where an experiment cannot be automated (for example it needs a model call), record the manual procedure instead.

| ID | Question | Design impact |
|---|---|---|
| V1 | Does OpenCode 2.2.5 discover and advertise a skill with no frontmatter? Which fields does it require? What is its identifier (folder or `name`)? | D1, identifier model, permission rules |
| V2 | Does a project-level `permissions` array in `opencode.json` **replace** or **merge/concatenate** with the global config? Is "last matching rule wins" confirmed with a deny-all then allow list? | Phase 3 merge strategy |
| V3 | What does the permission `resource` match: folder name, frontmatter `name`, or both? Are glob patterns supported? | Permission generator |
| V4 | Do deny rules only block loading, or also hide the skill from the advertised list? What does the model actually see? | Accuracy of "unselected skills are unavailable" |
| V5 | Does OpenCode support disabling or redirecting default skill discovery paths (supported isolation mechanism)? | Performance, 9.5 |
| V6 | Junie: exact syntax of `--skill-default-locations` and `--skill-location`. Does `--skill-location` take a parent directory of skills or individual skill directories? Can it repeat? Behavior if the flag is passed twice? | Junie launch design |
| V7 | Junie: does it follow symlinked skill directories? Do relative references inside skills (`../shared`, scripts) resolve? Are nested directories discovered? | Symlink design, 7.4 |
| V8 | Junie: how are skills without frontmatter treated? Does a generated wrapper `SKILL.md` work, and does the symlinked rest of the folder resolve? | D1 wrapper design |
| V9 | Do either agent expose a command or debug output that lists loaded skills? | Whether integration tests can be automated (see 13.4) |
| V10 | Does OpenCode read `opencode.jsonc` if both files exist? Which wins? Does it have an `instructions` (or equivalent) setting, and how do relative/global paths behave? | Phase 3 and rules delivery |
| V11 | Junie: where does it read guidelines or rules from (project and global), and what is the precedence versus the project `AGENTS.md`? | Phase 4 delivery |
| V12 | Does Junie's plan-saving location (`.junie/plans/`) have a configurable equivalent so plans can map to `doc/plans/`? | Plan mapping decision (Phase 5) |

If a result contradicts a design assumption, **stop and present the impact** before Phase 1.

## 6.4 Deliverable

`initial-environment-review.md` (redacted copy under the manager repo's `doc/reviews/` after approval), containing: environment findings, existing configurations, Git baseline, experiment results (V1 to V12), compatibility concerns, risks, outstanding questions, and recommended adjustments to this guideline.

**Approval gate:** present the review and any guideline adjustments before Phase 1.

---

# 7. Phase 1: Manager Repository, Configuration, and Discovery

**Objective:** Create the manager foundation with safe, fast discovery.

## 7.1 Repository setup

- Create the manager repository (D2) with an initial plan in `doc/plans/` (status `AWAITING_APPROVAL`).
- Do not install anything to `~/.local/` until the install script is reviewed (Phase 8 covers the full installer; Phase 1 may use a development launcher).

## 7.2 Global configuration

`~/.config/agent-skills/config.json` (JSON, schema versioned). Fields:

| Field | Purpose |
|---|---|
| `schema_version` | Integer; migration support |
| `manager_version` | Written by the manager |
| `library_root` | Shared skill library (default `~/.agents/skills`) |
| `allowed_roots` | Extra real-path roots for symlink allow-list |
| `generated_root` | Default `~/.local/share/agent-skills/projects` |
| `rules_path` | Default `~/.config/agent-skills/rules.md` |
| `agent_paths` | Optional executable overrides |
| `skill_overrides` | **User-authored** metadata for skills lacking frontmatter (see 7.4) |
| `tested_agent_versions` | For the version warning |

Rules: resolve paths dynamically (`Path.home()`, `expanduser`); validate on load; unknown keys are preserved on write; environment overrides `AGENT_SKILLS_HOME` or `AGENT_SKILLS_CONFIG` exist for tests; the config file is never rewritten without a backup of the previous version.

## 7.3 Skill discovery

Scan `library_root` for directories containing `SKILL.md`. For each skill record:

- `dir_name`, real source path, whether the entry is a symlink
- `declared_name`, `description` (from frontmatter), `frontmatter_status` (`valid`, `missing`, `malformed`, `partial`)
- `agent_id` resolution status per agent
- compatibility status and validation warnings

Performance and robustness:

- Use an **mtime-keyed cache** (stored under the generated root or a cache directory) so commands do not re-parse about 1,435 skills each run. Invalidate by `SKILL.md` mtime and size; `--no-cache` bypasses it.
- Read only `SKILL.md` frontmatter (bounded read, for example the first 64 KB) during discovery.
- Handle unreadable files, invalid UTF-8, empty library, and a missing library root with clear errors.
- Performance budget: cold discovery of about 1,500 skills should finish within a target set in Phase 0 after measuring (record the measured baseline; the acceptance check fails if a later phase regresses it by more than the agreed margin). Warm (cached) discovery should be near-instant.
- Never modify source files.

## 7.4 Custom skills

- `flutter-tamim` and `hive-db-tamim` are discovered normally with `frontmatter_status = missing`; this is **not an error** and must not block discovery or validation.
- Descriptions for internal recommendation purposes come from **user-authored `skill_overrides`** in config, not generated by the manager. If no override exists, the skill is still listed and selectable, with no description.
- The manager may offer to **extract** a candidate description from the skill content and show it to you for approval before saving it to config. It never writes to the skill's own files.
- If an agent requires metadata, use the D1 strategy: generated wrapper (Junie), V1-determined behavior (OpenCode). Do not claim availability until verified through the agent.

## 7.5 Frontmatter parser

No stdlib YAML parser exists. Define and document a **supported subset**: `key: value` scalars, quoted strings, `>` and `|` block scalars, values containing colons, comments. Constructs outside the subset produce a **warning** (`unsupported-yaml`), not a hard error, and the skill remains discoverable.

## 7.6 Metadata validation

For all skills: YAML syntax, presence and non-emptiness of `name` and `description`, duplicate `declared_name` across directories, duplicate or colliding identifiers, missing `SKILL.md`, unexpected directory layouts. Report problems clearly with severity (`error`, `warning`, `info`). Never repair original files.

## 7.7 Deliverables

Config module and schema, discovery with cache, frontmatter parser, identity module, unit tests with fixtures, a `list` command, an updated plan document. **Approval gate** before Phase 2.

---

# 8. Phase 2: Git Protection in Digital Pharmacy

**Objective:** Make sure agent files can never enter Git **before** any agent file is created in the project. (Moved earlier than v1's Phase 6.)

## 8.1 Pre-check (mandatory, read-only)

```bash
git ls-files AGENTS.md AGENTS.override.md CLAUDE.md GEMINI.md .aiignore \
  .agents .junie .opencode .claude opencode.json opencode.jsonc
git status --short --branch
git check-ignore -v AGENTS.md .agents/skills.json opencode.json
```

Ignoring a path does nothing if it is already tracked. If any of these files are tracked (`AGENTS.md` very likely is), **stop and report**. Changing tracking status (`git rm --cached`) requires explicit approval, a plan, and a note that the file stays on disk. Never run it silently.

## 8.2 Ignore rules (D4: `.gitignore`)

Use **anchored** patterns so nested files in other directories are not swallowed:

```gitignore
# Local-only AI and agent configuration
/AGENTS.md
/AGENTS.override.md
/CLAUDE.md
/GEMINI.md
/.aiignore
/opencode.json
/opencode.jsonc
/.agents/
/.junie/
/.opencode/
/.claude/
```

Evaluate other tool-specific paths (for example Cursor, Copilot) before adding them; do not add broad patterns that could hide application files. Never ignore `doc/`.

If `.gitignore` is the chosen mechanism, the edit is a tracked change that needs a commit (with approval per 4.4).

## 8.3 Verification

```bash
git status --short --branch
git check-ignore -v AGENTS.md
git check-ignore -v .agents/skills.json
git check-ignore -v opencode.json
git check-ignore -v doc/plans/example.md   # must produce no ignore match
git ls-files doc/plans doc/reviews
```

Confirm: agent config ignored, engineering docs not ignored, no unrelated change, existing user changes intact.

**Approval gate** before Phase 3.

---

# 9. Phase 3: Manifest, Detection, Selection, Symlinks

## 9.1 CLI contract

Global behaviors for every command:

- `--dry-run` on every mutating command: shows exactly what would change, changes nothing.
- `--json` for machine-readable output on read commands.
- `--yes` to accept confirmations; **without a TTY and without `--yes`, any command needing confirmation fails safely** (exit non-zero, no changes).
- Stable exit codes: `0` success, `1` general error, `2` usage error, `3` validation failure, `4` conflict requiring a decision.
- Mutating commands take the lock (5.6).

| Command | Behavior |
|---|---|
| `agent-skills init` | Create `.agents/skills.json` with an **empty** selection; show detected technologies and recommendations; require confirmation to add any skill. |
| `agent-skills list` | List library skills. Options: `--selected`, `--filter <text>`, `--tech <name>`, `--json`. |
| `agent-skills add <skill>...` | Add skills by `dir_name`; reject unknown or invalid IDs and duplicates. |
| `agent-skills remove <skill>...` | Remove from the manifest and from generated state (managed entries only). |
| `agent-skills detect` | Show technologies, frameworks, and the evidence for each. |
| `agent-skills recommend` | Show scored recommendations with reasons; never selects. |
| `agent-skills validate` | Validate config, manifest, library references, generated state. Read-only. |
| `agent-skills sync` | Regenerate project-generated state from the manifest. |
| `agent-skills doctor` | Environment checks: Python, PATH, agent versions, library health, lock state. Read-only. |
| `agent-skills clean` | Remove orphaned generated directories (confirmation, `--dry-run`). |
| `agent-skills junie [--prepare] [-- <args>]` | See Phase 5. |
| `agent-skills opencode <subcommand>` | See Phase 6. Subcommands separate preparation from validation so no invocation writes files unexpectedly. |

An empty selection is valid. Adapters must handle it explicitly (see Phases 5 and 6).

## 9.2 Project manifest

`<project>/.agents/skills.json`. Finalize the schema in the plan; baseline:

```json
{
  "schema_version": 1,
  "project": {
    "name": "DigitalPharmacy"
  },
  "skills": {
    "selected": ["flutter-tamim", "hive-db-tamim"]
  },
  "agents": {
    "junie": { "enabled": true },
    "opencode": { "enabled": true }
  }
}
```

Changes from v1:

- No `root` field (the project root is where the file lives).
- **No stored `technologies` list**: detection runs at runtime. If stored at all, it is an informational snapshot that never affects behavior.
- `selected` holds `dir_name` values only.

Validation rules:

- Valid JSON, known `schema_version` (older versions migrate through registered migration functions, with a backup; newer versions are rejected with a clear message).
- IDs match the safe pattern (5.4); unknown IDs rejected; duplicates rejected.
- **Severity split:** malformed manifest, invalid schema, or invalid ID = hard error (blocks launch). A selected skill that **disappeared from the library** = hard error for that skill's launch use but reported with the specific skill and remediation (`remove` or restore). A library change that only alters a skill's description or content = no error.
- Optional: record a content hash per selected skill and warn (not fail) when it changes silently.
- Never add skills merely because a technology was detected.

## 9.3 Technology detection

Use marker files at the project root, with bounded-depth scanning for monorepos (default depth 2, configurable). Always skip `node_modules`, `build`, `.dart_tool`, `.gradle`, `Pods`, `vendor`, `.git`.

| Technology | Evidence |
|---|---|
| Flutter / Dart | `pubspec.yaml` (Flutter if it depends on the `flutter` SDK) |
| Java / Maven | `pom.xml` (Spring Boot if it references `spring-boot`) |
| Java / Gradle | `build.gradle`, `build.gradle.kts` (Spring Boot from plugin or dependency) |
| .NET | `*.csproj`, `*.sln`, `*.slnx` |
| Laravel / PHP | `composer.json` containing `laravel/framework`; `artisan` as supporting evidence |
| React | `package.json` with `react` in dependencies |
| Android (native) | `settings.gradle(.kts)` **not** nested inside a detected Flutter project |

Rules:

- **A Flutter project's `android/` and `ios/` folders are platform folders, not separate projects.** If `pubspec.yaml` with Flutter is at the root, do not report Android or Java/Gradle from `android/`.
- A `package.json` is not React unless dependencies show it; classify other frameworks from dependencies (Vue, Angular, Next, and so on) or report `node`.
- Each result carries **evidence** (file and reason). Detection is extensible through a registry of detector functions.

## 9.4 Recommendations

Deterministic, offline, explainable:

- Score from: detected technologies and frameworks, keyword matches against skill `dir_name`, `declared_name`, `description` (and optional user override), and existing project instructions where readable.
- Output: capped list (default top 20), each with score and reasons; `--all` to widen.
- Recommendations never select; selection always requires confirmation (`add`, or interactive confirmation in `init`).

## 9.5 Symlink manager

Implements 5.4 to 5.6:

- Verify sources by real path against the allow-list; reject traversal and unsafe names.
- Detect broken links and name collisions (including case-insensitive).
- Never overwrite unrelated files; remove only managed entries (marker file).
- Atomic refresh and locking.
- Keep generated files separate from original skill sources.

## 9.6 Deliverables

Manifest, detection, recommendations, symlink manager, unit tests (see 13), updated plan. **Approval gate** before Phase 4.

---

# 10. Phase 4: Shared Engineering Rules and Delivery

**Objective:** Make OpenCode and Junie follow the same engineering workflow, with a real mechanism that causes each agent to read the rules.

v1 created `rules.md` but nothing made either agent read it, and it forbade modifying `AGENTS.md`. Fix:

## 10.1 Delivery mechanism (finalize from V10 and V11)

For each agent, document and implement one verified mechanism, for example:

- **OpenCode:** an `instructions` entry in the project `opencode.json` that points at `~/.config/agent-skills/rules.md` (if V10 confirms support and path handling).
- **Junie:** its supported guidelines/rules location, or a launch-time option if V11 shows one. If Junie can only read in-project files, generate a local-only file inside the ignored `.junie/` area that references or includes the rules, never touching `AGENTS.md`.

Define precedence: **the project `AGENTS.md` wins over global rules** where they conflict, and `rules.md` states this. The manager never edits `AGENTS.md`.

## 10.2 Contents of `rules.md`

Project-independent. Sections:

1. **Requirement analysis:** understand the request; identify missing requirements; clarify APIs, business rules, naming, dependencies, architecture; identify edge cases; challenge incorrect assumptions; recommend the most appropriate approach; never guess implementation-critical information.
2. **Mandatory implementation planning** (every feature and bug fix): scope, exact files and directories, dependencies and config changes, error handling, validation, security, edge cases, performance, breaking changes, testing strategy, assumptions. Wait for approval before modifying files.
3. **Architecture:** preserve existing architecture and conventions. For Clean Architecture projects respect Domain, Application, Infrastructure, Persistence, API/presentation separation. Do not impose Clean Architecture on projects that do not use it.
4. **Bug-fixing workflow:** inspect implementation, reproduce or verify, find root cause, inspect related components, identify regressions, write a concise review document, prepare the fix plan, obtain approval, implement, test and review. Never fix symptoms without root-cause investigation.
5. **Plans** in `doc/plans/` and **reviews** in `doc/reviews/` (formats in 10.3).
6. **Final review** checklist (10.4).
7. **Git conventions** (10.5).
8. **Safety:** no secrets in docs, no destructive Git commands, no untracking without approval.

## 10.3 Plan and review formats

**Naming:** `doc/plans/YYYY-MM-DD-<slug>.md` and `doc/reviews/YYYY-MM-DD-<slug>.md`. Each file begins with a metadata block (title, date, status, owner).

**Plan template sections:** Objective, Scope, Requirements, Architecture, Phases, Tasks, Validation, Risks, Approval Status, Completion Summary.
**Plan statuses:** `DRAFT`, `AWAITING_APPROVAL`, `APPROVED`, `IN_PROGRESS`, `BLOCKED`, `COMPLETED`, `CANCELLED`. Update the plan after each phase.

**Review template sections:** Review Scope, Files Inspected, Findings, Severity, Evidence, Risks, Recommendations, Verification Results.
**Review statuses:** `PENDING`, `IN_PROGRESS`, `FINDINGS_IDENTIFIED`, `REMEDIATION_IN_PROGRESS`, `VERIFICATION_PENDING`, `VERIFIED`, `ACCEPTED_RISK`, `BLOCKED`.
Do not mark a finding `VERIFIED` without implementation or test evidence.

**Plan location mapping:** Junie's local `.junie/plans/` is not tracked. Per V12, decide whether Junie can save plans to `doc/plans/`. If not, rules instruct the agent to **copy the approved canonical plan** to `doc/plans/` and keep `.junie/plans/` as working material only. The existing `.junie/plans/profit-calculation-remaining-fixes.md` is never moved or rewritten.

The **final acceptance report** is stored at `doc/reviews/YYYY-MM-DD-final-acceptance-review.md` in the manager repo.

## 10.4 Final review checklist (in rules)

Review all changed files; verify requirements; run relevant tests; check security, error handling, edge cases, performance (where applicable); check for unrelated modifications; update the plan and review; present outstanding risks.

## 10.5 Git conventions (in rules)

`<type>(<scope>): <description>`, types: feat, fix, refactor, perf, test, docs, build, ci, chore, style, revert. Imperative, lowercase subject, no trailing period. Never commit without approval; after authorization, propose the exact message and wait for approval.

**Approval gate** before Phase 5.

---

# 11. Phase 5: Junie Adapter

**Objective:** When launched through the manager, Junie sees only the project's selected skills.

## 11.1 Verified inputs

Finalize syntax from V6, V7, V8. The expected form, subject to verification:

```bash
junie --skill-default-locations false --skill-location "<generated-project-skill-directory>"
```

## 11.2 Behavior of `agent-skills junie`

1. Resolve the project root (5.7).
2. Load and validate the manifest. **If invalid, do not launch.**
3. Validate selected skills against the library.
4. Acquire the lock; generate or atomically refresh the generated skills directory (symlinks to originals; wrappers only for skills handled by D1).
5. Validate the generated directory (links resolve, markers present).
6. Launch Junie via `os.execvp` with an **argv list** (never through a shell), disabling default locations and passing only the generated directory. Signals and exit codes pass through.

Options and edge cases:

- `--prepare` generates and validates without launching.
- Extra arguments after `--` pass through to Junie.
- If the user supplies `--skill-location` or `--skill-default-locations` themselves, **refuse with an explanation** (they would defeat the managed policy) unless a documented override flag exists.
- Empty selection: launch with an empty generated directory and default locations disabled, and print a notice. (Never fall back to loading all skills.)
- If Junie is missing or the version differs from the tested one: error (missing) or warning (version).

## 11.3 Preservation

Never modify `~/.junie/settings.json`, `~/.junie/models/`, `~/.junie/skills/`, or existing project `.junie/` files. Never delete existing Junie skills. Document that managed launches also exclude `~/.junie/skills/`.

## 11.4 Custom skills

Implement the D1 wrapper for Junie if V8 requires it. Verify both custom skills load, with source files byte-identical (checksum before and after).

## 11.5 Limitations documentation

Document anything V6 to V8 revealed, plus the asymmetry from section 2.

**Approval gate** before Phase 6.

---

# 12. Phase 6: OpenCode Adapter

**Objective:** Restrict OpenCode to the project's selected skills.

## 12.1 Permission strategy (finalize from V2 to V5)

Conceptual shape (OpenCode V2 `permissions`, ordered, last match wins):

```json
{
  "permissions": [
    { "action": "skill", "resource": "*", "effect": "deny" },
    { "action": "skill", "resource": "<agent_id of selected skill>", "effect": "allow" }
  ]
}
```

Requirements:

- Allow rules use `agent_id["opencode"]` (5.3), not assumed folder names.
- If V2 shows project permissions **replace** the global ones, the generator must **not** silently drop unrelated global rules; it reports this and applies the verified-safe approach (for example, reproducing needed global rules after review, with your approval).
- The deny-all rule must be positioned so it cannot override unrelated existing allow rules for non-skill actions (it is scoped to `action: skill`).
- If V4 shows deny rules do not hide skills from the advertised list, document that "denied" means "not loadable," and measure what the model sees.

## 12.2 Configuration preservation

Create or update `<project>/opencode.json`:

- Parse the existing file; **preserve all unrelated settings** and key order where practical.
- Preserve existing permission rules; add manager rules in a clearly bounded position and record them in the ownership sidecar (5.5).
- Detect **conflicting** rules (for example a user-defined `allow` for a skill that is not selected, or a later `deny`) and report them; request a decision rather than overwriting.
- If `opencode.jsonc` exists, do not rewrite it as JSON; report and ask (V10 determines precedence).
- Write atomically; validate the result as JSON and against OpenCode behavior (V1 to V4).
- The file stays local-only (Phase 2). Inspect whether it is tracked before any change.

## 12.3 Subcommands (explicit, no surprise writes)

| Subcommand | Behavior |
|---|---|
| `agent-skills opencode plan` | Show the exact diff that would be applied. Read-only. |
| `agent-skills opencode apply` | Apply the configuration (confirmation unless `--yes`; supports `--dry-run`). |
| `agent-skills opencode validate` | Validate current `opencode.json` against the manifest. Read-only. |
| `agent-skills opencode run [-- <args>]` | Validate, then launch OpenCode. Does not write files. |

Empty selection: deny-all only, with a notice.

## 12.4 Custom skills

Per V1: if OpenCode skips frontmatterless skills, report them as unavailable in OpenCode; do not create duplicate identifiers; do not modify originals. Any generated metadata mechanism must be supported by OpenCode config and proven not to create duplicate IDs. Do not claim availability until verified through OpenCode.

## 12.5 Performance

Measure (and record in the review, with redacted paths): discovery time, OpenCode startup time, number of skills advertised, number actually accessible, configuration validation time. Define pass/fail budgets from the Phase 0 baseline. Permission filtering may not remove the cost of scanning the global library; if scanning is expensive, evaluate a **supported** isolation mechanism (V5) and propose it before changing the design.

## 12.6 Deliverables

Adapter, permission generator, configuration validator, compatibility tests, performance measurements, troubleshooting notes. **Approval gate** before Phase 7.

---

# 13. Phase 7: Digital Pharmacy Integration

**Objective:** Validate the full system on the existing Flutter project.

## 13.1 Project details

- Project path: `/Users/tamimhasan/OfficeWork/CharBindu/Digital-Pharmacy/DigitalPharmacy` (use only locally; redact in tracked docs).
- Branch: `chore/agent-skills-manager`, base `dp-dev-tamim`.
- Before any change, confirm the working tree state and record it.

## 13.2 Files to preserve unchanged

`AGENTS.md`, `.aiignore`, `.junie/`, `.junie/plans/profit-calculation-remaining-fixes.md`, `.gitignore` (except the approved Phase 2 additions), `doc/review/comprehensive-code-review.md`, `doc/review/purchase-sell-reports-review.md`.

The existing `AGENTS.md` holds important conventions and is never replaced by a template.

## 13.3 Initialization

1. Run `detect` and `recommend`; Flutter and Dart are expected from `pubspec.yaml`, and `android/` must **not** produce a second project.
2. **You confirm the selected skills** (candidates: `flutter-tamim`, `hive-db-tamim`). Do not assume both.
3. `init` and `add` with confirmation; run `validate`.

## 13.4 Documentation migration

`doc/review/` -> `doc/reviews/`:

1. Inspect the source directory; check whether any destination files exist.
2. **Grep for references** to `doc/review/` across the repository (including `AGENTS.md`, README, other docs). `AGENTS.md` cannot be edited, so report stale references to you rather than fixing them.
3. Compare contents; make sure nothing is lost.
4. Use `git mv`; never overwrite an existing destination.
5. Do not move or modify `.junie/plans/`.
6. Decide, with you, whether this rename belongs on the `chore/agent-skills-manager` branch or should be its own change.

## 13.5 Final structure

```text
DigitalPharmacy/
├── .agents/skills.json       # local-only (ignored)
├── .junie/                   # local-only (ignored)
├── doc/
│   ├── plans/                # tracked
│   └── reviews/              # tracked
├── AGENTS.md                 # local-only per policy; unchanged
├── .aiignore                 # local-only
├── .gitignore                # approved additions only
└── opencode.json             # local-only
```

**Approval gate** before Phase 8.

---

# 14. Phase 8: Automated and Manual Testing

Use `unittest` only (a dependency requires prior approval).

## 14.1 Test isolation (mandatory)

- Tests **never** touch the real `~/.agents`, `~/.config`, `~/.junie`, or `~/.local`.
- Support `AGENT_SKILLS_HOME` and `AGENT_SKILLS_CONFIG` overrides; every test uses a temporary directory and fixtures.
- Agents are replaced by stub executables that record their argv, so launch logic is testable without a model.

## 14.2 Unit tests

Skill discovery; frontmatter parser (quoted values, block scalars, colons, malformed, unsupported constructs); custom skills without frontmatter; manifest parsing, validation, migration, duplicate and unknown ID rejection; detection (including Flutter with `android/`, `package.json` without React, monorepo depth); symlink generation; broken link detection; path traversal; symlink escape; ownership marker; atomic refresh and lock; configuration generation and preservation; identifier model (duplicate `declared_name`, name/folder mismatch).

Edge fixtures: empty library, missing library, unreadable files, invalid UTF-8, spaces and unicode names, case-insensitive collisions, concurrent runs.

## 14.3 CLI tests

Every command and its `--help`, `--dry-run`, `--json`, `--yes`, non-TTY behavior, and exit codes. No destructive operation runs against real data.

## 14.4 Adapter tests

**Junie (automated via stub):** default locations flag present; only the generated directory passed; passthrough args; user-supplied conflicting flags refused; invalid manifest blocks launch; empty selection handled; settings files unchanged (checksums); custom skill sources byte-identical.

**OpenCode (automated):** generated JSON valid; V2 syntax; allow rules for selected, deny-all first; conflicts detected; unrelated settings and existing rules preserved; `.jsonc` handling; sidecar ownership correct.

**Real-agent verification (manual procedure unless V9 provides a listing command):** for each agent, start a session in the Digital Pharmacy project, ask the agent to list or use its available skills, and record: selected skills available, unselected unavailable, custom skills behavior. Record results in the review document. Do not claim automated coverage for this.

## 14.5 Git safety tests

Agent configuration ignored; `doc/plans` and `doc/reviews` trackable; no tracked file silently untracked; no skill source modified (checksums of the library before and after); no user changes discarded.

## 14.6 Performance checks

Compare against Phase 0 baselines and the agreed budgets (7.3, 12.5).

---

# 15. Phase 9: Documentation, Installation, Final Acceptance

## 15.1 Documentation (in the manager repo)

Installation (including idempotent `install.sh`, `PATH` check, upgrade, uninstall, config and manifest migration); configuration; CLI commands; skill discovery and selection; Junie and OpenCode integration with their verified limitations and the launch asymmetry; manifest schema; custom skills and D1 behavior; shell alias recommendation; troubleshooting; security; testing.

Every example must match implemented behavior. Do not document unimplemented commands. Examples to include:

```bash
agent-skills init
agent-skills list
agent-skills detect
agent-skills recommend
agent-skills add java-springboot
agent-skills validate
agent-skills sync
agent-skills junie
agent-skills opencode plan
agent-skills opencode apply
```

## 15.2 Final acceptance checklist

**Global manager**
- [ ] Global CLI works (all commands in 9.1).
- [ ] Library discovered with cache and measured performance within budget.
- [ ] Custom skills preserved byte-for-byte; missing frontmatter is not an error.
- [ ] Metadata validation, including duplicate `declared_name` detection.
- [ ] Manifest validation and migration.
- [ ] Detection correct (no false Android/Java for Flutter projects).
- [ ] Recommendations explainable and never auto-select.
- [ ] Symlink management safe (allow-list, ownership, atomic, locked).
- [ ] Consistent errors and exit codes; `--dry-run`, `--json`, `--yes` behave as specified.

**Junie**
- [ ] Defaults disabled; only generated directory passed.
- [ ] Selected skills exposed; unselected not loaded in managed launch (manual verification recorded).
- [ ] Existing settings unchanged (checksums).
- [ ] Custom skills verified.
- [ ] Rules delivered per 10.1.

**OpenCode**
- [ ] Configuration valid; permission rules use verified identifiers.
- [ ] Merge behavior with global config verified (V2); no unrelated rules lost.
- [ ] Selected available, unselected denied (manual verification recorded; V4 limits documented).
- [ ] Existing configuration preserved; `.jsonc` handled.
- [ ] Custom skills outcome verified and documented.
- [ ] Startup and discovery performance measured against budgets.
- [ ] Rules delivered per 10.1.

**Digital Pharmacy**
- [ ] `AGENTS.md` and other preserved files unchanged.
- [ ] Manifest valid; detection correct; selection confirmed by you.
- [ ] Skills verified with both agents.
- [ ] Reviews preserved under `doc/reviews/`; stale references reported.
- [ ] `.junie/plans/` untouched.
- [ ] Ignore rules verified; no unrelated files changed.

**Git**
- [ ] No agent configuration committed or tracked.
- [ ] Plans and reviews trackable.
- [ ] No existing changes lost; nothing staged or committed without approval.
- [ ] Tracked docs contain no secrets or absolute home paths.

---

# 16. Execution Protocol

Revised phase order:

| # | Phase |
|---|---|
| 0 | Environment inspection and verification experiments |
| 1 | Manager repository, configuration, discovery |
| 2 | Git protection in Digital Pharmacy |
| 3 | Manifest, detection, selection, symlinks |
| 4 | Shared rules and delivery mechanism |
| 5 | Junie adapter |
| 6 | OpenCode adapter |
| 7 | Digital Pharmacy integration and documentation migration |
| 8 | Automated and manual testing |
| 9 | Documentation, installation, final acceptance |

For every phase:

1. Inspect relevant files and configuration.
2. Identify risks and gaps; replan if the review finds any.
3. Write a concise phase plan (status `AWAITING_APPROVAL`).
4. **Stop for explicit approval.**
5. Implement only the approved scope.
6. Run relevant tests.
7. Update the plan and review documents.
8. Report completed work, verification evidence, and remaining issues.

If an experiment or an unexpected issue invalidates part of the architecture, stop and explain the impact before proceeding. Do not skip a phase because it looks simple.

---

# 17. Final Deliverables

1. A reusable global skill manager in its own repository.
2. A documented, tested Python CLI.
3. Centralized configuration with schema versioning and migration.
4. A project manifest with validation and migration.
5. Technology detection with evidence.
6. Deterministic, explainable recommendations with confirmed selection.
7. A Junie adapter and an OpenCode adapter, each verified against the installed versions.
8. Shared engineering rules with a verified delivery mechanism.
9. Safe symlink management with ownership markers, atomic refresh, and locking.
10. Automated tests with full isolation, plus a documented manual verification record.
11. Installation, upgrade, and uninstall documentation.
12. Digital Pharmacy integration.
13. Git protection and verification.
14. Final implementation and acceptance reports.

**Final principle:** One shared skill library, one project-specific selection system, two independent agent adapters, and one consistent engineering workflow, with every agent behavior verified rather than assumed, and no sacrifice of existing projects or user-created skills for convenience.
