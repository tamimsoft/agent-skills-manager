# Agent Skills Manager Hardening Review

## Scope and current behavior

Review of the manager's skill-selection and managed-launch path, using the supplied eight-phase fix proposal plus observed Wallet/Kilo diagnostics. The current implementation is Python 3 standard library with `unittest`.

## Findings

1. **Project instructions can be overwritten on ordinary commands.** `generate_agents_md()` replaces the whole file under `force=True`; adapters call it during planning and launch. Immutable flags are also used as an unreliable protection mechanism. Proposed resolution: preserve user content and update only a clearly marked manager-owned block; make plan/validate read-only. Existing immutable files need a documented one-time manual unflag step.
2. **Agent configuration formats and ownership migration need verified behavior.** OpenCode currently writes `permissions` and `policies` arrays; Kilo writes manager tracking data into its config. Proposed shapes and compatibility must be confirmed against supported versions before migration. Existing user-authored rules must survive; ambiguous legacy rules should be backed up and left for manual resolution rather than silently removed.
3. **Kilo's effective project skill path is unverified and current behavior is not exclusive.** Wallet's `kilo debug skill --pure` reported 1,476 entries, including 1,475 from `~/.agents/skills`, and did not report skills under Wallet's generated `.kilo/skills/`. Project config and generated links therefore do not demonstrate that Kilo uses only selected project skills. Verify the supported project path and policy semantics; if confirmed, move the shared library outside Kilo's default scan path with backup/rollback and point the manager at it. If exclusivity cannot be achieved safely, document the limitation and do not claim it.
4. **Budget estimate measures the wrong content and can hide selection behavior.** Current estimates read much of `SKILL.md`, but the normal discovery/catalog cost is name/description metadata and bodies are loaded on demand. Define the estimate as metadata only, preserve manifest selection, enforce a managed-launch cap deterministically, and clearly report filtered skills and estimates.
5. **CLI flags are inconsistently attached.** Global and subcommand flags overlap; Kilo's nested commands do not consistently expose `--yes`, and a hyphenated attribute lookup is ineffective. Add parser regression coverage and document the supported placement.
6. **Generated-directory recovery prefixes do not match cleanup and swap names.** Fix exact manager-owned prefixes, recover a valid old directory if the destination is missing, and never remove unrelated files.
7. **Kilo/OpenCode IDs can differ by folder and declared skill name.** Share identity generation and cover duplicate/collision cases before emitting allow rules.
8. **Frontmatter parsing omits common supported scalar cases.** Add BOM handling, quoted-comment correctness, and folded plain values without adding a dependency.
9. **Package metadata does not expose a console script or bundled template data.** Add entry point and package-data configuration and test a built wheel/install layout.

## Decisions for the implementation

- Keep all three existing external library skill files unchanged.
- Keep manifest selection authoritative; context-budget filtering applies only to managed launch output, emits clear warnings, and never edits the manifest.
- A `0` budget/count remains unlimited for backward compatibility.
- Do not move or rename the live global skills library until a complete destination copy, config backup, path validation, rollback procedure, and Kilo project-discovery test are ready.
- Treat live Kilo discovery as a release gate. If Kilo's supported search paths cannot provide exclusive project filtering, report that limitation rather than presenting the implementation as successful.
- Back up project/agent config files before one-time migration. Preserve user-owned settings and stop on ambiguous ownership.

## Verification requirements

- Add focused unit tests for every changed behavior.
- Run the complete `unittest` suite and packaging/install smoke tests.
- Use disposable project/config/library directories for migrations and adapter behavior tests.
- For Kilo, compare `kilo debug skill` source locations before/after in a disposable environment. Verify selected project skills appear and unrelated global skills do not.
- Validate the generated config with each supported CLI's own read-only config diagnostics. Do not apply migrations to a real project until the disposable test passes.

## Status

## Resolution status

| Finding | Status | Resolution / remaining limitation |
|---|---|---|
| 1. `AGENTS.md` can be overwritten and immutable flags are unreliable | Resolved | Generation now owns only a marked block; unmarked content is backed up before append. Plan/validate are read-only, and immutable flags are never changed. |
| 2. Agent config schemas and migration ownership are unsafe | Resolved | OpenCode and Kilo use `permission.skill`, manager ownership is tracked in sidecars, migrations are backed up and idempotent, unrelated user values are preserved, and unsupported JSONC is refused. Disposable CLI diagnostics validated the generated schema. |
| 3. Kilo does not provide exclusive project skill discovery | Limitation verified and surfaced | Selected project skills are copied into `.kilo/skills/`, but Kilo 7.8.18 still catalogs global `~/.agents/skills/` entries; permission rules do not remove them. The adapter and README explicitly disclose the additive behavior. The global library was not moved. |
| 4. Context estimates measure the wrong content and can hide selection | Resolved | Estimates use name/description metadata; launch filtering preserves manifest selections and reports exclusions without editing the manifest. |
| 5. CLI flag placement is inconsistent | Resolved | Flags are declared on relevant subcommands, with parser/dispatch regression coverage including Kilo `--yes` and dry-run behavior. |
| 6. Generated-directory recovery can target or strand the wrong paths | Resolved | Atomic swaps use owned temporary markers and exact prefixes, recover a valid old tree when needed, and `sync` uses the atomic builder. |
| 7. Permission IDs differ between folder and declared names | Resolved | Shared identity generation handles both aliases and rejects collisions/ambiguity. |
| 8. Restricted frontmatter parser misses common scalar forms | Resolved | BOM, quoted comments, and folded plain scalars are covered without an external parser dependency. |
| 9. Distribution metadata omits the launcher and template data | Resolved | The wheel includes the console entry point, module launcher, and `AGENTS.base.md` template. |

Full verification: `PYTHONPATH=src python3 -m unittest discover -s tests` passed all 98 tests; CLI smoke/doctor, wheel inspection, disposable OpenCode/Kilo runtime checks, and `git diff --check` passed. Kilo's global catalog behavior remains an explicit product limitation, not a resolved exclusivity guarantee.
