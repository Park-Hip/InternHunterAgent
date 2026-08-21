# The Agentic Workflow

> **Status:** research record, written 2026-08-19. No implementation.
> It describes how work actually moves through this repository when agents do it, measures where
> it stalls, and proposes what to fix and what to encode as a skill.
> It does not restate the generator's contract, which is
> [`docs/entries/README.md`](../docs/entries/README.md), or the numbering rules, which are the
> header of [`docs/roadmap.yaml`](../docs/roadmap.yaml).

> **Last verified:** 2026-08-19 against `main` at `cf5027a`, the 40 most recent merged pull
> requests, the 60 most recent `ci.yml` runs, `scripts/docs_lint.py`, and `scripts/docs_build.py`.

> **Eviction:** A block leaves this record when its bottleneck is measured away, when the
> improvement it proposes ships, or when a re-measurement contradicts the evidence it rests on.

---

## 0. TL;DR

1. **The pipeline is fast and the design is sound.**
   Median pull-request lifetime is 7 minutes, and 30 of the last 40 merged in under 30.
   Nothing below argues for restructuring it.
2. **Every failure has the same shape: a mechanical step that someone must remember.**
   Ticket agents forget to run the generator, integrators forget the caps and the snapshot, and
   both learn to ignore a linter that reports findings they know are false.
3. **42 percent of CI runs fail**, and the single most common failing step is the documentation
   gate, which is advisory and blocks nothing.
4. **The deepest bottleneck is derived state in version control.**
   Generated regions are committed, so every concurrent pull request collides on the same lines,
   which forces the merge queue to run one at a time.
5. **Highest-leverage fixes, in order:** stop hand-committing generated regions, make the
   integration checklist a skill, and push the two most-missed checks into the linter.

---

## 1. Method

Read sections 1 to 7 of [`CLAUDE.md`](../CLAUDE.md), `docs/entries/README.md`,
`docs/Docs_Conventions.md`, the `frozen:` list and caps table, and the exemption paths in
`scripts/docs_lint.py`.
Measured throughput from the 40 most recent merged pull requests, CI health from the 60 most recent
`ci.yml` runs, and the integration job surface from the 32 `docs(integration):` commits.
Reproduced two claims directly: the linter's exemption behaviour under two diff bases, and the
test-suite runtime with and without the fixture-backed modules.

## 2. The pipeline as built

| Stage | Owner | Write surface | Enforcement |
|---|---|---|---|
| Allocate a number | integration session | `docs/roadmap.yaml` | `registry` check |
| Draft the ticket prompt | prompt session | none | the ticket-prompt skill |
| Implement | coder session in its own worktree | code, plus one file under `docs/entries/` | `scope` check |
| Render the registers | coder session | generated regions | `generated` check |
| Review and gate | CI | none | `checks` job, `docs` job |
| Merge and publish | integration session | the eight `frozen:` registers | `frozen` check |

The design goal is stated plainly in `docs/entries/README.md`: before this structure, every open
branch carried an edit to all eighteen documents under `docs/`, and the conflicts were structural
rather than accidental.
Moving each ticket's write to a private path removed that conflict class.

## 3. What the measurements say works

| Measure | Value | Reading |
|---|---|---|
| Median pull-request lifetime | 7 minutes | Review is not a bottleneck |
| Merged under 30 minutes | 30 of 40 | The common case is fast |
| Ticket entries on `main` | 26 | The private write surface is being used |
| Integration commits | 32 | The role is real and routine |
| Conflicts on ticket-owned code paths | none observed in the M33 batch | Scope declaration works |

The M33 batch is the strongest evidence for the design.
Five tickets ran in parallel across five branches, touching prompts, the glossary, the eval
registry, the tools, and the UI, and not one conflicted with another on a code path.
Every conflict was on a generated register, which is section 4.1.

## 4. Bottlenecks

### 4.1 Derived state lives in version control

Generated regions are rendered by `scripts/docs_build.py` and then committed, so two branches that
each add a ticket entry both rewrite the same lines of the same three registers.
All four M33 pull requests reported `CONFLICTING` against `main` on 2026-08-19, and every one of
them conflicted only on `docs/Completion_Reports.md` or `docs/Known_Issues.md`.

The cost is serialization.
Each branch had to be rebased, re-rendered, re-pushed, and re-gated before the next one could
start, which is why four already-green pull requests took eight minutes of merge work.

This is the ordinary failure mode of committing derived state, and it has ordinary remedies:
render in CI rather than on the branch, install a merge driver that re-runs the generator instead
of merging text, or keep committing and accept the serialization.

### 4.2 The integration queue has one server

Pull requests #78, #79 and #80 were opened at 06:00 and 06:01 and merged at 08:23, 08:26 and 08:28.
The work was finished and green for over two hours; what it waited for was an integration session
to exist.
Median lifetime is 7 minutes but the ninetieth percentile is 207, and that tail is this queue.

An integration session is also forbidden from carrying a ticket, by section 7, for a good reason:
one writer per merge is what keeps the shared registers true.
The constraint is sound, so the fix is to make an integration pass cheap enough to run often
rather than to relax it.

### 4.3 Mechanical steps that must be remembered

The `generated` check exists because a ticket agent can forget to run the generator.
One sampled CI failure carried seven `generated` findings at once, and the documentation gate is
the most frequently failing step in the whole workflow.

Integration has the same defect one layer up.
Three integration commits are same-session corrections of the commit before them, and each one
restores a hand-written step the previous commit omitted.

```
20:06:50  claim M32 prompt surface pass
20:11:27  refresh M32 repository state          <- the snapshot, 5 minutes later
20:52:52  publish M38 registers
21:16:17  point next ticket to M38              <- the next-ticket section, 23 minutes later
10:43:47  scope M33 into five ticket bodies
14:13:10  refresh the clone-local snapshot region
```

The M33 integration on 2026-08-19 repeated the pattern on a fourth step.
It archived 226 lines out of `docs/Tickets.md`, taking the file from 307 lines to 86, and left the
cap at 325; commit `8359c67` is the precedent for moving it, having lowered that same cap from 400
to 350 after archiving the M29 plan.

### 4.4 The documentation gate fails most and blocks nothing

Across the 60 most recent `ci.yml` runs: 33 succeeded, 25 failed, 2 were cancelled.
Sampling twelve failures by failing step:

| Failing step | Occurrences in 12 sampled failures |
|---|---|
| `docs_lint.py --diff-base origin/main` | 11 |
| `pytest -q` | 10 |
| `evals.replay` | 1 |

The documentation gate is the workflow's most common red light, and it is advisory rather than
required, which the known-issue register already records as a maintainer decision.
A gate that fires constantly and blocks nothing trains everyone to scroll past it.

The linter compounds this by reporting findings that are correct behaviour.
Section 7 step 5 says to lint and then commit, but `is_integration()` reads committed subjects in
`origin/main..HEAD`, so an uncommitted working tree yields no subjects and every frozen register
the integrator is entitled to edit is reported as a violation.
Measured against `main` at `cf5027a`, with one uncommitted edit to `docs/Tickets.md`:

| Working tree | `frozen` findings |
|---|---|
| Edit uncommitted | 1 |
| Edit absent or committed | 0 |

The M33 integration session filtered these by hand six times.
That is the actual damage: hand-filtering a check is how a real finding gets waved through.

### 4.5 Local verification needs a database that is usually down

`uv run python -m evals.replay` and the fixture-backed tests need Postgres on port 5433, and with
Docker Desktop stopped there is no local verification path at all.
Worse, two test modules block on the connect instead of skipping.

| Suite | Runtime |
|---|---|
| `uv run pytest -q` | 271 s |
| The same, minus the two fixture-backed modules | 10.5 s |

M39 was allocated on 2026-08-19 to fix this, which closes the item.
The general lesson stands: an agent that cannot verify locally will either wait on CI or, worse,
guess.

### 4.6 Worktree and stash debt

The clone holds 23 worktrees against 3 remote branches that are unmerged, so most worktrees
correspond to work that already landed.
Two long-lived stashes sit beneath them, one of which the current-state register describes as
unverified and believed superseded.
The primary worktree also carries untracked screenshots, a `.playwright-mcp/` log directory, and an
uncommitted edit to `AGENTS.md` and `CLAUDE.md`, all of which trip the linter locally and none of
which reach CI.

This debt is cheap individually and expensive together: it is the reason a local lint run cannot be
read at a glance, which feeds straight back into 4.4.

## 5. The common shape

Four of the six bottlenecks are the same defect wearing different clothes.
A step is mechanical, a person or agent has to remember it, and sometimes they do not.

| Forgotten step | Detected by | Cost |
|---|---|---|
| Run the generator before pushing | `generated` check, after the fact | The top CI failure |
| Move a cap after archiving | nothing | Silent drift |
| Refresh the snapshot region | nothing | A corrective commit |
| Write the next-ticket section | nothing | A corrective commit |

Two of these four have no detector at all.
That is the gap worth closing, and it is closed by a check where the step is mechanical and by a
carried checklist where it is a judgment.

## 6. Improvements ranked by leverage

| # | Change | Fixes | Cost |
|---|---|---|---|
| 1 | Stop hand-committing generated regions | 4.1 and the top CI failure | Design decision |
| 2 | An `integrate` skill carrying the checklist | 4.2, 4.3 | One file |
| 3 | Correct the lint order in section 7 | 4.4 | One word |
| 4 | A cap-slack check in the linter | 4.3 | Small, needs a number |
| 5 | Make the `docs` job required once it is quiet | 4.4 | Maintainer decision |
| 6 | A worktree and stash sweep | 4.6 | One session |

Change 1 is the only structural one and deserves a decision rather than a ticket.
The lightest form is a git merge driver registered in `.gitattributes` for the three generated
registers, which re-runs `scripts/docs_build.py` instead of merging text; branches keep committing
their regions, and the conflict class disappears.
The stronger form renders the regions in CI and stops committing them, which also removes the
`generated` check's reason to exist.
Both are worth costing before either is built.

Change 3 is a one-word reordering with a measured payoff: stage, commit as `docs(integration):`,
then lint, and amend if the lint reports something.

## 7. What should become a skill

A skill earns its place where the work is judgment-bound but the procedure is fixed, and where a
cold session would otherwise re-derive it.
By that test:

| Candidate | Verdict | Why |
|---|---|---|
| Integration pass | **Yes** | 32 runs, fixed checklist, omission failure mode, existing precedent |
| Running the generator | No | Mechanical; belongs in a hook or a required gate |
| Cap maintenance | No | Mechanical; belongs in the linter |
| Ticket prompt drafting | Already one | `skills/generate-ticket-prompt/SKILL.md` |
| Worktree cleanup | No | A script, not a judgment |

The integration skill should carry four things and nothing else: the merge recipe, the ordered
checklist of hand-written steps with caps and next-ticket flagged as the most-missed, the
commit-then-lint order and its reason, and the preconditions worth checking in the first minute.
It should not restate what the generator does.

It was written on 2026-08-19 as [`skills/integrate/SKILL.md`](../skills/integrate/SKILL.md),
carrying exactly those four things.
The rest of this section is the evidence it was drafted from.

The merge recipe, written out:

- Rebase the pull-request head onto `origin/main`; never merge `main` into a ticket branch.
- Resolve a conflict inside a generated region by re-running `scripts/docs_build.py` from that
  worktree, never by hand-merging the region.
- Force-push the rebased head and merge only once CI is green **on the rebased head**.
- CI runs `on: pull_request` only, so a push to `main` triggers nothing and verifies nothing.
- Take open pull requests one at a time, because they all collide on the same generated register.
- If a branch is checked out in another worktree, rebase a detached head and push to its ref.

The preconditions, both one command:

- `docker compose ps` decides whether local verification is possible at all.
- With that database down, prefer CI over a local run, and expect the suite to take minutes.

## 8. Open items

| Item | Status |
|---|---|
| `skills/integrate/SKILL.md` | Written 2026-08-19; needs its `.claude/` mirror and a Codex interface |
| Section 7 step 5, commit-then-lint | Correction proposed; touches `CLAUDE.md` and `AGENTS.md` |
| Section 7 step 1, the merge recipe | Correction proposed; touches `CLAUDE.md` and `AGENTS.md` |
| Generated regions in version control | Decision open; two remedies costed above |
| Cap-slack check in `scripts/docs_lint.py` | Proposed; needs a ticket number |
| `docs/Tickets.md` cap at 325 against 86 lines | Open, from the 2026-08-19 M33 integration |
| Fixture-backed modules that block instead of skipping | Allocated as M39 on 2026-08-19 |
| 23 worktrees, 2 stashes, untracked captures | Open |
