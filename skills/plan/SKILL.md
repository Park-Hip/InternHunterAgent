---
name: plan
description: Prepare a concise, reviewable implementation plan for a repository change that needs approval before coding. Use for behavior, contract, operational, or multi-file changes, not routine focused edits.
---

# Plan a change

Read `CLAUDE.md`, `docs/Decision_Log.md`, and the relevant research record before planning.
Inspect the current implementation and tests before proposing file changes.

Use the tier rule in `CLAUDE.md`.
For a direct change, state briefly why no plan is needed and proceed with focused verification.
For a planned or research-led change, produce an approval artifact containing:

- Goal and expected outcome.
- Files to change and why.
- Explicit exclusions.
- Verification, including a manual check when applicable.
- Risks, sequencing constraints, and any decision the user must make.

Do not allocate ticket numbers, invent scopes, or create documentation entries.
Do not begin implementation until the user has approved a plan when the chosen tier requires it.
