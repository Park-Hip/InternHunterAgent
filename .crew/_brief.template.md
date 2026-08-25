# Brief: {ISSUE_TITLE}

- **Issue:** #{ISSUE_NUMBER} - {ISSUE_URL}
- **Branch:** `{BRANCH}`
- **Autonomy:** {SHIP_OR_SCOUT}
- **Dispatched:** {DATE_UTC}

## Goal

{GOAL - one paragraph, observable end state}

## Files in scope

{PATHS - used by the mate for shared-surface lock checks}

## Out of scope

{EXCLUSIONS - anything adjacent the worker must not touch; discovered follow-ups
become new issues, never scope creep}

## Verification

{CHECKS - focused tests/commands the worker must run before declaring done;
ship workers also run the full gate: uv run pytest plus available lint gates}

## Contract reminder

Read the brief and nothing else. Do exactly the brief. Ship workers open a PR with
the standard template, `Closes #{ISSUE_NUMBER}`, and `gh pr merge --squash --auto`;
never merge manually. Scouts write the report under `research/` and never push.
Blocked or uncertain means stop and record the blocker in `<issue>-status.md`;
never guess past the contract.
