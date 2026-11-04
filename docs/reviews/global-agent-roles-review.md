# Global Agent Roles Rules Review

## Scope and current state

Review the proposed 11 workflow rules against the bundled reusable template, `src/agent_skills/templates/AGENTS.base.md`, and the active user-level copy at `~/.config/agent-skills/templates/AGENTS.base.md`.

The bundled source was already revised to be more reusable, but the active user-level copy still contained older workflow rules and project-only Python, dependency, test, and schema details. The project root `AGENTS.md` is the appropriate home for those repository-specific conventions.

## Findings

1. **Workflow gates were underspecified.** The rules required a plan but did not explicitly require approval before implementation. Add a clear approval gate for substantive implementation.
2. **Always-on documentation would over-process small tasks.** Requiring review/plan files and branch creation for read-only, research, or trivial edits is inefficient and risks stale records. Keep persistent review/plan gates for substantive implementation and bug fixes; scale lightweight work appropriately.
3. **Branch handling had unresolved prerequisites.** The source branch must be named and verified, and dirty-worktree handling must protect existing changes. Never silently discard, stash, or mix conflicting work.
4. **Commit confirmation was ambiguous.** Separate permission to commit from approval of the exact proposed commit message; never push without separate authorization.
5. **“Don't trust me” could be misread as adversarial.** Replace it with evidence-based verification: challenge incorrect or unsupported claims respectfully, distinguish evidence from assumptions, and explain uncertainty.
6. **Subagent use could become a quota.** Delegate only when work is genuinely independent, parallelizable, or benefits from context isolation/specialized expertise. Avoid single-file edits and direct commands; require bounded objectives and verifiable results.
7. **Review and completion scope needed clarification.** Inspect the relevant implementation rather than auditing unrelated code. Update phase/review statuses only after acceptance criteria are verified.
8. **Path convention was inconsistent.** Use `docs/plans/` and `docs/reviews/`, not singular `doc/plans`.
9. **Global and project-specific instructions were mixed.** The active user-level global copy contained Python version, dependency, test, module-layout, and schema constraints. Remove those from both global copies and retain them in this repository's root `AGENTS.md`.
10. **The copies had drifted.** Reconcile the bundled template and active user-level copy while preserving useful global guidance; do not overwrite user-only additions without review.

## Recommended approach

Use one concise, reusable global policy in both the bundled and active user-level copies. Make process proportional to risk, require explicit approval before substantive implementation, require a verified source branch and safe worktree before implementation, and separate commit-message approval from commit authorization. Keep project-specific commands and architecture in project instructions.

## Resolution status

| Finding | Status |
|---|---|
| Missing plan approval gate | Resolved in both global copies |
| Over-processing low-risk tasks | Resolved with task-proportional workflow |
| Branch/worktree ambiguity | Resolved with verified source-branch and preserve-work gates |
| Commit approval ambiguity | Resolved with exact-message approval before commit |
| Adversarial interpretation risk | Resolved with evidence-based, respectful verification |
| Subagent quota risk | Resolved with deliberate-use criteria |
| Review/status scope | Resolved with relevant-scope and verified-status language |
| Documentation path mismatch | Resolved using `docs/` |
| Project-only details in global copy | Removed; retained in root `AGENTS.md` |
| Bundled/user-level copy drift | Reconciled and verified |

## Verification

- Both global copies contain the same reusable rules.
- Project-specific Python/test/schema conventions remain in the project root `AGENTS.md`, not either global copy.
- `git diff --check` passes.
- Documentation-only change; automated tests are not applicable.

## Review status

Complete. No commit was made.
