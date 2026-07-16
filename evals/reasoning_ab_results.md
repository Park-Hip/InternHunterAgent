# T0015.5 ReAct reasoning-effort A/B results

> **Status: BLOCKED for today on Groq's daily token quota (TPD).** No `none`-arm scenario data was collected — the run never got past preflight. Stopping here rather than continuing to cycle retries; resume in a future session (see "Resume instructions" below). **Baseline is not re-collected live** — see rationale below; that part of the plan still holds for the resumed attempt.
>
> **Two blockers hit and resolved** (these fixes carry forward, no need to redo):
> 1. Earlier HTTP 503 `provider_busy` was misdiagnosed — root cause was `LANGFUSE_BASE_URL=http://host.docker.internal:3000` unresolvable from a bare-metal (non-Docker) API process, so `client.get_trace_url()` timed out *after* a successful agent answer and got misclassified as provider pressure. Fix: run the API with `LANGFUSE_BASE_URL=http://localhost:3000` instead (or start the full `docker compose -f infra/docker-compose.yaml up` stack and use the container network, where `host.docker.internal` resolves normally).
> 2. A brief baseline live attempt (abandoned per the reuse-T0015.4-data plan) hit a genuine `groq.RateLimitError` on **daily** tokens (TPD, not TPM): `Limit 200000, Used 199893, Requested 2148`. This confirmed TPD is a continuously-refilling bucket (~2.3 tokens/sec matching the stated reset ETAs), not a fixed once-a-day reset.
>
> **Why this session couldn't push through:** four retry cycles (immediate, 11min, 11min, 25min waits) all still hit TPD 429s on the `none` arm's preflight call. Diagnosis: this session's *cumulative* Groq usage today — the original T0015.4 matrix, the abandoned baseline live attempt, and (avoidably) several of my own ad-hoc diagnostic probe calls while investigating the 429s — left the daily budget deep enough in deficit that the ~2.3 tokens/sec refill couldn't clear it within this session's timeframe. A full real agent turn needs ~1,400-1,500 tokens (agent call + nested SQL-generation call), and headroom never recovered that far even after 25 minutes untouched. Lesson for next attempt: **do not probe Groq directly to "check quota"** — each check itself consumes budget and delays recovery; only the runner's own preflight should touch the API.
>
> **Resume instructions:** confirm current headroom with exactly one small probe (`max_tokens=5`) before attempting the real run; if a tiny call succeeds but the real preflight still 429s, wait without further calls rather than re-probing. Ideally resume after a fresh daily quota window (a new day) for a clean shot, since a same-day resume inherits whatever deficit remains from today.

- Run date: 2026-07-16 (UTC)
- Prompt version: `v1` (the frozen T0015.4 prompt; no prompt text changed)
- Scope: 16 T0015.4 failing IDs only; 9 probe scenarios at 3 runs and 7 non-probes at 2 runs.
- Baseline source: `evals/v1_scenario_matrix.md` (T0015.4, commit `eba3e1f`) — not re-collected.
- Live prerequisite check (2026-07-16): the repo `.env` contains the Groq credential and `DATABASE_URL`; project Postgres healthy on port `5433`; fixture loader confirmed `COUNT(*) = 22`.

## Arm configuration

**Only two arms exist.** Verified live against Groq: `qwen/qwen3.6-27b` only accepts `reasoning_effort` values `none` or `default` — `low`/`medium`/`high` are for the `openai/gpt-oss-*` model family, not qwen3. A live probe against Groq confirmed `reasoning_effort="low"` returns `400 BadRequestError: reasoning_effort must be one of none or default`, so the originally-planned `low` arm was dropped from `config/settings.yaml`'s `eval.reasoning_ab` and from the runner's `--arm` choices.

| Arm | `agent.react.reasoning_effort` | Model | Temperature | Max tokens | SQL-generation effort | Source |
|---|---|---|---:|---:|---|---|
| Baseline | `default` (identical behavior to T0015.4's `null`) | `qwen/qwen3.6-27b` | 0.2 | 2048 | `none` (unchanged) | **Reused from T0015.4** (`eba3e1f`), not re-run |
| None | `none` | `qwen/qwen3.6-27b` | 0.2 | 2048 | `none` (unchanged) | Live, this ticket |

Before the live `none` run, `agent.react.reasoning_effort` was set to `none` in `config/settings.yaml` and the API restarted. The runner validates that the selected `--arm` matches the loaded configuration.

## Per-arm comparison

| Arm | Passing scenarios / 16 | Empty-answer failures | Observed tokens / turn | Status |
|---|---:|---:|---:|---|
| Baseline | 0/16 (all 16 are T0015.4's failing set by definition) | 8 instances across 6 IDs: B1 r2, C2 r1/r2, M-G03 r1/r2, M-D4 r3, M-D7 r1, M-D8 r2 (all literal `"I couldn't produce an answer for that — please try rephrasing."`, per `evals/v1_scenario_matrix.md`) | unavailable (not re-collected; see `evals/v1_scenario_matrix.md`) | reused from T0015.4 |
| None | pending | pending | unavailable until Langfuse/run logs are captured | blocked — daily quota exhausted, 0/16 collected, no scenario reached |

## Per-ID comparison

| ID | Required runs | Baseline (T0015.4, reused) | None (live) |
|---|---:|---|---|
| B1 | 2 | 1/2 FAIL | pending |
| C1 | 3 | 0/3 FAIL | pending |
| C2 | 3 | 0/3 FAIL | pending |
| C3 | 3 | 0/3 FAIL | pending |
| C4 | 3 | 2/3 FAIL | pending |
| C5 | 3 | 2/3 FAIL | pending |
| C6 | 2 | 0/2 FAIL | pending |
| C7 | 3 | 2/3 FAIL | pending |
| M-G03 | 2 | 0/2 FAIL | pending |
| M-G10 | 3 | 2/3 FAIL | pending |
| M-G29 | 3 | 0/3 FAIL | pending |
| M-D2 | 2 | 0/2 FAIL | pending |
| M-D4 | 3 | 2/3 FAIL | pending |
| M-D7 | 2 | 0/2 FAIL | pending |
| M-D8 | 2 | 0/2 FAIL | pending |
| M-D9 | 2 | 0/2 FAIL | pending |

## Token and regression notes

Token observations for the `none` arm must come from Langfuse traces or the run log; recorded as unavailable rather than estimated until captured. Regression-watch rows are `M-G44` (false-premise correction), `B1` (multi-turn accumulation), and `M-G03` (compound request); `M-G44` is outside the 16-ID rerun set (it passed in T0015.4) and gets a cheap live spot-check under `none` to confirm reasoning-off doesn't regress a currently-passing scenario.

## Recommendation

Do not lock an arm for T0015.6 or T0015.7 until the `none` arm and the `M-G44` regression spot-check have been completed and compared against the T0015.4 baseline verdicts above.
