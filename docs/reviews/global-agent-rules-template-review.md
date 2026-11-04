# Global Agent Rules Template Review

## Current implementation

`src/agent_skills/templates/AGENTS.base.md` is the bundled default global instruction template. It required review documents, phased plans, user approval, and feature branches for broadly described tasks. The CLI copies this template into the user config directory only when no user-level copy already exists.

## Findings and resolutions

1. **Scope mismatch:** Rules described as applying to every task required implementation actions even for read-only and non-code requests. **Resolved:** The template now explicitly protects read-only scope.
2. **Disproportionate process:** Persistent review/plan documents and approval gates were required even for routine changes. **Resolved:** Planning and documentation are now scaled to task size and risk.
3. **Branch workflow ambiguity:** Mandatory branch creation could conflict with repository and user workflows. **Resolved:** The template defers to the user or repository workflow and requires authorization where intent is unclear.
4. **Test expectation:** Behavioral changes needed a clear, practical test requirement. **Resolved:** The template requires relevant tests and appropriate verification, with transparent reporting of unavailable checks.
5. **Template propagation:** Existing user-level copies are not automatically updated from the bundled default. **Documented:** The initial polish changed only the bundled source as approved; the requested rule 13 was subsequently applied to both the bundled and active user-level templates.
6. **Subagent guidance:** A vague "don't forget" instruction could encourage unnecessary delegation. **Resolved:** Rule 13 recommends subagents for independent work, context isolation, or specialized expertise, and requires bounded objectives, verifiable output, and independent verification while discouraging needless delegation.
7. **Project-specific constraints in a reusable global template:** Python version, dependency policy, test command, module layout, and schema rules only apply to this repository. **Resolved:** Removed these constraints from the bundled global template; they remain in this repository's root `AGENTS.md`.

## Verification

Both template copies and the diff were reviewed. `git diff --check` passed. No automated test was needed for this documentation-only change.

## Review status

Complete. All findings in scope were addressed or explicitly documented.
