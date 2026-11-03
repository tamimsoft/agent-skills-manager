# Implementation Plan: Remaining Enhancements

**Task:** remaining-enhancements  
**Plan file:** docs/plans/remaining-enhancements-plan.md  
**Status:** PENDING (user said "Let's implement"; proceeding)  
**Date:** 2026-11-03  
**Reviewer:** Kilo

## Objective
Implement all remaining enhancement tasks to harden the agent-skills-manager:
1. Add unit tests for AGENTS.md hard enforcement
2. Fix L1: empty-library missing-skill silent pass
3. Fix M5: detection walk follows symlinked directories
4. Fix G7: doctor doesn't verify launcher binary
5. Fix opencode run/kilo run ignoring --dry-run
6. Add junie --dry-run flag

## Files in Scope (modified)
1. `tests/test_agents_md.py` — NEW test file for AGENTS.md enforcement
2. `src/agent_skills/cli.py` — L1 fix, G7 fix, cmd_validate AGENTS.md check (already present)
3. `src/agent_skills/detection.py` — M5 symlink walk fix
4. `src/agent_skills/adapters/opencode.py` — run respects dry-run
5. `src/agent_skills/adapters/kilo.py` — run respects dry-run
6. `src/agent_skills/adapters/junie.py` — add --dry-run flag

## Files NOT in Scope
- No new dependencies; keep `pyproject.toml` `dependencies = []`

## Phased Plan

### Phase 1 — P0: Tests + critical bug fix

1.1 Create `tests/test_agents_md.py` with tests for:
- `generate_agents_md()` default (no overwrite), force=True overwrite, write=False dry-run
- `cmd_sync()` regenerates AGENTS.md
- `cmd_validate()` exits 3 when AGENTS.md missing, passes when present/current
- `generate_project_skills_dir()` writes AGENTS.md into generated dir

1.2 `cli.py` `cmd_validate()`: remove `and rec_map` guard so missing skills always reported (L1).

Acceptance: 56+ existing tests pass + new AGENTS.md tests pass; `validate` reports missing skills even with empty library.

### Phase 2 — P1: Medium fixes

2.1 `detection.py` `_find_markers()`: skip symlinked directories (`full.is_symlink()` check) (M5).
2.2 `cli.py` `cmd_doctor()`: verify `agent-skills` binary exists on PATH (G7).
2.3 `adapters/opencode.py` `run()`: respect `--dry-run` — don't call `apply` with `dry_run=False`, don't `os.execvp` when dry-run (P1).
2.4 `adapters/kilo.py` `launch_kilo()` `run` subcommand: respect `--dry-run` — short-circuit before full apply (P1).

Acceptance: `opencode run --dry-run` and `kilo run --dry-run` don't apply changes; dry-run flag accepted by junie.

### Phase 3 — P2: junie --dry-run

3.1 `adapters/junie.py`: add `--dry-run` to parser; short-circuit before `os.execvp` when dry-run.

## Error Handling / Validation
- All fixes preserve existing return codes and confirmation gating
- No new exceptions introduced to public call paths
- Test file follows existing `setUp`/`tearDown` env-var pattern (`AGENT_SKILLS_HOME`, `AGENT_SKILLS_CONFIG`)

## Breaking Changes
- None to CLI surface or config/manifest schema

## Testing Strategy
- `PYTHONPATH=src python3 -m unittest discover -s tests` must remain green
- Add regression tests in `tests/test_agents_md.py`

## Assumptions / Unresolved Questions
- None

## Approval
User said "Let's implement" — proceeding without further confirmation.
