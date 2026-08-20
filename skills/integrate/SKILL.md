---
name: integrate
description: Merge ready pull requests one at a time and publish derived repository-state documentation. Use for integration sessions, not feature implementation.
---

# Integration

Do not implement a feature in the same session.

- Inspect ready pull requests and the active worktrees first.
- Rebase each pull request onto `origin/main`; never merge `main` into its branch.
- Wait for required checks on the rebased head before merging one pull request at a time.
- Resolve generated documentation conflicts by rerunning `python scripts/docs_build.py`, never by
  hand-editing generated regions.
- Refresh repository-state documentation with `python scripts/docs_build.py` and verify it with
  `python scripts/docs_build.py --check` plus `python scripts/docs_lint.py`.
- Do not use a bare `git stash` or PowerShell text round-trips for Markdown.
