## Current branch
`feature/t0019.5-unattended-safety` — HEAD at `bb75d10` (T0019.5). Branched off `feature/t0019.4-source-resilience`, which was branched off `feature/t0019.3-accumulate-lifecycle`, which was branched off `feature/t0019.2-alembic-baseline`, which was branched off `feature/t0019.1-robots-tos-gate`, which was branched off `feature/t0018.4-deploy`, which remains the deployed branch — **LIVE: https://internhunteragent.onrender.com** (verified end-to-end 2026-07-16). Note `main` sits at **T0017.2** (`e3e65ae`, reconciled 2026-07-16 — it *does* contain T0013/T0016/T0017; the long-repeated "stuck at T0009" claim was corrected 2026-07-19) and is **12 commits behind** this stack, missing all of T0018.x and T0019.x; the nightly `schedule:` trigger stays dormant until a maintainer merges this chain to `main` — see `Known_Issues.md`. Branch off `feature/t0018.4-deploy` (or its ticket-branch descendants), not `main`.

> ⚠️ **T0019.6 is complete but uncommitted, and its branch was never cut.** The work described below as T0019.6 — `.github/workflows/ingestion.yml` plus the doc updates — exists only as an untracked file and unstaged doc edits in this working tree, sitting on the T0019.5 branch. The intended `feature/t0019.6-nightly-cron` branch does not exist. **Maintainer action:** cut that branch off `bb75d10` and commit the workflow + docs before treating T0019.6 as landed; until then it is not recoverable from git and not reviewable as a diff.

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

- **T0019.1 - robots.txt / ToS gate (doc-only, no code):** resolved the `deployment-research-plan.md` §11 hard gate. **`ms.vietnamworks.com` serves no robots.txt at all (HTTP 404)**; `www.vietnamworks.com/robots.txt` permits the relevant paths with no `Crawl-delay`; the ToS contains **no** automated-access/scraping clause. **Recommended verdict: favorable — maintainer confirmed 2026-07-19** (`research/deployment-research-plan.md` §11, recorded under T0019.6). Evidence archived under `research/experiments/` (both robots fetches + a ToS excerpt with verbatim Vietnamese and labeled translations). One caveat registered in `Known_Issues.md`: ToS §7 restricts *republishing* content — a live question for the public demo, but not a cron blocker, since the deployed snapshot already raises it today.

- **T0019.2 - Alembic adoption: baseline migration + env wiring:** replaced `scripts/reset_db.sql` (DROP + recreate) as the de-facto migration strategy — that stops working once T0019.3 makes `raw_jobs` accumulate irreplaceable postings. Added `alembic` (`pyproject.toml`), scaffolding (`alembic.ini`, `alembic/env.py` reading `ALEMBIC_DATABASE_URL` → falls back to `settings.DATABASE_URL`, `target_metadata = Base.metadata`), and one hand-written baseline migration (`alembic/versions/f3a1c9d2e7b4_baseline_schema.py`, `down_revision = None`) reproducing the exact schema in `scripts/init_db.sql`. Aligned `RawJob.id`/`CleanJob.id` in `models.py` to `Identity(always=True)` (metadata-only fix — the DB already used `GENERATED ALWAYS AS IDENTITY`; the ORM metadata previously disagreed). `scripts/reset_db.sql` demoted to a local-dev-only header comment; `scripts/init_db.sql` untouched (the eval fixture loader still depends on it). New opt-in `tests/migrations/test_baseline_roundtrip.py` (skips without `SCRATCH_DATABASE_URL`). Verified: empty-DB `alembic upgrade head` builds the full 19-column `clean_jobs` schema correctly; the round-trip test passes against a scratch DB; `alembic stamp head` + `alembic upgrade head` is a clean no-op against the real local DB (row count unchanged at 50); the app boots and answers a live query against the migrated schema — verified via the Dockerized (Linux) `api` service, since native Windows `uv run uvicorn` hangs on a pre-existing, ticket-unrelated `ProactorEventLoop`/async-psycopg incompatibility (`Known_Issues.md`).

- **T0019.3 - Accumulate load semantics + hidden lifecycle columns:** dropped the `TRUNCATE` in `clean_store.py` — the already-written `ON CONFLICT (source, external_id) DO UPDATE` upsert (renamed `replace_clean_jobs` → `upsert_clean_jobs`) is now live code, so `raw_jobs`/`clean_jobs` accumulate across runs instead of being rebuilt each time. Added three hidden bookkeeping columns to `clean_jobs` — `is_active boolean not null default true`, `first_seen_at`/`last_seen_at timestamptz not null default now()` — via `alembic/versions/b7e2f4a91c3d_lifecycle_columns.py` (`down_revision = f3a1c9d2e7b4`), with a backfill from `raw_jobs.fetched_at` (confirmed the join was total: 0 orphaned `clean_jobs` rows on the 50-row local snapshot, so no row was left defaulted to migration-run time). The upsert now refreshes `last_seen_at = now()` and flips `is_active = true` on every conflict, and never touches `first_seen_at` (insert-only). New `expire_stale_clean_jobs(expire_after_days)` in `clean_store.py` runs a single time-based `UPDATE ... SET is_active = false WHERE last_seen_at < now() - make_interval(days => :days)` — never `DELETE`, never "not seen this run." `loader.py::run_ingestion` calls it after the upsert using `config/ingestion.yaml`'s new `lifecycle.expire_after_days: 7`, and the run summary gained `expired_count`. All three columns stay off the agent-visible surface — no `NormalizedJob`, `Schema_Contract.md`, or `config/prompts.yaml` change; the hidden-column guard in `tests/agents/runtime/test_prompts.py` was extended to assert `is_active`/`first_seen_at`/`last_seen_at` never appear in `schema_context`. `scripts/init_db.sql` was deliberately left untouched (now diverges from the Alembic head — logged in `Known_Issues.md`). Verified live against the local Docker DB: empty-DB `alembic upgrade head` builds the full 22-column schema; `alembic downgrade -1` cleanly drops the three columns; upgrading the real local DB preserved all 50 rows with a true backfill (0 rows at "now"); a synthetic row proved two upserts keep `is_active=true`/refresh `last_seen_at`/preserve `first_seen_at`, an 8-day-aged row flips to `is_active=false` under a 7-day window without being deleted, and re-seeding it flips `is_active` back to `true`; the Dockerized `api` service answered a live chat query ("13 AI Engineer jobs") with no mention of the hidden columns.

- **T0019.4 - Source resilience: per-page try/continue + retry/backoff:** `config/ingestion.yaml` gains `api.retry_attempts: 2` / `api.retry_backoff_seconds: 2.0`. `JobSource` (`sources/base.py`) gains a class-level `pages_failed: int = 0` counter. `VietnamWorksSource._post` stays an unchanged thin primitive; a new `_post_with_retry` wrapper retries transient failures (429, ≥500, timeouts, transport errors) with doubling backoff (2s, then 4s) and gives up immediately on permanent 4xx — on give-up it increments `pages_failed`, logs `ingestion.page_failed` (query + page + attempts + reason), and returns `None` without raising. `_collect` treats `None` as "skip this page" and a `try/finally` around the per-page body guarantees the politeness `time.sleep(self._delay)` still runs even when a page is skipped. `fetch()` resets `pages_failed = 0` at entry so a reused instance doesn't accumulate across runs. `loader.py::run_ingestion` reads `getattr(source, "pages_failed", 0)` after draining the generator and adds `"pages_failed"` to the summary dict — no other loader ordering changed. A single transient failure no longer discards an entire run's already-fetched pages.

- **T0019.5 - Unattended-run safety: pre-flight schema assertion, yield floor, dead-man ping:** new `src/services/ingestion/safety.py` with `IngestionSafetyError` and three functions. `assert_clean_jobs_schema()` queries live `information_schema.columns` for `clean_jobs` and compares against `{c.name for c in CleanJob.__table__.columns}` (derived from the ORM, never hand-maintained); on any mismatch it logs `ingestion.schema_drift` (missing + unexpected, both directions) and raises before any write — an absent table (empty column set) also raises, with its own message rather than listing all columns "missing." `assert_min_yield(fetched, min_yield)` raises `IngestionSafetyError` naming both numbers when `fetched < min_yield`, logging `ingestion.yield_floor_breached` first. `send_dead_man_ping(url)` POSTs to a healthchecks.io URL via `httpx`; `None`/empty logs `ingestion.ping_skipped` and returns `False` (the normal local path, not an error); any `httpx.HTTPError` or non-2xx logs `ingestion.ping_failed` as a warning and returns `False` without raising — a ping failure never fails the run. `config/ingestion.yaml` gains `safety.min_yield: 20`. `src/core/config.py` gains one optional field, `HEALTHCHECKS_URL: str | None = None`; documented (commented, optional) in `.env.example`. `loader.py::run_ingestion` now calls `assert_clean_jobs_schema()` first — before the source is constructed or anything fetched — then fetches, upserts raw (evidence preserved even on a bad run), calls `assert_min_yield(len(postings), settings.ingestion_yaml["safety"]["min_yield"])`, and only then normalizes/upserts clean/expires; a yield-floor abort happens before both the clean upsert and the expiry pass, so a skipped clean write can never have `expire_stale_clean_jobs` wrongly age out untouched rows. `run_ingestion` stays library code — it lets `IngestionSafetyError` propagate, no `sys.exit`. `main()` now owns the process contract: catches `IngestionSafetyError`, logs `ingestion.aborted`, exits 1; on the fully-green path it logs the existing `ingestion.completed` summary (unchanged: `fetched`/`raw_upserted`/`clean_loaded`/`skipped`/`expired_count`/`pages_failed`) and only then calls `send_dead_man_ping(settings.HEALTHCHECKS_URL)` — withholding the ping on any abort is the dead-man signal. All nine pre-existing `test_loader.py` tests were updated to patch the new `assert_clean_jobs_schema` and set `safety.min_yield: 0` in their mocked `ingestion_yaml` (no assertion weakened); three new loader tests cover schema-abort, yield-floor-abort, and the happy-path ordering/summary shape. New `tests/services/ingestion/test_safety.py` covers both schema-assertion mismatch directions, the empty-table case, both `assert_min_yield` branches, and all three `send_dead_man_ping` paths.

- **T0019.6 - GitHub Actions nightly ingestion cron (doc + workflow only, no application code):** new `.github/workflows/ingestion.yml` runs `uv run python -m src.services.ingestion.loader` on a GitHub-hosted runner — `schedule: '0 2 * * *'` (02:00 UTC / 09:00 ICT) + `workflow_dispatch`, `concurrency: {group: ingestion, cancel-in-progress: false}` so overlapping runs queue instead of double-writing, `timeout-minutes: 15`, `permissions: {contents: read}`. Install mirrors `docker/Dockerfile`: `actions/checkout@<pinned SHA>` (v7.0.0), `astral-sh/setup-uv@<pinned SHA>` (v8.3.2) pinned to `version: "0.8.15"`, `uv sync --frozen --no-dev`. Empirically resolved (moving `.env` aside and unsetting each var) that `GROQ_API_KEY`/`LANGFUSE_SECRET_KEY`/`LANGFUSE_PUBLIC_KEY` are all genuinely required by `Settings`'s no-default fields even though ingestion never reads them at runtime — all three stay in the `env:` block from `secrets.*`, with an inline comment explaining why. The keepalive step named in the ticket, `gautamkrishnar/keepalive-workflow`, could not be wired in: the repository returns HTTP 403 "Repository access blocked: tos" — GitHub disabled it for a ToS violation (the action was designed to defeat the same 60-day inactivity policy it worked around). No SHA is verifiable, so the step was omitted with a comment and `TODO(maintainer)` rather than pinning a defunct/ToS-violating action. `Full_Design_Document.md` §2's "no autonomous or background execution" exclusion was amended to scope it to *in-request* execution and name this workflow as the one permitted out-of-band exception, cross-referencing §3's "request pipeline must never import ingestion" law (preserved: the cron runs on a GitHub runner, never inside the API process). `research/deployment-research-plan.md` §11's T0019.1 verdict flipped from "pending maintainer confirmation" to "maintainer confirmed 2026-07-19." No file under `src/`, `tests/`, or `config/` touched.

**Status (2026-07-19):** T0016.1–T0016.4, T0017.1–T0017.2, **T0018.1–T0018.4**, the SQL-generation reasoning-effort hotfix, and the ReAct/SQL-generation config split are complete on this stack; **T0019.1–T0019.6 are complete.** T0019.9 (coverage) and T0019.10 (detail visibility) are now scoped corrective release gates: the prepared nightly workflow must not merge to `main` until both land. T0019.7 and T0019.8 remain independent milestone work. The schedule itself remains dormant while the chain is off `main`. Open issues live in [`Known_Issues.md`](Known_Issues.md); resolved/background items in [`Resolved_Issues.md`](Resolved_Issues.md).

**Milestone map (see `Tickets.md`):** T0013 freeze → T0016 security posture → T0017 streaming response delivery → T0018 clickable demo UI + go-live ✅ → **T0019 ingestion deploy readiness (live-DB) ◐ in progress (T0019.1–.6 ✅; T0019.9 coverage and T0019.10 detail visibility are release gates; T0019.7/.8 remain independent)**. The scheduler cannot merge to `main` or become live until .9 and .10 land.

**Next recommended ticket:** see [Next recommended ticket](#next-recommended-ticket) below — **T0019.9**, then **T0019.10**. Both must land before the prepared T0019.6 cron is allowed to merge to `main`.

## Current folder structure
```text
.
|-- .github/
|   `-- workflows/
|       `-- ingestion.yml
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
|       |   |-- safety.py
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
Latest results below, from the uncommitted T0019.6 working tree (see the branch warning above); earlier per-ticket logs (T0011–T0018.2) are archived in [`archive/Repo_State_History.md`](archive/Repo_State_History.md).

- `uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/ingestion.yml'))"` (T0019.6) → parses cleanly (the bare `on:` key parses to the YAML-1.1 boolean `True` under PyYAML — a known, harmless quirk; GitHub's own workflow parser handles it specially).
- `git status --short` (T0019.6, before/after) → confirms no file under `src/`, `tests/`, or `config/` touched; only `.github/workflows/ingestion.yml` (new) and the five allowed docs files.
- `uv run pytest -q` (T0019.6, full standard suite, re-run after all doc/workflow changes) → `319 passed, 8 skipped, 19 deselected, 4 subtests passed` in ~265s — identical to the T0019.5 baseline, confirming no regression.
- `uv run ruff check .` (T0019.6, whole repo) → all checks passed.
- `uv run mypy` (T0019.6, whole repo) → same 2 pre-existing, unrelated errors as every prior ticket (`src/core/checkpointer.py:25`, `src/agents/runtime/middleware.py:48`); confirmed pre-existing via `git stash && uv run mypy && git stash pop`.
- Manual check B (required-secrets question) run empirically: unsetting `GROQ_API_KEY`, `LANGFUSE_SECRET_KEY`, or `LANGFUSE_PUBLIC_KEY` in turn (with `.env` moved aside) each produced `ConfigLoadError: ... Missing required environment variables: <NAME>`, `exit=1`, before any DB/network call.
- Manual checks C/D (live Actions dispatch + concurrency) not run — require maintainer-configured GitHub Actions secrets and a push of this branch. Checklist appended to `Manual_Verification_Guide.md` → T0019.6.

- `uv run pytest -q` (T0019.5, full standard suite, DB-dependent tests skip without Docker up) → `319 passed, 8 skipped, 19 deselected, 4 subtests passed` in ~268s. No pre-existing test's assertions were weakened — the 9 pre-existing `test_loader.py` tests now patch `assert_clean_jobs_schema` and carry `safety.min_yield: 0` in their mocked config.
- `uv run pytest tests/services/ingestion/test_safety.py tests/services/ingestion/test_loader.py -q` (T0019.5, targeted) → `23 passed` in <1s.
- `uv run ruff check .` (T0019.5, whole repo) → all checks passed.
- `uv run mypy` (T0019.5, whole repo) → 2 pre-existing errors, both unrelated to this ticket (`src/core/checkpointer.py:25`, `src/agents/runtime/middleware.py:48` — logged in `Known_Issues.md`); the three touched files (`safety.py`, `loader.py`, `src/core/config.py`) are clean.
- Manual verification against a live local Docker DB (checks B–E of the T0019.5 checklist) was not run in this session — no local Docker Postgres was up. Flagged as a risk below; the checklist is appended to `Manual_Verification_Guide.md` for the next person with the stack running.

- `uv run pytest -q` (T0019.4, full standard suite) → `311 passed, 1 skipped, 19 deselected, 4 subtests passed` in ~5s. The 1 skip is `tests/migrations/test_baseline_roundtrip.py`, which needs `SCRATCH_DATABASE_URL`. No pre-existing test was modified.
- `uv run ruff check .` (T0019.4, whole repo) → all checks passed.
- `uv run mypy` (T0019.4, whole repo) → 2 pre-existing errors, both unrelated to this ticket (`src/core/checkpointer.py:25`, `src/agents/runtime/middleware.py:48` — logged in `Known_Issues.md`).
- Manual: a mock-client script driving `VietnamWorksSource` with one page failing 500 three times then a later page succeeding showed `pages_failed == 1`, surviving postings present, and an `ingestion.page_failed` JSON warning on stderr with the query/page/attempts/reason; `run_ingestion` against a stub source with `pages_failed = 2` returned that value in the summary dict alongside `fetched`/`raw_upserted`/`clean_loaded`/`skipped`/`expired_count`.
- `uv run pytest tests/services/ingestion/test_vietnamworks.py -v` (T0019.4, new `VietnamWorksResilienceTests`) → 7 new tests, all passing, in well under a second (confirms `time.sleep` is patched, not really waiting through backoff).

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
[`archive/Code_Review_Notes.md`](archive/Code_Review_Notes.md); its bugs are logged in `Known_Issues.md`
(open) / `Resolved_Issues.md` (closed).

## Next recommended ticket
**T0019 (Ingestion Deploy Readiness, live-DB) remains in progress** — T0019.1–.6 are complete and the cron is prepared but dormant on its feature branch. Two newly scoped corrective release gates, **T0019.9 coverage** and **T0019.10 detail visibility**, must land before the chain can merge to `main`; .7/.8 remain independent. Decision validation: [`research/ingestion-milestone-plan.md`](../research/ingestion-milestone-plan.md).

**T0019.1 is done** (2026-07-16, doc-only; verdict confirmed 2026-07-19): recommended verdict **favorable, maintainer confirmed** — record in `research/deployment-research-plan.md` §11, evidence in `research/experiments/`. **T0019.2 is done** (2026-07-18): Alembic scaffolding + baseline migration, `Identity(always=True)` alignment in `models.py`, `scripts/reset_db.sql` demoted to local-dev-only. **T0019.3 is done** (2026-07-18): `clean_store.py`'s `TRUNCATE` is gone — the upsert (`upsert_clean_jobs`) is live and accumulate semantics hold; `is_active`/`first_seen_at`/`last_seen_at` are hidden lifecycle columns with a truthful backfill and a time-based expiry pass (`expire_stale_clean_jobs`) wired into the loader. **T0019.4 is done** (2026-07-18): per-page retry-then-skip resilience lives in `VietnamWorksSource`, and `run_ingestion` surfaces `pages_failed` in its summary — a single transient failure (429/5xx/timeout/transport error) no longer discards an entire run's already-fetched pages. **T0019.5 is done** (2026-07-19): `run_ingestion` now aborts before any write on schema drift or under-floor yield, and `main()` sends a dead-man ping to healthchecks.io only after a fully-green run; `pages_failed` stays unconsumed by design (logged as an open item in `Known_Issues.md`). **T0019.6 is done** (2026-07-19): `.github/workflows/ingestion.yml` exists, validated, and manually dispatchable from the feature branch — but the `schedule:` trigger stays dormant until the branch chain merges to `main` (see below). The safety rule below is lifted.

**Maintainer action outstanding:**
1. Implement T0019.9 (coverage cap + fair query scheduling), then T0019.10 (detail-tool projection). They are deliberate release gates, not changes to the already-prepared cron workflow.
2. After both gates pass their focused and full-suite checks, the maintainer may merge the T0019.1–.6/.9/.10 branch chain to `main` — the trigger that makes the nightly `schedule:` fire. No ticket owns this merge itself; it also drives a Render auto-deploy.
3. Configure GitHub Actions secrets on the repo before the first dispatch: `DATABASE_URL` (Neon direct, non-pooled), `HEALTHCHECKS_URL`, `GROQ_API_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_PUBLIC_KEY`.
4. Run the documented (not yet executed) `alembic stamp head` Neon-adoption command from `Manual_Verification_Guide.md` → T0019.2 § F, once, deliberately, before any future migration targets Neon.
5. Decide a keepalive replacement for GitHub's 60-day scheduled-workflow auto-disable — the ticket's suggested action (`gautamkrishnar/keepalive-workflow`) is itself disabled by GitHub for a ToS violation; see `Known_Issues.md` for candidates.

**Sequencing:** .1 ✅ done, .2 ✅ done, .3 ✅ done, .4 ✅ done, .5 ✅ done, .6 ✅ prepared (schedule dormant); **.9 → .10 are release gates before merge**; .7/.8 float. **T0019.9 is the next coding-work ticket.**

> ✅ **Safety rule lifted:** the production-DSN ingestion freeze that was in force pending T0019.3 no longer applies — `clean_store.upsert_clean_jobs` no longer truncates `clean_jobs`, so a run against Neon accumulates instead of rebuilding the live table.
> ⚠️ **Schedule dormant:** T0019.6's `.github/workflows/ingestion.yml` cannot fire on its `schedule:` trigger until it exists on `main` — GitHub only triggers scheduled workflows from the default branch. `workflow_dispatch` works today from the feature branch for manual verification.

Unscheduled after T0019 (`Tickets.md` → Backlog): **CI merge gate** (`pre-deploy-refinement-plan.md` §6i — no automated gate today; Render auto-deploys straight off this branch) and **`main` reconciliation** (`main` sits at T0017.2 (`e3e65ae`), not T0009 — it carries through M17, but T0018.x (deploy + demo UI) and T0019.x live only on ticket branches, 12 commits' worth. Needs an explicit maintainer decision; **do not branch a deploy from `main`** — it lacks the deployed T0018.4 topology).

Open separately: **T0011.5** baseline calibration, still blocked on maintainer credentials — it also gates the `is_active` agent exposure that T0019 deliberately cut.
