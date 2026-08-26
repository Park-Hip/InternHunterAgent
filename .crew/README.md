# Crew mode

Mediator-driven parallel work for this repository.
One mate session dispatches, supervises, and lands worker sessions.
The maintainer talks only to the mate and gates every landing with one approving GitHub review.

This document is canonical for crew conventions.
`AGENTS.md` points here rather than duplicating it.

## Roles

| Role | What it does |
|---|---|
| Maintainer (captain) | Approves plans, approves ship merges on GitHub, answers escalations. Nothing else. |
| Mate | One standing agent session. Validates intake, writes briefs, launches workers, supervises, orders landings, escalates exactly what is listed below. |
| Workers | One session per task in its own disposable worktree. Reads only its brief. Ships open PRs; scouts write reports. Never push outside their contract, never merge. |

## Task shapes

- **Ship** - changes code or docs and delivers through a PR opened with `gh pr merge --squash --auto` and `Closes #<issue>`.

- **Scout** - investigates only and writes its report to the durable path recorded in its task manifest.
  Scouts never push.

A task never blurs between shapes on its own.
Changing shape is a decision for the maintainer.

## Durable task lifecycle

New task worktrees are created at `..\InternHunterAgent-worktrees\IHA-<issue>`.
The `<issue>-task.json` manifest in the primary checkout's `.crew\` directory is the authoritative locator for the task's worktree, brief, branch, terminal backend, and scout report path.
The launcher also copies the brief and manifest into the task worktree, so a worker can read its contract locally from `.crew\<issue>-brief.md`.

For scout tasks, the durable report path is `research\crew\<issue>-report.md` in the primary checkout.
The worker must not leave the only report copy inside its disposable worktree.

Existing worktrees keep their `IHA-<issue>` names and locations.
The launcher never moves them.
Teardown for an existing task without a manifest remains a manual, path-specific operation.

## Visible worker sessions

`scripts/crew_start.ps1` launches the worker through an explicit terminal backend.
By default it opens the task worktree in a new VS Code window.
Pass `-Backend wt` to open a new Windows Terminal tab instead.
Pass `-Backend vscode-task` to register a "Crew: IHA-<issue> worker" task in this
checkout's `.vscode/tasks.json` without launching anything - then start it from
the terminal panel of an already-running window (Terminal > Run Task), which is
the only way to land a worker inside a window that is already open, because the
VS Code CLI cannot inject terminals into running windows.

By default, it opens an interactive PowerShell prompt and does not start an AI harness.
Pass `-Harness <executable>` to start any installed command-line harness interactively.

```powershell
.\scripts\crew_start.ps1 -Issue 123 -Autonomy ship -Harness codex
.\scripts\crew_start.ps1 -Issue 123 -Autonomy ship -Harness claude
.\scripts\crew_start.ps1 -Issue 123 -Autonomy scout -Harness pi
.\scripts\crew_start.ps1 -Issue 123 -Autonomy scout -Harness aider
# Register the worker as a task in this checkout's terminal panel (pi example):
.\scripts\crew_start.ps1 -Issue 123 -Autonomy ship -Harness pi -Backend vscode-task
```

With `-Harness codex`, codex starts with `--yolo` unless `-HarnessArgs` supplies
different arguments. Other harnesses start without extra arguments.

With `-Backend vscode-task`, the harness is started with the task brief as its
initial prompt argument, so it begins working on its contract immediately.
Every backend passes the brief to the harness this way; no human needs to type
anything into the worker session.

The launcher validates the selected executable on `PATH` before it creates the worktree.
Use `-Harness shell` when you want to choose or start a harness manually.
Use `-WhatIfMode` to inspect the worktree root, manifest, brief, report, and backend launch plan without changing disk.

### VS Code backend (default)

The VS Code CLI cannot inject a session into an already-running window, so each dispatch
opens its own new VS Code window on the worktree folder. When a harness is selected, the
launcher also writes `.vscode/tasks.json` into the worktree defining a dedicated integrated-
terminal task that runs on folder open, so the harness starts in VS Code's terminal panel as
a switchable terminal tab. One-time prerequisite: allow automatic tasks when prompted, or set
`"task.allowAutomaticTasks": "on"`. With `-Harness shell`, no automatic task is written.

## Intake rules (enforced by the mate)

- **Crew trigger.** Crew mode activates only when at least two pending tasks touch disjoint areas, or one ship task is accompanied by a scout task.
  Otherwise run the default sequential workflow.

- **Shared-surface lock.** At most one active ship may touch `src/**/models.py` or `config/settings.yaml`.
  Check this at dispatch from the brief's files-in-scope list.

- **Plan gate unchanged.** Every ship task still needs an approved plan, including the change-proposal flow when its tier demands it, before any code exists.

Parallelism is bounded by these rules, not by a fixed number of workers.

## Merge policy

Every landed ship PR has, by construction, passed all three gates, enforced by branch protection rather than convention.

1. Required CI checks green.
2. A recorded `/code-review` verdict.
3. The maintainer's approving review.

PRs open with `gh pr merge --squash --auto`.
GitHub holds them until all three gates hold.
The mate presents each ready PR with a captain-facing summary covering what changed, risks, and the manual check.
The mate executes the serial landing order: merge, rebase remaining worktrees onto the new tip, then continue.
The mate never merges manually and cannot bypass protection.

One-time prerequisite: branch protection on `main` must require approval alongside the required status checks.
Verify it with:

```sh
gh api repos/Park-Hip/InternHunterAgent/branches/main/protection/required_pull_request_reviews
```

The response must be non-empty.

## Files

- `_brief.template.md` - skeleton filled by the mate or `crew_start.ps1`.

- `<issue>-brief.md` - primary-checkout copy of the contract for one task.
  The task-local copy is at `.crew\<issue>-brief.md` in its worktree.

- `<issue>-task.json` - durable, primary-checkout task manifest and authoritative locator for newly dispatched tasks.

- `<issue>-status.md` - worker-written progress lines in the primary checkout.
  The last non-empty line wins.

- `events.log` - structured events appended by `mate_watch.ps1` in the format `<UTC timestamp> | <subject> | <event> | <detail>`.
  Event kinds: `PR_OPENED`, `CHECKS_GREEN`, `CHECKS_FAILED`, `PR_READY_FOR_REVIEW`, `PR_LANDABLE`, `PR_MERGED`, `PR_GONE`, `WORKER_STATUS_CHANGED`, plus direct completion events: `SCOUT_REPORT_READY` (a scout task's durable report appeared) and `WORKER_IDLE` (a worktree's dirty-file count unchanged across sweeps).
- `.watch-state.json` - watcher bookkeeping that is safe to delete when no crew is active.

The watcher raises a Windows toast for escalation-grade events (`CHECKS_FAILED`, `PR_READY_FOR_REVIEW`, `PR_LANDABLE`, `PR_MERGED`, `SCOUT_REPORT_READY`, `WORKER_IDLE`) so completion and failures surface without polling. Suppress with `mate_watch.ps1 -NoToast`; tune the idle threshold with `-IdleSweeps <n>` (default 5).

## Escalation surface

The mate escalates exactly these and nothing else:

- Plan approval.

- A ship PR ready for approving review.

- Merge conflicts it cannot resolve by rebasing.

- Repeated check failures on the same PR.

- Shared-surface lock conflicts discovered after dispatch.

- Scout findings that require a maintainer decision.

Everything else is reported as outcomes, not narrated as mechanics.

## Teardown

Use the manifest-aware teardown command for newly dispatched tasks:

```powershell
.\scripts\crew_teardown.ps1 -Issue 123
.\scripts\crew_teardown.ps1 -Issue 123 -ConfirmScoutReportHandoff
```

Teardown never forces removal of a dirty worktree.
For a scout, it refuses to remove the worktree unless the durable report exists and the operator explicitly confirms the handoff with `-ConfirmScoutReportHandoff`.
On success, it leaves the primary manifest in place and records that the task was torn down.

When no crew is active, stop the watcher.
The retained manifest, brief, status, and durable scout report support later inspection and manual recovery.
