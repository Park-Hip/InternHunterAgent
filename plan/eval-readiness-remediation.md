# Evaluation readiness remediation plan

> **Status:** Draft for maintainer approval.
> This plan turns [evaluation readiness and Langfuse evaluators](../research/eval-readiness-and-langfuse-evaluators.md)
> into phases that can be executed without drifting into each other.
> A second record,
> [the evaluation driver after DeepSeek](../research/eval-driver-post-deepseek.md), added the
> driver's post-D-045 economics on 2026-08-21 and re-scoped Phase 3 and Phase 6 below.

> **Last verified:** 2026-08-22

> **Eviction:** This plan leaves when every approved phase is merged, or its scope is superseded by
> a recorded decision.

## Goal and expected outcome

Make the evaluation instrument measure what it claims to measure, so a full 29-scenario DeepSeek
Vietnamese capture produces evidence about the agent rather than evidence about the grader.

The measured starting point is a 2026-08-21 probe: 5 turns, **0 PASS**, and no failure caused by
agent behavior.

A second measurement, taken the same day, sets Phase 3 and Phase 6.
Capture on DeepSeek is 77 turns in 5m20s for about $0.04 with zero retries, while scoring the same
registry is 365 judge calls at best against a Gemini free tier throttled to 8 RPM, or about 46
minutes, and up to 82 if each `GEval` spends two calls.
Scoring still runs inside the capture loop, so the cheap half of the run is held hostage to the
expensive half, and the scores it produces reach no verdict.

The work is research-led because it changes grading semantics, a prompt rule, and evaluation
operations at once.

## The anti-drift contract

Three rules govern every phase. They exist because the failures in the research record were caused
by a correct plan not actually running, not by a missing plan.

1. **A file has exactly one owning phase.** The ownership table below is exhaustive. A phase that
   needs a file it does not own is blocked, not widened; re-scope the plan instead.
2. **A phase ships only its numbered requirements.** Anything discovered mid-phase that is not a
   listed requirement goes into the pull request body as a follow-up, per CLAUDE.md section 1.
3. **A phase is finished when its exit gate is demonstrably true**, not when its diff looks
   complete. Each gate below is a statement someone can check.

### File ownership

| File | Owning phase | Nobody else may touch it |
|---|---|---|
| `evals/scenarios_v1.yaml` | 1 | 2, 3 |
| `evals/execution_accuracy.py` | 1 | 2, 3 |
| `tests/evals/test_execution_accuracy.py` | 1 | 2, 3 |
| `tests/evals/test_scenarios.py` | 1 | 2, 3 |
| `evals/replays/t0025.9-committed.json` | 1 | 2, 3 |
| `tests/evals/test_replay.py` | 1 | 2, 3 |
| `config/prompts.yaml` | 2 | 1, 3 |
| `evals/grader.py` | 2 | 1, 3 |
| `tests/evals/test_grader.py` | 2 | 1, 3 |
| `tests/test_prompt_surface.py` | 2 | 1, 3 |
| `docs/Agent_Behavior_Spec.md` | 2 | 1, 3 |
| `tests/agents/runtime/test_prompts.py` | 2 | 1, 3 |
| `tests/agents/test_langfuse_tracing.py` | 2 | 1, 3 |
| `src/core/config.py` | 3 | 1, 2, 6 |
| `evals/driver.py` | 3 | 1, 2, 6 |
| `evals/writeback.py` | 3 | 1, 2, 6 |
| `evals/harness.py` | 3 | 1, 2, 6 |
| `evals/score.py` (new) | 3 | 1, 2, 6 | <!-- lint-allow-link-path -->
| `tests/evals/test_writeback.py` | 3 | 1, 2, 6 |
| `tests/evals/test_driver.py` | 3 | 1, 2, 6 |
| `tests/evals/test_score.py` (new) | 3 | 1, 2, 6 | <!-- lint-allow-link-path -->
| `evals/langfuse_dataset.py` | 3 | 1, 2, 6 | <!-- lint-allow-link-path -->
| `tests/evals/test_langfuse_dataset.py` | 3 | 1, 2, 6 | <!-- lint-allow-link-path -->
| `evals/README.md` | 6 | 1, 2, 3 |
| `evals/Operating_Manual.md` | 6 | 1, 2, 3 |

Phases 1, 2 and 3 share no file and may run in parallel in separate worktrees.
Phase 4 writes no code.
Phase 6 owns only the two manuals. Its code requirements need `evals/driver.py` and
`tests/evals/test_driver.py`, which Phase 3 owns, so Phase 6 follows Phase 3 on those files rather
than running beside it. See the ownership conflict note in Phase 6.

**Phase 3 followed a pull request in another plan, now merged.** Session 8 of the
[Langfuse observability remediation plan](langfuse-observability-remediation.md) modifies
`evals/driver.py`, `evals/harness.py`, `evals/writeback.py`, `tests/evals/test_driver.py` and
`tests/evals/test_writeback.py`, which is five of Phase 3's files, and it adds a sixth,
`evals/langfuse_dataset.py`.
Rule 1 applies across plans, not only inside this one.
It merged as `c8081cb` on 2026-08-21, so Phase 3 branches from the tip of `origin/main` and is
written against that merged result rather than rebased onto it.
`evals/langfuse_dataset.py` and `tests/evals/test_langfuse_dataset.py` join Phase 3's ownership for
R3.9, which has to see the dataset run to tell an ingested run from an empty one.

---

## Phase 0 - decisions, no code

Six decisions gate the phases below.
D-e and D-f were added on 2026-08-21 from
[the evaluation driver after DeepSeek](../research/eval-driver-post-deepseek.md).

| ID | Question | Decision | Gates |
|---|---|---|---|
| D-a | Must the capture be traced in Langfuse with environment, tags, release and cost, or is a graded artifact on disk sufficient for this baseline? | **Recorded 2026-08-21 as the recommendation: traced.** The earlier recommendation was untraced now, traced next. Session 8 merged as `c8081cb` and removed that option: it creates a dataset and a dataset run on every capture that finds a Langfuse handler, so a capture is now traced or it is broken. Holding session 8 back is no longer available, so the remaining choice is traced. Phase 3 therefore ships R3.7 to R3.9 and becomes a precondition of Phase 4. | Phase 3 scope, Phase 4 timing |
| D-b | Is execution accuracy "the query found the right postings" or "the query returned the right table"? | **Recorded 2026-08-21.** Row identity for listing scenarios, exact for count and aggregate scenarios. | Phase 1 |
| D-c | Where does score writeback belong for a recorded run? | **Recorded 2026-08-21, and reinforced.** A post-run step over the artifact. The original ground was that it is the only form surviving a resumed run. The driver record adds a second, independent one: an in-loop writeback cannot post corrected scores after a re-grade, which Phase 1's exit gate requires. Session 8 implements the opposite and must be corrected, not followed. | Phase 3 |
| D-d | Adopt Langfuse score configs, custom-evaluator score posting and the annotation queue, while declining managed LLM-as-a-judge evaluators until the existing judge is calibrated? | **Recorded 2026-08-21, but homeless.** Session 8 as written implements none of the three: `evals/langfuse_dataset.py` has no score config and no annotation queue. Rehome it to a new observability session or a real Phase 5. | Phase 5 | <!-- lint-allow-link-path -->
| D-e | On a provider 429 mid-capture, should the driver halt the run or continue to the next scenario? | **Recorded 2026-08-22: continue, behind a consecutive-failure threshold.** The halt-and-mark-`UNRUN` policy was correct against a rationed Groq budget and is wrong against DeepSeek's dynamic concurrency, where the remaining scenarios will likely succeed and finishing the run costs four cents. Halting on the first 429 turns a recoverable blip into a `PARTIAL` artifact, which costs the R4.2 classification pass rather than the capture. The threshold value is set in R6.2 and is a guess until a DeepSeek 429 is observed. | Phase 6 |
| D-f | Does an offline scoring pass replace `driver --score`, or stand beside it? | **Recorded 2026-08-21 as the recommendation: replace.** Replacing removes the two-scoring-paths problem R3.6 names and leaves one home for scores and their writeback. Keeping both would preserve an existing operator command at the price of leaving `harness.run_case` as a second path with different side effects, which is the defect R3.6 exists to close. `driver --score` is removed and the offline pass takes its place. | Phase 3 scope |

**Exit gate:** each decision is recorded, with D-a and D-f answered before Phase 3 opens a branch
and D-e answered before Phase 6 does.
All six are recorded, so Phase 3 and Phase 6 may both open a branch.
D-d remains homeless: it is recorded, but nothing in this plan carries it out, so Phase 5 rehomes it
or it stays a decision without an owner.

---

## Phase 1 - execution accuracy measures rows, not projections

**Problem.** `exact` mode keys on every value in a row, and nothing pins the model's select list.
The probe failed 5 of 5 turns while selecting the correct rows, and two repeats of one scenario
projected different column orders.

**Requirements.**

- **R1.1** Every scenario currently graded under `exact` is classified explicitly as either a
  row-identity scenario or a projection-pinned scenario. The classification is recorded per
  scenario in `evals/scenarios_v1.yaml`, never inferred by the grader.
- **R1.2** Row-identity scenarios declare `execution_comparison: ids_only`. This value is already
  accepted by `_validate_grading`, so no registry schema change is needed.
- **R1.3** Count and aggregate scenarios keep `exact`. Their projection is pinned by the existing
  `SELECT COUNT(*)` prompt rule, so `exact` is the correct assertion there.
- **R1.4** An `ids_only` comparison never compares an id multiset that silently dropped a row.
  Neither side may be filtered, because a filtered side can empty itself and match anything.
  - On the reference side, `ids_only` is rejected when the scenario's reference SQL does not select
    `id`. `ids_only` on a `COUNT(*)` reference would compare two empty sets and pass everything.
  - On the generated side, a query that does not project `id` is a `FAIL` naming the projection.
    This side is the likelier one, because the premise of this phase is that the model chooses its
    own column list, and `HON-ZERO-RESULTS-1` makes it reachable: its reference legitimately
    returns no rows, so a query that ignored the COBOL filter would otherwise compare an empty
    multiset against an empty one and pass. Naming the projection also stops a projection defect
    from reading like "found the wrong postings".
- **R1.5** The status vocabulary is unchanged. `PASS`, `FAIL`, `EXEMPT`, `INFRA` and `UNRUN` keep
  their current spelling and meaning, because `driver._expected_execution_accuracy` parses the
  grader's detail string and Phase 3 must not have to track this.
- **R1.6** The committed replay gate is brought back into agreement with the new semantics.
  `HON-CURRENCY-1` r1 t1 in `evals/replays/t0025.9-committed.json` carries
  `expected_execution_accuracy: FAIL`, recorded when `exact` was the comparison. The frozen query
  and the reference return the same posting, so row identity makes it a `PASS`. Only that
  expectation moves. The recorded seams, answers and `expected_grade` are not edited, and the
  turn's `expected_grade: FAIL` is where the scenario's real defect stays measured. The drift test
  in `tests/evals/test_replay.py` forces this same turn's status to prove the gate catches a
  mismatch, so it moves with the expectation.

**Ownership note.** R1.6 was added on 2026-08-21, after the Phase 1 branch turned the replay gate
red. The replay was re-scoped into Phase 1's ownership rather than edited outside it, per rule 1 of
the anti-drift contract.

**Files.** `evals/scenarios_v1.yaml` for R1.1 to R1.3, `evals/execution_accuracy.py` for the R1.4
guard, `evals/replays/t0025.9-committed.json` and `tests/evals/test_replay.py` for R1.6, and
`tests/evals/test_execution_accuracy.py` and `tests/evals/test_scenarios.py` for coverage.

**Exclusions.** Do not change the default comparison mode in code; the registry owns expectations
under D-041. Do not change any prompt to make a query match a reference. Do not touch
`evals/grader.py`, which only reads the status this module produces.

**Verification.** Focused tests for both modes and both sides of the R1.4 guard, including a
regression case with a superset projection over identical rows, and one where an id-less generated
query meets a reference that legitimately returns nothing. Then re-grade the 2026-08-21 probe artifact and confirm
the five `execution_accuracy` failures become passes without any change to agent behavior.
Run `python -m evals.replay`, the gate CI runs, and confirm it is green after R1.6.

**Risk.** `ids_only` measures less than `exact`. A query that returns the right postings with a
wrong column value would now pass. This is accepted deliberately: the scenario text asserts which
postings, and `contains_reference` remains available per scenario where a column value is the
point.

**Exit gate:** re-grading the probe artifact yields zero `execution_accuracy` failures, each of the
17 previously-`exact` scenarios carries an explicit, reviewed classification, and the committed
replay gate passes.

---

## Phase 2 - the answer-style rule, and its measurement

**Problem.** Two style defects are unmeasured, and one of them is misreported as a language defect.
The agent emits emoji and no rule forbids it. The agent quotes schema identifiers such as
`is_salary_negotiable = True` to users, and the purity check reports that as English prose because
`is` and `on` are fragments of those identifiers.

**Requirements.**

- **R2.1** `config/prompts.yaml` states one style rule forbidding emoji and decorative symbols in
  answers, placed under the existing `# Honesty and style` heading.
- **R2.2** `prompt_version` is bumped to `v5` in the same commit. The file's own rule requires it,
  and the bump is what stops this capture being compared against a pre-rule one.
- **R2.3** A structural grader check fails an answer containing emoji or decorative symbols.
- **R2.4** The emoji check is gated on `_prompt_is_current`, matching the `vietnamese_agent_prose`
  precedent. Without the gate it regrades `evals/replays/t0024.4-v3-obligations.json`, whose frozen
  `v3` answers contain a warning symbol the prompt did not forbid at capture time.
- **R2.5** `_answer_language_pure` strips schema identifiers before its English-prose probe, so the
  language check measures language. The identifier list comes from the existing schema context
  loader, not a second hand-maintained list.
- **R2.6** A separate structural check fails an answer that quotes a schema identifier, reported
  under its own name so the defect is legible. It is gated the same way as R2.4.
- **R2.7** `docs/Agent_Behavior_Spec.md` records the style rule under its existing conciseness and
  style section.

**Files.** `config/prompts.yaml`, `evals/grader.py`, `docs/Agent_Behavior_Spec.md`,
`tests/evals/test_grader.py`, `tests/test_prompt_surface.py`, and the two files the R2.2 bump
turns red.

**Ownership note.** Two files were added to Phase 2's ownership on 2026-08-21, following the R1.6
precedent. `tests/agents/runtime/test_prompts.py` and `tests/agents/test_langfuse_tracing.py` each
assert the literal `v4`, so R2.2 cannot ship without them. They were re-scoped into the phase
rather than edited outside it, per rule 1 of the anti-drift contract.
`tests/test_prompt_surface.py` needed no change: it inventories which strings are model-facing, not
what they say.

**Discovered, not fixed here.** `evals/harness.py` calls `langfuse_request_trace` with
`scenario_id` and `repeat`, which that function does not accept, so every capture on `origin/main`
returns `INFRA` before reaching the model. Session 8 of the
[Langfuse observability remediation plan](langfuse-observability-remediation.md) introduced it in
`c8081cb` and no test covers that call site. It blocks Phase 4 outright, and it belongs to Phase 3
and the observability plan by ownership, so Phase 2 verified against a local patch and reverted it.

**Why R2.1 and R2.5 are one phase.** They are not one topic, but they are one file region and one
review question: does the grader measure answer style correctly. Splitting them puts two branches
on the same function in `evals/grader.py`, which is the conflict this plan exists to avoid.

**Exclusions.** Do not fix the upstream cause of identifier leakage. `_build_answer` in
`src/agents/tools/query_clean_jobs.py` hands the model `column=value` pairs, and changing it is a
serving-behavior change that must not ride along inside a measurement change. File it; measure it
here. Do not change any glossary string or anchor: `evals/grader.py` validates anchors as
substrings of their canonical sentences at import, so a glossary edit here fails before a scenario
is graded. Do not touch `evals/scenarios_v1.yaml`.

**Verification.** Focused grader tests for an emoji answer, a clean answer, an identifier-quoting
answer, and a stale-prompt-version replay that must skip both new checks. Then re-grade the probe
artifact and confirm the two emoji turns fail on the emoji check, the four identifier turns fail on
the leakage check, and none of them fails `vietnamese_agent_prose` any more.

**Manual check.** Run one live turn on `HLP-LIST-1` after the prompt change and read the answer.
Expected: no emoji, no closing decorative symbol, Vietnamese prose unchanged in tone.

**Risk.** A prompt edit changes behavior, so this phase must land before the capture, not after.
The emoji rule adds a fifth instruction to a style block the prompt-refinement record warns against
growing; keep it to one sentence.

**Exit gate:** a live turn produces no emoji, and re-grading the probe attributes every style
failure to the check that names it.

---

## Phase 3 - scoring leaves the capture loop, and reaches Langfuse

**Problem.** Scoring is in the wrong place, and from there it cannot reach Langfuse correctly.

`driver._score_case` runs inside the capture loop, once per repeat, and `metric.measure()` blocks
on `_RpmThrottle.wait()`, a `time.sleep`, inside the driver's event loop.
So a five-minute capture is held open for 46 to 82 minutes, its checkpoint file stays mid-run for
all of it, and recorded evidence cannot be re-scored without re-capturing it.
That last property is the one the pipeline's capture-once-grade-many split provides everywhere
else.
Separately, the export target is a dead local address, and no recorded run has written a score to
Langfuse because `write_scores` was reachable only from the pytest path.

**Scope is settled by D-a and D-f.**
D-a chose traced, so R3.7 to R3.9 are in scope and Phase 3 is a precondition of Phase 4.
D-f chose replace, so `driver --score` is removed rather than kept beside the new pass, and R3.6
removes the second path rather than documenting it.

**Requirements.**

- **R3.1** `src/core/config.py` no longer defaults `LANGFUSE_BASE_URL` to a local address. A
  missing value fails loudly rather than pointing at `localhost`, per D-029.
- **R3.2** The operator's `.env` is corrected to the Langfuse Cloud host. This is an operator
  action on an untracked file, recorded in the pull request body and in `.env.example`.
- **R3.4** Scoring is an offline pass over a capture artifact, in its own module with its own
  entry point, taking the shape `evals/grader.py` already has. A capture no longer calls the judge.
- **R3.5** The scoring pass is resumable and re-runnable over the same artifact. A run interrupted
  at judge call 300 of 365 does not discard the 300, and a second pass over a fully scored artifact
  is not an error.
- **R3.6** Exactly one scoring path exists, per D-f. `harness.run_case` and `driver._score_case`
  stop being two paths with different side effects, and `write_scores` has one caller.
- **R3.7** Judge scores from a recorded run reach Langfuse from that pass, per D-c, including when
  the pass is re-run over an artifact whose grades have changed.
- **R3.8** The pass is idempotent against Langfuse. `write_scores` already derives a deterministic
  `score_id`; a rerun must not duplicate scores.
- **R3.9** A run whose traces were never ingested is distinguishable from one whose traces were.
  The probe recorded five non-null `trace_id` values pointing at traces that do not exist, and that
  must not be possible to mistake for success again. Session 8's dataset run is a second object
  that can look successful while pointing at nothing, so this check covers it too.

**R3.3 is withdrawn.** It required the driver to stop forcing `LANGFUSE_ENABLED` off. Session 3 of
the observability plan already did that: `evals/driver.py` reads
`os.environ.setdefault("LANGFUSE_ENABLED", "true")` on `origin/main`, changed in commit `41d16c8`,
which merged before this plan was written. The requirement was stale on the day it was recorded.

**Files.** `src/core/config.py`, `evals/driver.py`, `evals/writeback.py`, `evals/harness.py`,
`evals/score.py`, `tests/evals/test_writeback.py`, `tests/evals/test_driver.py`, <!-- lint-allow-link-path -->
`tests/evals/test_score.py`. <!-- lint-allow-link-path -->

**Ownership note.** `src/agents/tracing/langfuse.py` and `.env.example` were added to Phase 3's
ownership on 2026-08-22, following the R1.6 and R2.2 precedent. R3.1 removes the `LANGFUSE_BASE_URL`
default, and the only place that can then fail loudly is `create_langfuse_client`, which would
otherwise let the SDK substitute a default host of its own. R3.2 names `.env.example` already. No
other phase in this plan owns either file.

**Exclusions.** This phase does not add environments, tags, release attribution, prompt-version
trace attributes, model pricing, or dataset mirrors. Every one of those is already owned by
sessions 1, 2, 3 and 8 of the
[Langfuse observability remediation plan](langfuse-observability-remediation.md), and building them
here would be the same work twice in two plans.
It does not calibrate the judge, change a metric, or make any scenario declare a `judge_metric`.
It does not change the driver's retry or halt policy, which is Phase 6.
It does not raise `eval.judge.rpm`: that value sits below the Gemini free tier's cap on purpose,
and the fix for a slow judge pass is to stop blocking a capture on it.

**Verification.** Focused tests for the scoring pass, its resumability, and the writeback. Then
score a two-scenario capture end to end and confirm in the Langfuse UI that the traces exist, that
scores are attached, and that a second pass adds no duplicates. Time the capture and the scoring
pass separately and record both, since the separation is the point.

**Risk.** Turning eval tracing on spends Hobby-plan ingestion, which is the trade the observability
plan already approved. Retention is 30 days, so a dataset run is not durable evidence and the
capture artifact on disk remains the record.
Moving scoring out of the driver changes an operator command, so the two manuals in Phase 6 must
land in the same milestone or they will describe a command that no longer exists.

**Exit gate:** a capture completes without a judge call, a separate scoring pass over that artifact
attaches its scores in Langfuse, and re-running that pass changes nothing.

---

## Phase 4 - the capture

No code. This phase is the run the whole plan exists to enable.

**Preconditions.** Phase 1 and Phase 2 merged. Fixture database rebuilt. Working tree clean, so the
manifest records `baseline_eligible: true`.

Phase 3 is also a precondition, because D-a chose traced.
Session 8 of the observability plan has merged, so a capture writes a dataset and a dataset run
whenever a Langfuse handler exists and "capture untraced now" is no longer available.
Phase 6 is not a precondition, but landing D-e first means a transient 429 costs a retry rather
than a halted run and an operator-issued `--resume`.

**Requirements.**

- **R4.1** All 29 scenarios captured, then graded with execution accuracy and the deterministic
  grader.
- **R4.2** The result is read and classified before it is quoted. Every failure is attributed to
  behavior or to instrument, and the split is stated.
- **R4.3** The capture is recorded as the first Vietnamese DeepSeek baseline, not as a comparison.
  No prior capture is comparable: the newest is Groq, English, `prompt_version` v1, and partial.
- **R4.4** The artifact is preserved. `KI-2026-08-17-deepseek-capture-lost` records what happens
  when it is not.

**Exclusions.** Do not freeze this capture into a committed replay.
`KI-2026-08-18-freezer-rejects-no-sql-turns` is open, and `HLP-CONTEXT-1` turn 2 blocks the freeze
of any full-registry capture. Do not repair the two stale committed replays here; that is
`KI-2026-08-20-stale-replays` and it needs its own decision about which files are live evidence.

**Expected cost.** About five minutes and four cents, from the T0027.3 measurement.

**Exit gate:** a graded 29-scenario artifact exists, with every failure attributed.

---

## Phase 5 - Langfuse datasets, deferred by design

Not scoped here, and named so nobody builds it twice.

The dataset mirror and dataset-run association are **session 8** of the
[Langfuse observability remediation plan](langfuse-observability-remediation.md), and depend on its
session 3 for the `evaluation` environment. The research record's recommendation adds only that
score configs, deterministic-grader score posting, and the single Hobby annotation queue are worth
taking, and that managed LLM-as-a-judge evaluators are not, until the existing Gemini judge is
calibrated against human labels.

If D-d is approved, fold it into that plan's session 8 rather than opening a phase here.
As written, session 8 implements none of D-d's three items, so approving D-d without rehoming it
records a decision nothing carries out.

---

## Phase 6 - the driver stops behaving like a free-tier client

**Problem.** Two of the driver's mechanics were built against a constraint D-045 removed, and one
of them is now actively wrong.

`driver.run()` treats a 429 as an exhausted budget: it sets `PARTIAL_QUOTA`, marks every remaining
scenario `UNRUN`, and returns.
That was right on Groq, where the next twenty scenarios would fail for the same reason.
DeepSeek's 429 is dynamic concurrency backpressure, so the remaining scenarios will likely succeed
and finishing the run costs four cents, which makes the current policy a way of turning a
recoverable blip into a `PARTIAL` artifact.

`_RETRY_HINT_PATTERN` matches `try again in 14.16s`, which is Groq's message. DeepSeek 429s carry
no hint, so they fall to `QUOTA_BACKOFF_SECONDS = (20.0, 40.0)`, a ladder sized to outlast a
60-second per-minute window DeepSeek does not have, against published guidance of exponential
backoff with jitter from about one second.

**Requirements.**

- **R6.1** A 429 no longer halts the run by itself, per D-e. The failed repeat is still recorded
  `INFRA`, and the driver continues to the next scenario.
- **R6.2** `PARTIAL_QUOTA` survives as a status behind a consecutive-failure threshold, so a
  genuinely exhausted account still stops rather than burning through 29 scenarios of failures.
  The threshold is a named constant with the reasoning beside it, because no measured DeepSeek 429
  rate exists to derive it from.
- **R6.3** The no-hint quota ladder becomes exponential backoff with jitter from about one second,
  keeping `MAX_BACKOFF_SECONDS` as the cap. The provider hint parser is unchanged: it is the Groq
  arm's and is correct there.
- **R6.4** The three stale passages are corrected. `evals/README.md` bills the driver as spending
  "Groq serving quota" against an 8000 TPM ceiling and describes it as pacing turns to fit a quota
  window. `evals/Operating_Manual.md` justifies checkpointing with "every acceptance attempt so far
  has been interrupted by quota", and lists that ceiling first among four reasons the instrument
  cannot yet produce a quality score. The other three reasons stand and are not touched.
- **R6.5** Checkpoint and resume are re-justified as interrupt safety rather than quota survival.
  The mechanism does not change.

**Files.** `evals/driver.py`, `tests/evals/test_driver.py`, `evals/README.md`,
`evals/Operating_Manual.md`.

**Ownership conflict.** R6.1 to R6.3 need `evals/driver.py` and `tests/evals/test_driver.py`, which
Phase 3 owns. Phase 6 therefore does not run beside Phase 3; it follows it, on the same files, or
its code half is folded into Phase 3 and only R6.4 and R6.5 remain here. Splitting the file is not
an option, per rule 1.

**Exclusions.** Do not delete turn pacing or the Groq branch. `turn_pacing_seconds` is 0 and
`pause()` is inert, but D-045 keeps the Groq arm selectable on purpose and names `75` as the knob
to restore with it, so about fifteen inert lines are cheaper than overturning a live decision.
Do not prune checkpoint or resume; only their stated justification is wrong.
Do not change `MAX_RETRIES` in the same commit as R6.1, so the halt policy and the attempt count
are two separately reviewable changes.

**Verification.** A focused test that a single 429 no longer marks the rest of the run `UNRUN`, and
one that the threshold in R6.2 still halts. A ladder test asserting the first no-hint wait is near
one second rather than twenty. Then read the two manuals end to end against the current
configuration.

**Risk.** R6.1 makes a genuinely broken run longer and more expensive to discover, which is what
R6.2 exists to bound. The threshold is a guess until a DeepSeek 429 is actually observed; the
DeepSeek arm recorded zero in 77 turns.

**Exit gate:** an injected single 429 leaves the run completing all 29 scenarios, and no passage in
either manual describes a constraint D-045 removed.

---

## Sequencing

| Phase | Depends on | May run beside |
|---|---|---|
| 0 | nothing | nothing, it is a decision |
| 1 | D-b | 2, 3, 6 |
| 2 | nothing | 1, 3, 6 |
| 3 | D-a, D-c, D-f, and observability session 8 merged, which it is | 1, 2 |
| 4 | 1, 2 and 3 merged | nothing |
| 5 | observability plan session 3 | not scoped here |
| 6 | D-e, and Phase 3 merged | 1, 2 |

Phases 1, 2 and 3 are file-disjoint and can be three concurrent worktrees off `origin/main`.
Phase 6 is not disjoint from Phase 3 and follows it on the same two files.
Phase 4 must follow a rebase onto the merged result of Phases 1, 2 and 3.

## Explicit exclusions for the whole plan

This plan does not change agent behavior except for the single style rule in R2.1, does not fix the
`_build_answer` identifier leakage, does not repair or re-capture the stale committed replays, does
not change the freezer, does not calibrate the judge, does not make any scenario declare a
`judge_metric`, does not change a judge metric or its throttle, does not add Langfuse environments,
tags, release attribution, pricing or dataset mirrors, does not delete turn pacing or the Groq
provider branch, does not prune checkpoint or resume, and does not expand the scenario set.

It also does not migrate execution to Langfuse `run_experiment()`. That was rejected in
[evaluation readiness](../research/eval-readiness-and-langfuse-evaluators.md) section 8b and again
in the driver record: the driver's orchestration is what D-043 deliberately kept, and
`run_experiment()` offers `max_concurrency` in exchange for it.

## Risks carried

- Phase 2's prompt bump invalidates any capture taken before it, which is why Phase 4 is last.
- Phase 1 reduces what execution accuracy asserts. That is the intended trade, and it is reversible
  per scenario.
- The capture cannot become a frozen replay, so the regression gate does not improve as a result of
  this plan. Two open known issues stand between here and that.
- The plan assumes the probe's failure modes generalise to the full registry. Blast radius for
  Phase 1 is counted from the registry, not measured; Phase 4 is what measures it.
- Phase 3 is written on top of session 8 of another plan, merged the same day as this phase opened.
  It corrects that session's in-loop writeback rather than extending it, so a later change to
  session 8's dataset code has to be read against Phase 3's scoring pass.
- Phase 3 moves scoring but does not make anyone read it. No scenario declares a `judge_metric`, so
  the judge scores still reach a Langfuse dashboard and no verdict. That is deliberate while the
  judge is uncalibrated, and it means Phase 3 buys throughput and re-scoring, not a better verdict.
- R6.2's threshold is unmeasured. Zero DeepSeek 429s have been observed, so the number that halts a
  run is a guess until one is.
