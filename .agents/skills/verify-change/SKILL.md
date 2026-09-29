---
name: verify-change
description: Select and run focused verification after implementing a nontrivial change. Invoke after writing code or documentation, before requesting review.
---

# Verify a change

Derive the check list from the diff, not from habit:

1. Map each changed file to its nearest user-visible boundary (API route, service, agent runtime,
   ingestion, evaluation) and reproduce the behavior there.
2. Run the focused tests for the changed paths, for example `uv run pytest tests/<area>`.
3. For Markdown changes, run `uv run python scripts/docs_lint.py`.
4. For a change to `src/api/static/tokens.css`, run `uv run python scripts/check_contrast.py`.
   Every declared token pair must clear its floor in both themes.
5. For any change under `src/api/static/`, run `uv run python scripts/ui_screenshots.py` and
   **read the captured PNGs back**. Source review cannot see hierarchy, wrapping, or
   contrast as rendered. A UI change without a screenshot review is unfinished: name the
   single highest-impact visual flaw, fix only that, and capture again.
6. Before requesting review, run the full gate: `uv run pytest` plus available lint gates.
5. Record results in the pull request body, including one manual check with its expected result
   when an end-user or maintainer validation applies.

A failing check is fixed at the source or becomes a linked follow-up issue - never suppressed by
weakening the check without a decision record.
