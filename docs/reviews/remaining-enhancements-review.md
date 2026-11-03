# Review Document: Remaining Enhancements

**Task:** remaining-enhancements  
**Status:** COMPLETE (findings only; fixes implemented below)  
**Reviewer:** Kilo  
**Date:** 2026-11-03  
**Scope:** `src/agent_skills/cli.py`, `src/agent_skills/detection.py`, `src/agent_skills/adapters/{junie,kilo,opencode}.py`, `tests/`

## Current Implementation Summary

After the AGENTS.md hard enforcement feature, the codebase has these remaining gaps:

### 1. No unit tests for AGENTS.md hard enforcement (HIGH)
The AGENTS.md enforcement feature was added in `2685f7e` but has zero test coverage:
- `generate_agents_md()` with `force=True`, `write=False`, content return
- `cmd_sync()` regenerating AGENTS.md
- `cmd_validate()` checking AGENTS.md presence/staleness (exit 3 if missing)
- `generate_project_skills_dir()` writing AGENTS.md into generated dir

### 2. L1 — Missing-skill check silently passes when library empty (MEDIUM)
`cli.py` `cmd_validate()` line: `if sid not in rec_map and rec_map:` — the `and rec_map` guard means empty library + non-empty selection = no error.

### 3. M5 — Detection walk follows symlinked directories (MEDIUM)
`detection.py` `_find_markers()`: `if full.is_dir():` follows symlinks; symlinked subdirectories outside project root could be scanned.

### 4. G7 — doctor doesn't verify launcher binary (MEDIUM)
`cmd_doctor()` checks `~/.local/bin` is on PATH but never verifies `agent-skills` binary exists there.

### 5. opencode run/kilo run ignore --dry-run (MEDIUM)
`opencode run` calls `apply(cfg, dry_run=False, yes=True)` then `os.execvp()` — dry-run ignored. `kilo run` calls `launch_kilo()` which does full apply regardless of `args.dry_run`.

### 6. junie has no --dry-run flag (MEDIUM — feature gap)
Junie parser only has `--prepare` and `args`; no dry-run preview capability.

## Combined Fix Priority

| Priority | Task | Module | Effort |
|----------|------|--------|--------|
| P0 | Unit tests for AGENTS.md enforcement | tests/test_agents_md.py | Medium |
| P0 | L1 empty-library missing-skill | cli.py | Trivial |
| P1 | M5 detection symlink walk | detection.py | Small |
| P1 | G7 doctor launcher check | cli.py | Small |
| P1 | opencode run/kilo run dry-run | adapters/opencode.py, kilo.py | Small |
| P2 | junie --dry-run | adapters/junie.py | Small |

## Testing Requirements
- Run `PYTHONPATH=src python3 -m unittest discover -s tests` — all tests must pass
- New test file: `tests/test_agents_md.py` following existing setUp/tearDown env-var pattern
- No new external dependencies

## Review Status
**Status:** RESOLVED — all findings addressed below.
