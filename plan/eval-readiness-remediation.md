# Evaluation readiness remediation plan

> **Status:** Draft for maintainer approval.
> This plan turns [evaluation readiness and Langfuse evaluators](../research/eval-readiness-and-langfuse-evaluators.md)
> into phases that can be executed without drifting into each other.

> **Last verified:** 2026-08-21

> **Eviction:** This plan leaves when every approved phase is merged, or its scope is superseded by
> a recorded decision.

## Goal and expected outcome

Make the evaluation instrument measure what it claims to measure, so a full 29-scenario DeepSeek
Vietnamese capture produces evidence about the agent rather than evidence about the grader.

The measured starting point is a 2026-08-21 probe: 5 turns, **0 PASS**, and no failure caused by
agent behavior.

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
| `config/prompts.yaml` | 2 | 1, 3 |
| `evals/grader.py` | 2 | 1, 3 |
| `tests/evals/test_grader.py` | 2 | 1, 3 |
| `tests/test_prompt_surface.py` | 2 | 1, 3 |
| `docs/Agent_Behavior_Spec.md` | 2 | 1, 3 |
| `src/core/config.py` | 3 | 1, 2 |
| `evals/driver.py` | 3 | 1, 2 |
| `evals/writeback.py` | 3 | 1, 2 |
| `evals/harness.py` | 3 | 1, 2 |
| `tests/evals/test_writeback.py` | 3 | 1, 2 |
| `tests/evals/test_driver.py` | 3 | 1, 2 |

Phases 1, 2 and 3 share no file and may run in parallel in separate worktrees.
Phase 4 writes no code.

---

## Phase 0 - decisions, no code

Four decisions gate the phases below. Phase 1 and Phase 2 can start on the recommendations as
stated; Phase 3 cannot start until D-a is answered.

| ID | Question | Recommendation | Gates |
|---|---|---|---|
| D-a | Must the capture be traced in Langfuse with environment, tags, release and cost, or is a graded artifact on disk sufficient for this baseline? | Untraced now, traced on the next run. Tracing depends on two sessions of another plan; readiness does not. | Phase 3 scope, Phase 4 timing |
| D-b | Is execution accuracy "the query found the right postings" or "the query returned the right table"? | Row identity for listing scenarios, exact for count and aggregate scenarios. | Phase 1 |
| D-c | Where does score writeback belong for a recorded run? | A post-run step over the artifact, because it is the only option that survives a resumed or quota-halted run. | Phase 3 |
| D-d | Adopt Langfuse score configs, custom-evaluator score posting and the annotation queue, while declining managed LLM-as-a-judge evaluators until the existing judge is calibrated? | Yes. | Phase 5 |

**Exit gate:** each decision is recorded, with D-a answered before Phase 3 opens a branch.

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
- **R1.4** `ids_only` is rejected at load time when the scenario's reference SQL does not select
  `id`. Without this guard, `ids_only` on a `COUNT(*)` reference compares two empty sets and
  passes everything, which is a silent false pass and worse than the failure it replaces.
- **R1.5** The status vocabulary is unchanged. `PASS`, `FAIL`, `EXEMPT`, `INFRA` and `UNRUN` keep
  their current spelling and meaning, because `driver._expected_execution_accuracy` parses the
  grader's detail string and Phase 3 must not have to track this.

**Files.** `evals/scenarios_v1.yaml` for R1.1 to R1.3, `evals/execution_accuracy.py` for the R1.4
guard, `tests/evals/test_execution_accuracy.py` and `tests/evals/test_scenarios.py` for coverage.

**Exclusions.** Do not change the default comparison mode in code; the registry owns expectations
under D-041. Do not change any prompt to make a query match a reference. Do not touch
`evals/grader.py`, which only reads the status this module produces.

**Verification.** Focused tests for both modes and the R1.4 guard, including a regression case with
a superset projection over identical rows. Then re-grade the 2026-08-21 probe artifact and confirm
the five `execution_accuracy` failures become passes without any change to agent behavior.

**Risk.** `ids_only` measures less than `exact`. A query that returns the right postings with a
wrong column value would now pass. This is accepted deliberately: the scenario text asserts which
postings, and `contains_reference` remains available per scenario where a column value is the
point.

**Exit gate:** re-grading the probe artifact yields zero `execution_accuracy` failures, and each of
the 17 previously-`exact` scenarios carries an explicit, reviewed classification.

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
`tests/evals/test_grader.py`, `tests/test_prompt_surface.py`.

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

## Phase 3 - the eval run reaches Langfuse

**Problem.** Three defects stack, and fixing any one alone changes nothing. The export target is a
dead local address, the driver defaults tracing off, and no recorded run has ever written a score
to Langfuse because `write_scores` is reachable only from the pytest path.

**Scope depends on D-a.** If D-a says untraced, this phase reduces to R3.1 and R3.2 and Phase 4
proceeds without it.

**Requirements.**

- **R3.1** `src/core/config.py` no longer defaults `LANGFUSE_BASE_URL` to a local address. A
  missing value fails loudly rather than pointing at `localhost`, per D-029.
- **R3.2** The operator's `.env` is corrected to the Langfuse Cloud host. This is an operator
  action on an untracked file, recorded in the pull request body and in `.env.example`.
- **R3.3** `evals/driver.py` no longer forces `LANGFUSE_ENABLED` off by default. The manifest's
  `tracing.langfuse_enabled` field must continue to report the value the run actually used.
- **R3.4** Judge scores from a recorded run reach Langfuse, as a post-run step over the capture
  artifact per D-c. `harness.run_case` and `driver._score_case` stop being two scoring paths with
  different side effects.
- **R3.5** The post-run step is idempotent. `write_scores` already derives a deterministic
  `score_id`; a rerun must not duplicate scores.
- **R3.6** A run whose traces were never ingested is distinguishable from one whose traces were.
  The probe recorded five non-null `trace_id` values pointing at traces that do not exist, and that
  must not be possible to mistake for success again.

**Files.** `src/core/config.py`, `evals/driver.py`, `evals/writeback.py`, `evals/harness.py`,
`tests/evals/test_writeback.py`, `tests/evals/test_driver.py`.

**Exclusions.** This phase does not add environments, tags, release attribution, prompt-version
trace attributes, model pricing, or dataset runs. Every one of those is already owned by sessions
1, 2, 3 and 8 of the
[Langfuse observability remediation plan](langfuse-observability-remediation.md), and building them
here would be the same work twice in two plans. This phase makes the eval path reach Langfuse at
all; that plan makes what arrives attributable.

**Verification.** Focused tests for the writeback step and the driver default. Then a two-scenario
live capture with tracing on, confirming in the Langfuse UI that the traces exist, that scores are
attached, and that a rerun of the writeback step adds no duplicates.

**Risk.** Turning eval tracing on spends Hobby-plan ingestion, which is the trade the observability
plan already approved. Retention is 30 days, so a dataset run is not durable evidence and the
capture artifact on disk remains the record.

**Exit gate:** a capture's scores are visible on its traces in Langfuse, and re-running the
writeback changes nothing.

---

## Phase 4 - the capture

No code. This phase is the run the whole plan exists to enable.

**Preconditions.** Phase 1 and Phase 2 merged. Phase 3 merged only if D-a chose traced. Fixture
database rebuilt. Working tree clean, so the manifest records `baseline_eligible: true`.

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

---

## Sequencing

| Phase | Depends on | May run beside |
|---|---|---|
| 0 | nothing | nothing, it is a decision |
| 1 | D-b | 2, 3 |
| 2 | nothing | 1, 3 |
| 3 | D-a, D-c | 1, 2 |
| 4 | 1 and 2 merged, 3 if D-a chose traced | nothing |
| 5 | observability plan session 3 | not scoped here |

Phases 1, 2 and 3 are file-disjoint and can be three concurrent worktrees off `origin/main`.
Phase 4 must follow a rebase onto the merged result of all of them.

## Explicit exclusions for the whole plan

This plan does not change agent behavior except for the single style rule in R2.1, does not fix the
`_build_answer` identifier leakage, does not repair or re-capture the stale committed replays, does
not change the freezer, does not calibrate the judge, does not add Langfuse environments, tags,
release attribution, pricing or datasets, and does not expand the scenario set.

## Risks carried

- Phase 2's prompt bump invalidates any capture taken before it, which is why Phase 4 is last.
- Phase 1 reduces what execution accuracy asserts. That is the intended trade, and it is reversible
  per scenario.
- The capture cannot become a frozen replay, so the regression gate does not improve as a result of
  this plan. Two open known issues stand between here and that.
- The plan assumes the probe's failure modes generalise to the full registry. Blast radius for
  Phase 1 is counted from the registry, not measured; Phase 4 is what measures it.
