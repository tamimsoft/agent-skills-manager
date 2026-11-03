# Review Document: AGENTS.md Hard Enforcement

**Task:** agents-md-hard-enforcement  
**Status:** COMPLETE (findings + plan only; no code changes yet)  
**Reviewer:** Kilo  
**Date:** 2026-11-03  
**Scope:** `src/agent_skills/cli.py`, `src/agent_skills/links.py`, `src/agent_skills/adapters/{junie,kilo,opencode}.py`

---

## 1. Current Implementation Summary

`agent-skills init` calls `generate_agents_md(root, techs, cfg)` which writes `AGENTS.md` into the project root combining `AGENTS.base.md` + detected tech sections. This happens **only** during `init`, and only when `AGENTS.md` does not already exist (safe merge — never overwrites).

`generate_project_skills_dir()` (links.py) writes `.agent-skills-managed.json` marker and `opencode-owned-rules.json` into the generated dir, but **not** `AGENTS.md`.

`validate` (cli.py) checks manifest/library but does **not** check `AGENTS.md` presence.

Managed launches (`junie`, `opencode apply|run`, `kilo apply|run`, `sync`) do not regenerate `AGENTS.md` after the initial `init`.

**Gap:** `AGENTS.md` is advisory documentation only — agents can ignore it, it can go stale, and there's no enforcement that it exists or matches the current tech stack/selected skills.

---

## 2. Recommended Changes

### Phase 1 — sync + managed launches regenerate project AGENTS.md
- `cmd_sync()` calls `generate_agents_md(root, techs, cfg)` after generating skills dir (overwrites — sync is a refresh operation)
- `launch_junie()`, `launch_kilo()`, `run_opencode_subcommand()` call `generate_agents_md()` to ensure AGENTS.md is current before launch

### Phase 2 — generate_project_skills_dir writes AGENTS.md into generated dir
- Add optional `agents_md_content` parameter to `generate_project_skills_dir()`
- When provided, writes `AGENTS.md` into the generated dir alongside marker + owned-rules
- This makes global rules part of the agent's loaded skill context (hard enforcement at context level)

### Phase 3 — validate checks AGENTS.md presence/staleness
- `cmd_validate()` checks `root / "AGENTS.md"` exists; reports error if missing
- Optionally compares content to current expected content and warns if stale

---

## 3. Testing Strategy
- Existing suite: `PYTHONPATH=src python3 -m unittest discover -s tests` must remain green (56 tests)
- Manual verification: run `init`, `sync`, `junie --prepare`, `opencode plan`, `kilo plan`, `validate` against carebridge project; confirm AGENTS.md is created/updated in project root and generated dir
- No new dependencies; keep `pyproject.toml` `dependencies = []`

---

## 4. Review Status

**Status:** APPROVED (user said "yes" to recommendation). Ready for implementation.
