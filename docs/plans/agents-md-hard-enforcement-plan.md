# Implementation Plan: AGENTS.md Hard Enforcement

**Task:** agents-md-hard-enforcement  
**Plan file:** docs/plans/agents-md-hard-enforcement-plan.md  
**Status:** PENDING (user already said "yes" to recommendation; proceeding to implement)  
**Date:** 2026-11-03  
**Reviewer:** Kilo  
**Branch:** master (clean, latest commit `4663cf1`)

## Objective / Scope

Make AGENTS.md a hard-enforced artifact: regenerated on sync/managed launches, included in generated agent skill dirs, and validated by `validate`. No new dependencies; keep `pyproject.toml` `dependencies = []`.

## Files in Scope (modified)

1. `src/agent_skills/cli.py` — Phase 1 (sync/launches regenerate AGENTS.md), Phase 3 (validate checks AGENTS.md)
2. `src/agent_skills/links.py` — Phase 2 (write AGENTS.md into generated dir)
3. `src/agent_skills/adapters/junie.py` — Phase 1 (launch regenerates AGENTS.md)
4. `src/agent_skills/adapters/kilo.py` — Phase 1 (launch regenerates AGENTS.md)
5. `src/agent_skills/adapters/opencode.py` — Phase 1 (plan/apply regenerate AGENTS.md)

## Files NOT in Scope
- `manifest.py`, `project.py`, `detection.py`, `discovery.py`, `frontmatter.py`, `identity.py`, `recommend.py`, `cache.py`, `lock.py`, `resolution.py`, `adapter_common.py`
- `tests/` — existing tests unchanged; may add regression tests in follow-up

## Phased Plan

### Phase 1 — sync + managed launches regenerate project AGENTS.md

1.1 `cli.py` `cmd_sync()`: after `generate_project_skills_dir()`, call `generate_agents_md(root, techs, cfg)` to refresh project-root AGENTS.md. Pass result message to stdout.

1.2 `adapters/junie.py` `launch_junie()`: after building skills dir, call `generate_agents_md(root, techs, cfg)` to refresh project-root AGENTS.md.

1.3 `adapters/kilo.py` `launch_kilo()`: same as junie.

1.4 `adapters/opencode.py` `run_opencode_subcommand()` for `apply` and `plan`: call `generate_agents_md(root, techs, cfg)` before/after the subcommand action.

Acceptance: `sync`, `junie --prepare`, `opencode plan`, `opencode apply`, `kilo plan`, `kilo apply` all (re)write project-root AGENTS.md.

### Phase 2 — generate_project_skills_dir writes AGENTS.md into generated dir

2.1 `links.py` `generate_project_skills_dir()`: add optional `agents_md_content` parameter. When provided (non-None), write `AGENTS.md` into the generated dir alongside marker + owned-rules.json.

2.2 `cli.py` `cmd_sync()`: read the generated AGENTS.md content (from `generate_agents_md()` output or re-generate) and pass to `generate_project_skills_dir()`. Simpler: have `generate_agents_md()` return the content string, pass it through.

2.3 `adapters/{junie,kilo,opencode}.py`: pass AGENTS.md content through to `generate_project_skills_dir()` when calling.

Acceptance: Generated dir contains `AGENTS.md` file; agents loading skills from generated dir see global rules in context.

### Phase 3 — validate checks AGENTS.md presence/staleness

3.1 `cli.py` `cmd_validate()`: check `root / "AGENTS.md"` exists. If missing, report error (contributes to exit 3). If exists but content doesn't match expected (compare against `generate_agents_md()` output), report warning.

Acceptance: `validate` exits non-zero when AGENTS.md missing; warns when stale.

## Error Handling / Validation
- `generate_agents_md()` already handles `OSError` on write; returns `(False, message)` on failure
- Callers check return value and print message; don't fail the whole operation on AGENTS.md write failure (non-critical)
- `validate` treats missing AGENTS.md as an error (exit 3 contributor), stale as warning

## Security
- AGENTS.md content comes from trusted local template + local detection (no external input)
- Writing AGENTS.md into generated dir is safe (generated dir is agent-consumed, not user-edited)

## Breaking Changes
- `sync` and managed launches now overwrite project-root AGENTS.md (previously only `init` wrote it, and never overwrote). This is intentional — sync is a refresh operation.
- Generated dirs now contain an additional `AGENTS.md` file.

## Testing Strategy
- Existing suite: 56/56 tests must pass
- Manual end-to-end on carebridge: `init`, `sync`, `junie --prepare`, `opencode plan`, `kilo plan`, `validate` — confirm AGENTS.md created in project root and generated dir

## Assumptions / Unresolved Questions
- `generate_agents_md()` currently returns `(wrote, message)` tuple. Need to also return content string for Phase 2, or re-generate content in cli.py before passing to `generate_project_skills_dir()`. Simpler: have `generate_agents_md()` return `(wrote, message, content)` where content is the generated text.

## Approval
User already said "yes" to the recommendation. Proceeding to implement.
