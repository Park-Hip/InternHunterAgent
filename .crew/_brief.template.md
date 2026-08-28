# Brief: {ISSUE_TITLE}

- **Issue:** #{ISSUE_NUMBER} - {ISSUE_URL}
- **Branch:** `{BRANCH}`
- **Autonomy:** {SHIP_OR_SCOUT}
- **Dispatched:** {DATE_UTC}
- **Primary checkout:** `{PRIMARY_REPO}`
- **Task manifest:** `{TASK_MANIFEST}`
- **Primary status:** `{PRIMARY_STATUS}`
- **Scout report:** `{SCOUT_REPORT}`

## Goal

{GOAL - one paragraph, observable end state}

## Evidence

- **Source:** `{DURABLE_RESEARCH_OR_APPROVED_PLAN_PATH}`
- **Heading:** `{STABLE_HEADING}`
- **Label:** `{GAP_OR_FINDING_ID}`
- **Finding:** {CONCISE_EVIDENCE_BACKED_REASON_FOR_THIS_TASK}

Cite the existing research or approved plan when one exists; for example, use the
Part 3 ingestion research's `G1` rather than restating it. All four fields are
required for a research/plan citation. The progress report falls back to this brief's
Goal only when a durable citation is unavailable.

## Files in scope

{PATHS - used by the mate for shared-surface lock checks}

## Out of scope

{EXCLUSIONS - anything adjacent the worker must not touch; discovered follow-ups become new issues, never scope creep}

## Verification

{CHECKS - focused tests/commands the worker must run before declaring done; ship workers also run the full gate: uv run pytest plus available lint gates}

## Contract reminder

Read this task-local brief and its task-local manifest before doing work.
Do exactly the brief.
Ship workers open a PR with the standard template, `Closes #{ISSUE_NUMBER}`, and `gh pr merge --squash --auto`.
Ship workers never merge manually.
Scouts write their complete report to the durable **Scout report** path above and never push.
Blocked or uncertain means stop and record the blocker in the primary checkout's `<issue>-status.md` path named by the manifest.
Never guess past the contract.
