# Project Initialization Guided Setup Review

## Scope and current behavior

Reviewed `agent-skills init`, project manifest handling, interactive skill selection, agent adapters, and related CLI tests for the requested project setup flow.

- `init` detects project technologies, prints recommendations, and creates a manifest with no skills selected.
- `init --interactive` can invoke skill selection, but it does not ask which agents should be enabled.
- `default_manifest()` enables OpenCode, Junie, and Kilo for new manifests.
- The manifest already stores `agents.<id>.enabled`, but adapters use this mainly for resolution reporting; managed launch/apply commands are not consistently blocked for disabled agents.
- Skill selection can show all records with in-terminal search when curses is available. The non-curses numeric picker is limited to current recommendations; `--filter` and `--tech` are static command-line filters, not a runtime search interaction.
- Existing `init` notices an existing manifest but constructs a new default manifest rather than loading the existing choices. It can therefore fail to preserve the user's existing project metadata and selected agents when interactively updating.
- `save_manifest()` already validates, makes a backup, and atomically replaces the manifest.
- Kilo's adapter explicitly reports that global `~/.agents/skills` entries remain in Kilo's catalog. Project selection must not be described as exclusive Kilo isolation.

## Findings and recommendations

| # | Finding / gap | Recommendation |
|---|---|---|
| 1 | No guided agent choice during initialization. | Extend opt-in `init --interactive` into an ordered wizard: choose supported targets, then choose skills. Display installed/unavailable status as advisory; do not prevent selecting a supported but currently unavailable target. |
| 2 | Agent enabled state is descriptive, not consistently enforced. | Define it as manager-target intent. Managed operations for a disabled agent should fail with a clear actionable message; supported read-only diagnostics may still run. Keep unrelated unmanaged agent launches outside the manager's guarantee. |
| 3 | Skill recommendation and search experiences differ by terminal mode. | Provide a single selection model: recommendations first, with an in-picker way to search/browse the full catalog, retain prior selections, and toggle choices. Keep a usable non-curses interactive fallback. |
| 4 | Existing manifest choices are not safely reused by interactive init. | Load and validate an existing manifest, preselect its agents and skills, preserve unknown/project metadata fields, and update only fields owned by the wizard. Continue using the existing backup/atomic-save path. |
| 5 | Initialization does not create requested workflow folders. | On successful initialization, ensure `docs/plans/` and `docs/reviews/` exist idempotently. Do not add placeholder files; document that empty directories are local and Git does not track them. |
| 6 | Non-TTY automation and cancellation behavior need clear boundaries. | Keep noninteractive `init` backward-compatible. Interactive mode requires an interactive terminal; `--yes` confirms writes but must not fabricate user choices. Cancellation before confirmation should leave manifest and generated project instructions unchanged. |
| 7 | Kilo cannot guarantee a project-only catalog while global skills remain in its scan path. | Preserve explicit limitation messaging; do not make a claim that agent/skill selection hides global Kilo skills. |

## Proposed requirement

Add a backward-compatible, opt-in guided setup to `agent-skills init --interactive`:

1. Show supported agents (OpenCode, Junie, Kilo), report whether each appears available from configured executable paths or `PATH`, and allow users to enable/disable targets.
2. Show relevant recommendations first, with an interactive search/browse path for the full skill catalog. Preserve existing skill choices when editing a project.
3. Persist agent and skill choices in the existing manifest, preserving project metadata and using current backup/atomic-save behavior.
4. Ensure `docs/plans/` and `docs/reviews/` exist after successful initialization, without placeholder files.
5. Make the manager honor the enabled-agent setting for managed launch/apply operations, while keeping supported read-only diagnostics usable and documenting the boundary for unmanaged tool invocations.
6. Preserve current noninteractive defaults and behavior unless explicit CLI options are provided. Do not silently select recommendations or treat `--yes` as a choice.

## Scope boundaries and risks

- This is a CLI/manifest behavior change; schema version need not change if the existing fields suffice. Validate manifest agent values and compatibility before implementation.
- Check executable availability without running arbitrary agent binaries or installing software.
- Ensure all choices and validation finish before writing the manifest or generated `AGENTS.md`; dry-run and cancellation must not mutate project state.
- Plan/review directories are created at runtime but do not persist in Git until content is added.
- A selected Kilo target does not remove Kilo's separately discovered global skills.

## Resolution status

| # | Finding | Status and resolution |
|---|---|---|
| 1 | No guided agent choice during initialization | Resolved: `init --interactive` presents OpenCode, Junie, and Kilo with configured executable availability and persists enabled choices. |
| 2 | Agent enabled state was not consistently enforced | Resolved: Junie, Kilo, and OpenCode managed launch/apply paths reject explicitly disabled targets; existing OpenCode/Kilo plan and validate commands remain available. Junie exposes no plan/validate subcommands. Missing legacy entries retain enabled behavior. |
| 3 | Recommendation and search experiences differed by terminal mode | Resolved: recommendations appear first; curses typing searches all skills; the text picker supports `s <text>`, `/text`, `a`, and `r`. |
| 4 | Existing manifest choices were not safely reused | Resolved: interactive init loads and validates the manifest, preselects current settings, preserves unknown metadata and selected IDs missing from the library, and writes through the existing backup/atomic-save path. |
| 5 | Initialization did not create workflow folders | Resolved: successful init idempotently creates `docs/plans/` and `docs/reviews/` without placeholders. |
| 6 | Non-TTY and cancellation semantics were unclear | Resolved: interactive selection requires a TTY; `--yes` only confirms writes; cancellation and dry-run do not mutate project files. |
| 7 | Kilo could not guarantee a project-only catalog | Limitation retained and disclosed: Kilo global discovery remains additive; selecting/enabling Kilo does not hide global skills. |

## Verification

- Full unittest suite passed: 121 tests.
- Targeted guided-init/agent-gating tests and disposable CLI init/dry-run smoke checks passed.
- Init help/version and `git diff --check` passed.

## Review status

Complete. No unresolved implementation findings; Kilo's global catalog limitation remains documented.
