# Shared Engineering Rules — Global Agent Skill Manager

These rules apply to every adapter (OpenCode, Junie, Kilo) and every phase
of the manager. They are the consistent engineering rules referenced by
objective item 8 of the guideline (§2).

## 1. One shared skill library (§2.1)

The manager maintains a single centralized skill library
(`~/.agents/skills/` by default). All adapters draw from this same library;
no adapter maintains its own canonical copy of skill content.

## 2. Discover, never modify (§2.6)

The manager never duplicates or modifies original skill content. Discovery,
validation, recommendation, and apply are read-only with respect to the
source skill directories. Generated artifacts (symlinks, permission rules,
markers) live in project-local or generated locations only.

## 3. Skill content is untrusted input (§2.3 / R-09)

Skill scripts, examples, instructions, and remote references are **never
executed or followed** by the manager at any stage — discovery, validation,
recommendation, or apply — for any reason, including "just to test it works."

The manager never automatically follows a remote reference (URL, download
instruction) found inside skill content. Static discovery and validation
do not claim to prove a skill is safe to use; they only report structural
issues (malformed frontmatter, suspicious layouts) without modifying source.

## 4. Explicit confirmation before mutation (§9.1)

`add`/`remove` change manifest intent only; they do not refresh adapters.
Generated state is refreshed by an explicit `apply`/`sync`/`run`.
`apply`/`sync` require confirmation whenever they would remove a
manager-owned entry that is no longer selected. `run` applies implicitly
if the generated state is stale, then launches — this mutation is called
out explicitly in `run`'s help text and first-run confirmation.

`clean` requires confirmation and dry-run first; it only removes artifacts
verified manager-owned via the marker, never a path merely unreachable.

## 5. Git hygiene (§2.9, §8.1)

AI and agent configuration stays out of Git. The project `.gitignore`
includes anchored ignores for `AGENTS.md`, `KILO.md`, `.agents/`,
`.junie/`, `.opencode/`, `.claude/`, `.kilo/`, `kilo.jsonc`,
`opencode.json`, `opencode.jsonc`. Engineering plans and reviews are kept
in Git.

## 6. Per-agent resolution reporting (§2.2 / R-03)

`validate` and `list --selected` show a per-agent resolution breakdown for
every selected skill: `available` / `unavailable` / `unresolved` /
`conflict`, each with a reason string — not just pass/fail. A skill
`unavailable` in one adapter never silently becomes `available` under a
different identity in another adapter without that being visible.

No per-agent selection override exists in this version — only per-agent
resolution reporting.

## 7. Precedence caveat — policy, not verified behavior (§10.4)

The statement "`AGENTS.md` wins over global rules where they conflict" is
recorded as **this project's stated policy**, not as verified behavior of
any agent. Phase 0 experiments V11 and V17 determine whether each agent's
actual precedence matches this policy; if an agent's real precedence
differs, that is reported as a limitation, not silently treated as
compliant.

## 8. Guarantee levels are evidence-based (§0.3)

No adapter may be described as `exclusive` until the relevant Phase 0
experiment demonstrates that unselected skills are demonstrably
unavailable:

| Agent   | Guarantee level (pending evidence) |
|---------|------------------------------------|
| OpenCode| access-filtered (V2–V5 pending)    |
| Junie   | potentially exclusive (V6–V9 pending) |
| Kilo    | additive (V14 confirmed negative)   |

Until proven otherwise, descriptions use the conservative level above.
Kilo's additive limitation is visible in CLI output on every
`plan`/`apply`/`validate`/`run`.

## 9. Context-reduction claims require evidence (§2.1 / R-01)

No phase, document, or CLI message may claim a token or context reduction
without §2.1 measurement evidence attached. Metrics that cannot be
observed are labeled `unavailable`, never estimated or implied.

## 10. Recovery and locking (§5.5)

Generated state is built via build-then-swap with crash recovery
(`.tmp-*`/`.old-*` cleanup on next run) and guarded by an advisory lock
(`fcntl.flock`). A second concurrent writer waits briefly, then fails
clearly rather than interleaving writes. Manually replaced managed entries
are reported as conflicts requiring confirmation, not silently
overwritten.
