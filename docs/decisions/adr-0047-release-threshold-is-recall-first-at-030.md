# Release threshold is recall-first at 0.30 on corpus v7

> **Status:** Superseded by ADR-0052 · **Decided:** 2026-08-26

## Decision

The release gate for semantic judge scores uses threshold 0.30: a case passes only when the judge
score is at least 0.3. The threshold was swept from 0.1 to 1.0 over all 36 cases of
`evals/calibration_v7.yaml` (n=36, 18 semantic classes x one PASS + one FAIL), judged by
`google/gemma-4-31b-it` via Google AI Studio at rpm 10 with a 120 s client timeout. The recall-first
policy picks the highest sweep point that keeps recall at 1.00 overall and on every swept class.

Measured at the chosen threshold (`evals/runs/iha266-calibration-v7-agreement-report.json`):

| Group | n | Precision | Recall |
|---|---|---|---|
| Overall | 36 | 0.75 | 1.00 |
| SAF | 10 | 1.00 | 1.00 |
| HON | 14 | 0.6363636363636364 | 1.00 |
| HLP (not swept, reported) | 12 | 0.75 | 1.00 |

Judge scores are near-bimodal (21 cases at 1.0, 12 at 0.0, three mid-scores between 0.3 and 0.4), so
every sweep point below 0.4 yields identical metrics; 0.30 is the top of that plateau. Raising to
0.40 or beyond drops overall recall to 0.94 by failing a human-PASS case scored 0.4.

## Consequences

A false negative - failing the agent's genuinely correct behavior in CI - costs more than a false
positive, so six judge-human disagreements (all human-FAIL cases the judge passed) are accepted at
precision 0.75 rather than traded for recall. The disagreements concentrate in HON (4 of 6) and
become labeled evidence for grader-authority follow-up per ADR-0042. The sample size n=36 is small:
the gate claim is provisional and must be re-swept when the corpus grows. The provider switch
groq -> openrouter -> Google AI Studio re-documents ADR-0017's eval-only precedent (#238); the
120 s judge client timeout (`eval.judge.timeout_seconds`) is a measured fix for gemma CoT prompts
that need 50-90 s per call.
