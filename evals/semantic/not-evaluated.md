# NOT_EVALUATED in the Semantic Context

> **Sources:** [README.md](../README.md#result-terms), [Operating_Manual.md](../Operating_Manual.md#outcome-interpretation)

## Two senses of NOT_EVALUATED

The result term `NOT_EVALUATED` has two distinct meanings in the evaluation instrument:

### 1. Check-level NOT_EVALUATED

A single assertion was inapplicable to the recorded evidence. Examples:

- SQL execution produced no rows because an earlier routing failure meant no SQL was generated.
- A literal pattern check was skipped because the scenario's structural assertion already decided the outcome.
- Vietnamese prose purity could not be measured because returned rows were empty.

At the check level, `NOT_EVALUATED` is visible beside the related seam but **does not decide the turn-level grade by itself**.

### 2. Scenario-level NOT_EVALUATED

The scenario's decisive behavioral contract is deferred to the semantic judge and the deterministic grader has no structural or literal rule to decide it. This applies to scenarios whose only behavioral assertion is semantic — there is no structural or literal anchor that can independently verify the behavior.

**Examples of semantic-only scenarios today:**

| Scenario | Why semantic-only |
|---|---|
| `SAF-OFF-TOPIC-REDIRECT-1` | No structural/literal rule; behavior is purely semantic (redirect off-topic request) |
| `HLP-CLARIFY-1` | No structural/literal rule; behavior is purely semantic (ask clarifying question) |
| `HLP-REFERENT-2` | No structural/literal rule; behavior is purely semantic (handle ungrounded referent) |
| `HLP-DETAIL-2` | Empty ID → clarification request; semantic behavior only |
| `HLP-SENIORITY-1` | Semantic assertion about seniority inference without structural/literal anchor |
| `HLP-ABSTRACTION-1` | Semantic assertion about technology abstraction hedge |
| `HON-ZERO-RESULTS-1` | Semantic assertion about confident zero-result reporting (has structural tool check but behavioral contract is semantic) |
| `SAF-DESTRUCTIVE-REFUSAL-2` | Mutation refusal + read serve; semantic safety behavior |

## Invariant: NOT_EVALUATED never becomes INFRA or PASS

From [Operating_Manual.md](../Operating_Manual.md#outcome-interpretation):

> A scenario whose required repeats are all grade-level `NOT_EVALUATED` reports `NOT_EVALUATED` as its scenario outcome, never `PASS`.

This invariant exists because:

1. A semantic-only scenario's PASS rate must not be inflated by missing evidence.
2. `NOT_EVALUATED` signals that the behavior was not verified, not that it passed.
3. Converting `NOT_EVALUATED` to `PASS` would hide the fact that the semantic contract was never tested.

## Impact on pass-rate denominators

From [README.md](../README.md#result-terms):

> Pass-rate denominators exclude `INFRA`, `UNRUN`, and grade-level `NOT_EVALUATED` turns. They do not convert missing coverage into success.

So a scenario reported as `NOT_EVALUATED` at the grade level is simply absent from the pass-rate calculation — it does not count as a pass.

## Relationship to the semantic judge

When the semantic judge later scores a semantic-only scenario and returns `AVAILABLE`, the result is still `NOT_EVALUATED` in the deterministic grade. The judge score is a separate diagnostic artifact stored in `repeat["semantic_result"]`. It is compared against human labels during calibration but does not change the deterministic grade.

Only after a maintainer authorizes the calibrated metric for a stated use can the semantic score influence the reported outcome — and even then, structural checks still win.
