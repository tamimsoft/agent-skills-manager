# Phase 1: Manager Repository, Configuration, and Discovery

**Title:** Phase 1 — Manager repository, configuration, and discovery
**Date:** 2026-10-31
**Status:** COMPLETED
**Owner:** tamim

## Objective

Create the manager repository and implement configuration, frontmatter parsing, identity model, skill discovery with mtime-keyed cache, and a `list` command. No installation to `~/.local/` yet.

## Scope

- Repository scaffold (pyproject.toml metadata only, no runtime deps).
- Config module (`config.py`) with schema v1, env overrides, validation, backup on write.
- Frontmatter parser (`frontmatter.py`) for the supported YAML subset.
- Identity module (`identity.py`): dir_name, declared_name, agent_id.
- Discovery (`discovery.py`): scan library, build skill records, safe IDs, allow-list roots.
- Cache (`cache.py`): mtime-keyed, `--no-cache` bypass.
- Validation (`validation.py`): basic cross-component checks.
- CLI (`cli.py`, `__main__.py`): `list` command with `--selected`, `--filter`, `--tech`, `--json`, `--no-cache`.
- Unit tests with fixtures under `tests/`, fully isolated via env overrides.

## Requirements

- Python 3.9 floor (no `X | Y` types, no `match`).
- stdlib only.
- Tests never touch real `~/.agents`, `~/.config`, `~/.junie`, `~/.local`.
- Custom skills (`flutter-tamim`, `hive-db-tamim`, `isar-db-tamim`) discovered with `frontmatter_status = missing`; not an error.
- 9 declared-name/folder mismatches reported as warnings.

## Risks

- Frontmatter subset must not crash on unsupported constructs (warning, not error).
- Discovery performance: cold scan of ~1,500 skills within budget; warm cache near-instant.
- Safe IDs: reject traversal, path separators, NUL, leading dot, unicode/spaces reported but not selectable.

## Approval status

Approved by user on 2026-10-31.

## Completion summary

Implemented repository scaffold, config module, frontmatter parser, identity module, discovery with mtime cache, validation, CLI `list` command, adapters (placeholders), and 25 unit tests (all passing). Cold/warm discovery of 1,436 skills ~0.24s. Custom skills without frontmatter discovered as `missing` (not an error). 9 name-folder mismatch warnings reported. No installation to `~/.local/` performed.
