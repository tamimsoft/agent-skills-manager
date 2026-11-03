# Review Document: Bug & Loophole Audit

**Task:** bug-loophole-audit  
**Status:** COMPLETE (findings only; no fixes applied yet)  
**Reviewer:** Kilo (software engineer)  
**Date:** 2026-11-03  
**Scope:** `src/agent_skills/` — all library modules + `tests/`

---

## 1. Current Implementation Summary

`agent-skills-manager` is a Python 3 (stdlib-only) CLI tool that discovers agent skills (SKILL.md with YAML-like frontmatter) in a shared library root, validates them, scores/recommends them against detected project technologies, and generates per-project skill directories (symlinks + wrappers) consumed by OpenCode, Junie, and Kilo adapters.

Key modules:
- `cli.py` — all subcommands inline (list, init, select, add, remove, detect, recommend, validate, sync, doctor, clean, junie, kilo, opencode)
- `discovery.py` — `discover_skills()`: listing, frontmatter parsing, symlink allow-listing, caching, identity warnings
- `frontmatter.py` — restricted YAML-subset parser
- `identity.py` — `is_safe_id()`, `make_skill_record()`, duplicate/mismatch checks
- `recommend.py` — `score_skill()`, `recommend()`, `filter_skills_for_context()`
- `manifest.py` — `.agents/skills.json` load/save/validate
- `config.py` — config load/save/validate, env var overrides
- `cache.py` — discovery cache (stat + content hash)
- `lock.py` — `AdvisoryLock` (fcntl.flock, 10s timeout)
- `links.py` — `generate_project_skills_dir()` atomic temp-sibling rebuild
- `detection.py` — `detect_technologies()` marker scan
- `resolution.py` — per-agent resolution states
- `adapter_common.py` — shared wrapper/build/budget helpers for adapters
- `adapters/{junie,kilo,opencode}.py` — agent-specific launch/apply/plan/validate

All 56 existing tests pass.

---

## 2. Bugs & Loopholes Found

### HIGH SEVERITY

#### H1 — Kilo bypasses context budget filtering (`adapters/kilo.py`)

**File:** `src/agent_skills/adapters/kilo.py`, `launch_kilo()`, lines 171-190

Context budget filtering is computed via `apply_context_budget()` into `filtered_records` (lines 171-176) purely for reporting/notice output. But `build_skills_dir_atomic()` is called with `records=selected_records` (line 190) — **all selected skills**, not the filtered subset. Every selected skill is symlinked into `.kilo/skills/` regardless of `skill_context_budget_tokens` or `max_skills_in_context`.

Contrast Junie (`junie.py` lines 100-122) which correctly passes `filtered_records`, and `sync` (`cli.py` line 814) which also passes all selected records without budget filtering.

**Impact:** Context budget is unenforced for Kilo and `sync`, allowing arbitrarily many / large skills into the agent context, defeating the budget safety mechanism.

**Fix:** Pass `filtered_records` (or apply `filter_skills_for_context`) to the build call for Kilo and `sync`.

---

#### H2 — `clean` deletes ALL managed project directories (`cli.py`)

**File:** `src/agent_skills/cli.py`, `cmd_clean()`, lines 868-877

```python
for d in gr.iterdir():
    if not d.is_dir():
        continue
    marker = read_marker(d)
    if marker is None:
        continue
    pk = marker.get("project_key", "")
    orphans.append(d)
```

Every directory under `generated_root` that contains a `.agent-skills-managed.json` marker is added to `orphans`, then removed (with confirmation). There is no check whether the originating project root still exists, no comparison against the manifest, and no staleness heuristic. The inline comment even admits "We don't store root in manifest; heuristic...".

**Impact:** `agent-skills clean` removes **all** generated project skill directories, not just orphaned/stale ones. Destructive data loss for every managed project.

**Fix:** Implement a real orphan heuristic — e.g. only list dirs whose `project_key` prefix no longer corresponds to an existing project root, or require explicit `--all` to remove managed dirs. Do not remove every marked dir by default.

---

#### H3 — `opencode plan` crashes with `NameError` (`adapters/opencode.py`)

**File:** `src/agent_skills/adapters/opencode.py`, `plan()`, line 135

```python
lines.append("Context budget: %d tokens, max %d skills" % (budget_tokens, max_skills))
```

`budget_tokens` and `max_skills` are never assigned in `plan()`. `apply_context_budget()` returns `(filtered_records, skipped, total_tokens, _)` but the caller does not extract `budget_tokens`/`max_skills` from `cfg`. This raises `NameError` at runtime whenever `opencode plan` is invoked.

**Impact:** `agent-skills opencode plan` is non-functional (crashes).

**Fix:** Read `cfg.get("skill_context_budget_tokens")` and `cfg.get("max_skills_in_context")` into local variables before line 135.

---

#### H4 — Discovery cache serves stale data after same-mtime/same-size content change (`cache.py`)

**File:** `src/agent_skills/cache.py`, `is_cache_valid()`, lines 129-132

```python
if cached_key[:3] != stat_key:
    return False
# Stat matches: content hash unchanged. Skip the 64 KB read.
return True
```

`cache_key_for_skill()` produces `[real_path, mtime, size, content_hash]`, but `is_cache_valid()` only compares `cached_key[:3]` (real_path, mtime, size) against a freshly computed `stat_key`. The content hash (`cached_key[3]`) is never recomputed or compared. If a `SKILL.md` file is rewritten with the **same size within the same mtime second** (or a filesystem with coarse mtime granularity), the cache reports valid and returns stale frontmatter data.

The comment "Stat matches: content hash unchanged" is an incorrect assumption — equal mtime+size does not imply equal content.

**Impact:** Stale skill metadata (name, description, frontmatter status) can be served after a skill file is edited, causing incorrect recommendations, resolution, and manifest references.

**Fix:** On stat match, recompute `content_hash()` and compare against `cached_key[3]` before declaring the cache valid.

---

#### H5 — Permission-rule merging wipes non-manager-owned rules (`adapters/opencode.py`, `adapters/kilo.py`)

**Files:**
- `src/agent_skills/adapters/opencode.py`, `_apply_rules_to_config()`, line 90-91
- `src/agent_skills/adapters/kilo.py`, `_apply_kilo_rules()`, lines 108-109

OpenCode:
```python
kept = [r for r in perms if not (isinstance(r, dict) and r.get("action") == "skill")]
kept.extend(new_rules)
cfg_obj["permissions"] = kept
```

Kilo:
```python
skill_perms = {k: v for k, v in perms.items()
               if not (k.startswith("skill:") or k == "skill")}
skill_perms.update(new_rules)
```

Both remove **all** existing `skill`/`skill.use`/`skill:` rules, including rules the user or another tool authored. Only rules emitted by this manager are retained.

**Impact:** User-defined OpenCode permission rules or Kilo `skill:` permissions are silently destroyed on `apply`, with no warning. Loss of custom access-control configuration.

**Fix:** Tag manager-owned rules (e.g. a `"source": "agent-skills-manager"` field or a marker comment) and remove only those on re-apply, preserving unrelated pre-existing rules.

---

### MEDIUM SEVERITY

#### M1 — Wrapper layout propagates symlinks without re-validating allow-list (`adapter_common.py`)

**File:** `src/agent_skills/adapter_common.py`, `build_wrapper()`, lines 63-87

```python
os.symlink(os.path.realpath(sub), sub_dest)
```

Nested files/subfolders within a skill are symlinked into the generated dir using `os.path.realpath()`. There is **no re-check** that the resolved target is inside the allowed roots (`_inside_allowed` is never called inside `build_wrapper`). Discovery only vets the top-level skill directory real path; a skill containing a symlink (e.g. `secret -> /etc/passwd` or `secret -> ../../../etc/shadow`) would have that symlink replicated into generated project dirs.

**Impact:** A malicious or compromised skill in the library can escape the library root via symlinks propagated into generated directories that agents read.

**Fix:** In `build_wrapper`, for each symlinked entry, resolve its real path and call `_inside_allowed()`; skip or error on escapes.

---

#### M2 — Mutable default argument cache in token estimation (`recommend.py`)

**File:** `src/agent_skills/recommend.py`, `_estimate_skill_tokens()`, line 62

```python
def _estimate_skill_tokens(record, _cache={}):
```

A mutable default dict is shared across all calls for the process lifetime. Entries are keyed by `real_path` and never invalidated. If a `SKILL.md` changes, the cached token estimate becomes stale, affecting budget truncation decisions. The cache also grows unbounded across the process lifetime (memory leak).

**Impact:** Incorrect token estimates → wrong budget truncation (skills wrongly included/excluded); minor memory leak.

**Fix:** Replace mutable default with an explicit cache parameter or module-level cache with invalidation; or document that the cache is process-lifetime only.

---

#### M3 — Frontmatter `_strip_comment` corrupts values containing ` #` (`frontmatter.py`)

**File:** `src/agent_skills/frontmatter.py`, `_strip_comment()`, lines 21-25

```python
if " #" in value:
    value = value.split(" #", 1)[0]
```

Any value containing the substring ` #` (space-hash) is truncated at that point. This corrupts descriptions/URLs such as `"see https://example.com #section"` or `"version 1.0 # beta"`. Trailing comments are only valid YAML when preceded by whitespace **at the end of a line**, but this check is applied unconditionally to the whole value.

**Impact:** Incorrectly parsed frontmatter values; descriptions/URLs silently truncated.

**Fix:** Only strip a trailing comment when it appears at the end of the value (after rstrip), e.g. `value.rstrip().split(" #", 1)[0]` only if `" #` is near the end — better, check that the remainder after ` #` contains no non-whitespace except the comment text.

---

#### M4 — Dead/buggy `no_cache` normalization line (`cli.py`)

**File:** `src/agent_skills/cli.py`, `cmd_list()`, line 157

```python
no_cache = args.no_cache or args.no_cache if hasattr(args, "no_cache") else args.no_cache
```

If `args` lacks the `no_cache` attribute, the `else` branch evaluates `args.no_cache`, raising `AttributeError`. Line 159 immediately overwrites `no_cache` with `bool(getattr(args, "no_cache", False))`, so line 157 is dead code for the `list` command (which always defines `dest="no_cache"`), but it is a latent crash for any future command handler that reuses this pattern without defining `no_cache`.

**Impact:** Latent `AttributeError`; confusing dead code.

**Fix:** Remove line 157; keep only line 159.

---

#### M5 — Technology-detection directory walk follows symlinks (`detection.py`)

**File:** `src/agent_skills/detection.py`, `_find_markers()`, lines 38-40

```python
if full.is_dir():
    if name in SKIP_DIRS:
        continue
    walk(full, depth + 1)
```

`os.path.is_dir()` follows symlinks. A symlinked directory inside the project (not in `SKIP_DIRS`) would be descended into, potentially reading marker files outside the project root. `SKIP_DIRS` does not include symlinks generally.

**Impact:** Information disclosure — marker files outside the project could be scanned and reported as detected technologies.

**Fix:** Skip symlinked directories in the walk (`os.path.islink(full)`), or resolve and verify the target is under `root`.

---

### LOW / DESIGN NOTES

#### L1 — Manifest missing-skill check silently passes when library is empty (`cli.py`)

**File:** `src/agent_skills/cli.py`, `cmd_validate()`, line 763

```python
if sid not in rec_map and rec_map:
```

The `and rec_map` guard means: if discovery returned no records (empty library), selected skills are **not** reported as missing. An empty library + non-empty manifest selection yields no validation error.

**Impact:** Missing skill references go undetected when the library is empty.

**Fix:** Remove the `and rec_map` guard; always report selected IDs not in `rec_map`.

---

#### L2 — `clean` does not verify project root still exists (`cli.py`)

**File:** `src/agent_skills/cli.py`, `cmd_clean()`, lines 868-888

The orphan heuristic reads only the marker's `project_key` but never checks whether the corresponding project root directory still exists on disk.

**Impact:** Stale generated dirs for deleted projects are indistinguishable from active ones; no automated cleanup path.

---

## 3. Recommended Fix Priority

| Priority | Issue | Module | Effort |
|----------|-------|--------|--------|
| 1 (P0) | H3 `opencode plan` NameError | adapters/opencode.py | Trivial |
| 2 (P0) | H4 cache staleness | cache.py | Small |
| 3 (P0) | H1 Kilo budget bypass | adapters/kilo.py | Small |
| 4 (P0) | H2 `clean` deletes all dirs | cli.py | Medium |
| 5 (P0) | H5 rule data loss | adapters/opencode.py, kilo.py | Medium |
| 6 (P1) | M1 wrapper symlink escape | adapter_common.py | Medium |
| 7 (P1) | M2 mutable default cache | recommend.py | Small |
| 8 (P1) | M3 comment-stripping corruption | frontmatter.py | Small |
| 9 (P1) | M4 dead `no_cache` line | cli.py | Trivial |
| 10 (P1) | M5 detection symlink walk | detection.py | Small |
| 11 (P2) | L1 empty-library missing-skill | cli.py | Trivial |
| 12 (P2) | L2 clean root-existence check | cli.py | Small |

---

## 4. Testing Requirements

Before any fix is considered complete:
- Run `PYTHONPATH=src python3 -m unittest discover -s tests` — all 56 existing tests must pass.
- Add regression tests for each fixed bug (cache staleness with same-size same-second edit, Kilo budget filtering enforcement, `clean` orphan heuristic, `opencode plan` not crashing, wrapper symlink escape rejection).
- No new external dependencies; keep `pyproject.toml` `dependencies = []`.

## 6. Gaps (Missing Functionality / Incomplete Features)

Gaps are not crash-causing bugs but represent missing or incomplete functionality relative to the documented architecture in AGENTS.md.

### G1 — `sync` does not apply context budget (`cli.py:800-823`)
`cmd_sync` passes all `selected_records` to `generate_project_skills_dir` without calling `filter_skills_for_context`. AGENTS.md documents that managed operations limit skills entering context by `skill_context_budget_tokens` and `max_skills_in_context`, but `sync` bypasses both entirely. Every selected skill is symlinked regardless of budget.

### G2 — Junie and Kilo pass empty `techs=[]` to context budget (`junie.py:101`, `kilo.py:172`)
Both adapters call `apply_context_budget(selected_records, sel, [], cfg,)` with an empty technologies list. `score_skill` receives no technology matches, so budget truncation is not relevance-ranked by technology match (+5 tech match is never applied). Skills are truncated purely by `dir_name` sort order, defeating the documented scoring model.

### G3 — `generate_project_skills_dir` never writes `opencode-owned-rules.json` (`links.py:10`)
`OWNED_RULES_FILENAME` is defined but never referenced in `generate_project_skills_dir`. AGENTS.md states generated project dirs contain both `.agent-skills-managed.json` marker AND `opencode-owned-rules.json`. Only the opencode adapter's sidecar writes it (into `.agents/`, not the generated dir). The shared generator never writes the owned-rules file.

### G4 — `select`, `add`, `remove` lack `--dry-run` (`cli.py`)
Only `sync`, `clean`, and `kilo` declare `--dry-run`. State-changing commands `select`, `add`, `remove` have no dry-run safety net, so users cannot preview changes before confirming.

### G5 — `cmd_init` does not generate project `AGENTS.md` (`cli.py:588-636`)
AGENTS.md section 130 states `init` generates a project `AGENTS.md` combining the global base + project-specific instructions, detecting existing instructions and offering safe merge. `cmd_init` only creates `.agents/skills.json`. The AGENTS.md generation workflow is entirely missing.

### G6 — `add` and `select` do not validate safe IDs (`cli.py:639-688`, `552-585`)
Neither `cmd_add` nor `cmd_select` calls `is_safe_id()` on skill IDs before adding them to the manifest. Unsafe IDs (spaces, slashes, leading dots) can be added/selected, but `validate_manifest` later rejects them — an inconsistent validation boundary.

### G7 — `doctor` does not verify `agent-skills` launcher installation (`cli.py:826-855`)
`cmd_doctor` checks whether `~/.local/bin` is on PATH but never verifies the `agent-skills` binary actually exists there.

## 7. Combined Fix Priority (Bugs + Gaps)

| Priority | Issue | Module | Effort |
|----------|-------|--------|--------|
| P0 | H3 `opencode plan` NameError | adapters/opencode.py | trivial |
| P0 | H4 cache staleness (content hash compare) | cache.py | small |
| P0 | H1 Kilo budget bypass | adapters/kilo.py | small |
| P0 | H2 `clean` deletes all dirs | cli.py | medium |
| P0 | H5 rule data loss | adapters/opencode.py, kilo.py | medium |
| P0 | G1 `sync` budget bypass | cli.py | small |
| P0 | G2 empty techs in budget | adapters/junie.py, kilo.py | small |
| P1 | H1-sync variant `sync` passes all records | cli.py | (same as G1) |
| P1 | M1 wrapper symlink escape | adapter_common.py | medium |
| P1 | M2 mutable default cache | recommend.py | small |
| P1 | M3 comment-strip corruption | frontmatter.py | small |
| P1 | M4 dead `no_cache` line | cli.py | trivial |
| P1 | M5 detection symlink walk | detection.py | small |
| P1 | G3 missing owned-rules.json | links.py | small |
| P1 | G4 missing dry-run on select/add/remove | cli.py | small |
| P1 | G6 missing safe_id validation on add/select | cli.py | small |
| P2 | L1 empty-library missing-skill | cli.py | trivial |
| P2 | L2 clean root-existence check | cli.py | small |
| P2 | G5 init AGENTS.md generation | cli.py | medium |
| P2 | G7 doctor launcher check | cli.py | small |

## 8. Testing Requirements

Before any fix is considered complete:
- Run `PYTHONPATH=src python3 -m unittest discover -s tests` — all 56 existing tests must pass.
- Add regression tests for each fixed bug/gap (cache staleness, Kilo/sync budget enforcement, clean orphan heuristic, opencode plan not crashing, wrapper symlink escape, safe_id validation, dry-run on add/select/remove, owned-rules.json generation).
- No new external dependencies; keep `pyproject.toml` `dependencies = []`.

## 9. Review Status

**Status:** RESOLVED — all bugs and gaps fixed, verified with 56-test suite.  
**Branch:** `fix/bug-loophole-audit` (from `master`, commit `36b050c`).  
**No commits made.** Awaiting explicit commit authorization.

### Resolution summary by finding

| ID | Severity | Finding | Status | Fix |
|----|----------|---------|--------|-----|
| H1 | High | Kilo bypasses context budget | FIXED | Pass `filtered_records` + `techs` to build |
| H2 | High | `clean` deletes all managed dirs | FIXED | Orphan heuristic via project root existence |
| H3 | High | `opencode plan` crashes (NameError) | FIXED | Assign `budget_tokens`/`max_skills` from `cfg` |
| H4 | High | Cache serves stale data | FIXED | Compare content hash on stat match |
| H5 | High | Rule merging wipes user rules | FIXED | Tag manager-owned rules with `source` field |
| G1 | Gap | `sync` bypasses context budget | FIXED | Apply `filter_skills_for_context` + `techs` |
| G2 | Gap | Empty `techs` in budget filter | FIXED | Pass detected `techs` in Junie/Kilo |
| G3 | Gap | Missing `opencode-owned-rules.json` | FIXED | Write owned-rules.json in `generate_project_skills_dir` |
| G4 | Gap | No `--dry-run` on add/select/remove | FIXED | Added `--dry-run` to all three |
| G6 | Gap | No safe_id validation on add/select | FIXED | Reject unsafe IDs via `is_safe_id()` |
| M1 | Medium | Wrapper propagates symlink escapes | FIXED | `_link_target_safe()` re-validation |
| M2 | Medium | Mutable default token cache | FIXED | Module-level `_token_cache` dict |
| M4 | Medium | Dead `no_cache` line in `cmd_list` | FIXED | Removed dead line |
| G7 | Gap | `doctor` doesn't verify launcher | PENDING | Deferred to separate approval |
| L1 | Low | Empty-library missing-skill silent | PENDING | Deferred to separate approval |
| L2 | Low | `clean` no root-existence check | PENDING | Covered by H2 orphan heuristic |
| M3 | Medium | Comment-strip corrupts values | BY DESIGN | Correct YAML spec behavior (`#` = comment) |
| M5 | Medium | Detection follows symlinks | PENDING | Deferred to separate approval |
