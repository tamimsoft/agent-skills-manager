# Project Initialization Guided Setup Plan

## Objective

Make project initialization a guided, backward-compatible workflow for selecting agent targets and relevant skills, while creating local planning/review directories and honoring manifest choices during managed operations.

## Approved refined requirement

The implementation proposal is in [`project-init-guided-setup-review.md`](../reviews/project-init-guided-setup-review.md). In summary:

- `agent-skills init --interactive` guides users through supported agent selection and skill selection.
- Agent availability is displayed as information, not a hard restriction on selection.
- Recommendations are the initial skill view; users can search/browse the full library and retain existing selections.
- Existing manifests are loaded and edited without replacing unrelated metadata.
- Successful init ensures `docs/plans/` and `docs/reviews/` exist, without `.gitkeep` files.
- Disabled targets are blocked only for manager-controlled launch/apply operations; OpenCode and Kilo plan/validate diagnostics remain available.
- Noninteractive init keeps current defaults. `--yes` confirms writes but does not choose agents or skills.
- Kilo's global skill discovery remains an explicit limitation.

## Constraints

- Python 3.9+, standard library only, existing `unittest` conventions.
- Keep manifest/config schema versions unchanged unless code inspection proves a migration is required; if a schema change becomes necessary, stop and request approval.
- Preserve existing project metadata and make manifest writes through the existing backup/atomic-save helper.
- No agent installation, network calls, or execution of agent binaries merely to detect availability.
- No commits, merges, or pushes without the separate approvals required by project instructions.

## Files/components expected to change

- `src/agent_skills/cli.py`: guided init flow, CLI parser/help, interactive agent/skill selection, dry-run/cancellation behavior, availability display.
- `src/agent_skills/manifest.py`: validate and update supported agent settings safely while preserving extension fields.
- `src/agent_skills/adapters/junie.py`, `src/agent_skills/adapters/kilo.py`, `src/agent_skills/adapters/opencode.py`: consistently enforce enabled targets for manager-controlled launch/apply operations; preserve OpenCode/Kilo read-only plan/validate behavior.
- `README.md`: describe guided initialization, noninteractive behavior, target availability, and Kilo's limitation.
- `tests/`: focused init, picker, manifest-preservation, disabled-target, dry-run, and cancellation tests, following existing test conventions.

## Phases and acceptance criteria

1. **Finalize requirement and implementation review** — `COMPLETED`
   - Existing init, manifest, picker, and adapter behavior reviewed and recorded.
   - Acceptance: known gaps, compatibility requirements, and Kilo limitation documented.
2. **Approve this plan** — `COMPLETED`
   - User approved the refined requirement and plan before implementation.
3. **Implement agent selection and safe manifest updates** — `COMPLETED`
   - Interactive setup displays supported agents with availability status and preselects existing enabled values.
   - Existing manifest unknown/project fields remain intact; new-manifest defaults remain backward-compatible outside interactive mode.
   - Disabled agents are blocked for managed operations with actionable errors; OpenCode/Kilo read-only plan/validate commands still work.
   - Missing configured skill library is reported as a notice and does not prevent initializing a project without selected skills.
4. **Implement recommendation/search picker and initialization folders** — `COMPLETED`
   - Picker starts with recommendations and supports searching/browsing the full catalog, both in curses and a non-curses TTY.
   - Previous selections are shown and preserved unless explicitly toggled off.
   - Successful init creates both requested directories idempotently; no placeholder files are added.
5. **Document, test, and review** — `COMPLETED`
   - Add targeted regression tests, run focused tests then full unittest suite, update README, review diff and edge cases, and update this plan/review with verified status.

## Important edge cases

- Existing valid manifest: load choices and preserve unrelated project fields.
- Missing, malformed, or unsupported manifest: report clearly and avoid destructive overwrite.
- No TTY with `--interactive`: return an actionable error; do not treat `--yes` as interactive choices.
- User cancels either wizard stage: do not update manifest, create directories, or regenerate `AGENTS.md`.
- Empty agent or skill selection: persist intentional empty selection only after confirmation; preserve legacy defaults for plain noninteractive init.
- Agent unavailable: allow explicit selection but label unavailable; launching it later should report a clear executable/configuration error.
- Zero recommendations: full-catalog search remains available.
- Very large skill libraries: filter incrementally and avoid rendering or copying every full skill body into the prompt.
- Kilo: enabled-target state does not hide global skills from its built-in catalog.

## Verification strategy

- Unit tests for agent choice serialization, existing-manifest preservation, availability detection, picker search and selection retention, cancellation/no-write behavior, disabled adapter commands, dry-run, and directory creation.
- Run targeted tests for changed modules, then `PYTHONPATH=src python3 -m unittest discover -s tests`.
- Run CLI help and disposable-project init flows for TTY/non-TTY, existing/new manifest, dry-run, and cancellation paths.
- `git diff --check`; inspect final diff against the approved scope.

## Verification results

- `PYTHONPATH=src python3 -m unittest tests.test_init_guided_setup tests.test_agent_enabled tests.test_agents_md tests.test_cli_flags tests.test_opencode_config tests.test_kilo_config`: 55 tests passed.
- `PYTHONPATH=src python3 -m unittest discover -s tests`: 121 tests passed.
- `PYTHONPATH=src python3 -m agent_skills init --help` and `PYTHONPATH=src python3 -m agent_skills --version`: passed.
- Disposable Git-project CLI smoke checks verified normal init creates manifest, managed `AGENTS.md`, `docs/plans/`, and `docs/reviews/`; dry-run created none of them.
- Interactive flow was exercised with a scripted TTY input sequence, including agent toggling and searching beyond recommendations.
- `git diff --check`: passed.

## Status

Implementation and verification are complete. No commit was made.
