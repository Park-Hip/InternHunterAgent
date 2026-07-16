# Completion Reports

Per-ticket outcome records (`CLAUDE.md §5`). Append-only: each entry captures what changed,
files touched, test results, and follow-ups for one ticket. This is the durable record;
`Repo_Current_State.md` holds only the milestone-level snapshot and links here.

Entries are kept to the durable summary — full implementation detail lives in the code and
git. **Older milestones (M0–M14) are archived** in
[`archive/Completion_Reports_Archive.md`](archive/Completion_Reports_Archive.md); this file
holds the current deploy-era stack (M16+).

## Entry format
One entry per ticket: **Did** (what changed) · **Files** (key paths) · **Tests** (result) ·
**Follow-up** (where it went). Longer standalone entries may use the full `CLAUDE.md §5`
field list (Summary / Files / Commands / Build & test / Manual verification / Risks /
Follow-ups / Docs).

---

## Milestone 16 — Security Posture (Public-Endpoint Hardening)
- **T0016.1 — CORS middleware (config-driven, credential-less).**
  - **Did:** added an `api.cors` block to `config/settings.yaml` (credential-less defaults: empty `allowed_origins`, `allow_credentials: false`, methods `GET/POST/OPTIONS`); `src/api/app.py` registers `CORSMiddleware` before router includes; added `create_app(...)` so focused tests build a CORS app without opening the lifespan/runtime/DB.
  - **Files:** `config/settings.yaml`, `src/api/app.py`, `tests/api/test_cors.py`.
  - **Tests:** `tests/api/test_cors.py tests/api/test_query.py tests/api/test_startup_config.py` pass (allowed preflight returns CORS headers, disallowed omits them).
  - **Follow-up:** the deployed UI origin is still intentionally unset — fill it into `config/settings.yaml` when the demo host is known.
  - **Correction (2026-07-13):** no `T0016.5 Langfuse secrets hygiene` ticket exists; superseded when deploy moved to Langfuse Cloud Hobby and T0016 was scoped to CORS / rate-limit / input-cap / `/docs`.

- **T0016.2 — Per-IP rate limiting + graceful 429/quota degradation.**
  - **Did:** added `slowapi` + `api.rate_limit: "15/minute"`; `app.py` builds a per-app `Limiter(key_func=get_remote_address)` + friendly `RateLimitExceeded` handler, applied only to `POST /api/v1/agent/chat` (health not decorated). `errors.py` adds `ProviderBusyError` + `BUSY_MESSAGE` + a 429/quota/timeout classifier; `service.py` translates provider pressure to a friendly busy response, preserving the generic 500 for real bugs.
  - **Files:** `pyproject.toml`/`uv.lock`, `config/settings.yaml`, `src/api/app.py`, `src/core/errors.py`, `src/agents/service.py`, `src/api/routes/query.py`, `tests/api/test_rate_limit.py`, `tests/api/test_query.py`.
  - **Tests:** `16 passed` (focused API suite).
  - **Follow-up:** live provider-quota behavior not exercised — confirm the classifier with credentials when available.

- **T0016.3 — Request input hardening (length cap).**
  - **Did:** `api.max_query_chars: 2000` in config + matching static `DEFAULT_MAX_QUERY_CHARS = 2000` `Field(max_length=...)` on `QueryRequest.query`. Oversized bodies fail with HTTP 422 before the route runs (not logged, service not awaited); blank input keeps the existing 400 path.
  - **Files:** `config/settings.yaml`, `src/api/schemas.py`, `tests/api/test_query.py`.
  - **Tests:** `18 passed`; ruff clean.
  - **Follow-up:** the cap is static in code and mirrored in config — if the value changes later, update both or add a validated config loader.

- **T0016.4 — `/docs` exposure decision + minimal security headers.**
  - **Did:** `api.docs_enabled: true` makes Swagger/ReDoc/OpenAPI an explicit config choice; `app.py` wires `docs_url`/`redoc_url`/`openapi_url` together (all three removed when disabled), flippable via `create_app(docs_enabled=...)`. No security-header middleware added by design (still API-only until a same-origin HTML UI is served).
  - **Files:** `config/settings.yaml`, `src/api/app.py`, `tests/api/test_docs_exposure.py`.
  - **Tests:** focused API suite passes (enabled→200, disabled→404 for all three).
  - **Follow-up:** when FastAPI later serves an HTML UI, add frame-protection headers in that ticket (done in T0018.2).

## Milestone 17 — Streaming Response Delivery
- **T0017.1 — Runtime streaming + no-leak filter.**
  - **Did:** added `AgentRuntime.astream(...)` beside `ainvoke` using the stable `agent.astream(..., stream_mode="messages")` surface; emits transport-agnostic `token` dicts then one trailing `metadata` dict after Langfuse flush. Two-gate no-leak filter: only `langgraph_node == "model"` survives, and chunks with empty/non-string content or any `tool_call_chunks` are dropped. Enabled `agent.groq.streaming: true` + a system-prompt line to not narrate before tool calls.
  - **Files:** `src/agents/runtime/react_agent.py`, `config/settings.yaml`, `config/prompts.yaml`, `tests/agents/runtime/test_react_agent.py`, `research/streaming-implementation-plan.md`.
  - **Tests:** `9` focused stream tests pass; full suite `273 passed, 7 skipped, 19 deselected`.
  - **Follow-up:** live tool-using stream probe BLOCKED (no Groq creds / DB in sandbox) → `Known_Issues.md`.

- **T0017.2 — Streaming service + SSE endpoint.**
  - **Did:** `stream_agent_response(...)` in `service.py` — transport-agnostic async generator emitting `session` → `token`* → (`metadata` held until after the empty-answer fallback decision) / in-band `error` (carrying `BUSY_MESSAGE`, no `str(exc)` leak) → terminal `done`. `POST /api/v1/agent/chat/stream` reuses the chat limiter, keeps the pre-stream blank-query 400, and returns `EventSourceResponse` with explicit `json.dumps` framing + anti-buffering headers (`Cache-Control: no-cache`, `X-Accel-Buffering: no`). Verified FastAPI 0.136.3's `ServerSentEvent` isn't auto-encoded, hence the explicit framing.
  - **Files:** `src/agents/service.py`, `src/api/routes/query.py`, `src/api/schemas.py`, `tests/api/test_stream.py`.
  - **Tests:** `test_stream.py` `4 passed`; API suite `24 passed`; full suite `277 passed, 7 skipped, 19 deselected`.
  - **Follow-up:** live `curl -N` check BLOCKED (needs Groq creds + seeded Postgres) → `Known_Issues.md`.

## Milestone 18 — Clickable Demo (UI + go-live)
- **T0018.1 — Go-live glue: server session IDs, data disclaimer, DB readiness probe.**
  - **Did:** UUID4 session ids minted when omitted in both one-shot and streaming paths (client ids kept as advisory); `api.demo.data_snapshot_date: "2026-07-14"` as the disclaimer source of truth; `GET /api/v1/ready` runs `session_factory()` + `text("SELECT 1")` and returns readiness + snapshot date (or 503), included outside the chat limiter so probes aren't rate-limited; fixed the `/health` `async def` typo.
  - **Files:** `config/settings.yaml`, `src/api/routes/health.py`, `src/api/schemas.py`, `tests/api/test_ready.py`, `tests/agents/test_service.py`, `tests/api/test_stream.py`.
  - **Tests:** focused `11 passed`; API suite `29 passed`; full suite `282 passed, 7 skipped, 19 deselected`; ruff clean.
  - **Follow-up:** `data_snapshot_date` must be updated whenever the demo corpus changes; live `/ready` against a running Postgres not exercised in-sandbox.

- **T0018.2 — Same-origin static serving + frame protection.**
  - **Did:** `create_app()` registers a pure-ASGI frame guard injecting `X-Frame-Options: DENY`, includes API/docs routes first, then mounts `StaticFiles(directory=src/api/static, html=True)` at `/`. The root page is a deliberately minimal placeholder (no CSS/JS/UI behavior yet).
  - **Files:** `src/api/app.py`, `src/api/static/` (placeholder), `tests/api/test_static_serving.py`.
  - **Tests:** `test_static_serving.py` `4 passed`; `test_stream.py` `5 passed`; API suite `33 passed`; full suite `286 passed, 7 skipped, 19 deselected`.
  - **Follow-up:** none.
  - *(Backfilled from `Repo_Current_State` during the 2026-07-15 docs-hygiene pass — this ticket originally had no completion entry.)*

- **T0018.3 — Editorial streaming chat UI (vanilla).**
  - **Did:** three static assets — `index.html` + `styles.css` + `app.js` — replace the placeholder with the vanilla Editorial demo page (system serif stack, hairline rules, restrained vermilion accent, light theme; no build step, no framework, no new dependency, CSP-clean). Consumes `POST /api/v1/agent/chat/stream` via `fetch()` + a `ReadableStream` reader + a ~30-line in-app SSE parser dispatching `session`/`token`/`metadata`/`error`/`done` (stops on `done`, no reconnect). Reads the disclaimer date from `GET /api/v1/ready`; ships 4 send-on-click honesty chips; pins + reuses the server session id; shows `view-trace` only when `trace_url` is non-null; degrades mid-stream `error` to a friendly bubble and pre-stream 400/429 to a toast. Preserves the `InternHunter` string `test_static_serving` asserts. No backend change.
  - **Files:** `src/api/static/index.html`, `src/api/static/styles.css`, `src/api/static/app.js`.
  - **Tests:** `test_static_serving.py` `4 passed`; API suite `33 passed`; full suite `286 passed, 7 skipped, 19 deselected`. Rendered + screenshot-verified at 960px and 390px; the mid-stream `error` path is code-inspection-only.
  - **Follow-up:** mid-stream `error` bubble, SSE-parser assumptions, and no idle-timeout → `Known_Issues.md` § Demo UI (T0018.3).
  - *(Backfilled from `Repo_Current_State` during the 2026-07-15 docs-hygiene pass — this ticket originally had no completion entry.)*

## Backend hotfix — SQL-generation reasoning effort
- **Summary:** disabled qwen reasoning only for the hidden SQL-generation model build. `AgentProvider.build_model()` now accepts an optional per-call `reasoning_effort` kwarg (omitted by default, so the main ReAct agent path is unchanged); `query_clean_jobs.generate_sql()` reads `agent.query.sql_generation_reasoning_effort` and passes `"none"` only to the mechanical SQL-generation call. Fixes the `[HIGH]` empty-SQL-on-reasoning-heavy-queries issue.
- **Files:** `src/agents/runtime/provider.py`, `src/agents/tools/query_clean_jobs.py`, `config/settings.yaml`, `tests/agents/runtime/test_provider.py`, `tests/agents/tools/test_query_clean_jobs.py`, plus `docs/Known_Issues.md`, `docs/Resolved_Issues.md`, `docs/Repo_Current_State.md`.
- **Build & test:** focused provider/tool suite `15 passed`; ruff clean; full standard suite `296 passed, 19 deselected, 4 subtests passed`.
- **Manual verification:** live Groq SQL probe, streaming curl, and DeepEval regression BLOCKED (no `GROQ_API_KEY`/`GOOGLE_API_KEY` in sandbox; local Postgres `127.0.0.1:5433` was reachable) → `Known_Issues.md`.
- **Risks:** covered offline at the construction boundary; live provider behavior still needs maintainer credentials.
- **Follow-ups:** salary-sort SQL may need single-currency prompt tuning if it appears in evals; maintainer live verification remains blocked on credentials.

## Backend hotfix — Split ReAct-agent and SQL-generation LLM configs
- **Summary:** replaced the shared `agent.groq` model profile plus per-call `reasoning_effort` override with two explicit profiles: `agent.react` for the outer ReAct agent and `agent.sql_generation` for the nested SQL-generation LLM call. Both profiles expose the same fields; only `agent.sql_generation.reasoning_effort: none` is forwarded for SQL generation.
- **Files:** `config/settings.yaml`, `src/agents/runtime/provider.py`, `src/agents/runtime/factory.py`, `src/agents/tools/query_clean_jobs.py`, `tests/agents/runtime/test_provider.py`, `tests/agents/tools/test_query_clean_jobs.py`, plus `docs/Repo_Current_State.md`, `docs/Known_Issues.md`, `docs/MVP_Technical_Design.md`, `docs/Completion_Reports.md`, `docs/Manual_Verification_Guide.md`.
- **Commands:** `uv run pytest tests/agents/runtime/test_provider.py tests/agents/tools/test_query_clean_jobs.py -q`; `uv run pytest -q`.
- **Build & test:** focused provider/tool suite `16 passed`; full standard suite `297 passed, 19 deselected, 4 subtests passed`.
- **Manual verification:** confirm config has independent `agent.react` and `agent.sql_generation` blocks; confirm `agent_factory()` uses `build_model("react")`; confirm `query_clean_jobs.generate_sql()` uses `build_model("sql_generation")`; with maintainer credentials and seeded DB, run `generate_sql("List the AI Engineer jobs that require Python, sorted by salary descending.")`.
- **Risks:** live Groq behavior still requires maintainer credentials; no prompt, schema, eval fixture, API, or UI changes were made for this split.
- **Follow-ups:** none from the config split itself; existing salary-sort prompt-adherence and maintainer live-verification notes remain tracked in `Known_Issues.md`.

## T0015.5 — ReAct reasoning-effort A/B runner
- **Summary:** added config-declared `baseline`, `low`, and `none` ReAct arms; extended the scenario runner with explicit arm validation and independent output/checkpoint paths; preserved scenario ordering, resume behavior, and the SQL-generation profile.
- **Files:** `config/settings.yaml`, `scripts/run_scenario_matrix.py`, `evals/test_reasoning_ab_runner.py`, `evals/reasoning_ab_results.md`, `docs/Manual_Verification_Guide.md`, `docs/Repo_Current_State.md`, `docs/Known_Issues.md`, `docs/Completion_Reports.md`.
- **Commands:** `uv run pytest evals/test_reasoning_ab_runner.py evals/test_scenarios_v1_load.py -q`; `uv run pytest tests/agents/runtime/test_provider.py tests/agents/runtime/test_prompts.py -q`; `uv run python scripts/run_scenario_matrix.py --template`.
- **Build & test:** focused runner/scenario tests `5 passed`; provider/prompt tests `15 passed`; template generation passed after the frozen-v1 compatibility fallback. Live correction and resume: `.env` credentials resolved, project Postgres was healthy on port `5433`, fixture loader confirmed `COUNT(*) = 22`, then baseline preflight returned HTTP 503 `provider_busy` twice; low and none were not started. No manual export was required.
- **Manual verification:** run the three 16-ID commands in `Manual_Verification_Guide.md` with `--out` paths, verify exact IDs/repeat counts and frozen baseline immutability, then grade and populate `evals/reasoning_ab_results.md`.
- **Risks:** live arm winner and token/turn observations are blocked by Groq provider pressure; `M-G44` is a required regression-watch spot-check outside the 16-ID rerun set. See `Known_Issues.md`.
- **Follow-ups:** T0015.6 provider A/B and T0015.7 prompt/few-shot tuning must use the measured recommendation; do not infer a winner from offline tests.
- **Docs:** `Repo_Current_State.md`, `Manual_Verification_Guide.md`, `Known_Issues.md`, and `evals/reasoning_ab_results.md` contain the current status and runbook.

## T0015.6 — Provider A/B: qwen/Groq vs Gemini/Google
- **Summary:** Added a narrow profile-level provider switch in `AgentProvider`; Gemini construction uses `ChatGoogleGenerativeAI`, `GOOGLE_API_KEY`, configured model settings, and `thinking_budget: 0`. Groq behavior and the isolated SQL-generation profile remain available.
- **Files:** `src/agents/runtime/provider.py`, `config/settings.yaml`, `tests/agents/runtime/test_provider.py`, `evals/provider_ab_results.md`, `docs/Manual_Verification_Guide.md`, `docs/Known_Issues.md`, `docs/Repo_Current_State.md`, `docs/Completion_Reports.md`.
- **Commands:** `uv run pytest tests/agents/runtime/test_provider.py evals/test_judge.py -q`; prerequisite checks for environment variables, fixture loader, and `localhost:5433`.
- **Build & test:** focused provider/judge tests passed: `8 passed`. Full suite and live matrix remain pending until the project Postgres service is started.
- **Gemini live smoke / 29-scenario comparison:** not run; blocked because the project `postgres` service from `docker-compose.yml` was not started and `localhost:5433` was unavailable. The repo `.env` contains `GROQ_API_KEY` and `DATABASE_URL`, loaded automatically by `src/core/config.py`; no manual export is required. No observed Gemini artifact or fabricated result was added.
- **Manual verification:** use the T0015.6 checklist in `Manual_Verification_Guide.md`, including readiness, one clean Gemini turn, judge isolation, separate checkpoint, and frozen qwen artifact immutability.
- **Token, latency, quota:** unavailable. Current Google limits are account-specific; record AI Studio values before the live run.
- **Provider recommendation:** no lock recommendation yet; complete T0015.5 live arms and T0015.6 live comparison before T0015.7.
- **Risks / follow-ups:** live provider winner, quota headroom, and answer-quality comparison are blocked. Follow-up is T0015.7 prompt/few-shot tuning after the winner is measured.
- **Docs needing updates:** replace the pending sections in `evals/provider_ab_results.md`, `docs/Known_Issues.md`, and `docs/Repo_Current_State.md` after live verification.
