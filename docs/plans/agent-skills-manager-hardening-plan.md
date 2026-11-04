# Agent Skills Manager Hardening Plan

## Objective

Implement the supplied eight-phase hardening proposal while preserving user-authored project instructions/configuration, keeping selection separate from launch-time context limits, and proving Kilo behavior rather than inferring it from generated files.

## Approved scope and constraints

- Python 3.9+, standard library only, existing flat `src/agent_skills/` layout, `unittest`.
- No changes to the three external frontmatter-less library skills.
- No commit until all in-scope checks and review pass. The user authorized a commit at successful completion.
- Preserve existing worktree changes. Work on the current `docs/polish-global-agent-rules` branch; do not switch branches or discard existing changes.
- Any global-library relocation is a separate, reversible operation: copy and verify first, save config backup, validate the new configured root, then rename the old scanned path to a reversible backup only after the Kilo isolation test passes. Never recursively delete the old library.

## Design decisions

- `AGENTS.md`: only update an explicit `<!-- agent-skills:begin -->` / `<!-- agent-skills:end -->` block. Preserve all surrounding text. Back up an unmarked existing file under `.agents/backups/` before first append. Reject malformed or repeated markers. `plan` and `validate` are read-only. Since code will no longer toggle immutable flags, document the one-time manual removal of legacy immutable flags before first update.
- Context budget: estimate the name/description metadata actually catalogued, not full skill bodies. Keep the manifest's `selected` list unchanged; deterministically filter managed-launch output to the configured token/count limit and report all exclusions. `0` continues to mean unlimited. This is a launch cap, not a manifest-selection cap.
- Kilo: do not assume `.kilo/skills/` is consumed. The official/runtime research gate must identify a supported project skill path and whether permissions hide discovery or only invocation. If project skill placement and global-library isolation can be proven, implement them and test actual catalog locations. Otherwise document the verified limitation and do not claim exclusive Kilo support.
- Config migration: validate desired OpenCode/Kilo shapes using supported CLI versions in disposable configs before applying. Back up config before migration; preserve unrelated/user-authored values; abort on ownership ambiguity. Refuse JSONC files the manager cannot preserve.

## Phases and acceptance criteria

1. **Kilo behavior gate** — `COMPLETED WITH LIMITATION`
   - Verify official Kilo skill paths, permissions shape/effect, and diagnostic output.
   - Test a disposable project with selected, excluded, and global-only skills.
   - Acceptance: evidence distinguishes discovered catalog entries from generated files. Do not claim exclusivity unless the Kilo catalog confirms it.
2. **Protect AGENTS.md** — `COMPLETED`
   - Extract managed-block logic to `agents_md.py`; preserve all non-manager content and make first append backed up and recoverable.
   - Remove immutable-flag manipulation. Make adapter plan and validate operations read-only.
   - Tests: absent file, unmarked existing file/backup, marked replacement, malformed markers, unchanged surrounding text, read-only plan/validate.
3. **Correct config schemas and migration** — `COMPLETED`
   - Implement verified OpenCode and Kilo shapes, refusal for unsupported JSONC, ownership sidecars, safe one-time migration, idempotence, and backup.
   - Preserve user-authored rules; abort instead of guessing when ownership is ambiguous.
   - Tests: schema shape, allow/deny precedence assumptions, unrelated settings preservation, migration twice, ambiguity, JSONC refusal.
4. **Make context budget meaningful** — `COMPLETED`
   - Estimate name + description metadata; retain manifest selections; filter only managed launch payloads; produce explicit exclusion and estimate output.
   - Verify scores/tie ordering and unlimited values remain compatible.
5. **Normalize CLI flags** — `COMPLETED`
   - Put `--yes` and `--dry-run` on relevant subcommands using shared parser options; fix `kilo run --yes` and malformed attribute access.
   - Document any changed syntax and add parser/dispatch tests.
6. **Harden generated-directory swaps** — `COMPLETED`
   - Use exact temp/old prefixes, recover a valid old tree when destination is absent, and ensure cleanup only targets manager-owned paths.
   - Route `sync` through the atomic builder and remove duplicate generator only after callers/tests migrate.
7. **Unify skill identities** — `COMPLETED`
   - Share ID calculation across adapters; account for folder and declared names when different; reject collisions/ambiguous IDs.
   - Add adapter and collision tests.
8. **Improve restricted frontmatter parsing** — `COMPLETED`
   - Strip UTF-8 BOM, parse quoted scalars before comment stripping, fold multiline plain scalars, retain unsupported-YAML warnings.
   - Add edge-case tests; no PyYAML or other dependencies.
9. **Packaging, docs, and end-to-end validation** — `COMPLETED`
   - Add console entry point and include `templates/*.md` in built distributions.
   - Correct README claims for Kilo discovery, AGENTS ownership, budget behavior, and test coverage; include migration notes.
   - Run all unit tests, wheel/install smoke test, CLI help/doctor, and disposable adapter tests. Review complete diff and update review/plan status.
10. **Commit verified work** — `IN_PROGRESS`
    - Commit only after all acceptance criteria pass and no unresolved blocking issues remain. Use a concise Conventional Commit message and required co-author trailer. Do not push.

## Verification record

- `PYTHONPATH=src python3 -m unittest discover -s tests`: 98 tests passed.
- CLI version, root help, OpenCode help, Kilo help, and read-only `doctor --json`: passed. Doctor reported zero errors.
- Built a wheel in a temporary virtual environment with the declared setuptools build backend; verified the `agent-skills` console entry point, `agent_skills/__main__.py`, and `templates/AGENTS.base.md` are packaged.
- `git diff --check`: passed.
- Disposable OpenCode 2.2.5 apply/migration and `debug config --standalone` confirmed parsed `permission.skill` wildcard-deny and explicit allow rules.
- Disposable Kilo 7.8.18 checks confirmed copied project-selected skills are catalogued from `.kilo/skills/`. Kilo continues to catalogue global `~/.agents/skills/` entries, and `permission.skill` does not hide them. The adapter reports this limitation; no global library relocation was performed.
- No files in the global skills library were changed.

## Risks and rollback

- Config schema uncertainty: no production write until the disposable integration test validates the exact config.
- Kilo cannot be made exclusive solely by project config if global discovery remains active; stop short of claiming success if no supported isolation path exists.
- Library relocation can affect all agents: copy/verify first, retain the original as a named backup, and restore config/path if any CLI diagnostic fails.
- Existing `AGENTS.md` immutable flags may block updates. Document explicit manual unflag instructions; do not silently change filesystem flags.
- Existing branch includes unrelated-to-this-plan work from earlier user requests; review and commit only changes in the approved task scope, leaving unrelated edits untouched.
