# Evaluation Operating Manual

> **Last verified:** 2026-08-22.

> **Eviction:** A claim here leaves when the module, statuses, or constraint it describes changes.
> This file explains how the instrument works and why; [`README.md`](README.md) owns the module
> layout and the exact commands, [`scenarios_v1.yaml`](scenarios_v1.yaml) owns what gets asked, and
> [`docs/Agent_Behavior_Spec.md`](../docs/Agent_Behavior_Spec.md) owns what correct behavior is.

Reading final answers only tells you *that* something went wrong, never *where*.
If the agent says "3 machine learning jobs" and the truth is 5, the answer alone cannot say
whether it picked the wrong tool, wrote a bad query, or summarized good data badly - three
different bugs with three different fixes.
That is not hypothetical: an earlier evaluation round captured only final answers, and when eight
of them came back empty, the evidence could not say why.
So this instrument records the agent's work at three internal points and grades each one
separately against a frozen, known-correct database.

## The three seams

One user question produces one **turn**.
Inside that turn the agent typically makes three model calls, and each is a **seam** where
evidence gets captured.

1. **Routing.** The agent has three tools: `query_clean_jobs`, `get_job_details`, and
   `get_current_time`. Some questions should call no tool at all - a request to delete data, or to
   reveal the raw SQL - and this seam records which tool, if any, actually ran.
2. **NL to SQL.** A second call turns the question into a SQL query. This seam records the exact
   query text and the rows it returned. It is where a real bug was caught: matching `%ML%` against
   `tech_stack` silently pulled in *MLOps* and *MLflow*.
3. **Synthesis.** The rows come back and a third call writes the human answer, which this seam
   records. Correct rows can still produce a dishonest answer - naming one "highest paid" job
   across salaries in different currencies, for instance.

The evaluation does not call the web API or wrap the agent in special code.
It builds the same agent the product builds, runs it in-process, and reads the seams out of the
tracing spans the agent already emits.
A telemetry callback rides along on the same call to record tokens, latency, and each call's
finish reason.

The rule that shapes everything downstream: mark the **earliest** wrong seam and stop.
If the SQL was wrong, the bad answer downstream is not a second bug - it is the same bug, observed
later.
This is why the deterministic grader stops at the first failing tier (below), and why the viewer
shows one turn per screen in seam order.

## The three scenario classes

Every question lives in `scenarios_v1.yaml`, 29 entries.
The ID carries its own class, so `HON-CURRENCY-1` reads as honesty without a lookup table.

| Class | Count | Should |
|---|---:|---|
| `SAF` - Safety | 6 | Refuse or redirect: destructive requests, prompt injection, off-topic questions, discriminatory filtering. Correct behavior usually means no tool call at all. |
| `HON` - Honesty | 9 | Not overclaim: no cross-currency salary comparison, no record-creation date read as a posting date, no invented results, no leaked raw SQL. |
| `HLP` - Helpfulness | 14 | Actually answer: counts, lists, follow-ups that build on context, location synonyms like Saigon and Ho Chi Minh City, abbreviations like ML. |

Fifteen of the 29 are **probes** - cases judged most likely to wobble, so the determinism protocol
(`docs/Agent_Behavior_Spec.md` §5) runs each three times instead of two.
Two are **conversational**, sharing one memory thread across turns to test whether a follow-up
keeps earlier context.
Eighteen carry **reference SQL**: the query a correct agent's own query should be equivalent to,
by result set rather than by text.
The other eleven are exempt - a refusal has no correct SQL.
A full run is therefore 77 turns: 45 repeats from the 15 probes, 28 from the 14 non-probes, plus
one extra turn for each of the two conversational scenarios' two repeats.

## From command to graded artifact

```powershell
uv run python -m evals.driver --output evals/runs/run.json
```

One command starts a run.
Everything after that is designed around one assumption: the run will probably be interrupted, so
no completed work may ever be lost.

**The fixture.** The agent is not pointed at the real job database.
It queries a frozen 22-row copy built through the same Alembic migrations as production, so its
schema cannot silently drift from the real thing.
22 rows is deliberate: small enough that a human can verify every expected answer by hand, large
enough to contain the awkward cases - missing expiry dates, salaries in two currencies, Vietnamese
company names.

**The manifest.** Before the first model call, the run records what produced it: the Git commit,
hashes of the prompt, the settings, the scenario file, and the fixture, plus whether the working
tree was clean.
A run from an uncommitted tree is still readable, but it is flagged `baseline_eligible: false` and
`uv run python -m evals.driver diff` refuses to compare it with another run.

**Checkpointing.** The artifact is rewritten to disk after every turn, and again after every
repeat.
When a call fails on quota, the driver marks that repeat `INFRA` and moves to the next scenario.
A single 429 does not end the run: on DeepSeek it is concurrency backpressure rather than an
exhausted budget, the next scenario will likely succeed, and finishing the registry costs about
four cents (D-e).
Only `CONSECUTIVE_QUOTA_FAILURES_BEFORE_HALT` failures in a row read as an exhausted account. That
sets `status: PARTIAL_QUOTA`, marks every scenario after the current one `UNRUN`, and stops, so a
genuinely dead key does not burn the whole registry.
Because a survivable 429 no longer changes the run's own status, `status: COMPLETE` means the run
reached the end of the registry, not that every scenario in it succeeded.
Read `manifest.scenario_status_counts` for that: it tallies the scenario records, so a capture that
survived one blip reads `{"COMPLETE": 28, "INFRA": 1}` rather than requiring a walk through all 29.
`--resume` reopens that artifact, keeps only the repeats already marked `COMPLETE`, and continues
from there - so a scenario that completed 2 of its 3 probe repeats resumes on the third, not from
scratch.
Checkpointing is interrupt safety, not quota survival. A capture is five minutes of live model
calls that cannot be reproduced, so anything that ends the process early - a halt, a lost network,
a closed laptop - must leave readable evidence behind rather than nothing.

**Execution accuracy.** Rather than comparing SQL text - where many different queries are all
correct - `execution_accuracy.py` runs both the agent's query and the reference query against the
fixture and compares the result sets as unordered multisets (`collections.Counter`, including
duplicates).
Different-but-equivalent SQL passes; same-looking-but-wrong SQL fails.

Everything from execution accuracy onward makes no model call, so grading a captured run is free
and repeatable.

## Running an arm: the order that protects the evidence

The steps below are ordered by what is recoverable, not by convenience.
Exactly one of them spends money and cannot be repeated; everything else is free and idempotent.
[`README.md`](README.md) owns the exact commands.

1. **Pin the inputs.** Fixture up and hash-verified, registry frozen, working tree committed. The
   manifest records `fixture_hash`, `git_sha`, `prompt_hash`, provider, model, and sampling, and
   that block is the only thing that makes two arms comparable. Never capture from a dirty tree:
   the run is flagged `baseline_eligible: false` and `driver diff` will refuse it.
2. **Capture.** `driver --output evals/runs/<arm>.json`, resumable with `--resume`. This is the
   only step that spends serving credit and the only one that cannot be reproduced - the model is
   non-deterministic, and `git_sha` and `prompt_hash` move underneath you, so a later run is a new
   arm rather than the same one. Treat the artifact as write-once.
3. **Freeze, before reading anything.** Project the capture into a sanitized replay under
   [`replays/`](replays/) and commit it. Until this happens the measurement exists in one ignored
   directory on one machine; after it, every downstream step is reproducible from the repository
   alone. **This step has no command yet** - `replay.py` reads and validates the format but nothing
   writes it, so the one committed replay was assembled by hand and covers 4 scenarios of 29.
   T0030.1 is where the writer lands; until it does, this step is manual and therefore the step
   most likely to be skipped.
4. **Grade and read.** `grader` produces the report, and `viewer <run> --grade <grade>` joins it per
   turn. Filter to `FAIL` and walk each one, reading the failing check's `detail` beside the seam it
   judges. That is how 33 failures separate into behavior and rule artifacts.
5. **Write the dated record, then leave it alone.** It is evidence, superseded by re-measurement and
   never edited. Route real defects to the behavior milestone and rule artifacts to the registry.

Two rules carry the weight, and both have been learned the expensive way.

**Freeze before you analyze.** Analysis is what makes a run feel finished, so a capture left
unfrozen until "after the write-up" is a capture nobody froze. On 2026-08-16 the T0027.3 DeepSeek
capture was lost this way - 77 turns, 29 of 29 scenarios, the only full measurement taken to date -
when the worktree holding it was removed after its pull request merged. Its findings survive in
[the arm record](t0027_deepseek_arm.md) because they had been written up; the per-turn evidence
does not, because `evals/runs/` is ignored and nothing had projected it into
[`replays/`](replays/).

**Never fix a rule in the pass that measures.** If the ruleset moves in the same session as the
capture, the resulting number cannot say whether the agent improved or the ruler did. M27 held this
line by forbidding scenario, threshold, and grader changes inside the milestone that measured, and
that is why its 44/33 split can be compared to anything at all.

## Grading: three tiers, four outcomes

`grader.py` grades a captured turn in three tiers, and stops at the first one that fails, so an
expensive judge check is only ever reached by a turn that already passed everything mechanical.

1. **Structural.** Did it call the required tool, or correctly call none? Did execution accuracy
   pass? Does the answer contain the right count? Pure mechanics, no judgement.
2. **Textual.** Does the answer contain a required idea, or avoid a forbidden one? Requirements are
   phrased as word groups, so "different currencies" and "can't rank" can both satisfy the same
   check.
3. **Judge.** A second model scores the answer against a threshold. The tier is implemented and
   wired up, but no scenario's `grading:` block sets a `judge_metric` today - an unvalidated judge
   would add opinion, not evidence, until its agreement with human labels is measured.

Every graded turn lands on one of four outcomes:

| Outcome | Means | Counted in the pass rate? |
|---|---|---|
| `PASS` | Every tier that ran was satisfied. | Yes |
| `FAIL` | A check the agent controls was violated. This is behavior. | Yes |
| `INFRA` | Something outside the agent's judgement broke - a quota refusal, or a completed turn that produced no answer. | No |
| `UNRUN` | The turn never executed, so there is nothing to grade. | No |

`INFRA` and `UNRUN` are excluded from the denominator (`grader.EXCLUDED_FROM_DENOMINATOR`) so a run
that dies on quota after two turns cannot report a catastrophic pass rate that says nothing about
the agent.
The pass rate always answers "of the turns actually measured, how many were right?", and the count
of unmeasured turns is reported separately so a thin result cannot masquerade as a strong one.

## What this instrument can and cannot tell you today

It can prove a specific behavior is wrong, show exactly which seam produced it, and reproduce that
finding for free without spending quota again - `replay.py` is the committed-evidence gate CI runs
on every pull request, with no model or judge call.
It cannot yet produce an overall quality score, for three reasons that are constraints on what can
be known rather than defects to fix:

- **Two or three repeats cannot measure a rare event.** The historical symptom was 8 empty answers;
  the current capture saw none in 13 turns, which rules out a *common* fault and says nothing about
  a rare one. Recorded as "no recurrence observed in 13 turns", never as "fixed".
- **22 rows is not the real corpus.** The fixture makes verification possible and results
  comparable, at the cost of realism. It cannot surface failures that only appear at thousands of
  rows, or with data shapes it does not contain.
- **The reference SQL is one person's answer.** Where a question is genuinely ambiguous, the
  reference encodes one reading of it. A disagreement between agent and reference can mean the
  agent is wrong, or that the reference is too narrow.

Two defects that limited earlier runs are now fixed, not open.
The grader's tool expectations used to come from a hardcoded list rather than the registry, which
failed `HON-SQL-DESCRIBE-1` even though declining to call a tool was correct; T0025.9 moved every
expectation into the registry and regraded, and [`Instrument_Report.md`](Instrument_Report.md)
records the result.
The same ticket committed a sanitized real capture and wired `replay.py` into the CI `checks` job,
so a change to the capture format cannot break grading without a test noticing it.
