# T0015.6 Provider A/B results

> **Status:** Offline provider wiring is complete. The live Gemini matrix is blocked; no observed results are invented.

## Run configuration

- Run date: 2026-07-16 UTC
- qwen baseline: `qwen/qwen3.6-27b` via Groq, `temperature: 0.2`, `max_tokens: 2048`, `reasoning_format: hidden`.
- Gemini arm: `gemini-2.5-flash` via Google, `temperature: 0.2`, `max_tokens: 2048`, `thinking_budget: 0`.
- T0015.5 reasoning setting: no arm was selected because its live baseline/low/none run was blocked. The configured qwen ReAct value remains `null`; SQL generation remains qwen/Groq with `reasoning_effort: none`.
- Judge isolation: `eval.judge.provider: google`, `eval.judge.model: gemini-2.5-flash`, `eval.judge.thinking_budget: 0` unchanged.

## Comparison

| Measure | qwen v1 | Gemini Flash | Delta |
|---|---:|---:|---:|
| Full 29-scenario pass count | 13/16 baseline artifact scope | pending | pending |
| Per-scenario pass/fail | `evals/v1_scenario_matrix.observed.json` | pending live artifact | pending |
| Tokens per turn | unavailable | unavailable | pending |
| Latency | unavailable | unavailable | pending |
| Empty answers / reasoning leaks | baseline artifact only | pending | pending |
| Quota / rate-limit headroom | prior qwen runbook values; not revalidated here | account-specific; pending AI Studio check | pending |

The frozen qwen baseline and observed artifact were not modified. A Gemini artifact must be written separately as `evals/gemini_v1_scenario_matrix.observed.json` and graded with 3 reruns for probes and 2 for non-probes.

## Live blocker

The prerequisite check on 2026-07-16 found `GOOGLE_API_KEY`, `GROQ_API_KEY`, and `DATABASE_URL` unset, and `localhost:5433` unavailable. The fixture loader therefore did not provide the required 22-row confirmation. No Gemini request or 29-scenario result was claimed.

Google's current documentation says active limits are account/project-specific and must be checked in AI Studio; the published limits are not guaranteed. Record the actual Gemini 2.5 Flash RPM, TPM, and RPD values from the maintainer's AI Studio project before running the matrix: <https://ai.google.dev/gemini-api/docs/rate-limits>.

## Recommendation

Do not lock Gemini or qwen for T0015.7 yet. Run the blocked T0015.5 qwen reasoning arms and this Gemini comparison first. T0015.7 remains provider-neutral until the evidence-backed winner is recorded.
