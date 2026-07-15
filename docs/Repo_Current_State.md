## Current branch
`fix/sql-generation-reasoning-effort` - a narrow backend fix stacked on the **T0018.3 Editorial streaming chat UI** branch.

This branch is stacked on T0018.3 and keeps that UI work intact. It adds the surgical SQL-generation fix for the 2026-07-15 `[HIGH]` known issue: `generate_sql()` now builds only the hidden SQL-generation model with `reasoning_effort: "none"` from `agent.query.sql_generation_reasoning_effort`, while the main ReAct agent's default `build_model()` path remains unchanged.

- Do not rebase this branch onto `main` without an explicit maintainer decision. `main` has historically lagged the M12/M13/T0016 work; use the ticket branch topology recorded here and in `Tickets.md`.
- The M15 behavior work is not part of this branch unless explicitly merged later. Anything about `Agent_Behavior_Spec.md`, the scenario matrix, or `behavior_glossary` belongs to that parallel track.
- Everything for this branch's current work is in [`Tickets.md`](Tickets.md) → **T0018.3** and the T0018.3 manual checklist in [`Manual_Verification_Guide.md`](Manual_Verification_Guide.md).
- Older branch/roadmap snapshots (T0014 and earlier) are archived in [`archive/Repo_State_History.md`](archive/Repo_State_History.md).

## Completed milestones
One line per milestone. Per-ticket detail (files changed, test counts, follow-ups) lives in [`Completion_Reports.md`](Completion_Reports.md).

- **M0–M5** — Foundation → runnable request flow → ReAct runtime → self-hosted Langfuse → tracing integration → hardening.
- **M6** (T0006.1–.10) — First real SQL tool: read-only `query_clean_jobs` (schema → SQL gen → validate → execute → format), registered in the runtime, public API kept answer-only.
- **M7** (T0007.1–.4) — Short-term conversation memory: native Postgres checkpointer + async pool, `session_id → thread_id`, native `trim_messages` count cap.
- **M8** (T0008.1–.3) — Resumi persona, on-topic/honesty rules, SQL-generation hardening, schema context moved into `config/prompts.yaml`.
- **M9** (T0009.1–.11) — VietnamWorks data ingestion: `raw_jobs` landing + enriched `clean_jobs`, source-agnostic transform, idempotent loader; plus reset path, bounded query output (Groq `413` fix), and the `get_job_details` detail split.
- **M10** (T0010.1/.3/.4) — Pre-deploy hardening: typed error contract + graceful answer, true single-table SQL allowlist, off-event-loop LLM call; code-review bugs 3 & 4 fixed.
- **M11** (T0011.1–.6) — Model evaluation harness: DeepEval judge (Groq→Gemini) + RPM throttle, seeded fixture DB + versioned goldens, three-seam metric stack, Langfuse score writeback.
- **M12** (T0012.2–.10) — Hardening: qwen `<think>` leak fix, deepeval metric-template unblock, `trace_url` populated, graceful empty-answer fallback, non-str content coercion, eval-test marker hygiene, native-async `generate_sql`, cosmetic cleanup, eval judge cost/rate-limit reduction.
- **M13** (T0013.1–.5) — Schema Enrichment & v1 Freeze: `tech_stack` rebuilt against an external vocabulary (audit coverage 58% → 89%); `job_level`, `listing_expires_on`, and `created_on` exposed to the agent; the enriched **16-column** v1 contract recorded in [`Schema_Contract.md`](Schema_Contract.md) and enforced by prompt-freeze guards. **This is this branch's base (`51913f6`).**
- **M16** (T0016.1–.4) — Public-endpoint hardening: credential-less CORS, per-IP rate limit + friendly busy path, request length cap, explicit `/docs` exposure decision.
- **M17** (T0017.1–.2) — Streaming response delivery: runtime `astream` + no-leak filter, streaming service + `POST /api/v1/agent/chat/stream` SSE endpoint.

## In progress / next
**This branch = SQL-generation reasoning-effort fix complete, stacked on T0018.3.** T0016, T0017, T0018.1, T0018.2, and T0018.3 are complete underneath it:

- **T0016.1 - CORS middleware:** `config/settings.yaml` carries `api.cors`, and `src/api/app.py` registers credential-less `CORSMiddleware`.
- **T0016.2 - Rate limiting and friendly busy path:** `slowapi` is installed, `api.rate_limit` defaults to `"15/minute"`, chat is limited, health is not, and provider pressure maps to a public-safe busy response.
- **T0016.3 - Request input hardening:** `api.max_query_chars: 2000` is recorded in config, while `src/api/schemas.py` currently enforces the matching static `DEFAULT_MAX_QUERY_CHARS = 2000` Pydantic cap. If this value changes later, update both or introduce a deliberate config-backed schema loader.
- **T0016.4 - `/docs` exposure and headers decision:** `api.docs_enabled: true` keeps `/docs`, `/redoc`, and `/openapi.json` public for the portfolio demo; `api.docs_enabled: false` disables all three.
- **T0017.1 - Runtime streaming + no-leak filter:** `AgentRuntime.astream(...)` emits filtered token events plus trailing metadata without exposing tool internals.
- **T0017.2 - Streaming service + SSE endpoint:** `POST /api/v1/agent/chat/stream` emits the public `session` → `token`* → `metadata`/`error` → `done` contract.
- **T0018.1 - Go-live glue:** `generate_agent_response(...)` and `stream_agent_response(...)` mint UUID4 session ids when omitted; `config/settings.yaml` records `api.demo.data_snapshot_date`; `GET /api/v1/ready` runs `SELECT 1` outside the chat limiter and returns readiness plus the snapshot date.
- **T0018.2 - Same-origin static serving + frame protection:** `src/api/app.py` mounts `src/api/static/` at `/` after API/docs routes and injects `X-Frame-Options: DENY` with a pure-ASGI middleware.
- **T0018.3 - Editorial streaming chat UI:** `src/api/static/index.html` + `styles.css` + `app.js` replace the placeholder with the vanilla, Editorial-styled demo page (system serif stack, hairline rules, restrained vermilion accent, light theme only). It consumes `POST /api/v1/agent/chat/stream` via `fetch()` + a `ReadableStream` reader, renders tokens one-by-one, reads the disclaimer snapshot date from `GET /api/v1/ready`, ships 4 send-on-click honesty chips, pins the server session id and reuses it on later turns, shows a `view-trace` link only when `trace_url` is non-null, and degrades mid-stream `error` events to a friendly bubble and pre-stream 400/429 to a toast. No backend change.
- **SQL-generation reasoning-effort fix - Backend hotfix:** `AgentProvider.build_model()` has an optional per-call `reasoning_effort` override. `query_clean_jobs.generate_sql()` reads `agent.query.sql_generation_reasoning_effort: "none"` and applies it only to the mechanical SQL-generation call, preventing qwen hidden-reasoning token exhaustion without disabling the main agent's reasoning.

**Status (2026-07-15):** T0016.1–T0016.4, T0017.1–T0017.2, T0018.1, T0018.2, T0018.3, and the SQL-generation reasoning-effort hotfix are complete on this stack. Open issues live in [`Known_Issues.md`](Known_Issues.md); resolved/background items in [`Resolved_Issues.md`](Resolved_Issues.md).

**Milestone map (see `Tickets.md`):** T0013 freeze → T0016 security posture → T0017 streaming response delivery → T0018 clickable demo UI + go-live.

**Next recommended ticket:** **T0018.4** Deploy topology + first public deploy.

## Current folder structure
```text
.
|-- config/
|   |-- ingestion.yaml
|   |-- prompts.yaml
|   `-- settings.yaml
|-- docker-compose.yml
|-- docker/
|   `-- Dockerfile
|-- infra/
|   |-- docker-compose.yaml
|   `-- langfuse/
|       `-- README.md
|-- scripts/
|   |-- eval_judge_spike.py
|   |-- init_db.sql
|   `-- reset_db.sql
|-- evals/
|   |-- __init__.py
|   |-- conftest.py
|   |-- harness.py
|   |-- judge.py
|   |-- writeback.py
|   |-- test_judge_scaffold.py
|   |-- test_judge.py
|   |-- test_goldens_load.py
|   |-- test_three_seams.py
|   |-- test_writeback.py
|   |-- fixtures/
|   |   |-- __init__.py
|   |   |-- loader.py
|   |   |-- seed_eval_db.sql
|   |   `-- test_fixture_counts.py
|   `-- goldens/
|       |-- __init__.py
|       `-- golden_dataset.json
|-- docs/
|-- src/
|   |-- agents/
|   |   |-- runtime/
|   |   |   |-- factory.py
|   |   |   |-- middleware.py
|   |   |   |-- prompts.py
|   |   |   |-- provider.py
|   |   |   `-- react_agent.py
|   |   |-- tools/
|   |   |   |-- get_job_details.py
|   |   |   |-- query_clean_jobs.py
|   |   |   `-- time.py
|   |   |-- tracing/
|   |   `-- service.py
|   |-- api/
|   |   |-- routes/
|   |   `-- static/
|   |       |-- index.html
|   |       |-- styles.css
|   |       `-- app.js
|   |-- core/
|   |   |-- checkpointer.py
|   |   |-- config.py
|   |   |-- db.py
|   |   |-- errors.py
|   |   `-- logger.py
|   `-- services/
|       |-- ingestion/
|       |   |-- __init__.py
|       |   |-- models.py
|       |   |-- raw_store.py
|       |   |-- clean_store.py
|       |   |-- loader.py
|       |   |-- transform.py
|       |   |-- normalize/
|       |   |   |-- __init__.py
|       |   |   `-- vietnamworks.py
|       |   `-- sources/
|       |       |-- __init__.py
|       |       |-- base.py
|       |       `-- vietnamworks.py
|       `-- query/
|           |-- executor.py
|           |-- job_details.py
|           |-- models.py
|           |-- sql_validator.py
|           `-- table_formatter.py
|-- tests/
|   |-- core/
|   |-- agents/
|   |   |-- runtime/
|   |   `-- tools/
|   |-- api/
|   |   `-- test_static_serving.py
|   `-- services/
|       `-- query/
|-- pyproject.toml
|-- uv.lock
|-- README.md
|-- AGENTS.md
`-- .env
```

Notes on the reorg (commit `182aac0`): the Langfuse Docker stack moved from `docker/docker-compose.yaml` to `infra/docker-compose.yaml` (with a companion `infra/langfuse/README.md`), and the app-only Postgres compose file lives at the repo root (`docker-compose.yml`) on port `5433` to avoid colliding with the Langfuse stack's own Postgres.

## Installed dependencies
Runtime dependencies declared in `pyproject.toml`:
- `fastapi>=0.136.3`
- `langchain>=1.3.1`
- `langchain-groq>=1.1.2`
- `langfuse>=4.6.1`
- `pydantic-settings>=2.14.1`
- `psycopg[binary,pool]>=3.2`
- `sqlalchemy>=2.0`
- `structlog>=25.5.0`
- `uvicorn>=0.48.0`
- `langgraph-checkpoint-postgres>=2.0`
- `cloudscraper>=1.2.71`
- `beautifulsoup4>=4.15.0`
- `lxml>=6.1.1`
- `httpx>=0.27`
- `slowapi>=0.1.10` (T0016.2 - in-process per-IP rate limiting for the public chat endpoint)
- `langchain-google-genai>=4.2.6` (T0011.6 — eval judge only; the request path never uses it)

Dev/test dependencies declared in `pyproject.toml` under `[dependency-groups] dev`:
- `pytest>=9.1.1`
- `pytest-asyncio>=1.4.0`
- `pytest-mock>=3.15.1`
- `ruff>=0.15.20`
- `mypy>=2.1.0`
- `deepeval>=4.0.7` (T0011.1 — eval/judge tooling only, not in the prod runtime image)

`anyio` and `langsmith` are transitive (pulled in by `fastapi`/`langchain`), not declared directly.

## Available scripts
No package scripts or `tool.*.scripts` entries are defined in `pyproject.toml`.

Practical commands from the repository layout:
- `uv run uvicorn src.api.app:app --reload`
- `uv run pytest` (T0012.7: the standard suite excludes the `eval`-marked live tests by default — `addopts = "-m 'not eval' --strict-markers"` in `pyproject.toml`)
- `uv run pytest -m eval` (runs only the two live-API eval files, `evals/test_judge_scaffold.py` + `evals/test_three_seams.py`, 18 tests total; needs Groq/judge creds + fixture DB)
- `PYTHONUTF8=1 uv run deepeval test run evals/test_three_seams.py -m eval` (the verified working `deepeval` invocation — `-m eval` must be passed through explicitly or 0 tests are selected; see `Known_Issues.md`)
- `uv run ruff check .` (lint; config in `pyproject.toml` `[tool.ruff]`, `scripts/` spikes excluded)
- `uv run mypy` (type check `src`; config in `pyproject.toml` `[tool.mypy]`, pydantic plugin enabled)
- `python -m evals.fixtures.loader` (builds/refreshes the `internhunter_eval` fixture DB from scratch, prints `COUNT(*)`, T0011.2)
- `python -c "from evals.fixtures.loader import reset_fixture; reset_fixture()"` (drops + rebuilds the fixture tables)
- `docker compose up -d` (root `docker-compose.yml`: Postgres + API, port `5433` host-side)
- `docker compose exec -T postgres psql -U internhunter -d internhunter -f scripts/init_db.sql` (routine, non-destructive schema init/no-op)
- `docker compose exec -T postgres psql -U internhunter -d internhunter -f scripts/reset_db.sql` (destructive — drops and recreates both tables; use only when the schema shape changes, then re-ingest)
- `docker compose -f infra/docker-compose.yaml up --build` (Langfuse observability stack)

## Build/test status
Current-branch (T0018.3 + SQL-generation reasoning-effort hotfix) results only. Earlier per-ticket logs (T0011–T0018.2) are archived in [`archive/Repo_State_History.md`](archive/Repo_State_History.md).

- `uv run pytest tests/agents/runtime/test_provider.py tests/agents/tools/test_query_clean_jobs.py -q` (SQL-generation reasoning-effort hotfix) → `15 passed`.
- `uv run pytest tests/api/test_static_serving.py -q` (static-serving regression — the UI keeps the `InternHunter` string this test asserts on `GET /`) → `4 passed`.
- `uv run pytest tests/api -q` (API route suite — the UI is static assets only; backend untouched) → `33 passed`.
- `uv run pytest -q` (full standard suite) → `296 passed, 19 deselected, 4 subtests passed` in ~7s.
- Render check: served `src/api/static/` standalone and loaded `index.html` in a headless browser at 960px and 390px widths — Editorial masthead/chips/composer render, the vermilion editor's-rule marks agent answers, the streaming cursor and `view-trace` link render from injected turns, and the dateline degrades to the dateless sentence when `/api/v1/ready` is unavailable (no `undefined`, no crash).

## Known issues
Open known issues, risks, and out-of-scope follow-ups live in their own living register:
see [`Known_Issues.md`](Known_Issues.md). Append there when a ticket uncovers a new one.
Resolved items are archived in [`Resolved_Issues.md`](Resolved_Issues.md). A full per-module
logic review (2026-07-02) — bugs, improvement backlog, and doc insights — is captured in
[`Code_Review_Notes.md`](Code_Review_Notes.md); its bugs are logged in `Known_Issues.md`
(open) / `Resolved_Issues.md` (closed).

## Next recommended ticket
**T0018.4 Deploy topology + first public deploy** (confirm Render + Neon + Langfuse Cloud Hobby, inject secrets via env vars, first deploy of the same-origin app + DB + tracing). T0011.5 baseline calibration remains open separately when maintainer credentials are available.
