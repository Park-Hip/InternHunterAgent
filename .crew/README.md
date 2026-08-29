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
| Mate | One standing agent session. Validates intake, writes briefs, launches workers and independent PR reviewers, supervises, orders landings, escalates exactly what is listed below. |
| Workers | One session per task in its own disposable worktree. Reads only its brief. Ships open PRs; scouts write reports. Never push outside their contract, never merge. |
| Review subagent | Independently reviews one ship PR using the `code-review-and-quality` skill. Records its verdict and actionable findings on the PR; never merges. |

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
the only way to land a worker inside a window that is already open without help,
because the VS Code CLI cannot inject terminals into running windows.
Pass `-Backend vscode-task-auto` to register the same task and publish a launch
request into `.crew/launch-queue` that a local, opt-in VS Code extension runs in
the already-open window - no `Run Task` click. See
[the extension README](../vscode/crew-launcher/README.md).

By default, it opens an interactive PowerShell prompt and does not start an AI harness.
Pass `-Harness <executable>` to start any installed command-line harness interactively.

```powershell
.\scripts\crew_start.ps1 -Issue 123 -Autonomy ship -Harness codex
.\scripts\crew_start.ps1 -Issue 123 -Autonomy ship -Harness claude
.\scripts\crew_start.ps1 -Issue 123 -Autonomy scout -Harness pi
.\scripts\crew_start.ps1 -Issue 123 -Autonomy scout -Harness aider
# Register the worker as a task in this checkout's terminal panel (pi example):
.\scripts\crew_start.ps1 -Issue 123 -Autonomy ship -Harness pi -Backend vscode-task
# Register and auto-launch it in the current window (pi example):
.\scripts\crew_start.ps1 -Issue 123 -Autonomy ship -Harness pi -Backend vscode-task-auto
```

With `-Harness codex`, codex starts with `--yolo` unless `-HarnessArgs` supplies
different arguments. Other harnesses start without extra arguments.

With `-Backend vscode-task` or `-Backend vscode-task-auto`, the harness is started
with the task brief as its initial prompt argument, so it begins working on its
contract immediately.
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

### VS Code auto-launch backend

Pass `-Backend vscode-task-auto` to land a worker in an already-open window without
clicking **Run Task**. The launcher registers the usual workspace task and publishes
an immutable launch request into `.crew/launch-queue/requests`. A local, opt-in
extension (`vscode/crew-launcher`) watches that queue and calls the VS Code Tasks API
on the matching task in the current window.

Prerequisites:

- Install the packaged extension and reload VS Code.
- Trust the workspace.
- Turn on the opt-in: `"crew.vscodeTaskAuto.enabled": true` (default off).

The extension executes only a pre-registered workspace task whose `type`, `command`,
`args`, and `cwd` exactly match the canonical spec pinned in the task manifest; any
mismatch is `refused`. See [the extension README](../vscode/crew-launcher/README.md).

## Intake rules (enforced by the mate)

- **Crew eligibility.** Crew mode has no minimum task count: it may dispatch one approved ship or scout task, or a suitable set of tasks. When multiple ship tasks run concurrently, they must still have disjoint scopes except as allowed by the shared-surface lock.

- **Shared-surface lock.** At most one active ship may touch `src/**/models.py` or `config/settings.yaml`.
  Check this at dispatch from the brief's files-in-scope list.

- **Plan gate unchanged.** Every ship task still needs an approved plan, including the change-proposal flow when its tier demands it, before any code exists.

Parallelism is bounded by these rules, not by a fixed number of workers.

## Merge policy

Every landed ship PR has, by construction, passed all four gates.

1. Required CI checks green.
2. An independent review subagent has reviewed the PR with the `code-review-and-quality` skill.
3. That review has a recorded passing `/code-review` verdict with no unresolved required findings.
4. The maintainer's approving review.

When a ship PR has green checks, the mate dispatches a fresh, independent review subagent. The reviewer examines the change and its verification story across the skill's correctness, readability, architecture, security, and performance axes. It records the result as a GitHub PR **review comment**: a concise passing verdict when no required fixes remain, or a summary of required fixes when they do. Required findings are posted as actionable inline PR comments when they apply to a specific line; otherwise they belong in the review summary. The reviewer never uses a GitHub approval as its passing verdict, leaving that formal approval exclusively to the maintainer. Labels are optional dashboard metadata and never evidence of review.

A required finding sends the PR back to its worker. After the worker pushes the fixes and checks are green again, the mate dispatches a new independent review; the PR is not ready for maintainer approval until that re-review records a passing verdict. The mate then presents the PR with its number, one-line summary, top risks, and manual check.

PRs open with `gh pr merge --squash --auto`.
GitHub holds them until the protected CI and maintainer-approval gates hold; the mate additionally enforces the delegated-review gates above.
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

- `<issue>-heartbeat.json` - durable worker heartbeat in the primary checkout:
  `{"updatedAtUtc":"<ISO-8601 UTC>","phase":"<activity>"}`. Written on dispatch by
  `crew_start.ps1` and refreshed by the worker; its age drives stalled detection.

- `events.log` - structured events appended by `mate_watch.ps1` in the format `<UTC timestamp> | <subject> | <event> | <detail>`.
  Event kinds: `PR_OPENED`, `CHECKS_GREEN`, `CHECKS_FAILED`, `PR_READY_FOR_REVIEW`, `PR_LANDABLE`, `PR_MERGED`, `PR_GONE`, `WORKER_STATUS_CHANGED`, plus direct completion events `SCOUT_REPORT_READY` (a scout task's durable report appeared) and `WORKER_IDLE` (a worktree's dirty-file count unchanged across sweeps - informational, not a health verdict), and the health event `WORKER_STALLED` (a worker's heartbeat has been stale past `StalledAfterSec`).
- `.watch-state.json` - watcher bookkeeping that is safe to delete when no crew is active.

The watcher raises a Windows toast for escalation-grade events (`CHECKS_FAILED`, `PR_READY_FOR_REVIEW`, `PR_LANDABLE`, `PR_MERGED`, `SCOUT_REPORT_READY`, `WORKER_STALLED`) so completion and failures surface without polling. `WORKER_IDLE` (unchanged dirty-file count) is informational and raises no toast. Suppress with `mate_watch.ps1 -NoToast`; tune the idle threshold with `-IdleSweeps <n>` (default 5) and the stall threshold with `-StalledAfterSec <n>` (default 900).

## Progress reports

When the maintainer asks for crew progress, the mate first reconciles durable state and then uses `scripts/crew_progress_report.ps1 -Format markdown`. Markdown is the captain-facing default; use `-Format html` only when the maintainer explicitly asks for HTML, and `-Format data` when the structured payload itself is needed. All three formats are derived from the same payload.

The report has a fixed order: maintainer actions, active tasks, risks, fully merged PRs, recent material changes, and next-compatible tasks. Active tasks render as a table with the task goal, PR state, and evidence/source. A task brief should cite its durable research or approved plan in an `## Evidence` section with Source, Heading, Label, and Finding fields; the report falls back to that brief's Goal when no complete citation exists. Merged PRs are excluded from active tasks. A fully merged PR requires GitHub's merged state, a maintainer approval, and a passing `/code-review` verdict. Empty sections are explicit. It does not infer worker progress, ETA, evidence, approval, or dispatch decisions beyond the state it reads.

`.crew/candidates.json` is an ignored local runtime record for **undispatched** candidates. The mate creates or updates a candidate after durable local evidence is available, and removes it after dispatch or abandonment. Its top-level shape is `{ "schemaVersion": 1, "candidates": [] }`. Every candidate requires `issue`, `type` (`ship` or `scout`), `goal`, `filesInScope`, `planStatus`, `compatibility`, and an `evidence` object with `source`, `heading`, `label`, and `excerpt`. `source` is a local durable path; `heading` and `label` are stable finding/gap identifiers. The reporter ignores incomplete records and exposes a data warning instead of inventing provenance. It rechecks plan approval and the active `src/**/models.py` / `config/settings.yaml` shared-surface lock before marking a record dispatchable; it never dispatches automatically.

```powershell
# Default captain-facing Markdown
.\scripts\crew_progress_report.ps1

# HTML only when explicitly requested
.\scripts\crew_progress_report.ps1 -Format html
```

## Escalation surface

The mate escalates exactly these and nothing else:

- Plan approval.

- A ship PR ready for approving review.

- Merge conflicts it cannot resolve by rebasing.

- Repeated check failures on the same PR.

- Shared-surface lock conflicts discovered after dispatch.

- Scout findings that require a maintainer decision.

- A worker stalled past its heartbeat threshold.

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
For tasks dispatched with `-Backend vscode-task`, teardown also removes the matching `Crew: IHA-<issue> worker` entry from this checkout's `.vscode/tasks.json`. For `-Backend vscode-task-auto`, teardown additionally removes that request's queue and result records from `.crew/launch-queue`.

When no crew is active, stop the watcher.
The retained manifest, brief, status, and durable scout report support later inspection and manual recovery.
