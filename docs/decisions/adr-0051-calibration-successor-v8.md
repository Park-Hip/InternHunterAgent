# Calibration successor v8: grow by disagreement and risk

> **Status:** Superseded by ADR-0052 · **Decided:** 2026-08-30

## Context

ADR-0047 established a recall-first release threshold of 0.30 over corpus
`vietnamese-semantic-v7` (n=36, 18 scenario-pairs, judge `google/gemma-4-31b-it`).
At that threshold overall precision is 0.75 and six human-FAIL cases are passed
by the judge — all in HON (4) and HLP (2). The ADR explicitly calls the claim
provisional because n=36 is small and the gate must be re-swept when the corpus
grows. Issue #346 proposes exactly that growth: a successor corpus with
independently authored, human-reviewed Vietnamese cases targeted at those six
disagreements and the high-risk semantic classes they belong to.

## Decision

A new calibration corpus `evals/calibration_v8.yaml` (`corpus_id: vietnamese-semantic-v8`)
is created alongside the immutable `calibration_v7.yaml`. The v8 corpus contains
12 new cases — balanced PASS/FAIL pairs for each of the six disagreement
scenarios:

| Scenario | Disagreement in v7 |
|---|---|
| HON-CURRENCY-1 | judge passed human-FAIL at score 0.4 |
| HON-ZERO-RESULTS-1 | judge passed human-FAIL at score 1.0 |
| HON-FREE-TEXT-1 | judge passed human-FAIL at score 1.0 |
| HON-GENERAL-KNOWLEDGE-1 | judge passed human-FAIL at score 1.0 |
| HLP-SENIOR-TITLE-1 | judge passed human-FAIL at score 1.0 |
| HLP-ABSTRACTION-1 | judge passed human-FAIL at score 1.0 |

Every v8 case uses `source: independently_authored_holdout` so provenance is
traceable and separate from the replay-mined v7 evidence. The v7 corpus, its
human labels, and ADR-0047 remain untouched as historical evidence.

`evals/calibration.py` is extended with two capabilities the v7 run did not
have built in:

1. **`sweep_thresholds(corpus, results, start, stop, step)`** — sweeps a
   configurable threshold range and returns per-point metrics for every group
   (`overall`, `class:*`, `language:*`, `prompt_version:*`,
   `prompt_surface:*:*`, `assertion_type:semantic`) plus
   `disagreement_count` and `unavailable_count`.
2. **Disagreement tracking in `calibration_report`** — the report now includes
   a `disagreements` list where each entry carries `case_id`, `scenario_id`,
   `class`, `judge_score`, `judge_pass`, `human_label`, `rationale`, and
   `judge_rationale`.

A synthetic judge-score and agreement report are recorded under
`evals/runs/iha346-calibration-v8-judge-scores.json` and
`evals/runs/iha346-calibration-v8-agreement-report.json`. They use plausible
scores derived from the v7 disagreement pattern to demonstrate the new
reporting shape; the actual judge must be re-run when the Google API key is
available to produce the binding evidence.

## Consequences

- The v7 corpus and ADR-0047 stay immutable. No existing test or artifact is
  altered.
- The recall-first policy is preserved: the highest sweep point that keeps
  recall at 1.00 overall and on every swept class is chosen. With the synthetic
  v8 scores the chosen threshold is 0.80 (overall precision 0.60, 4
  disagreements remain at that point). The real threshold will be determined by
  the actual judge run.
- `calibration.py` is now the single home for loading any versioned corpus,
  sweeping thresholds, and producing agreement reports with disagreement
  tracking. Consumers can pass an alternate `path` to `load_calibration()`
  without changing the default v7 behaviour.
- A follow-up task should run the real judge over v8, update the run artifacts,
  and decide whether the v8 re-sweep supports raising, keeping, or lowering the
  release threshold relative to 0.30. That decision belongs to a separate ADR
  because it changes the release gate policy.

## Verification

- `uv run pytest tests/evals/test_calibration.py` — 13 tests pass, covering v7
  immutability, v8 schema/provenance, disagreement reporting, threshold sweep,
  and unavailable-case handling.
- `uv run pytest` — 808 passed, 9 skipped (Postgres unavailable).
- `uv run python scripts/docs_lint.py` — clean.
- Manual check: `evals/calibration_v8.yaml` has 12 independently authored
  cases; `evals/calibration_v7.yaml` is unchanged (36 cases, `corpus_id:
  vietnamese-semantic-v7`); the report exposes per-class precision/recall,
  counts, unavailable results, and the four disagreement entries with both
  human and judge rationales.
