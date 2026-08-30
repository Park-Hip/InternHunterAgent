# Crew mate workflow manual

> **Last verified:** 2026-10-10
>
> **Eviction:** Replace this guide when crew-mode dispatch, review, escalation, or teardown
> contracts change; keep the current contract in [.crew/README.md](README.md) and the mate
> behavior in [the crew-mate skill](../.agents/skills/crew-mate/SKILL.md).

This is the operating manual for a maintainer who wants to use the **crew mate** skill for the
first time. You communicate with one mate session. The mate coordinates workers, reviewers,
worktrees, and pull requests; you approve only the decisions that require a maintainer.

## 1. What crew mode is for

Crew mode turns one well-scoped GitHub issue into an isolated worker task. It is useful when a
task can be described as a durable contract and either:

- **Ship:** make a code or documentation change, validate it, open a pull request (PR), and let
  GitHub auto-merge it after all gates pass.
- **Scout:** investigate a question and write a durable report. A scout never pushes or opens a
  PR.

It can run one eligible task or several compatible tasks. It is not a way to skip planning,
review, CI, or maintainer approval.

### Roles and boundaries

| Role | You ask it to do | It must not do |
|---|---|---|
| Maintainer (you) | Create/clarify issues, approve plans, decide escalations, approve ready PRs on GitHub | Direct workers, manually merge ship PRs, or treat an agent summary as evidence |
| Mate | Validate intake, write task contracts, dispatch and supervise workers, order landings | Bypass a plan gate, approve a PR, manually merge, or hide a risk |
| Ship worker | Change only its briefed scope, verify, open and arm its PR | Work outside its brief or merge manually |
| Scout worker | Research only and save the report at its durable path | Push changes or leave the only report in its disposable worktree |
| Independent reviewer | Review the current PR head and publish a review verdict | Approve, merge, or reuse a verdict after a new push |

The mate is your only worker-facing interface. Do not message a worker to change scope or to
"just fix" something. Give the decision to the mate; it will update the durable workflow or
create a follow-up issue as appropriate.

## 2. Before the first dispatch

Complete these prerequisites in the primary checkout, not in a crew worktree:

1. **Authenticate tools.** `git`, GitHub CLI (`gh`), PowerShell, and the selected AI harness must
   be installed and available on `PATH`. `gh auth status` should identify the intended GitHub
   account.
2. **Protect `main`.** The repository requires status checks and a pull-request approval. Confirm
   that the GitHub protection endpoint described in [Merge policy](README.md#merge-policy) returns
   a non-empty result.
3. **Have an open GitHub issue.** Every crew task has exactly one issue. The issue is the
   accountability record; a ship PR must contain `Closes #<issue>`.
4. **Meet the planning gate.** Every ship task needs an approved plan before code work starts.
   Use the change-proposal process when the change tier requires it. A scout needs a clear research
   question and a durable report destination.
5. **Make scope explicit.** List files the task may change, files it must not change, verification
   commands, and a measurable end state. This is what lets the mate safely run work in parallel.
6. **Choose a task shape.** Say `ship` for an implementation/PR or `scout` for research only.
   Changing that choice later is a maintainer decision.

For multiple ships, compare every task's files-in-scope. Only one active ship may touch either
`src/**/models.py` or `config/settings.yaml`. This **shared-surface lock** is a safety boundary,
not a suggestion. Other overlapping scopes should normally be split or sequenced.

## 3. The commands you give the mate

Use the short phrases below in the mate chat. Replace `<n>` with the GitHub issue number.
The mate normalizes these phrases rather than guessing what you mean.

| What you type | What the mate does | What you should receive |
|---|---|---|
| `register #<n>` | Registers a VS Code terminal task; it does **not** open a terminal or window | The task label, primary `.vscode/tasks.json` path, and worktree path |
| `launch #<n>` or `open worker #<n>` | Opens a worker in a new VS Code window using the explicit VS Code backend | Worktree path and launch result |
| `review #<n>` or `review PR #<n>` | Sends a fresh, independent reviewer after the PR is ready to review | Review URL/id, reviewed head SHA, event, state, and inline-comment count |
| `status`, `progress`, `current progress`, or `how is the crew doing` | Reconciles durable state and generates the standard progress report | The report Markdown only |

If you say `run #<n>`, the mate must ask: **“Register it in this VS Code window, or open its own
VS Code window?”** Answer that question explicitly. `register` must never silently turn into a
new window launch.

### Recommended first-time sequence

For a first task, use this conversational sequence:

```text
I have an approved ship plan for issue #123. Register #123.
```

The mate checks eligibility and creates the durable task records. In the existing VS Code window,
start the returned `Crew: IHA-123 worker (...)` task through **Terminal: Run Task**. This is the
only standard backend that places the worker in an already-open VS Code window without a new
window.

Then ask:

```text
status
```

When CI is green, ask `review #123` only if the mate has not already dispatched the required
review. When the mate escalates the ready PR, inspect it and approve it **on GitHub**. Do not run
a local merge command.

## 4. What dispatch does, step by step

The mate must perform the following before treating a task as active:

1. Confirm the issue exists and is open.
2. Confirm the task is a ship or scout and that the required plan/research evidence is durable.
3. Check the shared-surface lock against active ships and the new brief's files-in-scope.
4. Prepare the task brief from the approved plan or research finding. A complete brief has a goal,
   evidence citation, scope, exclusions, and verification commands.
5. Use `scripts/crew_start.ps1` with the selected autonomy, harness, and explicit backend. For a
   `register` request, it uses `-Backend vscode-task`, `-Harness pi`, and
   `--model modelscope/deepseek-ai/DeepSeek-V4-Pro-0813`; it does not substitute a similarly
   named provider route.
6. Verify the launcher receipt: worktree, branch, brief, manifest, and terminal/task result.
7. Start `scripts/mate_watch.ps1` in the background if it is not already running.

The launcher creates a disposable worktree at a path like
`..\InternHunterAgent-worktrees\IHA-123`, from `origin/main`, and writes a manifest in the primary
checkout. The primary manifest is the authoritative locator. Do not move an existing crew
worktree by hand.

### Backends in plain language

| Backend | Use it when | What happens |
|---|---|---|
| `vscode-task` | You want to start the worker yourself in the current VS Code window | Registers a `Crew: IHA-<issue> worker` task; you run it from Terminal: Run Task |
| `vscode` | You want a dedicated VS Code worker window | Opens the worktree in a new window; the harness may start in its integrated terminal |
| `wt` | You prefer Windows Terminal | Opens a separate Windows Terminal tab at the worktree |
| `vscode-task-auto` | The optional local VS Code extension is installed and enabled | Registers the task and sends a constrained auto-launch request to the extension |

The launcher validates the requested harness before it creates a worktree. Use `-WhatIfMode` when
you need to inspect a launcher plan without changing disk. The mate should report a failed launch
as failed; a task is not successfully started just because a worker said it would start.

## 5. The durable records to trust

Crew mode is restart-safe because state lives on disk. On every new mate turn, the mate reconciles
these records instead of relying on chat memory.

| Record | Owner/purpose | How to use it |
|---|---|---|
| `.crew/<issue>-task.json` | Authoritative manifest | Find the worktree, branch, backend, brief, status, and scout report location |
| `.crew/<issue>-brief.md` | Task contract | Check goal, evidence, permitted scope, exclusions, and verification |
| `.crew/<issue>-status.md` | Worker status | The last non-empty line is the current worker update |
| `.crew/<issue>-heartbeat.json` | Worker liveness | Its age distinguishes a quiet worker from a stalled one |
| `.crew/events.log` | Watcher event history | Read new lines to see material changes and escalations |
| `research/crew` report named `<issue>-report.md` | Scout deliverable | Read the durable primary-checkout report after a scout completes |

The worker also receives a local copy of its brief and manifest in its worktree. That local copy is
for the worker's contract; the primary-checkout manifest is the durable source for coordination.

## 6. Supervision: what status means

The mate's normal supervision loop is deliberately mechanical:

1. Read new entries from `.crew/events.log`.
2. Run `scripts/crew_board.ps1` to obtain branches, dirty counts, worker status, heartbeat age,
   PR state, checks, and review status.
3. Report outcomes: landings, blockers, risks, and decisions needed.

When you explicitly ask for status, the mate must instead return the output of
`scripts/crew_progress_report.ps1 -Format markdown` without adding a hand-written substitute.
The report always has this order:

1. maintainer actions;
2. active tasks;
3. risks;
4. fully merged PRs;
5. recent material changes; and
6. next-compatible tasks.

Read the report as evidence, not an ETA forecast. An active task should cite durable plan or
research evidence. A merged PR is not active. A PR belongs in **fully merged** only when GitHub
shows it merged, the independent review has a current passing verdict, and you have approved it
on GitHub.

### Events and your response

| Event or condition | Mate action | Your action |
|---|---|---|
| Checks are pending | Continue supervision | Usually none |
| `CHECKS_FAILED` once | Return the failure to the worker | Usually none |
| Same checks fail twice consecutively | Escalate | Decide whether to change scope, diagnose, or stop the task |
| `PR_READY_FOR_REVIEW` / green checks | Dispatch an independent review | Wait for its receipt |
| Required review findings | Return findings to the worker; obtain a fresh review after the next green head | Usually none |
| Passing review on current head | Escalate the ready PR once | Inspect and approve or request changes on GitHub |
| `WORKER_STALLED` | Escalate | Choose restart or abandonment |
| Scout report raises a decision | Escalate | Decide the next issue/plan or close the question |
| Shared-surface conflict discovered after dispatch | Escalate | Choose which task proceeds or rescope them |

An unchanged dirty-file count (`WORKER_IDLE`) is informational. It is not proof that a worker has
failed. A stale heartbeat past the configured threshold is the escalation-grade stall signal.

## 7. Ship PR review and landing

A ship PR moves through these gates in this order:

```text
worker opens PR → required CI green → independent review on current head
→ no unresolved required findings → mate escalates → maintainer approves on GitHub
→ protected branch auto-merges → mate rebases remaining worktrees
```

The reviewer uses both the crew PR review process and the multi-axis code-review process. It checks
the diff, relevant tests, and verification story for correctness, readability, architecture,
security, and performance. Its evidence is a published GitHub **review comment**, not a label and
not a GitHub approval.

- A passing review comment includes a concise `/code-review` passing verdict tied to the current
  head SHA.
- Required fixes are summarized and, when line-specific, posted as actionable inline comments.
- After any worker push, the old verdict is stale. The mate waits for green checks and dispatches a
  fresh reviewer.
- Only you give GitHub's formal approval. The mate and reviewer never do so on your behalf.

When the mate escalates a ready PR, it should give its number, one-line summary, top risks, and a
manual check. Review those items in GitHub and approve there. The PR was opened with
`gh pr merge --squash --auto`; branch protection performs the actual landing after all gates pass.

If several PRs are ready, the mate selects a serial order. After each merge it fetches updated
`origin/main`, rebases each remaining worktree, resolves straightforward rebase work or escalates
a conflict, and confirms that checks re-run on the rebased tips. This prevents the next PR from
landing on an obsolete base.

## 8. Scout completion and follow-up

A scout is complete only after its report exists in `research/crew`, named
`<issue>-report.md`, in the primary checkout. Read that report before deciding the next step.
Possible outcomes are:

- create a new issue with the finding and approve a ship plan;
- request a different investigation; or
- accept the finding and end the work.

A scout does not create a PR and does not become a ship without an explicit maintainer decision.

## 9. Escalations: the complete list

The mate should interrupt you for exactly these matters:

1. plan approval;
2. a ship PR ready for your approving review;
3. a rebase conflict it cannot resolve alone;
4. two consecutive check failures on the same PR;
5. a shared-surface lock conflict found after dispatch;
6. a scout finding that requires your decision; or
7. a `WORKER_STALLED` worker that needs restart or abandonment.

For routine changes, the mate reports the outcome rather than narrating terminal commands or its
internal mechanics. Conversely, it must never hide a failure, risk, or escalation because it is
trying to be brief.

## 10. Completion, teardown, and recovery

After a ship is merged or a scout handoff is complete, the mate tears down the manifest-backed
worktree with `scripts/crew_teardown.ps1`:

```powershell
# Ship
.\scripts\crew_teardown.ps1 -Issue 123

# Scout: only after the durable report was checked and handed off
.\scripts\crew_teardown.ps1 -Issue 123 -ConfirmScoutReportHandoff
```

Teardown refuses to remove a dirty worktree. It also refuses a scout teardown unless the durable
report exists and the handoff is explicitly confirmed. A successful teardown retains the primary
manifest and marks it as torn down, preserving an audit trail.

For a task registered with `vscode-task`, confirm teardown removed only its matching `Crew:
IHA-<issue> worker` entry from the primary checkout's `.vscode/tasks.json`; unrelated tasks must
remain. The auto-launch backend also removes its launch-queue records.

When no crew task remains active, stop `scripts/mate_watch.ps1`. If you return after a restart,
ask `status`. The mate must rebuild the current picture from manifests, briefs, statuses,
heartbeats, events, GitHub, and the board rather than relying on the old conversation.

## 11. A compact checklist

### Before dispatch

- [ ] Open issue exists and has one clear ship or scout shape.
- [ ] Ship has an approved plan; scout has a clear question and report goal.
- [ ] Brief has goal, evidence, scope, exclusions, and verification.
- [ ] Concurrent scopes are compatible; the shared-surface lock is clear.
- [ ] You chose `register` or a dedicated-window launch deliberately.

### Before approving a ship PR

- [ ] Required CI is green on the current head.
- [ ] Fresh independent review is passing on that same head.
- [ ] No required review finding remains unresolved.
- [ ] Mate provided the PR summary, risks, and manual check.
- [ ] You reviewed and approved the PR on GitHub.

### Before declaring the fleet finished

- [ ] GitHub shows each ship PR as merged.
- [ ] Each scout report is present in `research/crew/` and its handoff is decided.
- [ ] Each manifest-backed task was safely torn down.
- [ ] The watcher is stopped because no crew task is active.

## Related references

- [Crew-mode conventions and scripts](README.md)
- [Crew mate skill contract](../.agents/skills/crew-mate/SKILL.md)
- [Crew worker contract](../.agents/skills/crew-worker/SKILL.md)
- [No-mistakes gate](../scripts/crew_no_mistakes.ps1)
- [Repository change policy](../AGENTS.md)
