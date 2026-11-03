# Implementation Plan: Bug, Loophole & Gap Fixes

**Task:** bug-loophole-audit  
**Plan file:** docs/plans/bug-loophole-audit-plan.md  
**Status:** COMPLETE (all phases implemented, awaiting commit authorization)  
**Date:** 2026-11-03  
**Reviewer:** Kilo  
**Branch:** `fix/bug-loophole-audit` (from `master`, commit `36b050c`)  
**Tests:** 56/56 passing

## Summary of Changes

### Phase 1 — P0 crash, data-loss, and budget enforcement (COMPLETE)

1.1 `adapters/opencode.py` `plan()`: assigned `budget_tokens` and `max_skills` from `cfg` before use. (H3)
1.2 `cache.py` `is_cache_valid()`: on stat match, recomputes `content_hash()` and compares to `cached_key[3]`. (H4)
1.3 `adapters/kilo.py` `launch_kilo()`: passes `filtered_records` (not `selected_records`) and detected `techs` to `apply_context_budget`/`build_skills_dir_atomic`. (H1, G2)
1.4 `adapters/junie.py` `launch_junie()`: passes detected `techs` to `apply_context_budget`. (G2)
1.5 `cli.py` `cmd_sync()`: applies `filter_skills_for_context` with `techs` from `detect_technologies(root)` before generating. (G1)

### Phase 2 — P0 destructive & data-loss prevention (COMPLETE)

2.1 `cli.py` `cmd_clean()`: orphan heuristic — only treats a managed dir as orphan if its `project_key` prefix does not correspond to an existing project root (`.agents/skills.json`). Added `_project_root_exists_for_prefix()` helper. (H2, L2)
2.2 `adapters/opencode.py` `_apply_rules_to_config()`: tags manager-owned rules with `"source": "agent-skills-manager"`; re-apply removes only tagged rules. (H5)
2.3 `adapters/kilo.py` `_apply_kilo_rules()`: tracks managed keys via `_agent_skills_managed` key; re-apply removes only tracked keys. (H5)

### Phase 3 — P1 correctness & gap fixes (COMPLETE)

3.1 `links.py` `generate_project_skills_dir()`: writes `opencode-owned-rules.json` alongside the marker file. (G3)
3.2 `adapter_common.py` `build_wrapper()`: `_link_target_safe()` re-validates each symlink target resolves inside the library root; skips escapes. (M1)
3.3 `recommend.py` `_estimate_skill_tokens()`: replaced mutable default `_cache={}` with module-level `_token_cache` dict. (M2)
3.5 `cli.py` `cmd_list()`: removed dead `no_cache` normalization line. (M4)
3.6 `cli.py` `cmd_add()` and `cmd_select()`: validate each skill ID with `identity.is_safe_id()` before adding to manifest. (G6)
3.7 `cli.py` `cmd_add()`, `cmd_select()`, `cmd_remove()`: added `--dry-run` argument that previews changes without saving. (G4)

### Deferred (P2 / separate approval)

- G5 — `cmd_init` AGENTS.md generation (medium effort)
- G7 — `doctor` launcher verification (small)
- L1 — Empty-library missing-skill report (trivial)
- M5 — Detection symlink walk (small)

### Not a fix (by design)

- M3 — Frontmatter `_strip_comment` correctly implements YAML spec: `#` preceded by whitespace starts a comment to end of line.

## Files Modified

1. `src/agent_skills/cli.py` — H2, G1, G4, G6, M4, module-level `Path` import
2. `src/agent_skills/adapters/kilo.py` — H1, G2, H5
3. `src/agent_skills/adapters/junie.py` — G2
4. `src/agent_skills/adapters/opencode.py` — H3, H5
5. `src/agent_skills/links.py` — G3
6. `src/agent_skills/adapter_common.py` — M1
7. `src/agent_skills/recommend.py` — M2
8. `src/agent_skills/cache.py` — H4

## Verification

- `PYTHONPATH=src python3 -m unittest discover -s tests` → 56/56 passing
- Manual verification of cache staleness fix, orphan heuristic, safe_id validation, dry-run, owned-rules.json generation, wrapper symlink re-validation all confirmed

## Next Step

Awaiting explicit commit authorization. No commits have been made.
