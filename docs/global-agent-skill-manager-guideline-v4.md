# Global Agent Skill Manager
## Implementation Guideline for OpenCode, Junie, and Kilo (v4)

**Project:** Global Agent Skill Manager
**Platform:** macOS (zsh)
**Supported agents:** OpenCode CLI 2.2.5, Junie CLI 26.10.27, Kilo Code CLI **7.8.18** (confirmed via `kilo --version`; binary `kilo`, npm `@kilocode/cli`)
**Implementation language:** Python 3, standard library only
**Shared skill library:** `~/.agents/skills/`
**First integration target:** Digital Pharmacy (Flutter)
**Digital Pharmacy branch:** `chore/agent-skills-manager` (base: `dp-dev-tamim`)
**Document status:** `AWAITING_APPROVAL`
**Incorporates:** external technical review `global-agent-skill-manager-v3-technical-review.md` (all 10 findings accepted; see §0.2)

---

# 0. Revision Notes (v3 -> v4)

## 0.1 Version correction (not a review finding — a direct fact check)

`kilo --version` returns **7.8.18**, not "1.0+". v3's Kilo-specific facts (compatibility directories, skill-dir layout, config file names) came from documentation that described "Kilo CLI 1.0 and later" in general terms. A six-major-version gap between the documented baseline and the installed binary means **none of those facts can be trusted without re-confirmation against 7.8.18 specifically**. Phase 0 (§6) now treats every Kilo-specific fact from v3's §0.1/§3/§5.6 as unverified again, not as background that only needed a version-mismatch warning.

## 0.2 Review findings incorporated

All 10 findings (R-01 to R-10) from the external review are accepted. Three change the architecture, not just add caveats:

- **R-01 (context-reduction measurability):** added a measurement protocol (§2.1) that separates "skills discovered," "metadata exposed to the model," "full instructions loaded," and other context sources. Nothing in this document claims a context reduction without agent-provided evidence.
- **R-03 (per-agent skill resolution):** replaced the single vague "unresolved" tag with a defined four-state resolution model (§2.2) computed per skill per agent.
- **R-09 (skill trust and provenance):** added an explicit untrusted-content model (§2.3): skill scripts and remote references are never executed or followed by the manager at any stage.

The remaining seven (R-02, R-04 through R-08, R-10) sharpen specific sections; each is addressed where it applies, cross-referenced below.

| Finding | Where addressed |
|---|---|
| R-01 | §2.1 (new), §15 (testing), §16 (acceptance) |
| R-02 | §2 (terminology), §13 (Kilo phase), unchanged from v3 otherwise |
| R-03 | §2.2 (new), §9.1 (manifest/CLI), §16 |
| R-04 | §5.5, §6.2 (V18, V21), §13.2 |
| R-05 | §2 (terminology), §12.1, §6.2 (V2-V5 reframed) |
| R-06 | §8.2 (fixed: `KILO.md` now local-only by default) |
| R-07 | §7.2 (cache keys expanded) |
| R-08 | §6.2 (V19), §13.3, §11.4 |
| R-09 | §2.3 (new), §4 |
| R-10 | §9.1 (state-transition table, new) |

## 0.3 Terminology (resolves R-02 and R-05 together)

v3 used "exclusive" loosely for all three adapters. v4 fixes this with three defined guarantee levels, used consistently everywhere below:

| Term | Meaning |
|---|---|
| **Exclusive** | Unselected skills are demonstrably unavailable to the agent — not just denied by a rule, but actually not loadable. Requires verification, not just the presence of a restriction mechanism. |
| **Access-filtered** | A rule prevents selected use of unselected skills, but the agent may still discover, scan, or expose metadata for them. Discovery cost and context exposure are not necessarily reduced. |
| **Additive** | The agent's own default behavior is untouched; the manager only adds the project's selected skills with higher precedence. No claim of restricting anything else. |

No phase may describe an adapter as "exclusive" until the relevant Phase 0 experiment demonstrates it. Until then, OpenCode is assumed **access-filtered** (pending V2-V5) and Kilo is assumed **additive** (pending V14). Junie is the only adapter with a plausible path to **exclusive**, pending V6-V9.

---

# 1. Open Decisions (confirm before Phase 1)

Unchanged from v3 (D1-D5; see that document for full text: custom-skill wrapper strategy, manager repo location, Python floor, `.gitignore` as the ignore mechanism, and Kilo's compatibility-directory handling). No new open decision is introduced in v4 — the review's findings were specification gaps, not user-facing forks, except where §0.1 and §8.2 resolve them outright.

---

# 2. Project Objective

Build a reusable global skill management system so **OpenCode, Junie, and Kilo** use the same centralized skill library while loading only the skills relevant to each project, **to the extent each agent's own design and verified behavior actually allows** — see §0.3 for the guarantee levels used to describe this honestly per agent.

The system must:

1. Maintain one centralized skill library.
2. Discover available skills automatically.
3. Recommend skills from project technologies (deterministic, offline, explainable).
4. Let users select skills per project, always with explicit confirmation.
5. Integrate with OpenCode, Junie, and Kilo through independent adapters, each labeled with its actual guarantee level (§0.3).
6. Never duplicate or modify original skill content.
7. Treat all skill content as untrusted input (§2.3).
8. Apply consistent engineering rules to all three agents.
9. Keep AI and agent configuration out of Git.
10. Keep engineering plans and reviews in Git.
11. Provide reliable validation, error handling, and diagnostics.
12. Measure what it actually changes, not merely what it was intended to change (§2.1).

**Do not build a Digital Pharmacy-specific solution.**

## 2.1 Context-reduction measurement protocol (R-01)

"Reduces context" is not one measurement. The manager must distinguish:

1. **Discovered/indexed skills** — directories an agent's scanner finds, regardless of whether any are ever used.
2. **Metadata exposed to the model** — names and descriptions the agent actually puts in front of the model (observable only where the agent exposes this; otherwise marked `unavailable` — never estimated).
3. **Full skill instructions loaded** — the complete `SKILL.md` body loaded into a live context during an actual task (observable only via the agent's own debug output or a documented listing command, per V9/V20).
4. **Other context sources** — project instructions (`AGENTS.md`, `KILO.md`), MCP tool descriptions, system prompts, agent-generated summaries. The manager does not claim to affect these.

**Measurement rule:** for each agent, before and after integration, run the same small set of repeatable prompts/tasks against the same project state, and record:

- Count of discovered skill directories.
- Count of metadata entries exposed (where observable).
- Count of full skill bodies loaded during the fixed task (where observable).
- Initial and total context tokens (where the agent exposes reliable token counts).
- Startup and discovery time.
- Whether an unselected skill can still be loaded or invoked when explicitly requested in the task.

Record agent version, model, project state, and the exact task text alongside every measurement. **A metric that cannot be observed is labeled `unavailable`, never estimated or implied.** No phase, document, or CLI message may claim a token or context reduction without this evidence attached.

## 2.2 Per-agent skill resolution model (R-03)

The manifest keeps one shared `skills.selected` list — the user's project-level intent is a single list, not per-agent lists, unless a real need for divergence appears later (the review explicitly recommends not over-engineering this upfront). On top of that single list, the manager computes a **resolution result per selected skill per enabled agent**:

| State | Meaning |
|---|---|
| `available` | The skill is selected, its agent identifier resolves cleanly, and it is actually exposed to that agent (per the agent's verified mechanism). |
| `unavailable` | The skill is selected but cannot be exposed to that agent at all (for example: OpenCode rejects a skill with no frontmatter, per V1). |
| `unresolved` | The skill's identifier cannot be determined for that agent yet (verification pending, or a parsing ambiguity). |
| `conflict` | The skill's identifier collides with another skill already visible to that agent (for example, a `declared_name` collision between the shared library and Kilo's own `~/.kilo/skills/`, per V16). |

Rules:

- `validate` and `list --selected` show this per-agent breakdown, with a reason string, not just a pass/fail.
- A skill `unavailable` in one adapter must never silently become `available` under a different identity in another adapter without that being visible in the resolution output.
- No per-agent *selection* override is introduced in this version — only per-agent *resolution reporting*. If a real case later requires selecting different skills per agent, that is a deliberate schema change, not a default.

## 2.3 Skill trust and provenance model (R-09)

Skill content (scripts, examples, instructions, remote references) is **untrusted input**, regardless of whether it lives in the shared library or a project-local directory. Rules, binding on every phase:

- The manager never executes a skill's scripts or embedded commands during discovery, validation, recommendation, or apply — at any phase, for any reason, including "just to test it works."
- The manager never automatically follows a remote reference (URL, download instruction) found inside skill content.
- Where known, the manager records a skill's source/origin (for example: "present in the shared library at discovery time," or "added by the user on <date>" if that becomes trackable) — this is informational, not a safety proof.
- Static discovery and validation never claim to prove a skill is safe to use; they only report structural issues (malformed frontmatter, suspicious or unsupported layouts) without modifying the source.
- Any future feature that would execute skill content is explicit, separately scoped, and separately approved — never bundled into discovery/validation/apply.

**Known asymmetries across agents (§0.3 terminology applies):**

- **Junie** — potentially exclusive when launched through `agent-skills junie`; a plain `junie` invocation still loads everything in `~/.junie/skills/`. Verify via V6-V9.
- **OpenCode** — access-filtered at best until V2-V5 prove otherwise; the shared library may still be scanned in full regardless of the permission rules.
- **Kilo** — additive at best until V14 proves a disable mechanism exists on 7.8.18 specifically; the shared library is loaded by default independent of the project selection.

---

# 3. Existing Environment (to verify, not assume)

| Component | Expected configuration |
|---|---|
| OS / shell | macOS, zsh |
| Home | `/Users/tamimhasan` (resolved dynamically; never hardcoded) |
| OpenCode | 2.2.5, config at `~/.config/opencode/` |
| Junie | 26.10.27, skills at `~/.junie/skills/`, settings at `~/.junie/settings.json` |
| Kilo | **7.8.18 (confirmed)**, binary `kilo`; all other Kilo facts (config paths, skill directories, compatibility-directory behavior) are **unconfirmed for this version** and must be re-checked in Phase 0, not carried over from v3's documentation-sourced assumptions |
| Python | Verify version (D3) |
| Shared skills | `~/.agents/skills/` |

Reported inventory (re-verify in Phase 0): about 1,435 global skills; 68 Junie skills, all present in the global library; no duplicate folder names found; duplicate frontmatter `name` values across directories were never checked and must be, across three agents' identifier schemes; collisions between `~/.agents/skills/` and `~/.kilo/skills/`/`~/.claude/skills/` are unknown.

Custom skills requiring special handling: `flutter-tamim`, `hive-db-tamim`. Missing frontmatter is intentional; files and directory structure remain byte-identical for all three agents; never inject generated frontmatter into the originals.

---

# 4. Non-Negotiable Engineering Rules

Unchanged from v3 (§4): requirement analysis and approval gates per phase; never overwrite, delete, or modify without inspection; no destructive Git commands; no secrets in logs or tracked docs; implement only approved scope; Git commits require explicit, exact-message approval; tracked-document redaction; version-mismatch warnings.

**Addition (R-09):** the trust and provenance model in §2.3 is binding at every phase, not only in the discovery module. Any phase plan that would have the manager execute, render, or evaluate skill content as code must stop and flag it rather than proceeding.

---

# 5. Target Architecture

## 5.1 Repository and install layout

Unchanged from v3 (§5.1): separate manager repository; `adapters/{junie,opencode,kilo}.py`; `agent_paths` in config includes `kilo`.

## 5.2 Responsibilities

Unchanged (v3 §5.2), with one addition: a `resolution.py` module implementing §2.2's four-state model, called by `validate`, `list --selected`, and each adapter before it acts.

## 5.3 Identifier model

Unchanged three-field model (`dir_name`, `declared_name`, `agent_id[agent]`). **Collision rule (R-10/gaps table):** a detected collision is always surfaced as a `conflict` resolution state (§2.2) with both colliding sources named. The manager **never silently renames a skill** to resolve a collision — renaming is a user decision, presented through `validate`'s output, not an automatic remediation.

## 5.4 Symlink and path policy

Unchanged from v3 (§5.4): allow-listed real-path roots, including `~/.kilo/skills/` as a legitimate Kilo-specific destination root (pending V15).

## 5.5 Ownership of generated artifacts (R-04 expanded)

Unchanged marker mechanism (`.agent-skills-managed.json`; OpenCode's `opencode-owned-rules.json` sidecar) **with explicit atomic-replacement and crash-recovery semantics**, since "atomic refresh" alone is not a complete specification when a destination already exists:

- **Build-then-swap:** generate the new state in a sibling temp path (`<target>.tmp-<pid>-<random>`), validate it fully, then perform the swap as a single `rename()` onto the final path. A `rename()` onto an existing directory is not atomic on all filesystems, so the swap target for a directory is: rename the old directory aside (`<target>.old-<pid>`), rename the temp into place, then remove the old one — and if the process dies between the two renames, the next run detects a leftover `<target>.old-*` and `<target>.tmp-*` and cleans them up itself during the next `apply`/`sync`/`validate --repair`, rather than leaving the project in a half-migrated state silently.
- **Lock file:** an advisory lock (`fcntl.flock`) guards the whole build-then-swap sequence per generated location. A second concurrent writer waits briefly, then fails clearly rather than interleaving writes (R-04, also directly relevant to V21).
- **Marker placement for Kilo specifically:** since `.kilo/skills/` is itself a directory Kilo scans, whether a hidden marker file there is ignored by Kilo is **unverified** (V18). If V18 shows Kilo chokes on or misreports a hidden file inside a scanned directory, the marker for Kilo moves **outside** the scanned directory (for example, under the project's `.agents/` directory, keyed by project), and `.kilo/skills/` contains only the actual skill symlinks. This decision is made from evidence, not assumed either way going in.
- **Manual-replacement detection:** before any refresh, the manager compares the current state of each managed entry against what the marker recorded. If a managed entry was manually replaced (no longer a symlink to the recorded source, or missing), it is reported as a conflict requiring confirmation, not silently overwritten — this covers the review's "what happens when a managed link is replaced manually" question directly.

## 5.6 Generation strategy per agent

Unchanged mechanism table from v3 (§5.6: Junie external+flag, OpenCode permission list, Kilo in-place `.kilo/skills/` pending V15), with the Kilo row's marker-location caveat from §5.5 above, and the explicit note that Kilo's row is labeled **additive** per §0.3 unless V14 changes that.

## 5.7 Cache design (R-07)

v3's cache (keyed by `SKILL.md` mtime and size) is replaced with an explicit, fuller key:

- Resolved real path of the library root (and any additional allowed roots).
- Per-skill: resolved real source path, `SKILL.md` mtime, size, **and** a fast content fingerprint (e.g. a cheap hash) so a file replaced with the same size and timestamp is still detected — content hashing is applied here, where the review explicitly flagged a concrete correctness gap, not added elsewhere by default.
- Manager/parser schema version (a bump invalidates the whole cache).
- User-authored metadata override version (`skill_overrides` in config) — changing an override invalidates just that skill's cached record.
- Presence/absence of each previously-seen skill directory, so a rename or removal is detected even though no single file's mtime changed (directly answers V22 and the review's stale-cache scenarios).

`--no-cache` bypasses it for diagnostics; `doctor` reports cache staleness explicitly rather than silently serving old data.

## 5.8 Project root

Unchanged from v3 (§5.7), with fixtures added in Phase 9 for worktrees, monorepos with nested manifests, and symlinked project roots (gaps table item).

---

# 6. Phase 0: Environment Inspection and Verification Experiments

Unchanged constraint reconciliation from v3 (§6.1: read-only inspection; redact before any tracked document; experiments run only in a sandbox, never against the real library or real configs).

## 6.1 Inspection tasks (updated for the version fact)

1-8. Unchanged from v3 (Python, OpenCode, Junie versions; library inventory; configs; `PATH`; Digital Pharmacy git state; `doc/review/` references).
9. **Run `kilo --version` and `kilo --help` fresh, against the actual installed 7.8.18, and do not reuse any v3 fact sourced from general "1.0+" documentation without re-deriving it from this output or a sandboxed experiment.**
10. Inspect `~/.config/kilo/kilo.jsonc` structure (redact secret values).
11. List `~/.kilo/skills/` and compare names against `~/.agents/skills/` for collisions.
12. Check whether "Claude Code Compatibility" is enabled for Kilo.

## 6.2 Verification experiments

All of v3's V1-V17 remain, now explicitly re-scoped to 7.8.18 for the Kilo-specific ones (V13-V17), plus five additions from the review:

| ID | Question | Design impact |
|---|---|---|
| V18 | Does Kilo (7.8.18) ignore a hidden marker file (`.agent-skills-managed.json`) placed inside a directory it scans for skills, such as `.kilo/skills/`? | §5.5 marker placement; if it interferes, the marker moves outside the scanned directory |
| V19 | Do all three agents correctly resolve relative resource references (nested folders, scripts, paths with spaces) through the proposed symlink/wrapper layouts? | §11.4 (Junie wrapper), §13.3 (Kilo wrapper); wrapper layout must preserve original relative directory structure, not flatten it |
| V20 | Can any of the three agents expose reliable evidence distinguishing discovered skills from metadata-exposed skills from fully-loaded skill bodies? | §2.1; determines which context-reduction metrics are `unavailable` vs measurable |
| V21 | What happens when the manager process is interrupted mid-refresh, or two `apply`/`sync` invocations run concurrently? | §5.5 crash recovery and locking; must be reproduced in a sandbox, not the real project |
| V22 | Does changing a skill's symlink target, or a `skill_overrides` metadata entry, correctly invalidate the discovery cache? | §5.7 cache invalidation correctness |

As before, a result that contradicts a design assumption stops the process for review before Phase 1.

## 6.3 Deliverable

Same as v3 (§6.3), now covering V1-V22 and the updated Kilo version fact. **A separate Phase 0 verification plan document** (method, expected evidence, and stop conditions for each experiment) is produced alongside this guideline, per your decision to do both in this pass.

**Approval gate** before Phase 1.

---

# 7. Phase 1: Manager Repository, Configuration, and Discovery

Unchanged from v3 (§7), with §5.7's cache design now the authoritative spec for the discovery cache (replacing v3's narrower mtime/size key), and `tested_agent_versions` recording Kilo as **7.8.18** specifically, not a range.

**Approval gate** before Phase 2.

---

# 8. Phase 2: Git Protection in Digital Pharmacy

Unchanged pre-check-first mechanism from v3 (§8.1, §8.3).

## 8.1 Ignore rules (R-06 fix)

```gitignore
# Local-only AI and agent configuration
/AGENTS.md
/AGENTS.override.md
/CLAUDE.md
/GEMINI.md
/KILO.md
/.aiignore
/.agents/
/.junie/
/.opencode/
/.claude/
/.kilo/
/kilo.jsonc
/opencode.json
/opencode.jsonc
```

`KILO.md` now defaults to **local-only and ignored**, consistent with every other agent instruction file, reversing v3's inconsistent default. If Digital Pharmacy (or any project) later genuinely needs a team-shared `KILO.md`, that is an **explicit, approved, project-level exception** — made only after inspecting whether the file already exists and is already tracked (same pre-check discipline as `AGENTS.md`), never a default and never an automatic untrack.

**Approval gate** before Phase 3.

---

# 9. Phase 3: Manifest, Detection, Selection, Symlinks

Unchanged manifest schema, detection rules, and recommendation engine from v3 (§9.1-§9.3 there), with these additions.

## 9.1 CLI lifecycle (R-10): state-transition table

Every command is specified by what it does, not left to inference:

| Command | Reads | Writes manifest | Mutates generated state | Launches agent | Confirmation |
|---|---|---|---|---|---|
| `list`, `list --selected`, `detect`, `recommend`, `validate`, `doctor` | yes | no | no | no | never |
| `init` | yes | yes (creates, empty selection) | no | no | per added skill |
| `add` / `remove` | yes | yes | **no** (manifest only; see below) | no | `add`: yes; `remove`: no (removal of intent is not destructive to files) |
| `<agent> plan` | yes | no | no | no | never |
| `<agent> apply` / `sync` | yes | no | yes | no | yes, unless `--yes`; **always required when the operation would remove a manager-owned entry** |
| `<agent> run` | yes | no | **yes, implicitly** (validates, then applies if the generated state is stale, then launches) | yes | same as `apply` for the implicit mutation; this is called out explicitly in `run`'s own `--help` text and its first-run confirmation, not left implicit |
| `clean` | yes | no | yes (deletion) | no | yes; dry-run first; only removes artifacts verified manager-owned via the marker, never a path that is merely unreachable (see below) |

Resolved answers to the review's specific questions:

- **`add`/`remove` do not auto-refresh adapters.** They change intent only. Generated state is refreshed by an explicit `apply`/`sync`/`run`. This keeps "what will change on disk" always a deliberate, separately confirmable step.
- **`sync` requires confirmation whenever it would remove a manager-owned entry** that is no longer selected — same rule as `apply`.
- **Disabling an adapter in the manifest** (`agents.<name>.enabled: false`) after it was previously applied does **not** retroactively delete its generated state. The next `validate` reports the now-orphaned generated state and recommends `clean` or `sync`; nothing is deleted without that explicit step.
- **Stale ownership markers** are recovered via `validate --repair`: it re-derives what *should* exist from the manifest, compares it to what the marker and the filesystem actually show, and reports (never auto-fixes beyond what `apply`/`sync` would already do) any mismatch for your confirmation.
- **Manifest migration backups:** each migration writes `skills.json.bak-<schema_version>-<timestamp>`; if a backup with that exact name already exists (re-running a migration), the new backup gets a numeric suffix rather than overwriting the old one.
- **`clean` vs. a temporarily unavailable volume:** `clean` only ever considers a project "stale" if its root path does not exist **and** the parent directory that should contain it does exist and is reachable (ruling out an unmounted drive or a disconnected network share, which instead produces a warning to re-check later, not a deletion candidate).

## 9.2 Manifest and detection

Unchanged from v3 (§9.1, §9.2's `agents` block and detection rules), with `list --selected` and `validate` now also printing the §2.2 per-agent resolution state for every selected skill.

**Approval gate** before Phase 4.

---

# 10. Phase 4: Shared Engineering Rules and Delivery

Unchanged `rules.md` content and template from v3 (§10.2-§10.5 there). Two additions:

- **Trust model reference:** `rules.md` restates §2.3's rule in agent-facing terms: an agent following these rules must not be instructed, by this manager or by any skill, to execute skill scripts or follow remote references as part of setup.
- **Precedence caveat (gaps table item):** the statement "`AGENTS.md` wins over global rules where they conflict" is recorded as **this project's stated policy**, not as a verified behavior of any agent. Phase 0's V11 and V17 determine whether each agent's actual precedence matches this policy; if an agent's real precedence differs, that is reported as a limitation, not silently treated as compliant.

**Approval gate** before Phase 5.

---

# 11. Phase 5: Junie Adapter

Unchanged from v3 (§11.1-§11.3). One addition for R-08:

## 11.4 Wrapper layout (R-08)

The wrapper for `flutter-tamim`/`hive-db-tamim` preserves the **original relative directory structure exactly**: only the top-level `SKILL.md` is regenerated (frontmatter added, original body copied verbatim beneath it, unmodified); every other file and subfolder is symlinked at the same relative path it occupied in the source, not flattened or re-arranged. This is the layout V19 tests against nested folders, executable scripts, and paths containing spaces, before it is trusted for real use. Checksums of every original file are compared before and after wrapper generation.

**Approval gate** before Phase 6.

---

# 12. Phase 6: OpenCode Adapter

Unchanged mechanism from v3 (§12.1-§12.4), reframed per §0.3's terminology:

## 12.1 Guarantee level

The OpenCode adapter is documented as **access-filtered**, not exclusive, until V2-V5 prove otherwise. §6.2's V2-V5 (inherited from v3, now explicitly read together with §2.1) must separately establish: whether rules block loading at all; whether a blocked skill remains visible to the model as metadata; whether OpenCode still scans the full library regardless of permissions; and whether any supported discovery-isolation mechanism exists (distinct from permission filtering). Startup time and discovery-cost measurements (§2.1) are recorded independently of whether access filtering works, since the two are different claims.

Remaining content (performance, custom-skill handling, configuration preservation) unchanged from v3 (§12.2-§12.5).

**Approval gate** before Phase 7.

---

# 13. Phase 7: Kilo Adapter

**Objective:** Make Kilo's project-local skill set match the manifest's selection, and describe the result honestly as **additive** (§0.3) unless V14 proves otherwise — all against the confirmed **7.8.18** binary, not the "1.0+" assumptions from v3.

## 13.1 Preconditions

Do not begin implementation until V13-V22 (as they pertain to Kilo) are resolved **against 7.8.18 specifically**. If V14 shows no disable mechanism for the compatibility-directory load, this phase proceeds anyway (the additive value is still real), but every piece of CLI output and documentation states "additive" rather than implying exclusivity.

## 13.2 Behavior of `agent-skills kilo apply` / `run`

1. Resolve the project root; confirm it matches Kilo's own project-config resolution (V13).
2. Load and validate the manifest; compute §2.2's resolution state for every selected skill against Kilo specifically (identifier collisions per V16).
3. If invalid, do not modify `.kilo/skills/` and do not launch.
4. Acquire the lock (§5.5); build the new symlink set in a temp location, validate it, then swap it in using the build-then-swap sequence in §5.5 (not a bare rename), recording ownership in the marker — whose placement follows V18's result (inside or outside `.kilo/skills/`).
5. Remove only manager-owned, deselected symlinks; report (never overwrite) anything manually replaced, per §5.5's manual-replacement detection.
6. Validate the result.
7. For `run`: validate, apply if the generated state is stale (an implicit mutation, called out per §9.1's table), then launch `kilo` via `os.execvp` with an argv list from the project directory.
8. Print the additive-only limitation notice on every `plan`, `apply`, `validate`, and `run`, unless V14 found and applied a working disable mechanism.

## 13.3 Custom skills (R-08)

Same wrapper layout rule as §11.4: preserve original relative structure, regenerate only the top-level `SKILL.md`, symlink everything else at its original relative path, verify with V19 and checksums before trusting it for Kilo specifically (Kilo's own symlink-following behavior is a separate unknown from Junie's, even if the layout strategy is shared).

## 13.4 Preservation

Unchanged from v3 (§13.4): never modify `~/.kilo/skills/`, `~/.config/kilo/kilo.jsonc`, or non-managed entries in `.kilo/skills/`; never touch `KILO.md` without explicit instruction — now reinforced by §8.1's default-ignored policy for that file.

## 13.5 Collision handling

Reframed through §2.2's resolution model: a detected collision between a selected skill and anything Kilo would already load from `~/.kilo/skills/`, `~/.agents/skills/`, or (if enabled) `~/.claude/skills/` is reported as a `conflict` resolution state, with both sources named, never silently resolved by renaming (§5.3).

## 13.6 Limitations documentation

Unchanged intent from v3 (§13.6), phrased now with §0.3's defined terms: Kilo's adapter is additive, not exclusive or access-filtered, unless V14 changes that — stated plainly in user-facing docs, not minimized.

**Approval gate** before Phase 8.

---

# 14. Phase 8: Digital Pharmacy Integration

Unchanged from v3 (§14), with the final structure's `KILO.md` entry now consistently local-only per §8.1 (no longer an open question), and the manager still never creating `KILO.md` speculatively — only if you ask for it.

**Approval gate** before Phase 9.

---

# 15. Phase 9: Automated and Manual Testing

Unchanged isolation rules and unit/CLI test scope from v3 (§15.1-§15.3 there), with these additions:

## 15.1 Context-measurement test protocol (R-01)

Implements §2.1 as an actual, repeatable test procedure: a fixed small set of prompts run against a fixed project state, before and after each adapter is applied, with results recorded per the metrics list in §2.1 and explicitly labeled `unavailable` where an agent gives no observable signal (per V20). This is a recorded procedure, run manually where no automation is possible, not a one-off claim in a report.

## 15.2 Resolution-model tests (R-03)

Unit tests for §2.2: every combination of `available`/`unavailable`/`unresolved`/`conflict` is exercised with fixtures, including the case where a skill is `unavailable` in one adapter and `available` in another, verifying the two are reported independently and never conflated.

## 15.3 Crash and concurrency tests (R-04 / V21)

In the sandbox only: kill the process mid-refresh (after the temp build, before the swap; after the first rename, before the second) and verify the next run detects and cleans up leftover `.tmp-*`/`.old-*` paths without data loss; run two `apply` invocations concurrently and verify the lock serializes them rather than interleaving writes.

## 15.4 Wrapper relative-path tests (R-08 / V19)

For each agent's wrapper generation: nested folders, an executable script, and a path containing spaces, verified both by checksum (unchanged originals) and, where feasible, by an actual agent session reading the wrapped skill.

## 15.5 Never-execute tests (R-09)

A fixture skill containing a shell script and a fake "remote reference" instruction is run through discovery, validation, recommendation, and apply; the test asserts the script was never executed and the reference was never followed, at any stage.

## 15.6 Cache invalidation tests (R-07)

Unit tests for every key component in §5.7: rename, removal, content change with identical mtime/size, override change, schema bump, and root change, each verified to invalidate exactly the expected cache entries and no others.

## 15.7 Manual verification

Unchanged procedure from v3 for Junie and Kilo (§15.2 there): start a real session, ask what skills are available, record selection vs. exclusivity separately, now also explicitly logging whatever V20 found observable for context-measurement purposes.

**Approval gate** before Phase 10.

---

# 16. Phase 10: Documentation, Installation, Final Acceptance

Unchanged documentation scope from v3 (§16 there), with the limitation statement (§13.6) and the §0.3 terminology used consistently throughout, not only in one section.

## 16.1 Final acceptance checklist additions (from the review, §7)

- [ ] Context-reduction measurements are recorded separately from skill-discovery counts, with `unavailable` used honestly where no signal exists.
- [ ] No agent is described as **exclusive** unless unselected skills are demonstrably unavailable, per §0.3.
- [ ] Every selected skill has a per-agent availability result (§2.2), visible through `validate` and `list --selected`.
- [ ] Kilo's compatibility limitation is visible in CLI output (`plan`, `apply`, `validate`, `run`) if it cannot be disabled.
- [ ] Kilo's ownership marker does not interfere with skill discovery (V18 resolved, and the marker relocated if needed).
- [ ] Wrapper-based custom skills preserve relative resource paths for both Junie and Kilo (V19 resolved).
- [ ] Cache invalidation covers library changes, metadata overrides, renames/removals, and schema changes (§5.7).
- [ ] No skill content or script is executed during discovery, validation, recommendation, or apply (§2.3), verified by the §15.5 tests.
- [ ] Interrupted refreshes and concurrent `apply`/`sync` operations leave recoverable state (§5.5, §15.3).
- [ ] `KILO.md` follows the local-only default unless an explicit, approved project exception exists (§8.1).
- [ ] Every mutating CLI command has documented confirmation, dry-run, and recovery semantics per the §9.1 state-transition table.

All acceptance items from v3 (§16.1 there, carried forward) remain, exercised against the confirmed Kilo 7.8.18 binary rather than the superseded "1.0+" assumption.

---

# 17. Execution Protocol

Unchanged order from v3 (§17): Phase 0 through Phase 10 as listed there, now explicitly covering V1-V22 in Phase 0 and the version correction throughout. Per-phase procedure (inspect, risk, plan with `AWAITING_APPROVAL`, **stop for explicit approval**, implement only approved scope, test, update docs, report) is unchanged.

**Next deliverable (per your decision):** a standalone Phase 0 verification plan document, covering V1-V22 with method, expected evidence, and stop conditions for each, produced alongside this guideline.

---

# 18. Final Deliverables

Unchanged from v3 (§18), restated with §0.3's honest terminology: three independent agent adapters, each verified against its installed version (Kilo confirmed at 7.8.18), each labeled exclusive/access-filtered/additive based on evidence rather than intent, with skill content always treated as untrusted and context-reduction claims always backed by the §2.1 measurement protocol.

**Final principle:** One shared skill library, one project-specific selection system with per-agent resolution reporting, three independently verified agent adapters described by their actual guarantee level, and one consistent engineering workflow — with every agent behavior verified rather than assumed, every claim of reduced context backed by evidence, skill content always treated as untrusted, and no sacrifice of existing projects or user-created skills for convenience.
