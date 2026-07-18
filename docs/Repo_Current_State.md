## Current branch
`feature/t0019.3-accumulate-lifecycle` — **T0019.3 Accumulate load semantics + hidden lifecycle columns.** Branched off `feature/t0019.2-alembic-baseline`, which was branched off `feature/t0019.1-robots-tos-gate`, which was branched off `feature/t0018.4-deploy`, which remains the deployed branch — **LIVE: https://internhunteragent.onrender.com** (verified end-to-end 2026-07-16). Note `main` is stale at T0009; branch off `feature/t0018.4-deploy` (or its ticket-branch descendants), not `main`.

Built clean off `e4076b2` (the kept ReAct/SQL-generation config split) with the T0018.3 Editorial UI committed as `7d4cfef`, then deployed: API on **Render** (Docker, Singapore, Free), Postgres on **Neon** (PG17, static 50-row snapshot), tracing on **Langfuse Cloud Hobby (JP)**. Secrets are Render env vars; `api.cors.allowed_origins` stays `[]` (same-origin). Full record in [`Completion_Reports.md`](Completion_Reports.md) → T0018.4, and the confirmed topology in `research/deployment-research-plan.md` §12. The dumped T0015.6/.7 provider-A/B phase is parked recoverably at `45d333c` on `feature/t0015.6-provider-ab`.

- Do not rebase this branch onto `main` without an explicit maintainer decision. `main` has historically lagged the M12/M13/T0016 work; use the ticket branch topology recorded here and in `Tickets.md`.
- The M15 behavior work is not part of this branch unless explicitly merged later. Anything about `Agent_Behavior_Spec.md`, the scenario matrix, or `behavior_glossary` belongs to that parallel track.
- Everything for this branch's current work is in [`Tickets.md`](Tickets.md) → **T0018.4** and the T0018.4 manual checklist in [`Manual_Verification_Guide.md`](Manual_Verification_Guide.md).
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
**Nothing in progress — T0018 closed 2026-07-16 with the first public deploy.** This branch carries the full T0016 → T0018 stack (security posture → streaming → clickable demo), plus the SQL-generation reasoning-effort hotfix and the ReAct/SQL-generation config split, and it is deployed:

- **T0016.1 - CORS middleware:** `config/settings.yaml` carries `api.cors`, and `src/api/app.py` registers credential-less `CORSMiddleware`.
- **T0016.2 - Rate limiting and friendly busy path:** `slowapi` is installed, `api.rate_limit` defaults to `"15/minute"`, chat is limited, health is not, and provider pressure maps to a public-safe busy response.
- **T0016.3 - Request input hardening:** `api.max_query_chars: 2000` is recorded in config, while `src/api/schemas.py` currently enforces the matching static `DEFAULT_MAX_QUERY_CHARS = 2000` Pydantic cap. If this value changes later, update both or introduce a deliberate config-backed schema loader.
- **T0016.4 - `/docs` exposure and headers decision:** `api.docs_enabled: true` keeps `/docs`, `/redoc`, and `/openapi.json` public for the portfolio demo; `api.docs_enabled: false` disables all three.
- **T0017.1 - Runtime streaming + no-leak filter:** `AgentRuntime.astream(...)` emits filtered token events plus trailing metadata without exposing tool internals.
- **T0017.2 - Streaming service + SSE endpoint:** `POST /api/v1/agent/chat/stream` emits the public `session` → `token`* → `metadata`/`error` → `done` contract.
- **T0018.1 - Go-live glue:** `generate_agent_response(...)` and `stream_agent_response(...)` mint UUID4 session ids when omitted; `config/settings.yaml` records `api.demo.data_snapshot_date`; `GET /api/v1/ready` runs `SELECT 1` outside the chat limiter and returns readiness plus the snapshot date.
- **T0018.2 - Same-origin static serving + frame protection:** `src/api/app.py` mounts `src/api/static/` at `/` after API/docs routes and injects `X-Frame-Options: DENY` with a pure-ASGI middleware.
- **T0018.3 - Editorial streaming chat UI:** `src/api/static/index.html` + `styles.css` + `app.js` replace the placeholder with the vanilla, Editorial-styled demo page (system serif stack, hairline rules, restrained vermilion accent, light theme only). It consumes `POST /api/v1/agent/chat/stream` via `fetch()` + a `ReadableStream` reader, renders tokens one-by-one, reads the disclaimer snapshot date from `GET /api/v1/ready`, ships 4 send-on-click honesty chips, pins the server session id and reuses it on later turns, shows a `view-trace` link only when `trace_url` is non-null, and degrades mid-stream `error` events to a friendly bubble and pre-stream 400/429 to a toast. No backend change.
- **Split ReAct/SQL-generation LLM config - Backend hotfix:** `AgentProvider.build_model("react")` builds the outer ReAct model from `agent.react`; `AgentProvider.build_model("sql_generation")` builds the nested SQL-generation model from `agent.sql_generation`. Both profiles expose the same model fields, and only the SQL-generation profile sets `reasoning_effort: "none"`.
- **T0018.4 - Deploy topology + first public deploy:** API on **Render** (Docker, Singapore, Free, `WEB_CONCURRENCY=1`, health check `/api/v1/health`), Postgres on **Neon** (PG17, static 50-row snapshot), tracing on **Langfuse Cloud Hobby (JP)**; secrets are Render env vars, `api.cors.allowed_origins` stays `[]` (same-origin). Auto-deploy on push to this branch. **$0/mo** against a $10 ceiling. No app-code change was needed. **Live: https://internhunteragent.onrender.com**, verified end-to-end 2026-07-16.

- **T0019.1 - robots.txt / ToS gate (doc-only, no code):** resolved the `deployment-research-plan.md` §11 hard gate. **`ms.vietnamworks.com` serves no robots.txt at all (HTTP 404)**; `www.vietnamworks.com/robots.txt` permits the relevant paths with no `Crawl-delay`; the ToS contains **no** automated-access/scraping clause. **Recommended verdict: favorable — pending maintainer confirmation**, so **T0019.6 stays blocked until the maintainer signs off** (then on T0019.2–.5). Evidence archived under `research/experiments/` (both robots fetches + a ToS excerpt with verbatim Vietnamese and labeled translations); decision record in `research/deployment-research-plan.md` §11. One caveat registered in `Known_Issues.md`: ToS §7 restricts *republishing* content — a live question for the public demo, but not a cron blocker, since the deployed snapshot already raises it today.

- **T0019.2 - Alembic adoption: baseline migration + env wiring:** replaced `scripts/reset_db.sql` (DROP + recreate) as the de-facto migration strategy — that stops working once T0019.3 makes `raw_jobs` accumulate irreplaceable postings. Added `alembic` (`pyproject.toml`), scaffolding (`alembic.ini`, `alembic/env.py` reading `ALEMBIC_DATABASE_URL` → falls back to `settings.DATABASE_URL`, `target_metadata = Base.metadata`), and one hand-written baseline migration (`alembic/versions/f3a1c9d2e7b4_baseline_schema.py`, `down_revision = None`) reproducing the exact schema in `scripts/init_db.sql`. Aligned `RawJob.id`/`CleanJob.id` in `models.py` to `Identity(always=True)` (metadata-only fix — the DB already used `GENERATED ALWAYS AS IDENTITY`; the ORM metadata previously disagreed). `scripts/reset_db.sql` demoted to a local-dev-only header comment; `scripts/init_db.sql` untouched (the eval fixture loader still depends on it). New opt-in `tests/migrations/test_baseline_roundtrip.py` (skips without `SCRATCH_DATABASE_URL`). Verified: empty-DB `alembic upgrade head` builds the full 19-column `clean_jobs` schema correctly; the round-trip test passes against a scratch DB; `alembic stamp head` + `alembic upgrade head` is a clean no-op against the real local DB (row count unchanged at 50); the app boots and answers a live query against the migrated schema — verified via the Dockerized (Linux) `api` service, since native Windows `uv run uvicorn` hangs on a pre-existing, ticket-unrelated `ProactorEventLoop`/async-psycopg incompatibility (`Known_Issues.md`).

- **T0019.3 - Accumulate load semantics + hidden lifecycle columns:** dropped the `TRUNCATE` in `clean_store.py` — the already-written `ON CONFLICT (source, external_id) DO UPDATE` upsert (renamed `replace_clean_jobs` → `upsert_clean_jobs`) is now live code, so `raw_jobs`/`clean_jobs` accumulate across runs instead of being rebuilt each time. Added three hidden bookkeeping columns to `clean_jobs` — `is_active boolean not null default true`, `first_seen_at`/`last_seen_at timestamptz not null default now()` — via `alembic/versions/b7e2f4a91c3d_lifecycle_columns.py` (`down_revision = f3a1c9d2e7b4`), with a backfill from `raw_jobs.fetched_at` (confirmed the join was total: 0 orphaned `clean_jobs` rows on the 50-row local snapshot, so no row was left defaulted to migration-run time). The upsert now refreshes `last_seen_at = now()` and flips `is_active = true` on every conflict, and never touches `first_seen_at` (insert-only). New `expire_stale_clean_jobs(expire_after_days)` in `clean_store.py` runs a single time-based `UPDATE ... SET is_active = false WHERE last_seen_at < now() - make_interval(days => :days)` — never `DELETE`, never "not seen this run." `loader.py::run_ingestion` calls it after the upsert using `config/ingestion.yaml`'s new `lifecycle.expire_after_days: 7`, and the run summary gained `expired_count`. All three columns stay off the agent-visible surface — no `NormalizedJob`, `Schema_Contract.md`, or `config/prompts.yaml` change; the hidden-column guard in `tests/agents/runtime/test_prompts.py` was extended to assert `is_active`/`first_seen_at`/`last_seen_at` never appear in `schema_context`. `scripts/init_db.sql` was deliberately left untouched (now diverges from the Alembic head — logged in `Known_Issues.md`). Verified live against the local Docker DB: empty-DB `alembic upgrade head` builds the full 22-column schema; `alembic downgrade -1` cleanly drops the three columns; upgrading the real local DB preserved all 50 rows with a true backfill (0 rows at "now"); a synthetic row proved two upserts keep `is_active=true`/refresh `last_seen_at`/preserve `first_seen_at`, an 8-day-aged row flips to `is_active=false` under a 7-day window without being deleted, and re-seeding it flips `is_active` back to `true`; the Dockerized `api` service answered a live chat query ("13 AI Engineer jobs") with no mention of the hidden columns.

**Status (2026-07-18):** T0016.1–T0016.4, T0017.1–T0017.2, **T0018.1–T0018.4**, the SQL-generation reasoning-effort hotfix, and the ReAct/SQL-generation config split are complete on this stack; **T0019.1** is complete pending the maintainer's verdict confirmation; **T0019.2** and **T0019.3** are complete. Open issues live in [`Known_Issues.md`](Known_Issues.md); resolved/background items in [`Resolved_Issues.md`](Resolved_Issues.md).

**Milestone map (see `Tickets.md`):** T0013 freeze → T0016 security posture → T0017 streaming response delivery → T0018 clickable demo UI + go-live ✅ → **T0019 ingestion deploy readiness (live-DB) ◀ in progress (T0019.1 ✅, T0019.2 ✅, T0019.3 ✅)**.

**Next recommended ticket:** **T0019.4** — see [Next recommended ticket](#next-recommended-ticket) below.

## Current folder structure
```text
.
|-- alembic.ini
|-- alembic/
|   |-- env.py
|   |-- script.py.mako
|   `-- versions/
|       |-- f3a1c9d2e7b4_baseline_schema.py
|       `-- b7e2f4a91c3d_lifecycle_columns.py
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
|   |-- migrations/
|   |   `-- test_baseline_roundtrip.py
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
- `alembic>=1.14` (T0019.2 — schema migrations; `alembic.ini` + `alembic/` at repo root)
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
- `docker compose exec -T postgres psql -U internhunter -d internhunter -f scripts/init_db.sql` (routine, non-destructive schema init/no-op; retained because `evals/fixtures/loader.py` depends on it to build the eval fixture DB — it and the Alembic baseline migration coexist as two independent schema-creation paths)
- `docker compose exec -T postgres psql -U internhunter -d internhunter -f scripts/reset_db.sql` (**destructive, local dev only** — production and any deployed schema change goes through Alembic; must never be pointed at Neon)
- `uv run alembic current` (T0019.2 — shows the revision the target DB is stamped at)
- `uv run alembic history` (T0019.2 — lists migration history)
- `uv run alembic upgrade head` (T0019.2 — applies pending migrations; DSN from `ALEMBIC_DATABASE_URL` or falls back to `settings.DATABASE_URL`)
- `docker compose -f infra/docker-compose.yaml up --build` (Langfuse observability stack)

## Build/test status
Current-branch (T0019.3) results below; earlier per-ticket logs (T0011–T0018.2) are archived in [`archive/Repo_State_History.md`](archive/Repo_State_History.md).

- `uv run pytest -q` (T0019.3, full standard suite) → `303 passed, 1 skipped, 19 deselected, 4 subtests passed` in ~5s. The 1 skip is `tests/migrations/test_baseline_roundtrip.py`, which needs `SCRATCH_DATABASE_URL`.
- `uv run ruff check .` (T0019.3, touched files) → all checks passed.
- `uv run mypy` (T0019.3, touched files) → no issues.
- Manual: empty-DB `alembic upgrade head` built the full 22-column `clean_jobs` schema (19 baseline + `is_active`/`first_seen_at`/`last_seen_at`); `alembic downgrade -1` cleanly dropped the three columns; upgrading the real local DB preserved all 50 rows and backfilled `first_seen_at`/`last_seen_at` truthfully from `raw_jobs.fetched_at` (0 rows at "now", join confirmed total — 0 orphans); a synthetic-row probe against the local DB proved the upsert refreshes `last_seen_at`/`is_active` and preserves `first_seen_at` across repeat runs, an 8-day-aged row expires under a 7-day window without deletion, and re-seeding flips it back active; the Dockerized (Linux) `api` service answered a live chat query with no mention of the hidden columns. Native Windows `uv run uvicorn` boot still hangs on the pre-existing `ProactorEventLoop` incompatibility, unrelated to this ticket (`Known_Issues.md`).
- Prior (T0019.2): `alembic upgrade head` against an empty scratch DB built the correct 19-column `clean_jobs` schema; `alembic stamp head` + `alembic upgrade head` against the real local DB was a clean no-op (row count unchanged at 50); the Dockerized (Linux) `api` service booted cleanly and answered a live query against the migrated/stamped schema.

- `uv run pytest tests/agents/runtime/test_provider.py tests/agents/tools/test_query_clean_jobs.py -q` (ReAct/SQL-generation config split) -> `16 passed`.
- `uv run pytest -q` (full standard suite after ReAct/SQL-generation config split) -> `297 passed, 19 deselected, 4 subtests passed`.
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
**T0019.4 — Source resilience: per-page try/continue + retry/backoff.** T0019.3 landed the accumulate/expiry semantics, and T0019.5 (unattended-run safety) is blocked on both T0019.3 (done) and T0019.4's `pages_failed` summary field, so .4 is next in the spine. T0019 (Ingestion Deploy Readiness, live-DB) was scoped 2026-07-16 into eight sub-tickets: it replaces the static 50-row snapshot with a nightly refresh into the live Neon DB, and absorbs the three ops items previously deferred — the dead-man's switch (`deployment-research-plan.md` §9A), the **keep-alive ping** decided 2026-07-16 (§1a), and the **schema-drift assertion/migration** re-pointed from T0018.4 (`Known_Issues.md` `[HIGH · OPEN]`). Decision validation: [`research/ingestion-milestone-plan.md`](../research/ingestion-milestone-plan.md).

**T0019.1 is done** (2026-07-16, doc-only): recommended verdict **favorable, pending maintainer confirmation** — record in `research/deployment-research-plan.md` §11, evidence in `research/experiments/`. **T0019.2 is done** (2026-07-18): Alembic scaffolding + baseline migration, `Identity(always=True)` alignment in `models.py`, `scripts/reset_db.sql` demoted to local-dev-only. **T0019.3 is done** (2026-07-18): `clean_store.py`'s `TRUNCATE` is gone — the upsert (`upsert_clean_jobs`) is live and accumulate semantics hold; `is_active`/`first_seen_at`/`last_seen_at` are hidden lifecycle columns with a truthful backfill and a time-based expiry pass (`expire_stale_clean_jobs`) wired into the loader. The safety rule below is now lifted.

**Maintainer action outstanding:** confirm T0019.1's favorable verdict before T0019.6 is built; separately, run the documented (not yet executed) `alembic stamp head` Neon-adoption command from `Manual_Verification_Guide.md` → T0019.2 § F, once, deliberately, before any future migration targets Neon. Nothing else in the milestone waits on either.

**Sequencing:** .1 ✅ done (hard-blocks the cron in .6 only), .2 ✅ done, .3 ✅ done, then the spine **.4 → .5 → .6**; .7/.8 float.

> ✅ **Safety rule lifted:** the production-DSN ingestion freeze that was in force pending T0019.3 no longer applies — `clean_store.upsert_clean_jobs` no longer truncates `clean_jobs`, so a run against Neon accumulates instead of rebuilding the live table. (T0019.6, the nightly cron, still separately waits on the T0019.1 maintainer sign-off.)

Unscheduled after T0019 (`Tickets.md` → Backlog): **CI merge gate** (`pre-deploy-refinement-plan.md` §6i — no automated gate today; Render auto-deploys straight off this branch) and **`main` reconciliation** (`main` remains stuck at T0009; M10–M19 live on ticket branches — needs an explicit maintainer decision; **do not branch a deploy from `main`**).

Open separately: **T0011.5** baseline calibration, still blocked on maintainer credentials — it also gates the `is_active` agent exposure that T0019 deliberately cut.
