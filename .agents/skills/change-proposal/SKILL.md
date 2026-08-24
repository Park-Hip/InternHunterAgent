---
name: change-proposal
description: Prepare an approval-ready proposal for a substantial, contract-affecting, or uncertain change. Invoke before implementing a planned or research-led change, never for focused low-risk edits.
---

# Propose a change

1. Confirm the tier from `AGENTS.md` section 2. Direct changes do not need this skill.
2. Open one issue using the **Change proposal** template and fill every field:
   - Goal and expected outcome, stated as the observable end state.
   - Files and change surface, with explicit exclusions.
   - Compatibility boundary: contracts, APIs, schemas, documented claims touched.
   - Verification plan, including the manual check and its expected result.
   - Rollback path.
   - For research-led changes, linked evidence: measurements, spikes, primary sources.
3. Wait for maintainer approval on the issue before writing code.
4. Implement in a dedicated worktree branched from `origin/main`; keep the proposal's exclusions
   honest by recording discovered follow-ups as new issues instead of expanding scope.
5. Link the implementing pull request with `Closes #<n>` so approval and outcome stay attached to
   one thread.

One coherent change per proposal; do not bundle unrelated work to save a review cycle.
