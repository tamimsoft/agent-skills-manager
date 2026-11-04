# Global Agent Rules Template Plan

## Objective and scope

Make the bundled global agent-rules template concise, reusable, and practical across code and non-code tasks, including a clear test expectation for behavioral code changes.

The bundled source template was revised in the initial polish. The requested subagent rule was subsequently added to both the bundled template and active user-level template so they remain aligned on that guidance.

## Approach

- Respect read-only scope and user constraints.
- Ask only when material uncertainty could change the result.
- Inspect relevant context before code changes and challenge concrete risks.
- Scale planning and documentation to task size and risk.
- Preserve user work and follow the user's or repository's Git workflow.
- Add/update relevant behavioral tests, run suitable checks, and report results honestly.
- Use subagents when independent work, context isolation, or specialized expertise improves the result; verify delegated work.
- Require authorization for consequential Git operations.
- Keep repository-specific Python, test, module-layout, dependency, and schema constraints in that repository's own `AGENTS.md`, not in the reusable global base template. This repository's root `AGENTS.md` already carries those constraints.

## Files

- Updated `src/agent_skills/templates/AGENTS.base.md`.
- Kept this repository's Python, dependency, test, module-layout, and schema guidance in the root `AGENTS.md`; removed the duplicated project-only section from the bundled global template.
- Updated `~/.config/agent-skills/templates/AGENTS.base.md` with rule 13.
- Added `docs/reviews/global-agent-rules-template-review.md`.
- Added this plan.

No dependencies, configuration, or schema changes were made.

## Edge cases and limitations

- Read-only tasks must not change files or Git state.
- Small routine work does not require persistent planning or review artifacts unless the user or repository asks for them.
- Existing user-level templates are not changed automatically when the bundled default changes; keep the two copies aligned when explicitly requested.

## Phases

1. **Audit and requirements** — `COMPLETED`
2. **Revise the template** — `COMPLETED`
3. **Verify and close** — `COMPLETED`

## Verification

- Reviewed the changed template and diff for scope and consistency.
- `git diff --check` passed for the template change.
- Confirmed rule 13 is present in both bundled and active user-level templates.
- Manually reviewed the added review and plan documents.
- No automated tests were needed because this was documentation-only.

## Status

Implementation and verification are complete.
