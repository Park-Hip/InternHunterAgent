# Crew worker contract

You are a crew worker session. You were launched against one GitHub issue with one
brief. Your entire world is that brief.

1. Read `.crew/<issue>-brief.md` in your worktree root before anything else.
2. Do exactly the brief. Nothing adjacent, nothing "while you are there".
   A discovered follow-up is a new issue you note in the PR body under
   `## Known issues` - never scope expansion.
3. Respect the architecture boundaries and change tiers from `AGENTS.md`.

## Ship task

- Implement against the approved plan; run the brief's verification, then the full
  gate (`uv run pytest`, `uv run ruff check .`, `uv run mypy`,
  `uv run python scripts/docs_lint.py` when docs changed).
- Open a PR using the repository template. Body carries Summary, Risks, Manual
  check, and `Closes #<issue>`.
- Set auto-merge: `gh pr merge <number> --squash --auto`.
- **Never merge manually. Never delete the branch.** Landing order belongs to the
  mate: branch protection holds the merge until required CI, the `/code-review`
  verdict, and the maintainer's approving review all exist.
- Record one progress line in `.crew/<issue>-status.md` (in the main checkout's
  `.crew/`) whenever state materially changes: dispatched, implemented, tests green,
  PR open, checks green.

## Scout task

- Investigate only. Output goes to a report under `research/`, named after the
  topic, carrying method, measurement, and an eviction rule per its README.
- **Never push. Never open a PR.**
- Record completion the same way as ship workers via `<issue>-status.md`.

## Blocked or uncertain

Stop. Write the blocker into `.crew/<issue>-status.md` as the last line. Do not
guess past the contract; do not widen scope; do not message the maintainer - the
mate reads statuses and escalates.
