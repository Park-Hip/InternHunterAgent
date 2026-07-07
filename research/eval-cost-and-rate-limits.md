# Eval Cost & Rate-Limit Analysis — 3-Seam Golden Harness

> **Status:** Research / cost-and-capacity analysis (captured 2026-07-07). Measures the
> token cost, dollar-equivalent, and provider rate-limit exposure of one full
> `evals/harness.py` run, and ranks levers to reduce judge load **before** the T0011.5
> baseline is run repeatedly. Nothing here is implemented — any change is its own ticket
> (per `CLAUDE.md` §1). Feeds the reminder in `docs/Known_Issues.md` → Evaluation harness.

## 1. What actually runs on each eval

Per full run, `evals/harness.py` executes **17 goldens** (A1–A4, B1–B2 conversational,
C1–C6, D1–D3, E1–E2) against **two separate LLMs on two separate free-tier budgets**:

| Layer | Model | Provider | Budget it draws from |
|---|---|---|---|
| **Agent** (produces the answer/SQL) | `qwen/qwen3.6-27b` | **Groq** free tier | 30 RPM / 1K RPD / **200K TPD** |
| **Judge** (scores the metrics) | `gemini-2.5-flash` | **Google** free tier | ~10–15 RPM / 250K–1M TPM / 250–1500 RPD |

Metrics fired per golden (`seam1_metrics` / `seam2_metrics` / `seam3_metrics`):

| Seam | Metric | Uses judge LLM? | ~Judge calls |
|---|---|---|---|
| 1 routing | `ToolCorrectnessMetric` | ❌ deterministic | 0 |
| 1 routing | `GEval("Argument Correctness")` | ✅ | 1 |
| 2 NL→SQL | `GEval("SQL Schema Quality")` | ✅ (only if SQL produced) | 1 |
| 3 synthesis | `GEval("Task Completion")` | ✅ | 1 |
| 3 synthesis | `FaithfulnessMetric` | ✅ **multi-step** | ~3 |
| 3 synthesis | `GEval("Honesty")` | ✅ | 1 |

The codebase itself anchors the total: `score()` fires **~119 sequential judge calls per
full 17-golden run** (`evals/harness.py:16-17`; Known_Issues T0011.6 record). Back-to-back
with no inter-metric delay. `FaithfulnessMetric` alone (claims → verdicts → reason) is
roughly **one third** of those calls.

## 2. Cost estimate per run

**Token estimate (judge side, ~120 calls):**

| | Per call (avg) | Per run (~120 calls) |
|---|---|---|
| Input (deepeval scaffolding + question + answer + schema/tool-output context) | ~1,200 tok | ~145K tok |
| Output (**Gemini 2.5 Flash is a *thinking* model** — reasoning billed as output; `evals/judge.py` sets `max_tokens=4096`) | ~1,500 tok | ~180K tok |
| **Total** | ~2,700 tok | **~325K tok** (range ~250K–400K) |

Context-size inputs used for the estimate (measured): `schema_context` ≈ 296 tok,
`system_prompt` ≈ 664 tok, `sql_generation` ≈ 509 tok (`config/prompts.yaml`); tool output
capped at `agent.query.max_rows = 20` rows.

**Actual money cost today: $0** — judge is on Google free tier, agent on Groq free tier.
Nothing is billed; the binding constraint is **quotas, not dollars**.

**Paid-equivalent** (reference only, if the judge ever moves to paid `gemini-2.5-flash` @
$0.30/M input, $2.50/M output):

- Input: 145K × $0.30/M ≈ **$0.04**
- Output: 180K × $2.50/M ≈ **$0.45**
- **≈ $0.50 per full run**, ~**90% output-driven** because the thinking model spends tokens
  on hidden reasoning.

## 3. Rate limits (the real bottleneck)

Google no longer publishes a stable table and **cut free-tier quotas in Dec 2025**; current
third-party trackers for **Gemini 2.5 Flash free tier** (verify against the live docs):

- **RPM:** 10–15
- **TPM:** 250K–1M
- **RPD:** 250–1,500

The harness throttle is set to `rpm: 8` (`config/settings.yaml`), deliberately under the
~10 RPM cap. Per full run:

| Limit | Your usage | Binding? |
|---|---|---|
| **TPM** 250K | ~8 calls/min × 2,700 ≈ **22K TPM** | ❌ Nowhere near — tokens-per-minute is **not** the problem |
| **RPM** 10 | 8 (throttled) | 🟡 Managed by `_RpmThrottle` |
| **RPD** 250–1500 | **~120 calls/run** | ✅ **Ceiling** — only ~2 full runs/day if RPD=250 |
| **Wall clock** | 120 calls ÷ 8 RPM ≈ **~15 min/run** | ✅ Everyday pain |

On the **agent side (Groq)**, the 200K **TPD** was already exhausted mid-session during
testing (`199305/200000 used`; Known_Issues T0011.6 HIGH). A full live run is **also**
Groq-TPD-constrained, independent of the judge.

**Conclusion: the constraint is requests-per-day + run wall-time (+ Groq TPD), not
tokens-per-minute.** Trimming raw token usage won't unblock anything — cutting **call
count** and **thinking output** will.

## 4. Recommendation — ranked levers (none implemented)

Do **not** gut the metric suite; each seam earns its keep. In order of payoff:

1. **Cap / disable Gemini's thinking budget (biggest lever, zero metric loss).** The
   dominant cost and the cause of the earlier truncated-JSON 429s (Known_Issues T0011.6) is
   reasoning output. Set `thinking_budget=0` (or a small cap) on `ChatGoogleGenerativeAI`
   in `evals/judge.py`. Slashes output tokens ~5–10×, drops paid-equivalent to ~$0.10/run,
   and tends to **improve** JSON reliability. Spot-check 2–3 goldens first.

2. **Drop the one redundant seam-3 metric.** `FaithfulnessMetric` (~3 calls) and
   `GEval("Honesty")` (1 call) both check "the answer doesn't drift from
   `retrieval_context`." Keep **Honesty** (the honesty probes C1–C6 are built around it) and
   **drop Faithfulness** → removes ~40 calls/run (**~1/3 cut** in calls, run time, RPD
   pressure) for near-zero coverage loss.

3. **Pre-supply `evaluation_steps` to the GEvals instead of `criteria`.** Passing `criteria`
   makes GEval spend a call generating steps; fixed `evaluation_steps` skips that with **no
   scoring change** and makes runs deterministic. Also lets the hardcoded criteria move into
   `config/` (closes the Known_Issues T0011.3 LOW item).

4. **Consider `gemini-2.5-flash-lite` as judge** ($0.10/$0.40, non-thinking) — cheaper, no
   reasoning blowup, but a weaker judge. Only if (1) isn't enough; re-run the
   judge-agreement spot check before trusting it.

**Do NOT bother with:** trimming input context / `max_rows`. Input is ~15% of cost and TPM
is not the bottleneck.

**Net of 1+2+3:** ~120 calls / ~15 min / ~$0.50-equiv → roughly **~75 calls / ~9 min /
~$0.08-equiv per run**, ~doubling how many runs fit under RPD, losing no metric that
matters.

## Sources

- [Google Gemini API rate limits (official)](https://ai.google.dev/gemini-api/docs/rate-limits)
- [Gemini API pricing (official)](https://ai.google.dev/gemini-api/docs/pricing)
- [Gemini free-tier limits 2026 guide](https://www.aifreeapi.com/en/posts/gemini-api-free-tier-rate-limits)
- [Gemini 2.5 Flash pricing (pricepertoken)](https://pricepertoken.com/pricing-page/model/google-gemini-2.5-flash)
