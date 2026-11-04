# Global Agent Roles Rules Plan

## Objective

Refine the proposed global agent workflow rules into concise, reusable instructions, align the bundled template with the active user-level copy, and keep project-specific conventions out of global instructions.

## Scope

- `src/agent_skills/templates/AGENTS.base.md`
- `~/.config/agent-skills/templates/AGENTS.base.md`
- `docs/reviews/global-agent-roles-review.md`
- This plan
- Leave repository-specific instructions in root `AGENTS.md`.
- Documentation only; no code, dependency, schema, or test behavior changes.
- Do not commit or push.

## Approach

1. Review the current bundled and active user-level copies and record concrete loopholes.
2. Add explicit approval and branch/worktree gates for substantive changes, while scaling process to task risk.
3. Define evidence-based requirement review, relevant-scope implementation review, tests and verification, phase-status updates, and honest completion reporting.
4. Require explicit commit authorization and separate approval of the exact commit message.
5. Use subagents only for genuinely independent work or useful context isolation, with bounded objectives and verifiable results.
6. Apply the same global rule content to both copies. Keep project-specific Python, dependency, test, and schema guidance in root `AGENTS.md`.
7. Verify copy consistency, path/scope separation, and whitespace; do not commit.

## Phases

1. **Review proposed requirements and current copies** — `COMPLETED`
   - Findings recorded in `docs/reviews/global-agent-roles-review.md`.
2. **Resolve branch and preserve existing changes** — `COMPLETED`
   - No source branch was supplied. The verified current branch `docs/polish-global-agent-rules` at `7eed41c` was used as the source; related uncommitted edits were carried to `docs/global-agent-roles` without alteration.
3. **Reconcile global rule copies** — `COMPLETED`
   - Update bundled and active user-level copies; remove project-specific conventions from both.
4. **Verify and close** — `COMPLETED`
   - Confirm identical global rules, confirm project-specific rules remain in root `AGENTS.md`, and run `git diff --check`.

## Acceptance criteria

- The rules clearly distinguish read-only/research work from implementation.
- Requirements are refined and concrete risks/counterevidence are raised respectfully.
- Substantive changes require relevant implementation review, a phased plan, and approval before implementation.
- Source branch and dirty-worktree checks protect existing work.
- Code changes include relevant tests and exact verification reporting.
- Review/plan statuses are updated only after verified acceptance criteria.
- Commit and push are never implicit; exact commit message approval is required before committing.
- Subagents are used only when justified, with bounded tasks and verifiable outcomes.
- Both global copies are aligned and contain no project-specific Python/test/schema constraints.
- No commit or push is made.

## Status

Implementation and verification are complete. No commit or push was made.
