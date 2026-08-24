# Evaluation readiness for the DeepSeek Vietnamese run, and the Langfuse evaluator question

> **Status:** Research record.
> Answers three questions asked together on 2026-08-21: is the instrument ready for a full
> 29-scenario DeepSeek capture, does that capture reach Langfuse with usable metadata, and should
> Langfuse's own evaluators replace or join the DeepEval judge.
> No decision is taken here and nothing below is implemented.

> **Last verified:** 2026-08-21

> **Eviction:** This record leaves when its four maintainer decisions are harvested into the
> decision log and the readiness blockers are closed or re-filed as known issues.

## 1. Summary

**The run is not ready.**
Five blockers were found, four of them by running the instrument rather than by reading it.
Three would silently produce a capture that looks complete and measures the wrong thing.

A two-scenario live probe was captured on 2026-08-21 against the seeded fixture, on the current
`deepseek-v4-flash` configuration at `prompt_version: v4`.
It graded **0 PASS out of 5 turns**, and not one failure is a behavior defect.

| # | Blocker | Severity | Found by |
|---|---|---|---|
| B1 | Execution accuracy compares projections, so a correct answer fails whenever the model picks its own column list | Blocking | Probe: 5/5 FAIL with identical row identity |
| B2 | An eval capture reaches Langfuse with no scores, no dataset run, and, as configured today, no trace at all | Blocking | Probe: exporter refused at `host.docker.internal:3000` |
| B3 | The agent emits emoji, and nothing in the prompt or the grader forbids it | High | Probe: `😊` in 2 of 2 `HLP-LIST-1` answers |
| B4 | The Vietnamese purity check fails on schema identifiers the tool taught the model to quote | High | Probe: 4/5 turns, on `is` and `on` |
| B5 | No comparable baseline exists, and the capture cannot become a frozen replay | Medium | `evals/runs/`, `KI-2026-08-18-freezer-rejects-no-sql-turns` |

On the Langfuse question: **yes, adopt datasets and dataset runs; no, do not adopt managed
LLM-as-a-judge evaluators yet.**
Section 7 gives the reasoning. The short version is that dataset runs solve a problem we
demonstrably have, and a second unvalidated judge solves a problem we do not have while creating
the exact correlated-error risk this project already identified.

---

## 2. What was actually run

Reading the code answers none of these questions on its own, so the instrument was run.

| Field | Value |
|---|---|
| Date | 2026-08-21 |
| Scenarios | `HLP-LIST-1` (2 repeats), `HON-NEGOTIABLE-SALARY-1` (3 repeats) |
| Turns | 5, all `COMPLETE`, zero retries, zero infra errors |
| Provider, both profiles | `deepseek` / `deepseek-v4-flash`, `thinking: disabled` |
| Prompt version | `v4` (Vietnamese output rule active) |
| Fixture | `internhunter_eval`, 22 rows, rebuilt through Alembic on the day |
| Tracing | `LANGFUSE_ENABLED=true` set explicitly |
| Artifact | scratchpad only, deliberately not committed |

The probe was chosen to cost almost nothing and still exercise both a listing path and an honesty
probe.
It cost well under a cent and finished in under a minute, which is itself the finding that the
instrument is cheap enough to run before deciding anything.

Working tree state at the time was dirty, so `baseline_eligible` is `false` and this capture is
evidence about the instrument, never a baseline for behavior.

The full test suite for the changed layers is green: `tests/evals` and `tests/agents` pass at
204 passed, 41 subtests passed.
Every blocker below is therefore invisible to CI, which is the point.

---

## 3. B1: execution accuracy compares projections, not answers

**Severity: blocking. This is the single largest problem in the report.**

All five probe turns failed `execution_accuracy`, and in all five the agent selected the correct
rows.

| Scenario | Generated rows | Reference rows | Row identity | Verdict |
|---|---|---|---|---|
| `HLP-LIST-1` r1 | 5 | 5 | same 5 postings | FAIL |
| `HLP-LIST-1` r2 | 5 | 5 | same 5 postings | FAIL |
| `HON-NEGOTIABLE-SALARY-1` r1-r3 | 1 | 1 | same posting | FAIL |

The mechanism is in `evals/execution_accuracy.py`.
The default comparison mode is `exact`, and `_result_key` builds its key from **every value in the
row**:

```python
return json.dumps([_value_key(value) for value in row.values()], ensure_ascii=False)
```

The reference query for `HLP-LIST-1` selects four columns.
The agent selected fifteen.
Same rows, different tuples, no match.

Nothing tells the model which columns to project.
`config/prompts.yaml` constrains the projection twice, and both rules are about what to avoid:
never select `description`, and select `id` first when listing.
Column choice beyond that is free, and the model uses that freedom differently between repeats of
the same scenario: r1 ended its column list with `is_salary_negotiable`, r2 with `source_url`.

So the check is unstable against itself, not merely against the reference.

**Blast radius.** Of the 29 scenarios, 11 declare `execution_accuracy_exempt` and exactly one
declares `execution_comparison: contains_reference`.
The remaining **17 run under `exact`** and are exposed to this every time the model reprojects.

**This has already been misread once.** The T0027.3 arm record attributes 10 failing turns to
"generated SQL returns a different result set than the reference".
For at least this family of failures, the result set is identical and the projection differs.
That distinction changes the fix from a prompt or model problem to a grader problem, and it means
some part of the DeepSeek arm's 33 recorded failures is instrument noise that was counted as
behavior.

**Target practice.** Text-to-SQL execution accuracy is normally defined on the denotation of the
query, not its select list. The standard formulations compare result sets after normalising for
column order and, where the task does not pin the projection, for projection breadth.

**Three ways out, in preference order.**

1. **Grade on row identity by default.** `ids_only` already exists in `compare_result_sets` and is
   unused by every scenario. For any scenario whose reference query selects `id`, comparing the
   multiset of ids answers "did the query find the right postings", which is what the scenario
   text actually asserts. This is the smallest change and it fixes 17 scenarios at once.
2. **Pin the projection in the prompt** so the model has no freedom to drift, and keep `exact`.
   This makes the grader honest but changes serving behavior to satisfy a measurement, which is
   backwards, and it makes every future column addition a prompt edit.
3. **Make `contains_reference` the default**, so a superset projection passes and a missing column
   fails. This preserves more signal than `ids_only` and is more work to get right, because it
   currently keys off `reference_rows[0]` and needs a defined behavior on an empty reference.

Option 1 with option 3 available per scenario is the recommendation.
Either way this is a registry and grader change under D-041 and D-042, and it must land **before**
the capture, or the capture measures the grader.

---

## 4. B2: the eval run reaches Langfuse with nothing useful

**Severity: blocking for the stated goal, which was traced eval calls with metadata, latency,
token cost and prompt version.**

Three independent defects stack. Fixing any one of them alone changes nothing.

### 4a. The export target is a local address that is not listening

The probe emitted this, repeatedly, then gave up:

```
Failed to establish a new connection: host='host.docker.internal', port=3000 ...
/api/public/otel/v1/traces
```

`.env` sets `LANGFUSE_BASE_URL="http://host.docker.internal:3000"`, a leftover from self-hosting,
while **D-029 records Langfuse Cloud in Japan as the decision**.
`src/core/config.py` defaults the same variable to `http://localhost:3000`, so a missing value
fails toward a local address rather than loudly.
This is the `LANGFUSE_BASE_URL` item from
[Langfuse observability gaps](langfuse-observability-gaps.md) section 15, now observed rather than
predicted.

The capture still recorded non-null `trace_id` values for all five turns.
**A recorded trace id is not evidence that a trace was ingested.** Those five ids point at traces
that do not exist, and the demo's `trace_url` has the same property.

### 4b. The driver defaults tracing off

`evals/driver.py` calls `os.environ.setdefault("LANGFUSE_ENABLED", "false")`.
The comment explains why, and the reasoning was sound when Langfuse quota was the binding
constraint. Under the observability plan's approved decision to trace evals in their own
`evaluation` environment, this default is the thing that has to change, and it is a one-line
change once 4a is fixed.

### 4c. The driver never writes scores, and no code path does during a recorded run

This is the substantive one and it is not in the observability research.

`evals/writeback.py` is reachable from exactly one caller:

```
evals/harness.py:417:    scores_written = write_scores(final_run.trace_id, results)
```

That line is inside `harness.run_case()`.
**The driver does not call `run_case`.** Its `--score` path calls `driver._score_case()`, which
builds the same seam cases, measures the same metrics, and returns them into the run artifact
without ever touching Langfuse.
`run_case` is used by `evals/test_three_seams.py`, the pytest path.

So today, for a recorded run: judge scores land in JSON on disk and nowhere else.
The score writeback that D-018 and the evaluation strategy both describe as wired is wired to the
path nobody runs.

### 4d. What a fixed capture would and would not carry

Assuming 4a, 4b and 4c are fixed, and the observability plan's sessions 1 to 6 are not:

| Wanted | State after fixing 4a-4c | Gap |
|---|---|---|
| Trace per turn | Yes, named `eval-<scenario-id>` by `harness._run_turn` | none |
| Latency | Yes, in the capture artifact; in Langfuse as span duration | none |
| Token usage | Yes on this path. The eval harness runs `ainvoke`, not streaming, so `usage_metadata` is present. The probe recorded 4,763 in / 593 out on one turn | F1 does not bite the eval path; it bites serving |
| **Cost** | **No.** `deepseek-v4-flash` has no Langfuse model definition, so tokens are never priced | Observability plan session 2 |
| **Prompt version** | **No.** `prompt_version` is in the capture manifest only. Nothing puts it on a trace | Session 3 |
| **Environment separation** | **No.** Eval traces would land in the same undifferentiated stream as production | Session 3 |
| **Release / git SHA** | **No.** In the manifest, not on the trace | Session 3 |
| **Scores on traces** | Only after 4c | new work, not in the plan |
| **Dataset run grouping** | **No** | Session 8 |

The honest summary: the eval path already has better token accounting than the serving path,
because `ProviderTelemetryCallback` collects usage per LLM call and the harness does not stream.
Everything else the question asked for is missing, and most of it is exactly what the
[Langfuse observability remediation plan](../plan/langfuse-observability-remediation.md) sessions 3
and 8 exist to add.

**Sequencing consequence.** If the point of this capture is to have traced, attributable evidence,
then observability sessions 3 and 8 are prerequisites, not follow-ups.
If the point is a behavior baseline on disk, the capture can go first and be traced later.
That is a maintainer choice, and it is decision D-a in section 9.

---

## 5. B3: the emoji, confirmed

**Severity: high, and the cheapest fix in this document.**

Reproduced on the first attempt.
Both `HLP-LIST-1` repeats ended their answer with a smiling emoji, in a listing of job postings:

```
... | 5 | AI Engineer ... |

Bạn muốn tôi xem chi tiết tin nào không? 😊
```

`HON-NEGOTIABLE-SALARY-1` produced none across three repeats, so this is style variance on
conversational closers, not a constant.
Two of five probe turns carried one.

**There is no rule against it anywhere in the repository.**
A search across `config/`, `src/`, `evals/`, `docs/`, `research/` and `plan/` finds the word
"emoji" twice, both in an archived question bank, both describing emoji as *user input* to be
handled, never as *agent output* to be suppressed.
`config/prompts.yaml` constrains tone with "Keep answers concise and friendly", which if anything
invites it.
The grader has no forbidden pattern for it, so a full capture would grade emoji-laden answers as
clean.

**Fix, and where it belongs.** Two halves, both small, and they belong in one change:

1. **Prompt.** One line under `# Honesty and style`: no emoji or decorative symbols in answers.
   This bumps `prompt_version` to `v5` by the rule at the top of the file, which is correct and is
   exactly why that rule exists.
2. **Grader.** A `forbidden_patterns` entry so the rule is measured, not hoped for. The mechanism
   already exists: `TextRule.forbidden_patterns` is applied per scenario from the registry. A
   style rule that applies to every scenario is a poor fit for a per-scenario field, so this is
   more likely a new global structural check beside `vietnamese_agent_prose`, which is the
   precedent for a cross-scenario style assertion.

**Do this before the capture, not after.** A prompt change invalidates the capture as a baseline
by the project's own doctrine, and re-capturing to fix a one-line style rule wastes the run.

**Related, and worth a decision rather than a silent fix.** The same answers use markdown tables
and bold. That is fine: the demo UI renders markdown through `marked` with `DOMPurify`, so tables
display as tables. It is not a table dump in the prohibited sense. Left as is.

---

## 6. B4: the purity check fails on column names, and both halves are real

**Severity: high, because it silently converts a real defect into a mislabelled one.**

Four of five probe turns failed `vietnamese_agent_prose`.
The English words that tripped it were:

| Turn | Offending tokens |
|---|---|
| `HLP-LIST-1` r1 | `on` |
| `HON-NEGOTIABLE-SALARY-1` r1-r3 | `is` |

Neither is English prose.
They are fragments of schema identifiers the model quoted to the user:

```
**Về mức lương:** Tin đăng này **không công bố con số cụ thể** (salary_min, salary_max đều
trống) và ghi nhận **mức lương có thể thương lượng** (is_salary_negotiable = True).
```

`_answer_language_pure` strips returned row values, then extracts `[a-z]{2,}` tokens and
intersects with `_ENGLISH_PROSE_WORDS`.
`is_salary_negotiable` yields `is`, `salary`, `negotiable`; `is` is in the word set.
`created_on` yields `on`, which is also in the set.

**Two defects, and they need separating.**

1. **The agent should not quote column names to the user.** This is a genuine honesty and style
   defect. The prompt says "Never expose raw SQL or raw table dumps"; `is_salary_negotiable = True`
   is a raw schema fact in user-facing prose, in a Vietnamese answer.
   The upstream cause is `_build_answer` in `src/agents/tools/query_clean_jobs.py`, which hands the
   model `column=value` pairs and a header naming the columns. The model faithfully relays what it
   was given.
2. **The check names the wrong cause.** Its failure detail reads "agent prose excludes English
   words outside returned row values", which points a reader at the Vietnamese output rule when
   the actual problem is schema leakage. On a 77-turn capture this produces a class of failures
   that reads as a language regression and is not one.

**Fix direction.** Strip schema identifiers before the prose probe, so the language check measures
language, and add a separate structural check for column-name leakage, so the real defect is
measured under its own name.
The identifier list is already available: `load_schema_context()` owns it.

This is the same failure shape the DeepSeek arm record documented for the safety class, where
18 of 18 correct refusals scored 11 of 18 against hand-written whitelists.
The instrument has a recurring habit of failing correct behavior for the wrong stated reason, and
that is the pattern worth naming.

---

## 7. B5: no baseline to compare against, and no way to freeze this one

**Severity: medium. It does not stop the run; it limits what the run can conclude.**

The newest capture in `evals/runs/` is `t0025.7-acceptance.json`, and it is not comparable to
anything the current tree would produce:

| | Frozen capture | What would be captured now |
|---|---|---|
| Ran | 2026-08-13 | 2026-08-21 |
| Provider | `groq` / `qwen/qwen3.6-27b` | `deepseek` / `deepseek-v4-flash` |
| Prompt version | not recorded, backfilled as `v1` | `v4` |
| Language | English | Vietnamese |
| Status | `PARTIAL_QUOTA`, 13 turns of a planned 77 | expected `COMPLETE`, 77 |

The T0027.3 DeepSeek capture that would have been the closest baseline is lost
(`KI-2026-08-17-deepseek-capture-lost`), and it predates the Vietnamese translation anyway.

**So this run is the first Vietnamese DeepSeek baseline, not a comparison.**
That is fine, and it should be stated that way rather than discovered later.
It also means `driver diff` will refuse every comparison it is offered, correctly.

Two further constraints on what the run can produce:

- **It cannot become a committed replay.** `KI-2026-08-18-freezer-rejects-no-sql-turns` is open:
  `freeze_capture` requires `PASS`, `FAIL` or `EXEMPT` for every turn, and `HLP-CONTEXT-1` turn 2
  legitimately produces no SQL and therefore none of them. One turn blocks the whole capture.
- **The replay gate is already stale.** `KI-2026-08-20-stale-replays` is open: two of three
  committed replays no longer validate against the Vietnamese registry, and CI replays only the
  third. The regression gate this capture would feed is currently proving less than it appears to.

Neither is a reason to delay the run. Both are reasons not to promise the run will produce a
frozen regression case at the end of it.

---

## 8. Langfuse evaluators: what they are, and what to do about them

### 8a. What is on offer

Verified against the Langfuse documentation on 2026-08-21, for the Cloud Hobby plan this project
uses under D-029.

| Capability | Available on Hobby | What it does |
|---|---|---|
| Datasets and dataset runs | Yes | A named set of items; each execution becomes a run whose scores aggregate and compare run over run in the UI |
| `run_experiment()` SDK | Yes | Runs a task over a dataset with item-level and run-level evaluator callables, creating the run and its traces |
| Managed LLM-as-a-judge evaluators | Yes | Langfuse-maintained templates (hallucination, relevance, toxicity, helpfulness, some contributed by RAGAS) plus custom prompts, run by a judge model you connect |
| Custom code evaluators | Yes | Deterministic checks, run in your own process, results posted as scores |
| Score configs | Yes | Declared score names, types and ranges, so a score is a tracked category rather than a free string |
| Annotation queues | 1 queue | Human labelling in the UI |
| Online evaluation on live traces | Yes | Evaluators run asynchronously against sampled production observations, with filters on tags, user, session, version |

Limits that matter here: 50k ingested units per month, 30-day retention, 2 users.
A 77-turn capture is small against 50k units, but **30-day retention is a real constraint**: a
dataset run older than 30 days stops being readable evidence, while a capture artifact in
`evals/runs/` does not expire.

### 8b. Should we adopt datasets and dataset runs? Yes

This is already the approved direction in the observability plan's session 8, and the probe
strengthens the case rather than changing it.

The argument is that we currently have no way to answer "did this prompt change improve things"
inside a tool that shows the traces.
Comparison today means two JSON files, a `driver diff` that refuses anything with a different
`config_hash`, and a human reading a table.
A dataset run groups a capture's traces and scores under one comparable object, which is the exact
gap section 5b of the evaluation strategy calls "the single largest gap between our practice and
production practice".

Adopt with the direction session 8 already fixes: **`evals/scenarios_v1.yaml` stays authoritative
and the Langfuse dataset is a derived, drift-checked mirror.** D-041 makes this non-negotiable, and
the 30-day retention limit independently forbids treating Langfuse as the source of truth.

Do **not** migrate execution to `run_experiment()`.
Our task function is not a simple callable: it has checkpoint and resume, per-turn persistence,
provider-aware retry ladders, quota halting, and conversational threading through an
`InMemorySaver`. `run_experiment()` would replace all of that with `max_concurrency`, and the
driver's orchestration is the part D-043 explicitly decided to keep.
Attach dataset runs to the existing driver; do not hand the driver's job to Langfuse.

### 8c. Should we adopt managed LLM-as-a-judge evaluators? Not yet

Four reasons, in order of weight.

1. **We would be adding a second unvalidated judge.** The evaluation strategy's correction 1
   records that judge validation here is roughly 20 times undersized: practice validates a judge
   against 100-plus human labels with Cohen's kappa at a 0.6 floor, and this project has a
   4-5 golden spot-check. The existing Gemini judge is already in that position. A Langfuse
   managed evaluator would be a second judge with **no** calibration against our labels, scoring
   the same turns. Two uncalibrated judges do not average into one calibrated one.
2. **Prefab metrics are the specific thing the research warned against.** "Measure only what
   analysis found, ranked by frequency times severity. Generic prefab metrics manufacture false
   confidence." A hallucination or helpfulness template is generic by construction. Our failure
   taxonomy is not generic: it is truncation disclosure, provenance honesty about `created_on`,
   cross-currency refusal, listing expiry versus application deadline. No managed template
   measures any of those.
3. **The tiering doctrine points the other way.** D-042 and the grader hierarchy put structural
   checks above textual above judge, and the probe just demonstrated that our structural tier is
   the tier that is broken. Adding judge capacity while tier 1 mis-grades correct answers spends
   effort at the wrong altitude.
4. **Online evaluation needs traffic we do not have.** The strongest thing Langfuse evaluators
   offer is scoring sampled production traces continuously. Section 5b already identifies this as
   available-not-blocked, and D-018 sequences offline before online. The demo has little real
   traffic. Buying the capability before the traffic is premature.

**What to adopt from the evaluator surface now, cheaply:**

- **Score configs.** Declare the seam metric names and ranges so scores are a typed vocabulary
  rather than free strings assembled as `f"{seam_name}/{metric_name}"`. Small, and it makes the
  scores chartable.
- **Custom evaluators as the integration shape.** Our deterministic grader is precisely a custom
  code evaluator. Posting its per-turn verdicts as scores, alongside the judge scores, is the
  fix for B2c and it lands the tier-1 signal in Langfuse where the tier-3 signal already goes.
- **The annotation queue, for judge calibration.** This is the one managed feature that addresses
  a documented gap. One queue on Hobby is enough to label turns at the turn level, which is what
  correction 1 says is needed to reach a usable label count without inventing scenarios. This is
  a way to *validate* our judge, not to add another.

**Revisit the managed evaluators** when the judge is calibrated to kappa at or above 0.6 and
production traffic exists to sample. Both are already on the roadmap as phase 5 and phase 6.

### 8d. Where we stand against industry practice

The 2026 consensus shape is three evaluation points: offline against curated datasets,
pre-merge in CI, and online against sampled production traffic.

| Practice | Our state | Verdict |
|---|---|---|
| Offline suite on a curated golden set | 29 scenarios, requirement-seeded, registry-owned | Strong. Coverage of distinct failure modes beats raw count, and this set is built that way |
| Deterministic checks preferred over judges | Three-tier hierarchy, structural first | Strong in design, **broken in execution** per B1 |
| CI gate that does not call the model | Replay gate over frozen captures | Right idea, currently stale per B5 |
| Judge calibrated against human labels with kappa | Not done | The largest methodological gap, already recorded |
| Online evaluation on sampled traffic | Not done, deliberately | Correctly deferred |
| Living, versioned dataset | `prompt_version` stamping, registry hash in the manifest | Ahead of typical practice |
| Cost and latency tracked per run | Latency and tokens yes, cost no | Gap, and it is observability session 2 |

The notable thing is that the design is closer to good practice than the execution is.
The failures in this report are not gaps in the plan. They are places where a correct plan is not
actually running.

---

## 9. Recommended sequence before the capture

Ordered so nothing later invalidates something earlier.
Steps 1 to 3 are prerequisites; step 4 is a maintainer choice; step 5 is the run.

| Step | Work | Cost | Why before the run |
|---|---|---|---|
| 1 | Fix B1: default execution accuracy to row identity, keep `exact` only where a scenario pins its projection | none | Otherwise 17 scenarios measure the grader |
| 2 | Fix B3: the emoji prompt rule plus its check, bumping `prompt_version` to `v5` | none | A prompt change after the capture invalidates it |
| 3 | Fix B4: strip schema identifiers from the purity probe, add a column-leakage check | none | Otherwise a whole failure class is mislabelled |
| 4 | Decide D-a below, then either fix `LANGFUSE_BASE_URL` and the driver default and add score writeback, or record that this capture is untraced | small | Determines whether the run is traced evidence or disk evidence |
| 5 | Capture all 29 scenarios, then grade and read | ~5 min, ~$0.04 | |

Steps 1 to 3 cost no provider quota and no money.
That matters: the whole point of D-045 was that a full capture now costs five minutes and four
cents, so there is no reason to run a capture through a known-broken grader to save time.

**Also worth doing in step 4, and cheap:** the agent quoting `is_salary_negotiable = True` at users
is a serving defect with an obvious cause in `_build_answer`. It is out of scope for a measurement
change and should be filed rather than fixed inline, but the capture will measure it either way,
so file it first so the result is expected rather than surprising.

---

## 10. Open questions for the maintainer

1. **D-a: traced or untraced.** Does this capture need to land in Langfuse with environment, tags,
   release and dataset run, which makes observability sessions 3 and 8 prerequisites? Or is a
   graded artifact on disk sufficient for this baseline, with tracing added on the next run?
   Recommendation: untraced now, traced next, because B1 and B3 gate the run's usefulness far more
   than tracing does.
2. **D-b: execution accuracy semantics.** Is the assertion "the query found the right postings"
   (row identity) or "the query returned the right table" (projection included)? Section 3 argues
   the first, per scenario text. This is a D-041 registry decision.
3. **D-c: score writeback ownership.** `write_scores` is reachable only from the pytest path.
   Should the driver call it, should `run_case` and `_score_case` be collapsed into one scoring
   entry point, or should writeback move to a post-run step over the artifact? The third is the
   only one that works for a resumed or partially quota-halted run.
4. **D-d: Langfuse evaluator scope.** Section 8c recommends adopting score configs, custom-evaluator
   score posting, and the annotation queue, while declining managed LLM-as-a-judge evaluators until
   the existing judge is calibrated. Confirm, because the alternative changes what session 8 of the
   observability plan builds.

---

## 11. Limits of this record

The probe is 5 turns over 2 scenarios, not 77 turns over 29.
It is sufficient to establish that B1, B3 and B4 exist and reproduce, and insufficient to
establish their frequency across the registry.
Specifically, B1's blast radius of 17 scenarios is counted from the registry's comparison modes,
not measured; the number of those that actually reproject on a given run is unknown until a full
capture runs.

Nothing here re-measures behavior quality.
Every failure examined turned out to be an instrument defect, which is a finding about the
instrument and says nothing about whether the agent answers well.
That question is what the capture is for, and it cannot be answered until the instrument stops
failing correct answers.

The Langfuse feature and plan details in section 8a were read from the vendor documentation on
2026-08-21 and were not exercised against the live project.

---

## 12. Sources

- [Langfuse evaluation overview](https://langfuse.com/docs/evaluation/overview)
- [Langfuse LLM-as-a-judge evaluators](https://langfuse.com/docs/evaluation/evaluation-methods/llm-as-a-judge)
- [Langfuse experiments via the SDK](https://langfuse.com/docs/evaluation/experiments/experiments-via-sdk)
- [Langfuse pricing and plan limits](https://langfuse.com/pricing)
- [Offline evaluation for AI agents](https://www.datadoghq.com/blog/offline-llm-evaluations/)
- [AI evaluation engineering handbook](https://www.freecodecamp.org/news/ai-evaluation-engineering-build-a-production-grade-llm-evaluation-platform-handbook/)
- [Judging the judges: alignment and vulnerabilities in LLMs-as-judges](https://arxiv.org/html/2406.12624v1)
- [Calibrating an LLM judge with human annotations](https://galileo.ai/blog/calibrate-llm-judge-human-annotations)
- [Building a golden dataset for AI evaluation](https://www.getmaxim.ai/articles/building-a-golden-dataset-for-ai-evaluation-a-step-by-step-guide/)
- In-repo: [Langfuse observability gaps](langfuse-observability-gaps.md),
  [evaluation strategy](evaluation-strategy.md),
  [T0027.3 DeepSeek arm](../evals/t0027_deepseek_arm.md),
  [Known Issues](../docs/Known_Issues.md), [Decision Log](../docs/Decision_Log.md) <!-- archived-on-tag -->
