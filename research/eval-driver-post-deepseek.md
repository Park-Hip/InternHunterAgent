# The evaluation driver after DeepSeek

> **Status:** Live research. Feeds a decision on what to prune, retune, or split in `evals/`
> before the first Vietnamese DeepSeek baseline capture.
> It answers a question the
> [evaluation readiness record](eval-readiness-and-langfuse-evaluators.md) did not ask: which of
> the driver's mechanics were built for a constraint that D-045 removed.

> **Last verified:** 2026-08-21

> **Eviction:** This record leaves when its recommendations are taken as decisions or rejected,
> or when a later dated capture supersedes its measurements.

## The answer, first

Do not rewrite the evaluation system, and do not prune the checkpoint and resume machinery.
The pipeline's shape - registry, capture, offline grade, committed replay - is provider-agnostic
and is the part worth keeping.
What D-045 changed is not the shape but the economics, and exactly four things follow from that.

| # | Finding | Move | Size |
|---|---|---|---|
| F1 | Turn pacing is inert at 0 but is the Groq arm's restore knob | Keep the code, fix the prose that describes it as live | Docs only |
| F2 | Halting the whole capture on a 429 is now the wrong response | Change the policy: retry, record `INFRA`, keep going | ~15 lines |
| F3 | The retry ladder is tuned for a 60-second Groq window | Retune the no-hint ladder to exponential-with-jitter from ~1s | ~10 lines |
| F4 | The bottleneck moved to the judge, and nothing consumes its output | Split scoring out of the capture loop into an offline pass | New module |

F4 is the finding that matters.
The other three are cleanup around it.

## What actually changed at D-045

The serving side stopped being the constraint.

| Measure | Groq free tier | DeepSeek | Source |
|---|---|---|---|
| Full 29-scenario capture | 13 turns in 21 minutes, then `PARTIAL_QUOTA` | 77 of 77 turns in 5m20s, `COMPLETE` | [T0027.3 arm](../evals/t0027_deepseek_arm.md) |
| Retry events | recorded in the artifact | 0 | same |
| Cost | four days of rationed quota | about $0.04 | same |
| `turn_pacing_seconds` | 75 | 0 | `config/settings.yaml` |

Two scenarios were previously unreachable on the free tier because a single turn exceeded the
8,000 TPM ceiling on its own: `HLP-CONTEXT-1` peaked at 10,231 tokens on synthesis and
`HLP-COMPOUND-1` spent 7,653 on routing alone.
Both were captured in the DeepSeek arm.

DeepSeek publishes no RPM or TPM table.
Its documented control is account-level concurrency, and a 429 means dynamic backpressure under
load rather than an exhausted budget.
This distinction is what makes F2 a defect rather than dead weight.

## F1 - pacing is inert, and deleting it would cost the second arm

`eval.driver.turn_pacing_seconds` is 0, so `pause()` is a no-op and `spent_a_window` never gates
anything.
The mechanism costs about 15 lines across `driver.py` and one parameter threaded through
`harness.run_conversational_case`.

Deleting it is the wrong trade.
D-045 keeps the Groq branch selectable on purpose, states that two working branches are what keep
the provider seam honest, and names `turn_pacing_seconds: 75` as the knob to restore with it.
Fifteen inert lines are cheaper than overturning a live decision and losing the ability to run the
second arm.

What is wrong is the prose, not the code.
Three passages still describe a system that no longer exists:

- `evals/README.md` bills `driver` as spending "Groq serving quota" against "an 8000 TPM ceiling",
  and describes `driver.py` as a module that "paces turns to fit the quota window".
- `evals/Operating_Manual.md` justifies checkpointing with "every acceptance attempt so far has
  been interrupted by quota", which was true on Groq and is not true of the DeepSeek arm.
- `evals/Operating_Manual.md` lists "an 8,000 TPM ceiling is the binding constraint" first among
  four reasons the instrument cannot yet produce an overall quality score.
  That constraint was removed at D-045.
  The other three reasons stand.

## F2 - halting the capture on a 429 is now the wrong response

`driver.run()` catches a failed repeat, and when `_is_quota_error` matches it sets the artifact to
`PARTIAL_QUOTA`, marks every remaining scenario `UNRUN`, and returns.

That policy was correct on Groq.
A rationed token budget meant the next twenty scenarios would fail for the same reason, so stopping
and saving the partial evidence was the only useful move.

It is incorrect on DeepSeek.
A 429 is transient concurrency backpressure, so the remaining scenarios are likely to succeed, and
finishing the run costs four cents and five minutes.
The current policy converts a recoverable blip into a `PARTIAL` artifact and forces a `--resume`
that a human has to notice and issue.

**Recommendation.** Keep the retry ladder and keep recording the failed repeat as `INFRA`, but
continue to the next scenario instead of returning.
Retain `PARTIAL_QUOTA` as a status only behind a consecutive-failure threshold, so a genuinely
exhausted account still halts rather than burning through 29 scenarios of failures.
The `--resume` path and its tests stay as they are; this changes when the driver stops, not how it
recovers.

## F3 - the retry ladder is Groq-shaped

`_RETRY_HINT_PATTERN` matches `try again in 14.16s`, which is Groq's 429 message.
DeepSeek 429s carry no such hint, so every DeepSeek quota error falls through to
`QUOTA_BACKOFF_SECONDS = (20.0, 40.0)`, a ladder sized to outlast a 60-second per-minute window
that DeepSeek does not have.

Published guidance for DeepSeek 429s is exponential backoff with jitter starting around one second.
Waiting 20 seconds for a concurrency blip is roughly an order of magnitude too long.

**Recommendation.** Keep the hint parser, which is the Groq arm's and is correct there.
Replace the fixed no-hint quota ladder with exponential backoff plus jitter from about one second,
keeping `MAX_BACKOFF_SECONDS` as the cap.
`MAX_RETRIES = 2` is worth raising once the halt policy in F2 no longer makes a third attempt
expensive.

## F4 - the bottleneck moved to the judge, and nothing reads its output

This is the substantive finding.
Capture stopped being expensive; scoring did not, and scoring was never moved out of the capture
loop.

### The measurement

The registry is 29 scenarios, 73 repeats, 77 turns, from `repeat_count`: 3 for a probe, 2
otherwise.
`driver._score_case` scores the final turn of each repeat against five metrics: two on seam 1, one
on seam 2, two on seam 3.
The judge is Gemini on the free tier, throttled to `rpm: 8` by `judge._RpmThrottle`.

| Quantity | Value |
|---|---|
| Repeats scored | 73 |
| Judge calls at one per metric | 365 |
| Floor at 8 RPM | about 46 minutes |
| Judge calls if each GEval spends two, steps then evaluation | 657 |
| Duration at 8 RPM | about 82 minutes |

Against a 5m20s capture, the judge pass is nine to fifteen times the run it scores.

### Why the shape is wrong

`_score_case` runs **inside** the capture loop, once per repeat, and `metric.measure()` is
synchronous: it calls `_RpmThrottle.wait()`, which is `time.sleep`, inside the driver's event loop.
Three consequences follow.

1. A capture that takes five minutes is held open for over an hour, and its checkpoint file stays
   mid-run for that whole time.
2. A judge failure or an interrupt at minute 50 leaves a capture artifact that is complete as
   evidence but incomplete as a run.
3. Re-scoring recorded evidence is impossible without re-capturing it, which is the exact property
   the pipeline's capture-once-grade-many split exists to provide everywhere else.

### And nothing consumes the scores

`grader.py` produces the verdict that the release bar, the viewer, and the CI replay gate read.
It takes judge input from `turn["judge_scores"]` through `Evidence.from_turn`.
The driver writes its scores to `repeat_record["scores"]` instead, and no scenario in
`scenarios_v1.yaml` declares a `judge_metric`, so `_judge_checks` never fires.
`evals/Operating_Manual.md` records this as deliberate: the tier is wired but dormant until human
agreement is re-measured, and `evals/Instrument_Report.md` says the same.

So the 46 to 82 minutes of throttled judge calls currently produce scores that reach a JSON field
and, once session 8 lands, a Langfuse dashboard.
They do not reach any verdict.
That is a defensible state for an uncalibrated judge, but it is a poor reason to hold a capture
open for an hour.

### Recommendation

Split scoring out of capture into an offline pass over the artifact, the same shape `grader.py`
already has:

```text
driver --output run.json        # 5 minutes, $0.04, DeepSeek, no judge
score --run run.json            # 46-82 minutes, Gemini, resumable, re-runnable
grader --run run.json ...       # free, no model
viewer run.json --grade ...     # free, no model
```

This is not new policy.
It is what D-c of the
[evaluation readiness plan](../plan/eval-readiness-remediation.md) already decided for score
writeback, on the narrower ground that a post-run step is the only form that survives a resumed
run.
The throughput measurement above is a second, independent argument for the same shape, and it
applies to the scoring itself and not only to the writeback.

It also resolves a conflict.
Session 8 of the
[Langfuse observability plan](../plan/langfuse-observability-remediation.md) calls `write_scores`
from inside the driver's capture loop, which is the opposite of D-c.
An offline scoring pass gives the scores and their Langfuse writeback one home, and lets a re-grade
of an existing artifact post corrected scores, which the in-loop form cannot do.

## What not to do

**Do not migrate execution to Langfuse `run_experiment()`.**
Already concluded in
[evaluation readiness](eval-readiness-and-langfuse-evaluators.md) section 8b and unchanged by
anything here.
The driver's job is checkpointing, per-turn persistence, retry accounting, and conversational
threading through an `InMemorySaver`; `run_experiment()` offers `max_concurrency` in exchange.
D-043 kept this orchestration deliberately.

**Do not prune checkpoint and resume.**
They are interrupt safety, not quota machinery.
Per-turn persistence is what `freeze` and the viewer read, and a five-minute run can still lose a
network connection or take an interrupt.
Only the justification is written in quota terms, and only that needs rewriting.

**Do not delete the Groq branch or its pacing.**
See F1.

**Do not raise `eval.judge.rpm` to shorten the judge pass.**
The value is set below the Gemini free tier's cap on purpose, and the fix for a slow judge pass is
to stop blocking a capture on it, not to spend into 429s.

## Sequencing against work already in flight

| Item | Relationship |
|---|---|
| Observability session 8 | Overlaps F4. It writes scores from inside the capture loop; an offline scoring pass would move that call. Decide F4 before merging, or accept a follow-up that moves it |
| Readiness phase 1 | No overlap. Different files |
| Readiness phase 3 | Overlaps F4 through D-c and through `evals/driver.py`, `evals/harness.py`, `evals/writeback.py` |
| Readiness phase 4, the capture | F2 and F3 should land first. Neither is required, but a 429 mid-capture is cheaper to survive than to resume |

## Open questions

1. Does F4's offline scoring pass replace `driver --score`, or stand beside it?
   Replacing it is cleaner and removes the two-scoring-paths problem that readiness R3.4 names;
   keeping both preserves an existing operator command.
2. Should `harness.run_case` and its pytest entry point `evals/test_three_seams.py` survive an
   offline scoring pass?
   `run_case` is the second scoring path and the only current caller of `write_scores`.
3. What consecutive-failure threshold should halt a run under F2?
   Any number is arbitrary without a measured DeepSeek 429 rate, and the arm recorded zero 429s in
   77 turns.

## Evidence

- [T0027.3 DeepSeek arm](../evals/t0027_deepseek_arm.md) for the throughput, cost, and retry counts.
- `evals/scenarios_v1.yaml` and `evals.scenarios.repeat_count` for 29 scenarios, 73 repeats, 77
  turns.
- `config/settings.yaml` for `eval.judge.rpm: 8` and `eval.driver.turn_pacing_seconds: 0`.
- `evals/judge.py` for the sliding-window throttle, `evals/harness.py` for the five metrics.
- DeepSeek's published rate-limit position: concurrency rather than an RPM or TPM table, with
  exponential backoff advised on 429.
