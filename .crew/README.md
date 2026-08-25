# Crew mode

Mediator-driven parallel work for this repository. One mate session dispatches,
supervises, and lands worker sessions; the maintainer talks only to the mate and
gates every landing with one approving GitHub review.

This document is canonical for crew conventions. `AGENTS.md` points here rather
than duplicating it.

## Roles

| Role | What it does |
|---|---|
| Maintainer (captain) | Approves plans, approves ship merges on GitHub, answers escalations. Nothing else. |
| Mate | One standing agent session. Validates intake, writes briefs, launches workers, supervises, orders landings, escalates exactly what is listed below. |
| Workers | One session per task in its own disposable worktree. Reads only its brief. Ships open PRs; scouts write reports. Never push outside their contract, never merge. |

## Task shapes

- **Ship** - changes code or docs, delivers through a PR opened with
  `gh pr merge --squash --auto` and `Closes #<issue>`.
- **Scout** - investigation only; output goes to `research/`. Never pushes.

A task never blurs between shapes on its own. Changing shape is a decision for the
maintainer.

## Visible worker sessions

`scripts/crew_start.ps1` creates a new Windows Terminal tab in the worker's isolated worktree.

By default, it opens an interactive PowerShell prompt and does not start an AI harness.

Pass `-Harness <executable>` to start any installed command-line harness interactively in the new tab.

```powershell
.\scripts\crew_start.ps1 -Issue 123 -Autonomy ship -Harness codex
.\scripts\crew_start.ps1 -Issue 123 -Autonomy ship -Harness claude
.\scripts\crew_start.ps1 -Issue 123 -Autonomy scout -Harness pi
.\scripts\crew_start.ps1 -Issue 123 -Autonomy scout -Harness aider
```

The launcher validates the selected executable on `PATH` before it creates the worktree.

Use `-Harness shell` when you want to choose or start a harness manually.

The launcher is terminal-based and does not create sessions in VS Code, HerdR, or any other harness-specific UI.

## Intake rules (enforced by the mate)

- **Crew trigger.** Crew mode activates only when at least two pending tasks touch
  disjoint areas, or one ship task is accompanied by a scout task. Otherwise run the
  default sequential workflow.
- **Shared-surface lock.** At most one active ship may touch `src/**/models.py` or
  `config/settings.yaml`. Checked at dispatch from the brief's files-in-scope list.
- **Plan gate unchanged.** Every ship task still needs an approved plan (issue +
  change-proposal flow when the tier demands it) before any code exists.

Parallelism is bounded by these rules, not by a fixed number of workers.

## Merge policy

Every landed ship PR has, by construction, passed all three gates, enforced by
branch protection - not by convention:

1. Required CI checks green.
2. A recorded `/code-review` verdict.
3. The maintainer's approving review.

PRs open with `gh pr merge --squash --auto`; GitHub holds them until all three
hold. The mate presents each ready PR with a captain-facing summary (what changed,
risks, manual check) and executes serial landing order: merge, rebase remaining
worktrees onto the new tip, continue. The mate never merges manually and cannot
bypass protection.

One-time prerequisite (maintainer action): branch protection on `main` must enable
*require approve* alongside required status checks. Verify:

```sh
gh api repos/Park-Hip/InternHunterAgent/branches/main/protection/required_pull_request_reviews
```

Must return non-empty.

## Files

- `_brief.template.md` - skeleton filled per task by the mate or `crew_start.ps1`.
- `<issue>-brief.md` - the contract for one task: goal, files in scope, out of
  scope, verification, autonomy level.
- `<issue>-status.md` - worker-written progress line(s); last line wins.
- `events.log` - structured event lines appended by `mate_watch.ps1`:
  `<UTC timestamp> | <subject> | <event> | <detail>`.
- `.watch-state.json` - watcher bookkeeping; safe to delete when no crew is active.

## Escalation surface

The mate escalates exactly these and nothing else:

- Plan approval (unchanged gate).
- A ship PR ready for approving review.
- Merge conflicts it cannot resolve by rebasing.
- Repeated check failures on the same PR.
- Shared-surface lock conflicts discovered after dispatch.
- Scout findings that require a maintainer decision.

Everything else is reported as outcomes, not narrated as mechanics.

## Teardown

Worktrees are disposable: `git worktree remove ../IHA-<issue>` and delete the
matching `<issue>-*.md` records. When no crew is active the `.crew/` directory holds
only this README and the template.
