# Global Agent Skill Manager
## Implementation Guideline for OpenCode, Junie, and Kilo (v3)

**Project:** Global Agent Skill Manager
**Platform:** macOS (zsh)
**Supported agents:** OpenCode CLI 2.2.5, Junie CLI 26.10.27, Kilo Code CLI 1.0+ (binary `kilo`, npm `@kilocode/cli`)
**Implementation language:** Python 3, standard library only
**Shared skill library:** `~/.agents/skills/`
**First integration target:** Digital Pharmacy (Flutter)
**Digital Pharmacy branch:** `chore/agent-skills-manager` (base: `dp-dev-tamim`)
**Document status:** `AWAITING_APPROVAL`

---

# 0. Revision Notes (v2 -> v3)

v3 adds **Kilo Code CLI** as a third managed agent. Everything in v2 that referred to "both adapters" or "two agents" now reads "three agents." Specific additions:

1. New **Phase 7: Kilo Adapter**, inserted after OpenCode. Phases 7-9 from v2 (Digital Pharmacy, Testing, Documentation/Acceptance) shift to 8-10.
2. New **Phase 0 verification experiments V13-V17** for Kilo-specific unknowns.
3. **Identifier model, config schema, CLI, Git ignore list, rules-delivery mechanism, and acceptance checklist** all extended to cover Kilo.
4. A new, **confirmed-by-you** fact set (section 0.1) replacing what would otherwise be open decisions, since you already answered the two questions that mattered.
5. A documented **structural difference**: unlike Junie (external directory via a flag) and OpenCode (permission allow/deny list), Kilo has no known flag to point at an arbitrary skill directory. The design therefore generates symlinks **directly inside the project's own `.kilo/skills/`** (already local-only), not an external generated path — pending V15.
6. A documented **known limitation**: Kilo loads the shared library (`~/.agents/skills/`) by default as a "compatibility directory," independent of the project selection. Phase 0 must determine whether this can be disabled (V14); if it cannot, Kilo's "unselected skills are unavailable" guarantee does **not** hold, and this must be stated plainly in the docs and the acceptance checklist, not glossed over.

## 0.1 Facts confirmed by you (not open decisions)

| Fact | Value |
|---|---|
| Kilo binary | `kilo` (npm package `@kilocode/cli`, CLI 1.0+) |
| Kilo global config | `~/.config/kilo/kilo.jsonc` |
| Kilo project config | `./kilo.jsonc` or `./.kilo/kilo.jsonc` (precedence between these two: **verify**, V13) |
| Kilo global skills dir | `~/.kilo/skills/` |
| Kilo project skills dir | `.kilo/skills/` (project-level skill of the same name overrides global) |
| Kilo compatibility dirs | `~/.agents/skills/` and `.agents/skills/` loaded **by default**; `~/.claude/skills/` and `.claude/skills/` loaded only if "Claude Code Compatibility" is enabled (assume off unless you say otherwise) |
| Kilo discovery timing | Skills are scanned at session start (metadata only: name, description, path); `/reload` re-scans without restarting |
| Kilo project context file | `KILO.md`, analogous to `AGENTS.md` |
| Handling of default-library compatibility dir | **Verify and try to disable** (your choice). If no disable mechanism exists, document as a known limitation rather than attempt a workaround that fights the tool. |

Everything else about Kilo in this document is **unverified** and marked for Phase 0.

---

# 1. Open Decisions (confirm before Phase 1)

Carried over from v2, plus one new item.

| ID | Decision | Recommended default | Why |
|---|---|---|---|
| D1 | Custom skills (`flutter-tamim`, `hive-db-tamim`) lack frontmatter. How to expose them across all three agents? | User-authored `name`/`description` overrides in manager config. Generated wrapper directories for Junie and Kilo (both require frontmatter per their own docs/tooling). OpenCode: decided by V1. | Keeps originals untouched, avoids fabricated descriptions, avoids duplicate identifiers. |
| D2 | Where does manager source live? | Separate Git repository. | `~/.local/lib` is not a repo. |
| D3 | Minimum Python version | 3.9, verified in Phase 0. | Avoids a Homebrew dependency unless Phase 0 says otherwise. |
| D4 | Ignore mechanism in projects | `.gitignore`, anchored patterns. | Team-wide protection. |
| D5 | Kilo compatibility-directory behavior (see 0.1) | Verify and try to disable (V14); if impossible, document as a limitation and adjust acceptance criteria for Kilo instead of forcing a workaround. | Matches your answer; avoids fighting the tool's own design. |

---

# 2. Project Objective

Build a reusable global skill management system so **OpenCode, Junie, and Kilo** use the same centralized skill library while loading only the skills relevant to each project, to the extent each agent's own design allows.

The system must:

1. Maintain one centralized skill library.
2. Discover available skills automatically.
3. Recommend skills from project technologies (deterministic, offline, explainable).
4. Let users select skills per project, always with explicit confirmation.
5. Integrate with OpenCode, Junie, and Kilo through independent adapters.
6. Never duplicate or modify original skill content.
7. Apply consistent engineering rules to all three agents.
8. Keep AI and agent configuration out of Git.
9. Keep engineering plans and reviews in Git.
10. Provide reliable validation, error handling, and diagnostics.

**Do not build a Digital Pharmacy-specific solution.** It is the first validation target, not the scope boundary.

**Known asymmetries across agents (must be documented, not hidden):**

- **Junie** is restricted only when launched through `agent-skills junie`; a plain `junie` invocation still loads everything in `~/.junie/skills/`.
- **OpenCode** is restricted on every run, through the project's `opencode.json` permissions.
- **Kilo** is restricted for its own skill directories on every run (since the generated symlinks live inside the project), **but** continues to load the entire shared library (`~/.agents/skills/`) regardless, unless V14 finds a way to disable that. This is the weakest guarantee of the three and must be stated as such, not implied to be equivalent.

---

# 3. Existing Environment (to verify, not assume)

| Component | Expected configuration |
|---|---|
| OS / shell | macOS, zsh |
| Home | `/Users/tamimhasan` (resolved dynamically in code; never hardcoded) |
| OpenCode | 2.2.5, config at `~/.config/opencode/` |
| Junie | 26.10.27, skills at `~/.junie/skills/`, settings at `~/.junie/settings.json` |
| Kilo | 1.0+, binary `kilo`, global config `~/.config/kilo/kilo.jsonc`, global skills `~/.kilo/skills/` |
| Python | Verify version (D3) |
| Shared skills | `~/.agents/skills/` (used by the manager, and also auto-loaded by Kilo) |

Reported inventory (re-verify in Phase 0):

- About 1,435 global skills; 68 Junie skills, all present in the global library.
- No duplicate folder names found. **Duplicate frontmatter `name` values across directories were never checked and must be**, now across three agents' identifier schemes.
- Whether any skills in `~/.agents/skills/` already collide with names in `~/.kilo/skills/` or `~/.claude/skills/` is unknown and must be checked, since Kilo merges compatibility directories with its own.

Custom skills requiring special handling: `flutter-tamim`, `hive-db-tamim`. Missing frontmatter is intentional. Files and directory structure remain byte-identical for all three agents. Never inject generated frontmatter into the originals.

---

# 4. Non-Negotiable Engineering Rules

Unchanged from v2 (requirement analysis and approval gates per phase; never overwrite, delete, or modify without inspection; no destructive Git commands; no secrets in logs or tracked docs; implement only approved scope; Git commits require explicit, exact-message approval; tracked-document redaction; version-mismatch warnings). These rules now apply identically to the Kilo adapter and its phase. See v2 sections 4.1-4.6 for full text; nothing in them is agent-specific, so nothing changes.

**Version policy addition:** the manager also records Kilo 1.0+ as a tested version and warns (not fails) on mismatch, same as the other two agents.

---

# 5. Target Architecture

## 5.1 Repository and install layout

Unchanged structure from v2, with one addition to the adapters directory:

```text
src/agent_skills/adapters/
├── base.py
├── junie.py
├── opencode.py
└── kilo.py        # NEW
```

No other structural change. `agent_paths` in config gains a `kilo` entry.

## 5.2 Responsibilities

Unchanged (v2 §5.2); "Adapters" now explicitly means three implementations of `base.py`'s interface, not two.

## 5.3 Identifier model (extended)

The three-field model (`dir_name`, `declared_name`, `agent_id[agent]`) now resolves `agent_id["kilo"]` as well. Per Kilo's own docs, skill identity for loading purposes appears to be the directory/skill name read from frontmatter `name` combined with its path — **confirm exact matching and collision rules in V16** (what happens when two discovered directories declare the same `name`: does project override global cleanly, or does Kilo warn/fail?).

`validate` must also check: does any skill in `~/.agents/skills/` collide by `declared_name` with anything already present in `~/.kilo/skills/` or (if enabled) `~/.claude/skills/`? If so, Kilo's merge behavior for that specific name is unverified and the skill is marked `unresolved` for Kilo.

## 5.4 Symlink and path policy

Unchanged (v2 §5.4), with the allow-list of roots extended to include `~/.kilo/skills/` as a legitimate destination root for Kilo-specific generation (5.6 below), since — unlike Junie and OpenCode — Kilo's generated location is inside directories Kilo itself defines, not an arbitrary manager-chosen path.

## 5.5 Ownership of generated artifacts

Unchanged mechanism (marker file `.agent-skills-managed.json` in every generated directory; for OpenCode, a sidecar `opencode-owned-rules.json`). For Kilo, the marker file lives inside the project's `.kilo/skills/` directory itself (see 5.6), so the manager can tell its own symlinks apart from any skill the person may have placed there by hand, and never deletes the latter.

## 5.6 Generation strategy per agent (this is the key structural difference)

| Agent | Mechanism | Generated location |
|---|---|---|
| Junie | External directory, passed via `--skill-location`, with default discovery disabled via `--skill-default-locations false` | `~/.local/share/agent-skills/projects/<key>/junie/` |
| OpenCode | Permission allow/deny list in `opencode.json`; the shared library stays as-is, access is filtered by rule, not by relocating files | N/A (no generated skill directory; a sidecar rule record only) |
| Kilo | **Pending V15.** If no external-path flag or env var exists, symlinks for the project's selected skills are generated **directly inside `<project>/.kilo/skills/`** (already git-ignored), each pointing at the real skill directory in the shared library. This directory is scoped to the project already, so no cross-project key is needed here (contrast with Junie's path-hash-keyed external directory). | `<project>/.kilo/skills/` (in-place, ignored) |

This means Kilo's "selected skills available" guarantee comes from **adding** symlinks for the selection, not from restricting discovery — Kilo will still also see `~/.kilo/skills/` (global) and `~/.agents/skills/` (compatibility, per D5/V14) regardless of the manifest. The acceptance checklist (section 10.2) reflects this distinction explicitly rather than claiming parity with Junie/OpenCode.

If V15 finds an external-path mechanism after all (an env var, a `kilo.jsonc` field, or a CLI flag), switch to the keyed-external-directory pattern used for Junie, for consistency, and update this section.

## 5.7 Project root

Unchanged (v2 §5.7). Kilo's own project config resolution (`./kilo.jsonc` vs `./.kilo/kilo.jsonc`, V13) must agree with the manager's project-root resolution, or launches could target the wrong directory; Phase 7 checks this explicitly.

---

# 6. Phase 0: Environment Inspection and Verification Experiments

Unchanged in structure and constraint reconciliation (v2 §6.1 applies as-is: read-only inspection, redaction before any tracked document, sandboxed experiments only). Add Kilo experiments to the table in §6.3.

## 6.1 Additional inspection tasks

9. Verify `kilo --version` matches the binary name and version confirmed in 0.1; note if the installed version differs materially from "1.0+" assumptions.
10. Inspect `~/.config/kilo/kilo.jsonc` structure (without printing secret values such as API keys).
11. List contents of `~/.kilo/skills/` and compare names against `~/.agents/skills/` for collisions.
12. Check whether "Claude Code Compatibility" is currently enabled (affects whether `~/.claude/skills/` is also merged in).

## 6.2 New verification experiments (V13-V17)

| ID | Question | Design impact |
|---|---|---|
| V13 | If both `./kilo.jsonc` and `./.kilo/kilo.jsonc` exist in a project, which does Kilo read, or are they merged? | Where the manager writes project-level Kilo config; avoids writing to a file Kilo ignores |
| V14 | Is there any documented or discoverable way to disable Kilo's default loading of `~/.agents/skills/` and `.agents/skills/` (a config flag, an env var, a CLI flag)? | D5; directly determines whether Kilo's "unselected skills unavailable" guarantee can exist at all |
| V15 | Does Kilo support pointing at an arbitrary external skills directory (env var, CLI flag, or a `kilo.jsonc` field listing extra skill paths), analogous to Junie's `--skill-location`? | Chooses between the in-place `.kilo/skills/` generation (5.6 default) and an external keyed directory (consistent with Junie) |
| V16 | When two discovered skill directories (for example one in `~/.agents/skills/` and a manager-generated symlink in `.kilo/skills/`) declare the same frontmatter `name`, what does Kilo do: silently prefer project-level, warn, or error? | Identifier/collision handling (5.3); whether the manager must pre-emptively rename or warn before generating |
| V17 | Where does Kilo read project-wide instructions/rules from: `KILO.md` only, a `kilo.jsonc` field, both, and what is the precedence against `AGENTS.md` if both exist? | Rules-delivery mechanism (Phase 4) for Kilo |

As in v2, if a result contradicts a design assumption, stop and present the impact before Phase 1.

## 6.3 Deliverable

Same as v2 §6.4, now also containing results for V13-V17 and the Kilo-specific inspection tasks.

**Approval gate** before Phase 1.

---

# 7. Phase 1: Manager Repository, Configuration, and Discovery

Unchanged from v2 (§7.1-7.7), with these additions:

- `config.json`'s `agent_paths` gains an optional `kilo` executable override.
- `tested_agent_versions` includes Kilo.
- Discovery's compatibility note: since Kilo merges `~/.agents/skills/` on its own, the discovery module does not need a Kilo-specific scan of that directory — Kilo already does this itself. The manager's job for Kilo is limited to (a) generating project-level symlinks for the selection, and (b) reporting the compatibility-directory limitation from D5/V14.

**Approval gate** before Phase 2.

---

# 8. Phase 2: Git Protection in Digital Pharmacy

Unchanged mechanism (v2 §8.1-8.3: pre-check for already-tracked files first; anchored `.gitignore` patterns; verification commands), extended with Kilo paths.

## 8.1 Additional pre-check paths

```bash
git ls-files kilo.jsonc .kilo KILO.md
```

If `KILO.md` is already tracked (plausible, since it is meant to hold project context much like `AGENTS.md`), treat it exactly as v2 treats an already-tracked `AGENTS.md`: report, do not untrack without approval.

## 8.2 Ignore rules addition

```gitignore
# Kilo (local-only, same policy as other agent configs)
/kilo.jsonc
/.kilo/
```

`KILO.md` is **not** added to the ignore list by default — unlike `AGENTS.md`, Kilo's docs describe it as project context, which is plausibly meant to be shared with the team. Confirm with you before deciding; until confirmed, treat it as trackable (the opposite default from `AGENTS.md`) and flag the inconsistency explicitly in the review for a decision.

## 8.3 Verification addition

```bash
git check-ignore -v kilo.jsonc
git check-ignore -v .kilo/skills/example
```

**Approval gate** before Phase 3.

---

# 9. Phase 3: Manifest, Detection, Selection, Symlinks

Unchanged CLI contract, manifest schema, detection rules, and recommendation engine from v2 (§9.1-9.4), with these extensions:

## 9.1 Manifest `agents` block

```json
{
  "agents": {
    "junie": { "enabled": true },
    "opencode": { "enabled": true },
    "kilo": { "enabled": true }
  }
}
```

## 9.2 CLI table addition

| Command | Behavior |
|---|---|
| `agent-skills kilo plan` | Show what symlinks in `.kilo/skills/` would be created, changed, or removed. Read-only. |
| `agent-skills kilo apply` | Generate/refresh the project's `.kilo/skills/` symlinks from the manifest (confirmation unless `--yes`; `--dry-run` supported). |
| `agent-skills kilo validate` | Validate `.kilo/skills/` against the manifest and ownership markers; report the compatibility-directory limitation (D5) every time, not just once, so it is never silently forgotten. |
| `agent-skills kilo run [-- <args>]` | Validate, apply if needed, then launch `kilo` in the project directory via `os.execvp` with an argv list. |

Empty selection: `.kilo/skills/` contains only the marker file; `validate` and `run` still report the compatibility-directory limitation.

## 9.3 Symlink manager addition

The symlink manager (v2 §9.5, now also used for 5.6's in-place Kilo generation) must additionally:

- Refuse to create a symlink in `.kilo/skills/` whose name collides with a **non-managed** entry already there (something the person put there by hand) — report the conflict instead of overwriting it.
- Record every created link in the project-local marker file described in 5.5, scoped to `.kilo/skills/`.

**Approval gate** before Phase 4.

---

# 10. Phase 4: Shared Engineering Rules and Delivery

Unchanged content and template for `rules.md` (v2 §10.2-10.5). The delivery mechanism (§10.1) now covers three agents:

## 10.1 Delivery mechanism (finalize from V11, V17)

- **OpenCode:** as in v2, an `instructions` entry in `opencode.json` pointing at `~/.config/agent-skills/rules.md`, if V10 confirms support.
- **Junie:** as in v2, its supported guidelines location or a launch-time option (V11).
- **Kilo:** per V17, likely `KILO.md` and/or a `kilo.jsonc` field. If `KILO.md` turns out to be local-only (pending the 8.2 decision) it can safely reference or embed the shared rules. If it is meant to be shared/tracked, the manager does **not** write generated content into it automatically — doing so would make a tracked file carry generated, machine-written content without review. Instead, the rules are referenced from it manually by you, or from a `kilo.jsonc` field if one exists (local-only, so safe to generate into).

Precedence is unchanged: **`AGENTS.md` wins over the global rules where they conflict**, and this applies per-agent-file too — `KILO.md`, if present, states the same precedence rather than contradicting `AGENTS.md`.

**Approval gate** before Phase 5.

---

# 11. Phase 5: Junie Adapter

Unchanged from v2 (§11.1-11.5). No Kilo-related changes.

**Approval gate** before Phase 6.

---

# 12. Phase 6: OpenCode Adapter

Unchanged from v2 (§12.1-12.6). No Kilo-related changes.

**Approval gate** before Phase 7.

---

# 13. Phase 7: Kilo Adapter (NEW)

**Objective:** Make Kilo's project-local skill set match the manifest's selection, and document clearly what this guarantee does and does not cover given D5.

## 13.1 Preconditions from Phase 0

Do not begin implementation until V13-V17 are resolved. If V14 shows no way to disable the `~/.agents/skills/` compatibility load, this phase still proceeds (selection is still useful and additive), but every piece of documentation and CLI output for Kilo must state the limitation rather than imply equivalence with the other two adapters.

## 13.2 Behavior of `agent-skills kilo apply` / `run`

1. Resolve the project root (5.7); confirm it matches where Kilo itself would resolve its project config (V13).
2. Load and validate the manifest. If invalid, do not modify `.kilo/skills/` and do not launch.
3. Validate selected skills against the library.
4. Acquire the lock (5.6/9.3); for each selected skill, create or refresh a symlink inside `<project>/.kilo/skills/` pointing at the real source directory, atomically, recording it in the marker file.
5. Remove any manager-owned symlink in `.kilo/skills/` that is no longer selected. Never remove a non-managed entry.
6. Validate the result (links resolve; marker file consistent).
7. For `run`: launch `kilo` via `os.execvp` with an argv list (never a shell) from the project directory, so Kilo's own project-config resolution applies; pass through any arguments after `--`.
8. Print the D5 limitation notice (one line, not buried) every time `apply`, `validate`, or `run` is used, unless V14 found a working disable mechanism, in which case the notice only appears if that mechanism could not be applied for some reason (for example, the person overrode it in their own `kilo.jsonc`).

## 13.3 Custom skills

Apply the D1 wrapper strategy: generate a wrapper `SKILL.md` (with the user-authored `name`/`description` override) for `flutter-tamim` and `hive-db-tamim`, symlink the rest of each skill's files, and place the wrapper under the same `.kilo/skills/` generation as any other selected skill. Verify with checksums that the original skill directories remain untouched.

## 13.4 Preservation

Never modify `~/.kilo/skills/`, `~/.config/kilo/kilo.jsonc`, or any existing entries in `.kilo/skills/` that the manager did not create. Never touch `KILO.md` without your explicit instruction (10.1).

## 13.5 Collision handling

Before generating, check (per V16's findings) whether any selected skill's `declared_name` collides with something Kilo would already load from `~/.kilo/skills/`, `~/.agents/skills/`, or (if enabled) `~/.claude/skills/`. Report collisions rather than silently generating a symlink that Kilo might ignore or override unpredictably.

## 13.6 Limitations documentation

Write a short, explicit section (for Phase 10's documentation) stating: Kilo always loads the full shared library by default (unless V14's disable mechanism is applied), so the Kilo adapter's purpose is to **add** the project's chosen skills with higher (project-level) precedence and to support consistent rule delivery — not to provide the same exclusivity guarantee as Junie or OpenCode. This must not be minimized in the user-facing docs.

**Approval gate** before Phase 8.

---

# 14. Phase 8: Digital Pharmacy Integration

Unchanged from v2 (§13.1-13.5, renumbered), with these additions:

- Initialization (previously §13.3) now also confirms Kilo as an enabled agent in the manifest, and whether Kilo Code is actually used on this project before generating anything for it — do not assume every project wants all three agents configured.
- Final structure gains `.kilo/skills/` (local-only, generated) and, pending the 8.2 decision, either a tracked or ignored `KILO.md` and a local-only `kilo.jsonc`.
- If `KILO.md` does not yet exist in Digital Pharmacy, do not create it speculatively; only create it if you ask for it, since the manager's rule (4.2) is to implement only approved scope.

**Approval gate** before Phase 9.

---

# 15. Phase 9: Automated and Manual Testing

Unchanged isolation rules, unit-test scope, and CLI-test scope from v2 (§14.1-14.3, renumbered). Adapter tests extended:

## 15.1 Kilo adapter tests (automated via stub)

- `apply` creates exactly the expected symlinks for the selection, with the marker file recorded.
- `apply` removes only manager-owned, deselected symlinks; a hand-placed, non-managed entry in `.kilo/skills/` with a colliding name is reported, not overwritten.
- `run` launches the stub `kilo` executable with the correct working directory and passthrough arguments, via argv (never a shell).
- Invalid manifest blocks `apply` and `run`.
- Empty selection leaves only the marker file and still prints the D5 limitation notice.
- Custom skill wrapper generation matches the Junie wrapper tests; original sources are checksummed unchanged.

## 15.2 Manual verification (Kilo)

Since skill-loading visibility inside a real Kilo session cannot be automated without V-series confirming a listing command, run the same manual procedure as v2 §14.4 for Kilo: start a session in Digital Pharmacy, ask Kilo what skills are available, and record whether the project-selected skills appear and whether the full shared library also appears (expected, per D5, unless V14 changes this). Record results in the review, explicitly distinguishing "selection worked" from "exclusivity worked," since for Kilo these are different claims.

## 15.3 Git safety tests addition

Confirm `kilo.jsonc` and `.kilo/` are ignored (unless a decision was made otherwise for specific files), and confirm the `KILO.md` tracking decision from §8.2 is actually what ends up happening, not assumed.

**Approval gate** before Phase 10.

---

# 16. Phase 10: Documentation, Installation, Final Acceptance

Unchanged documentation scope from v2 (§15.1, renumbered), with Kilo examples added:

```bash
agent-skills kilo plan
agent-skills kilo apply
agent-skills kilo run
```

Documentation must include the limitation statement from §13.6 prominently, not as a footnote.

## 16.1 Final acceptance checklist additions

**Kilo**
- [ ] `kilo.jsonc` project-config precedence resolved (V13) and the manager writes to the file Kilo actually reads.
- [ ] Compatibility-directory behavior resolved (V14); either disabled for managed projects, or the limitation is documented plainly everywhere it matters (CLI output, docs, acceptance report).
- [ ] Selected skills appear as symlinks in `.kilo/skills/` with correct precedence over same-named global/compatibility skills (V16).
- [ ] Non-managed entries in `.kilo/skills/` are never overwritten or removed.
- [ ] Custom skills verified through the wrapper strategy; originals unchanged (checksums).
- [ ] Rules delivered per §10.1, respecting the `KILO.md` tracking decision.
- [ ] Manual verification recorded distinguishing "selection present" from "exclusivity," per §15.2.
- [ ] Existing `~/.kilo/skills/`, `~/.config/kilo/kilo.jsonc` untouched.

All other acceptance items from v2 (§15.2) remain as written, now also exercised against a project with Kilo enabled.

---

# 17. Execution Protocol

| # | Phase |
|---|---|
| 0 | Environment inspection and verification experiments (incl. V13-V17) |
| 1 | Manager repository, configuration, discovery |
| 2 | Git protection in Digital Pharmacy |
| 3 | Manifest, detection, selection, symlinks |
| 4 | Shared rules and delivery mechanism |
| 5 | Junie adapter |
| 6 | OpenCode adapter |
| 7 | **Kilo adapter** |
| 8 | Digital Pharmacy integration and documentation migration |
| 9 | Automated and manual testing |
| 10 | Documentation, installation, final acceptance |

Per-phase procedure is unchanged from v2 §16: inspect, identify risks, write a plan with status `AWAITING_APPROVAL`, **stop for explicit approval**, implement only the approved scope, test, update docs, report. Do not skip a phase because it looks simple; do not skip Phase 7 because Kilo "just needs symlinks" — §13 shows it has its own unresolved questions.

---

# 18. Final Deliverables

Unchanged from v2 (§17), with "two adapters" replaced by "three adapters, each verified against its installed version, with Kilo's exclusivity limitation explicitly documented rather than assumed away."

**Final principle:** One shared skill library, one project-specific selection system, three independent agent adapters, and one consistent engineering workflow — with every agent behavior verified rather than assumed, honest about where an agent's own design limits what the manager can guarantee, and no sacrifice of existing projects or user-created skills for convenience.
