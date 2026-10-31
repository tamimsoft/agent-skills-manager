# Initial Environment Review

**Status:** `PENDING` (awaiting user approval before Phase 1)
**Date:** 2026-10-31
**Phase:** 0 (Environment inspection and verification experiments)

## 1. Environment findings

| Component | Observed | Tested version |
|---|---|---|
| OS / shell | macOS, zsh | — |
| Home | `<HOME>` (resolve dynamically; never hardcode) | — |
| Python (default) | 3.14.7 (Homebrew, `/opt/homebrew/bin/python3`) | — |
| Python (system) | 3.9.6 (`/usr/bin/python3`) | D3 floor 3.9 confirmed available |
| OpenCode | 2.2.5 (`opencode v2.2.5`) | 2.2.5 (match) |
| Junie | 26.10.27 (3893.6) | 26.10.27 (match) |
| `~/.local/bin` on PATH | yes | — |
| Filesystem | case-insensitive (macOS default) | — |

## 2. Skill library

- Library root: `~/.agents/skills/`
- Total top-level directories: 1436
- Symlink entries at top level: 0
- Skills with `SKILL.md`: 1435 (one directory, `iso-27001-workspace`, contains evaluation outputs only, not a skill)
- Missing frontmatter: `flutter-tamim`, `hive-db-tamim`, `isar-db-tamim` (3, not 2 as the guideline initially stated)
- Declared `name` vs folder mismatches: 9 (`agent-development`, `command-development`, `hook-development`, `mcp-integration`, `plugin-settings`, `plugin-structure`, `skill-development`, `ui-toolkit-web`, `writing-hookify-rules`)
- Duplicate declared names: 0
- Junie skills: 68, all also present in the global library

## 3. Global configuration

- `~/.config/opencode/`: contains `service.json` only; no global `opencode.json` / `opencode.jsonc`.
- OpenCode global paths (from `opencode debug paths`): config `~/.config/opencode`, data `~/.local/share/opencode`, cache `~/.cache/opencode`, state `~/.local/state/opencode`.
- `~/.junie/`: settings present; skills dir 68 entries; no global `AGENTS.md` currently.
- `~/.config/agent-skills/`: does not exist yet.

## 4. Digital Pharmacy baseline

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

## 5. Experiment results (V1-V12)

### V6 — Junie skill flags (verified by command parsing)

- `--skill-default-locations=false --skill-location=<path> --version` exits 0.
- Space-separated form (`--skill-default-locations false --skill-location <path>`) also exits 0.
- Repeated `--skill-location` is accepted.
- Conclusion: both syntaxes work; repeated flag supported; value is text (`true`/`false`).
- Semantics (parent vs individual skill dir): from Junie docs, `skill-locations` are folders Junie searches for skills, i.e. parent directories. Use parent directory.

### V10 — OpenCode `opencode.json` vs `opencode.jsonc` (verified)

- `opencode debug config --standalone` lists both files as separate config sources when both exist.
- The `instructions` key is supported (array of paths, e.g. `~/.config/agent-skills/rules.md`).
- Conclusion: if both files exist, both are loaded. Manager must not rewrite `.jsonc` as JSON (comments lost); report and ask for a decision. `instructions` is the verified delivery mechanism for shared rules.

### V11 — Junie guidelines/rules locations (verified from bundled docs)

- Project: `.junie/AGENTS.md`; or `AGENTS.md` + `.junie/playbook.md` + `.junie/rules/*.md`; or legacy `.junie/guidelines.md` / `.junie/guidelines/`.
- Global: `~/.junie/AGENTS.md`.
- Precedence: project-level over global.
- Additional delivery mechanisms: `guidelines-location` in `config.json`, and `--ide-guidelines=<path>` (prepends content to existing guidelines).
- Conclusion: shared rules can be delivered via `--ide-guidelines` at managed launch (prepend `rules.md`) without touching `AGENTS.md`. Global `~/.junie/AGENTS.md` is an option but applies to all projects.

### V12 — Junie plan location (verified from bundled docs)

- Plans are saved to `.junie/plans/`; no configurable equivalent found.
- Conclusion: canonical plans must be copied to `doc/plans/` by the agent; `.junie/plans/` remains working material only.

### V1, V2, V3, V4, V5, V7, V8, V9 — manual procedure required

These require a model call or agent interaction and cannot be cleanly automated in this environment (OpenCode runs are slow and the model explored the filesystem instead of answering; Junie authenticated successfully but produced no skill list before timeout). Manual procedures are recorded below; they must be executed and recorded in this document (or the final acceptance review) before claiming coverage.

**V1 — OpenCode frontmatterless discovery and identifier:**
1. Create a sandbox HOME with `~/.agents/skills/no-fm-skill/SKILL.md` (no frontmatter) and `~/.agents/skills/with-fm/SKILL.md` (frontmatter `name: with-fm-alias`).
2. Launch OpenCode in a temp project; ask "List the skill identifiers you have available."
3. Record whether `no-fm-skill` appears and which identifier OpenCode uses (folder vs `name`).

**V2 — OpenCode project permission merge:**
1. Sandbox HOME with a global `opencode.json` granting an allow for one skill.
2. Project `opencode.json` with deny-all then allow for a different skill.
3. Launch OpenCode; observe which skills are usable and whether global rules survive.

**V3 — OpenCode permission resource matching:**
1. Project `opencode.json` with `resource` values using folder name, frontmatter `name`, and a glob.
2. Observe which selected skills load.

**V4 — OpenCode deny hide vs block:**
1. With a deny rule for one skill, ask OpenCode to list available skills; record whether the denied skill appears in the list.

**V5 — OpenCode disable/redirect default skill paths:**
1. Inspect OpenCode config schema for a skill-path or `instructions`-only mechanism; test any candidate key in a sandbox project.

**V7 — Junie symlink following:**
1. `junie --skill-default-locations=false --skill-location=<parent>` where one skill entry is a symlink to a directory, with a relative reference inside.
2. Ask Junie to use the skill; record whether it loads and whether relative references resolve.

**V8 — Junie frontmatterless wrapper:**
1. Create a generated wrapper directory (SKILL.md with frontmatter + symlinks to original files) for a frontmatterless skill.
2. Launch with `--skill-location=<wrapper-parent>`; ask Junie to use it; verify source files are byte-identical (checksums before/after).

**V9 — Agent exposes loaded-skill list:**
1. OpenCode: no command found (`opencode debug` has no skills subcommand). Verification is by asking the model; record as manual.
2. Junie: no command found. Verification is by asking the model; record as manual.

## 6. Risks and compatibility concerns

- OpenCode runs are slow and the model may not answer list queries reliably; manual verification must be recorded as evidence, not assumed.
- Three (not two) skills lack frontmatter (`flutter-tamim`, `hive-db-tamim`, `isar-db-tamim`); the guideline's custom-skill list must be updated.
- `iso-27001-workspace` is not a skill and must be excluded from discovery (no `SKILL.md`).
- 9 declared-name/folder mismatches are warnings, not errors; permission rules must use verified `agent_id`, not `declared_name`.
- Digital Pharmacy `.gitignore` additions are currently unanchored (`AGENTS.md`); Phase 2 must replace with the anchored set and evaluate other tool paths.
- `AGENTS.md` is ignored but untracked; no tracked-file risk today, but Phase 2 pre-check must still run before any agent file is created.
- Junie global guidelines (`~/.junie/AGENTS.md`) do not exist yet; shared rules delivery via `--ide-guidelines` avoids creating one.

## 7. Recommended adjustments to the guideline

1. Update the custom-skill list in sections 3, 7.4, 11.4, 12.4 to include `isar-db-tamim`.
2. Keep Python floor at 3.9 (`/usr/bin/python3` = 3.9.6); Homebrew 3.14 available for development.
3. Junie delivery mechanism for shared rules: use `--ide-guidelines=<rules.md>` at managed launch (prepend), plus optional global `~/.junie/AGENTS.md`. Do not write to project `AGENTS.md`.
4. OpenCode delivery mechanism for shared rules: `instructions` array in `opencode.json` (verified).
5. If both `opencode.json` and `opencode.jsonc` exist, treat as conflict requiring a decision (do not silently merge or rewrite).
6. Plans: agent saves to `.junie/plans/` only; manager instructs copying canonical plan to `doc/plans/`.

## 8. Approval gate

This review and the adjustments above are presented for approval. No Phase 1 work begins until approved. The manual procedures in section 5 remain to be executed and recorded; they do not block Phase 1 planning but must be completed before the Phase 6/7 acceptance claims.
