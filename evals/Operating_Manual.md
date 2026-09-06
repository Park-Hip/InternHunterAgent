# Evaluation Operating Manual

> **Last verified:** 2026-08-23.

> **Eviction:** This manual leaves when the review process, authority boundary, or evidence states change.

This manual tells a maintainer how to review an evaluation result without confusing a model failure, a missing observation, and a grader disagreement.
Use [`README.md`](README.md) for the exact commands and the glossary of terms.
Use [`Instrument_Report.md`](Instrument_Report.md) for the current baseline and open cases.

## What the instrument observes

Every user question is a turn with up to three seams.

1. Routing records whether the agent chose the required tool or correctly chose no tool.
2. SQL generation records generated SQL and the fixture rows it returned.
3. Synthesis records the answer presented to the user.

The earliest failed seam is the primary diagnosis.
If routing failed, a later missing SQL comparison is `NOT_EVALUATED`, not a second infrastructure failure.
If generated SQL failed execution accuracy, an incorrect answer downstream remains evidence of that earlier SQL failure.

The evaluator creates the same agent used by the product and binds it to a frozen 24-row fixture database.
The fixture makes the SQL contract repeatable and manually inspectable, but it is not a production-corpus quality sample.

## Authority and the four kinds of check

Structural assertions check observable facts such as tool use, SQL result contracts, row counts, and prohibited identifiers.
Literal assertions check fixed, reviewable text conditions such as a secret-like pattern.
Semantic assertions ask whether the response satisfied a behavior requirement over the complete conversational trajectory.

Structural results take precedence over literal, semantic, and judge-metric results.
The judge-metric check compares a persisted per-seam harness score (e.g. `seam1_routing`, `seam2_nl_to_sql`, `seam3_synthesis`) against `rule.judge_threshold` (default 0.5); it is the lowest-precedence tier and cannot override structural, literal, or semantic results. See [deterministic/index.md §Canonical cascade description](deterministic/index.md#canonical-cascade-description).

During calibration, human review wins over both deterministic and semantic results.
Each disagreement requires a new or corrected labelled corpus case and a written disposition.
Only a maintainer can authorize a calibrated metric for a stated use after reviewing the published report.
An authorization to report a diagnostic metric is not authorization to impose a release gate.

## Outcome interpretation

| Result | Operator interpretation | Required action |
|---|---|---|
| `PASS` | The evaluated deterministic checks passed. | Inspect only as part of normal sampling. |
| `FAIL` | The agent violated an applicable deterministic check. | Verify the earliest failing seam and route it as product behavior work. |
| `INFRA` | Required evidence was not captured because of a provider, quota, database, or other external failure. | Repair or rerun the affected measurement. Do not count it as a pass. |
| `UNRUN` | The capture did not attempt the turn or scenario. | Resume or replace the capture. Do not publish it as complete coverage. |
| `NOT_EVALUATED` | A single check was inapplicable to recorded evidence, **or** a semantic-only behavioral contract has no usable numeric judge score. | Keep the earlier applicable result and do not relabel this as `INFRA`. For a grade-level `NOT_EVALUATED`, the summary excludes the turn from the pass-rate denominator. |
| `EXEMPT` | Execution accuracy is intentionally absent because the scenario has no SQL contract. | Verify the registry exemption remains appropriate. |
| `AVAILABLE` | The semantic judge returned a numeric score and rationale. | The grader evaluates it against the calibrated class threshold; compare it with the human label or sample review. |
| `UNAVAILABLE` | The semantic judge did not produce a usable result. | Preserve the error and keep the result for rerun. |

Pass-rate denominators exclude `INFRA`, `UNRUN`, and grade-level `NOT_EVALUATED` turns.
They do not convert missing coverage into success.
A check-level `NOT_EVALUATED` is visible beside the related seam and does not decide the turn-level grade by itself.
A scenario whose required repeats are all grade-level `NOT_EVALUATED` reports `NOT_EVALUATED` as its scenario outcome, never `PASS`.

## Baseline review workflow

Perform the commands in [`README.md`](README.md) in their listed order.
The order protects the only non-repeatable artifact, which is the serving-model capture.

1. Confirm the worktree is clean and the fixture is rebuilt.
2. Capture the registry and retain the raw artifact under `evals/runs/`.
3. Generate the execution-accuracy report.
4. Score the preserved raw capture through the semantic path when judge credentials are available.
5. Generate the deterministic grade report, which consumes the persisted semantic scores.
6. Freeze the capture before analyzing the result and commit only the resulting sanitized replay.
7. Replay the committed artifact with no serving-model or judge credentials.
8. Open the viewer with deterministic and execution reports joined.
9. Update the instrument report with provenance, coverage, metrics, disagreements, and unresolved cases.
10. Request maintainer acceptance only after the manual sample below is complete.

Never alter prompts, provider configuration, fixture data, registry rules, or a human label in the same pass that measures a baseline.
That would make a score unable to distinguish model change from measurement change.

## Manual viewer sample

Use the viewer to inspect at least these four examples in every full baseline.

| Sample | What to inspect |
|---|---|
| Refusal | Confirm the routing seam, refusal answer, and any prohibited-content check agree. |
| Zero result | Confirm reference and generated row counts are zero and that the answer does not invent a result. |
| Conversational scenario | Confirm every turn is present, the second question receives the expected context, and a missing SQL comparison is marked `NOT_EVALUATED` only when appropriate. |
| SQL mismatch | Compare generated and reference rows, the declared comparison contract, and the first failing seam. |

Record the scenario, repeat, turn, observed evidence, and disposition in the pull request body or the dated instrument report.
Do not change a rule merely because the current captured answer fails it.

## Disagreement workflow

Treat a disagreement as evidence to classify, not as a reason to pick the convenient score.

1. Read the scenario contract and the complete turn trajectory in the viewer.
2. Check structural evidence first, including tool calls and execution rows.
3. Check whether the disputed assertion was applicable.
4. Compare the human judgement with the semantic score and rationale when it is `AVAILABLE`.
5. Label the disagreement as an agent behavior failure, a deterministic grader defect, a semantic judge disagreement, or infrastructure.
6. Add an independently written labelled case to `calibration_v8.yaml` when the disagreement tests semantic behavior.
7. Record why the label won and rerun only the appropriate offline stage.

A judge score must never silently replace a human label.
A failed structural check must never be waived by a favorable semantic score.
An unavailable judge result is rerunnable evidence, not a pass or a failure.

## Baseline acceptance checklist

The maintainer can accept a published baseline only after confirming all of these statements.

- The capture has `baseline_eligible: true`, a clean worktree state, and recorded prompt, registry, fixture, provider, model, and sampling lineage.
- The run's scenario and turn coverage is explicit, including all `INFRA` and `UNRUN` cases.
- The frozen replay is sanitized and replays to the stored execution and deterministic outcomes without a model call.
- The deterministic result reports class, scenario, and turn outcomes separately.
- The semantic calibration report identifies its corpus, available and unavailable results, threshold status, precision, recall, confusion counts, and disagreement rate.
- Every sampled disagreement has a written disposition.
- The report names the metric's authorized use and the claims it does not support.

If any item is missing, the correct result is an incomplete baseline, not a green baseline.
