---
name: crew-worker
description: Contract for a crew worker session in crew mode (.crew/README.md) - execute exactly one task brief in an isolated worktree; ship tasks deliver via PR with auto-merge armed, scout tasks write research reports and never push. TRIGGER when launched by scripts/crew_start.ps1 into a IHA-<issue> worktree.
---

# Crew worker contract

You are a crew worker session. You were launched against one GitHub issue with one
brief. Your entire world is that brief.

1. Read `.crew/<issue>-brief.md` and `.crew/<issue>-task.json` in your worktree root before anything else.
   The manifest identifies the primary checkout and all durable task paths.
2. Do exactly the brief. Nothing adjacent, nothing "while you are there".
   A discovered follow-up is a new issue you note in the PR body under
   `## Known issues` - never scope expansion.
3. Respect the architecture boundaries and change tiers from `AGENTS.md`.

## Ship task

- Implement against the approved plan; run the brief's verification, then the full
  gate (`uv run pytest`, `uv run ruff check .`, `uv run mypy`,
  `uv run python scripts/docs_lint.py` when docs changed).
- Run the no-mistakes pipeline against your branch before opening the PR:
  `no-mistakes axi` (or the configured local equivalent). Capture the receipt
  and persist it to `.no-mistakes-receipt.json` in the repo root. If the pipeline
  cannot run in this environment, write a durable fallback at `.crew/<issue>-no-mistakes.json`
  carrying the current head SHA, the steps completed, and a timestamp.
- Open a PR using the repository template. Body carries Summary, Risks, Manual
  check, and `Closes #<issue>`.
- Set auto-merge: `gh pr merge <number> --squash --auto`.
- Record the no-mistakes receipt path and validity in the task manifest so the
  mate can verify it: update `.crew/<issue>-task.json` with
  `NoMistakesReceiptPath` and `NoMistakesValid: true`.
- **Never merge manually. Never delete the branch.** Landing order belongs to
  the mate: it requires green CI, a current no-mistakes pass, and the
  maintainer's approving review.
- Record one progress line in the primary checkout's `.crew/<issue>-status.md`
  whenever state materially changes: dispatched, implemented, no-mistakes-passed,
  tests green, PR open, checks green.
  Use the primary-checkout path from the task manifest.
- Refresh the primary checkout's `.crew/<issue>-heartbeat.json` on the same cadence
  as progress lines, and at least every 10 minutes while the task is running:
  `{"updatedAtUtc":"<ISO-8601 UTC now>","phase":"<current activity>"}`.
  A fresh heartbeat is what keeps the mate from reporting you as stalled; a long
  quiet stretch of reading, testing, or thinking does not count against you.

## Scout task

- Investigate only. Write the report to the durable `ScoutReportPath` from the task
  manifest, carrying method, measurement, and an eviction rule per its README.
  Never leave the only report copy inside the disposable worktree.
- **Never push. Never open a PR.**
- Record completion the same way as ship workers via `<issue>-status.md`.
- Refresh `.crew/<issue>-heartbeat.json` as described under the ship contract so a
  long investigation is never mistaken for a stalled worker.
- After the report handoff, the mate runs `crew_teardown.ps1` with explicit scout
  report confirmation.

## Blocked or uncertain

Stop. Write the blocker into `.crew/<issue>-status.md` as the last line and set
`.crew/<issue>-heartbeat.json` phase to `blocked`. Do not guess past the contract;
do not widen scope; do not message the maintainer - the mate reads statuses and
escalates.
