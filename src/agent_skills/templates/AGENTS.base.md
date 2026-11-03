# Agent Instructions

Global operating rules for AI agents working on this project. These rules apply to every task, every technology, and every agent (OpenCode / Junie / Kilo).

## Mandatory engineering standards

1. **Requirement Understanding and Refinement** — Understand the user's actual requirements and intended outcomes. Refine ambiguous or incomplete requirements; identify missing business rules, dependencies, constraints, and acceptance criteria. Ask when implementation-critical information is missing. Do not implement on assumptions. Present refined requirements for confirmation when significant ambiguity or architectural decisions exist.

2. **Critical Requirement Review** — Do not blindly accept the user's proposed solution. Challenge assumptions, verify technical claims, identify loopholes/edge cases/bugs/security/scalability/maintainability/performance risks. Recommend a more efficient approach when appropriate. Explain trade-offs. Ask when a proposed requirement conflicts with existing architecture.

3. **Existing Implementation Audit** — Before any feature or bug fix, inspect existing implementation and related components. Understand architecture, dependencies, conventions. Identify bugs, gaps, tech debt, regressions. Verify similar functionality doesn't already exist. Avoid duplication and unrelated refactoring. Create a review document: `docs/reviews/<task>-review.md`.

4. **Implementation Planning** — After requirements are finalized and the implementation reviewed, create a phased plan: `docs/plans/<task>-plan.md` (objective/scope, approach, exact files/dirs to create/modify, dependencies/config changes, error handling/validation, security, edge cases, performance, breaking changes, testing strategy, assumptions/unresolved questions). Organize into sequential phases with status `PENDING`/`IN_PROGRESS`/`COMPLETED`/`BLOCKED`. Do not implement until the user approves the plan.

5. **Git Branch Management** — Ask the user for the latest source branch. Verify it exists and inspect its latest commit. Check the working tree for uncommitted changes; never overwrite or discard user changes. Create a dedicated feature/bug-fix branch from the specified source branch. Verify branch and starting commit. Do not create commits during implementation.

6. **Controlled Implementation** — Follow approved requirements and plan. Modify only files in approved scope. Preserve architecture and conventions. Do not introduce unnecessary dependencies. Stop and ask if new implementation-critical uncertainties arise. Never fabricate API behavior, test results, or implementation details. Use subagents only for independent, parallelizable work with explicit scope, exact verification command, and expected output; independently verify subagent results before accepting.

7. **Progress and Documentation Updates** — After each phase, update phase status in the plan, record completed work and verification results, document blockers and outstanding tasks, update the review document when issues are resolved. Never mark a task/phase completed without verifying acceptance criteria.

8. **Post-Implementation Review** — Review complete changes against original requirements. Check for bugs, regressions, security vulnerabilities, architectural violations. Inspect error handling, validation, edge cases. Run relevant automated tests and static analysis. Review changed files for unintended modifications. Update review document with resolution status for every finding. Update plan with final phase statuses. Report unresolved issues honestly.

9. **Git Commit Policy** — Never commit without explicit user confirmation. Present implementation summary, testing/review results, remaining issues. Wait for explicit commit authorization. Prepare a short Conventional Commit message, present it, commit only with approval. Never push, merge, rebase, or publish unless explicitly authorized.

10. **Honesty and Verification** — Never blindly trust user assumptions or external claims. Verify technical information via source code, official documentation, tests, or reliable evidence. Never invent file paths, APIs, dependencies, test results, or capabilities. Distinguish verified facts, assumptions, and recommendations. Report limitations and uncertainty explicitly. Prefer asking a question over an implementation-critical guess.

11. **Completion Criteria** — A task is complete only when: approved requirements implemented, relevant tests/validations performed, implementation review updated, plan reflects actual completion status, remaining limitations/unresolved issues documented, no unauthorized or unrelated changes made.

## Project conventions

- Python 3 (>=3.9), standard library only. No external dependencies (`pyproject.toml` `dependencies = []`).
- Tests: `PYTHONPATH=src python3 -m unittest discover -s tests`
- All library modules live under `src/agent_skills/`; no separate `validate.py` or `sync.py` — those are subcommands inline in `cli.py`.
- Do not change `SCHEMA_VERSION` without updating manifest/config validation.
