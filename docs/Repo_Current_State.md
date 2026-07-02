## Current branch
feature/t0010.3-sql-single-table

## Completed tickets
- T0000: Milestone 0 - Foundation (FastAPI, logging, health endpoint)
- T0001: Milestone 1 - Runnable Request Flow (POST /api/v1/agent/chat)
- T0002: Milestone 2 - ReAct Agent Runtime
- T0003: Milestone 3 - Self-Hosted Langfuse (Docker Compose, now under `infra/langfuse/`)
- T0004: Milestone 4 - Tracing Integration
- T0005: Milestone 5 - Hardening (Error handling, timeouts, integration tests)
- T0006.1: DB Foundation (Postgres, dependencies, settings, session factory)
- T0006.2: Query result models (`TableArtifact`, `QueryRefusal`, `QueryToolResult` locked down + serialization tests)
- T0006.3: Deterministic table formatter (`format_rows` in `src/services/query/table_formatter.py` + empty/single/multi/missing-key tests)
- T0006.4: Schema context + SQL-generation prompt (`build_clean_jobs_schema_context()`, `sql_generation` prompt block, `load_sql_generation_prompt()`)
- T0006.5: SQL validator (deterministic, read-only) (`src/services/query/sql_validator.py::validate_sql`, 13 tests)
- T0006.6: SQL executor, sync/threadpool-friendly (`src/services/query/executor.py::execute_validated_sql`, custom `ExecutorError`)
- T0006.7: `query_clean_jobs` LangChain tool adapter (`src/agents/tools/query_clean_jobs.py`, schema -> SQL gen -> validate -> execute -> format -> answer string)
- T0006.8: Registered `query_clean_jobs` in `src/agents/runtime/factory.py` and strengthened the agent system prompt to force tool use for job-data questions
- T0006.9: Confirmed/locked the public API stays answer-only (`{answer, session_id, trace_id, trace_url}`, no SQL/table leakage) — audit only, no code changes needed
- T0006.10: End-to-end manual verification (full stack exercised live; no code changes needed)
- T0007.1: Startup lifecycle + async checkpointer foundation (`src/core/checkpointer.py`, FastAPI `lifespan` in `src/api/app.py`, agent assembled at startup via `app.state.runtime` instead of an import-time singleton; checkpointer accepted by `agent_factory()` but not yet wired into `create_agent`)
- T0007.2: Wire checkpointer + `session_id -> thread_id` lifecycle (`agent_factory()` now passes the checkpointer into `create_agent(...)`; `AgentRuntime.ainvoke` merges `configurable.thread_id` into the Langfuse config; `service.py` generates a `uuid4` session_id when the client omits one and returns the id used; `query.py` returns the service-provided id instead of echoing the request payload)
- T0007.3: Native context trimming (count cap) (`src/agents/runtime/middleware.py::TrimMessagesMiddleware` applies LangChain's native `trim_messages` — strategy `last`, count-based to `agent.memory.max_messages` — inside a `wrap_model_call`/`awrap_model_call` hook attached via `create_agent(middleware=...)`; trims only the per-turn model input, leaving the checkpointer's stored history intact)
- T0007.4: Memory tests, manual verification, and doc status flips (closes Milestone 7) — `tests/agents/runtime/test_memory.py` proves the five memory capabilities (multi-turn refinement within one `session_id`, session isolation, generated-id returned, persistence across a simulated restart, trimming cap holds); flipped the `Status: planned` tags for memory in `MVP_Technical_Design.md` §2.4/§3/§4/§6 to `implemented`; added the T0007.4 manual checklist. No runtime/source behavior changed — tests and docs only.
- T0008.1: Resumi persona + on-topic policy + honesty rules — rewrote `config/prompts.yaml` `prompts.system_prompt` only; introduced the Resumi persona, on-topic/off-topic policy, the available-fields gate (title/company/description/tech_stack; salary/location/remote/deadline not present), multi-turn refinement rule, and honesty + no-SQL/no-raw-table style rules. No source code changed.
- T0008.2: SQL-generation prompt hardening + schema context to YAML — moved schema facts from `src/services/query/schema_context.py` (deleted) into `config/prompts.yaml::prompts.schema_context`; added `load_schema_context()` to `src/agents/runtime/prompts.py`; updated `generate_sql()` to call `load_schema_context()`; strengthened `prompts.sql_generation` with ILIKE/'%term%' rules and comma-separated tech_stack guidance; relocated schema-context tests from the deleted `tests/services/query/test_schema_context.py` into `tests/agents/runtime/test_prompts.py`.
- T0008.3: Manual verification checklist (closes Milestone 8) — rebuilt API image (`docker compose build --no-cache api`) to pick up T0008.1/T0008.2 prompt changes, ran 12-question checklist against the live stack, all 12 items passed; recorded observed answers in `docs/Manual_Verification_Guide.md`; confirmed 70 tests still pass (no regressions). No source code changed.
- T0009.1: Schema & migration — `raw_jobs` + enriched `clean_jobs`. Replaced `scripts/init_clean_jobs.sql` (7 fixtures, 4 old columns) with `scripts/init_db.sql` (idempotent, no seed rows). New `raw_jobs` table (verbatim landing with JSONB payload + content_hash). `clean_jobs` enriched with `role`, `source`, `external_id`, `source_url`, `posted_date`, `is_internship`, `job_level`, `location`, and structured salary (`salary_min`/`salary_max` NUMERIC nullable, `salary_currency`, `is_salary_negotiable`); unique `(source, external_id)` on both tables; both PKs use GENERATED ALWAYS AS IDENTITY. Added `src/services/ingestion/__init__.py` + `src/services/ingestion/models.py` (SQLAlchemy 2.0 declarative `RawJob` + `CleanJob` mirroring the DDL; no eager DB connection). 70 tests still pass.
- T0009.2: Config & ingestion models — created `config/ingestion.yaml` (separate file loaded via `settings.ingestion_yaml`) containing the full ingestion config: VietnamWorks API params (URL, hits_per_page, pages_per_query, timeout, delay, User-Agent), 8 AI/Data keyword queries, jobFunction ids (parent 5 / child 27), max_jobs cap (50), tech_dictionary (~69 terms), role_taxonomy (6 canonical roles with keyword match lists), and city_alias_map (seeded aliases for Hanoi / Ho Chi Minh City / Da Nang + Hai Phong / Can Tho). Added `ingestion_yaml` field to `Settings` and wired `_load_yaml_file("config/ingestion.yaml")` in `load_settings()`. Added `RawPosting` and `NormalizedJob` Pydantic models to `src/services/ingestion/models.py`. 70 tests still pass.
- T0009.3: JobSource interface + VietnamWorksSource adapter — `src/services/ingestion/sources/base.py` (`JobSource` ABC with `source: str` and `fetch() -> Iterator[RawPosting]`); `src/services/ingestion/sources/vietnamworks.py` (`VietnamWorksSource`) reads all fetch params from `settings.ingestion_yaml`, posts to VietnamWorks JSON API with keyword recall + jobFunction precision filter (parentId 5, child 27), dedupes by jobId, respects max_jobs cap, emits `RawPosting` with verbatim `raw_payload` and SHA-256 `content_hash`. Accepts an injected `httpx.Client` for tests. Promoted `httpx` from dev to main deps. 14 new tests in `tests/services/ingestion/test_vietnamworks.py` cover precision filter, internship retention, dedup, field correctness, hash stability/divergence, cap enforcement, and no-live-network. 84 tests pass total.
- T0009.4: Raw landing — upsert `RawPosting` into `raw_jobs`. `src/services/ingestion/raw_store.py` exposes `upsert_raw_postings(postings) -> int` using a single batched PostgreSQL `INSERT ... ON CONFLICT (source, external_id) DO UPDATE` (refreshes `raw_payload`, `content_hash`, `source_url`, and bumps `fetched_at` to `func.now()`). Returns the processed count; handles empty input with no DB hit; wraps `OperationalError`/`DBAPIError` in `RawStoreError`; commits inside `with session_factory()`. 9 new tests in `tests/services/ingestion/test_raw_store.py` (mocked session_factory, no live DB) cover: empty returns 0, count accuracy, `ON CONFLICT DO UPDATE` statement emitted, conflict target includes `source`/`external_id`, commit on success, session closed on success and failure, both error types wrapped as `RawStoreError`. 93 tests pass total.
- T0009.5: Normalize + transform — shared, source-agnostic pure functions in `src/services/ingestion/transform.py` (`html_to_text`, `derive_is_internship`, `find_tech_stack`, `classify_role`, `normalize_location`) and the VietnamWorks-specific normalizer in `src/services/ingestion/normalize/vietnamworks.py` (`to_normalized_job`). All functions read dictionaries from `settings.ingestion_yaml` (tech_dictionary, role_taxonomy, city_alias_map); no DB or network calls. Word-boundary guards prevent false positives for single-char techs (R, Go, C#). Description is one merged blob (jobDescription + jobRequirement + benefit values). Salary is structured with `is_salary_negotiable = not isSalaryVisible`; hidden-salary rows have NULL min/max/currency. Fixture updated with `benefits` and `workingLocations` fields on job 1001 for edge-case coverage. 7 tests in `test_transform.py` classes (27 total methods) and 17 tests in `test_normalize_vietnamworks.py`. 100 tests pass total.
- T0009.6: Loader — idempotent batch pipeline entrypoint. `src/services/ingestion/clean_store.py` exposes `replace_clean_jobs(jobs) -> int`: atomically TRUNCATEs then INSERTs with `ON CONFLICT (source, external_id) DO UPDATE` in a single transaction; empty-input guard returns 0 and skips TRUNCATE, protecting against silent bad-fetch wipeout; wraps `OperationalError`/`DBAPIError` as `CleanStoreError`. `src/services/ingestion/loader.py` exposes `run_ingestion(source=None) -> dict` (fetch → raw upsert → normalize → clean replace) and a `main()` so `uv run python -m src.services.ingestion.loader` runs the full pipeline live. Both modules are import-safe (no DB/network at import time). 9 tests in `test_clean_store.py` (mocked session_factory) and 5 tests in `test_loader.py` (stub JobSource, no live DB/network). 184 tests pass total.
- T0009.7: Agent-layer follow-through (Rich schema) — updated `config/prompts.yaml`: `schema_context` now lists all 12 agent-visible `clean_jobs` columns (title, company, role, description, tech_stack, location, source_url, is_internship, salary_min, salary_max, salary_currency, is_salary_negotiable); `system_prompt` "# Available fields" block updated to the full column set and salary honesty rule changed from "NOT in the data" to "may be NULL or negotiable"; `sql_generation` extended with canonical-value ILIKE examples (role/location), currency-scoped numeric salary comparisons, and boolean filters for is_internship/is_salary_negotiable. `posted_date` intentionally omitted (not yet populated — see `Known_Issues.md`). Updated `test_prompts.py::test_yaml_schema_context_mentions_rich_schema` to assert new columns present and `posted_date`/`remote`/`id` absent. 184 tests pass total.
- T0009.8: End-to-end manual verification (closes Milestone 9) — full stack exercised live: rebuilt the API image, ran the ingestion CLI (`{'fetched': 50, 'raw_upserted': 50, 'clean_loaded': 50}`), verified `raw_jobs`/`clean_jobs` contents and idempotency, ran all 8 agent questions against the live rich schema, and checked `ms.vietnamworks.com/robots.txt` (404 — no restrictions). Found and fixed one trivial, verification-blocking defect: `to_normalized_job` (`src/services/ingestion/normalize/vietnamworks.py`) read the wrong field name (`name` instead of the live API's `cityName`) from `workingLocations`, silently defeating all location canonicalization (every row landed as `"Other"`); fixed the field name and the test fixture that encoded the same wrong assumption (`tests/services/ingestion/fixtures/vietnamworks_raw.json`, `tests/services/ingestion/test_normalize_vietnamworks.py`). Three further issues were surfaced but *not* fixed here (out of scope — logged as follow-ups in `Known_Issues.md`): large-result-set queries can exceed Groq's 12000 TPM limit (413) now that `clean_jobs` holds 50 verbose real postings; the freshness-honesty decline is non-deterministic (1/3 attempts fabricated a "most recently posted" job); the hidden-salary honesty rule's exact wording ("not in the data") is not reliably followed by the model. 184 tests pass total (no regressions). Full results in `Manual_Verification_Guide.md`.
- T0009.9: Explicit schema reset path — added `scripts/reset_db.sql` (`DROP TABLE IF EXISTS clean_jobs, raw_jobs CASCADE;` then `\i scripts/init_db.sql`, no duplicated `CREATE` statements) as the explicit, manual schema-change mechanism; `scripts/init_db.sql` itself is untouched and stays non-destructive (`CREATE TABLE IF NOT EXISTS`). Documented the "reset then re-ingest" workflow in `README.md` and `docs/Manual_Verification_Guide.md`. Reframed the T0009.8 migration-gap entry in `Known_Issues.md` as resolved by this ticket, with Alembic still named as the future escalation trigger ("when deployed data becomes irreplaceable"). No Python/ORM/entrypoint code touched; no new deps; schema shape unchanged. 184 tests still pass.
- T0009.10: Bounded query output (fixes the Groq TPM `413`) — enforces the bounded-output law deterministically at the tool boundary, independent of the model's SQL. `src/services/query/table_formatter.py::format_rows(rows, max_rows)` now drops any column named `description` (case-insensitive) from the returned result regardless of what was `SELECT`ed, and caps the rows returned to the model at `max_rows` while `row_count` carries the true total match count. `src/agents/tools/query_clean_jobs.py` adds `load_max_rows()` (mirrors `load_max_messages()`'s config-validation pattern) reading `agent.query.max_rows` from `config/settings.yaml` (new value: `20`), and `_build_answer` now says `"Showing N of M matching result(s) (narrow your search to see the rest)"` when truncated, or the unchanged `"Found M result(s)"` wording when not. `COUNT(*)`/aggregate results pass through unaffected (single row, never truncated). Reframed the `Known_Issues.md` Capacity & performance entry as resolved. 8 new/updated tests (4 in `test_table_formatter.py`, 2 new in `test_query_clean_jobs.py` for truncation notice and `COUNT(*)` pass-through); 188 tests total pass.
- T0009.11: Job detail tool (`get_job_details`) — completes the structured-query-vs-detail split. `src/services/query/job_details.py::fetch_job_details(ids)` is a deterministic, parameterized fetch-by-id (`WHERE id = ANY(:ids)`, ids bound as a param, never string-interpolated) mirroring `executor.py`'s `SET TRANSACTION READ ONLY` + `ExecutorError` pattern; returns full rows incl. `description` (the only place description is allowed to surface); empty input returns `[]` without hitting the DB; no cap applied here. `src/agents/tools/get_job_details.py` is the `@tool async def get_job_details(ids: list[int]) -> str` wrapper: `load_max_detail_ids()` reads `agent.query.max_detail_ids` (new value: `3`) with the same validation shape as `load_max_rows()`; caps ids client-side and states "Showing N of M requested" when capped; runs the fetch via `asyncio.to_thread`; returns a plain string with a readable block per row, "No posting found for id X" for unmatched ids, and the safe DB-error string on `ExecutorError` (no exception leakage); empty `ids` returns short guidance instead of hitting the DB. Registered in `src/agents/runtime/factory.py`'s `tools=[...]`. `config/prompts.yaml`: added `id (bigint)` to `schema_context`; `sql_generation` now says to always `SELECT id` first when listing rows (never for `COUNT`/aggregate/`GROUP BY`); `system_prompt` "# Available fields" includes `id`, plus a routing line sending "tell me more about / compare specific jobs" to `get_job_details`. `config/settings.yaml` adds `agent.query.max_detail_ids: 3`. Updated pinned tests: `test_prompts.py::test_yaml_schema_context_mentions_rich_schema` now asserts `id` present (moved out of the not-in tuple); `test_factory.py` extended to assert `get_job_details` is registered. New tests: `tests/services/query/test_job_details.py` (6 tests — row mapping incl. description, empty-input short-circuit, `READ ONLY` transaction, parameterized `ids` bind (not interpolated), both error types wrapped as `ExecutorError`), `tests/agents/tools/test_get_job_details.py` (5 tests — plain-string happy path, id cap + notice, missing-id graceful degradation, empty-ids guidance without DB hit, `ExecutorError` safe string). Logged the id-in-SQL nudge's best-effort nature (model-generated SQL may omit `id` on some turns) in `Known_Issues.md` — intentionally not "fixed" by force-injecting `id` into the model's SQL, to keep the model-generated-vs-deterministic tool-boundary line intact. 199 tests total pass.
- T0010.1: Graceful answer + minimal typed error contract — stops two failure modes (C1, C5) from collapsing into an opaque `500 "Failed to process query"`. `src/agents/service.py` now returns a local `AgentResponse` `TypedDict` (`answer: str`, not `str | None`) and coerces a `None`/empty/whitespace-only runtime answer into `FALLBACK_ANSWER` ("I couldn't produce an answer for that — please try rephrasing."). New `src/core/errors.py::InvalidQueryError` (`ValueError` subclass, no hierarchy). `src/api/routes/query.py` raises `InvalidQueryError` for a blank/whitespace-only `payload.query` and maps it to `400 "Query must not be empty."` before `generate_agent_response` is called; genuine internal failures still map to `500 "Failed to process query"` with the `query.failed` server-side log intact; an `except HTTPException: raise` guard keeps the 400 from being re-swallowed by the broad `except Exception`. `answer`/`session_id`/`trace_id`/`trace_url` response shape unchanged; `trace_url` remains `None` (C4, still open, out of scope). Added `GenerateAgentResponseTests` (service-level, mocked runtime) and route-level 400/fallback tests to `tests/api/test_query.py`. `uv run mypy` no longer flags the `service.py`/`query.py` null-into-`str` union error; 3 pre-existing benign residuals remain (documented in `Known_Issues.md`). 204 tests total pass.
- T0010.3: Enforce a true single-table allowlist in the SQL validator — closes the read-scope escape where `validate_sql` only checked `"clean_jobs" in statement.lower()` (substring presence), letting a query also reference `raw_jobs`/other tables via `JOIN` or a comma-separated `FROM` list. `src/services/query/sql_validator.py` now masks string-literal contents (`STRING_LITERAL_PATTERN`, scoped to this check only — does not fix the bug-4 denylist-literal false positives), rejects a comma-separated `FROM` list (`FROM_CLAUSE_LIST_PATTERN`, alias-tolerant), and requires every `FROM`/`JOIN` table reference (`TABLE_REF_PATTERN`) to equal `clean_jobs`; a table-less query (`SELECT 1`) remains valid. No new dependency (no SQL parser). Added 6 tests to `tests/services/query/test_sql_validator.py` (rejects `JOIN raw_jobs`, comma-join, bare `SELECT * FROM raw_jobs`; still allows a `WHERE`-clause `clean_jobs` query, a `clean_jobs` query with another table name inside a string literal, and a table-less `SELECT 1`) — 19 tests in that file, all pass; 210 tests total pass. `uv run ruff check src tests` clean; `uv run mypy` unchanged at 3 pre-existing residuals (no new errors).

## In progress
- Milestone 9 (T0009: data ingestion) closed; T0009.9, T0009.10, and T0009.11 follow-ups also closed. The structured-query-vs-detail split (`query_clean_jobs` → `get_job_details`) is now complete. Milestone 10 (T0010: pre-deploy hardening) in progress — T0010.1 (C1/C5) and T0010.3 (SQL single-table allowlist) closed; C4 (`trace_url`) remains open; T0010.2 (non-string model content) and T0010.4 (blocking LLM call) remain open. Remaining lower-priority items: the freshness-honesty and hidden-salary-phrasing determinism issues logged in `Known_Issues.md`, and the id-in-SQL nudge's best-effort nature (also logged there).

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
|   |-- init_db.sql
|   `-- reset_db.sql
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
|   |   `-- routes/
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
|   `-- services/
|       `-- query/
|-- main.py
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

Dev/test dependencies declared in `pyproject.toml` under `[dependency-groups] dev`:
- `pytest>=9.1.1`
- `pytest-asyncio>=1.4.0`
- `pytest-mock>=3.15.1`
- `ruff>=0.15.20`
- `mypy>=2.1.0`

`anyio` and `langsmith` are transitive (pulled in by `fastapi`/`langchain`), not declared directly.

## Available scripts
No package scripts or `tool.*.scripts` entries are defined in `pyproject.toml`.

Practical commands from the repository layout:
- `uv run uvicorn src.api.app:app --reload`
- `uv run pytest`
- `uv run ruff check .` (lint; config in `pyproject.toml` `[tool.ruff]`, `scripts/` spikes excluded)
- `uv run mypy` (type check `src`; config in `pyproject.toml` `[tool.mypy]`, pydantic plugin enabled)
- `docker compose up -d` (root `docker-compose.yml`: Postgres + API, port `5433` host-side)
- `docker compose exec -T postgres psql -U internhunter -d internhunter -f scripts/init_db.sql` (routine, non-destructive schema init/no-op)
- `docker compose exec -T postgres psql -U internhunter -d internhunter -f scripts/reset_db.sql` (destructive — drops and recreates both tables; use only when the schema shape changes, then re-ingest)
- `docker compose -f infra/docker-compose.yaml up --build` (Langfuse observability stack)

## Build/test status
- Command run: `uv run pytest`
- Result: passed
- Summary: `210 passed in 2.90s`
- Command run: `uv run mypy`
- Result: `Found 3 errors in 3 files (checked 40 source files)` — all 3 are pre-existing, documented residuals (`checkpointer.py:25`, `middleware.py:48`, `query_clean_jobs.py:41`); unchanged by T0010.3 (no new errors).
- Command run: `uv run ruff check src tests`
- Result: `All checks passed!`

## Known issues
Known issues, risks, and out-of-scope follow-ups now live in their own living register:
see [`Known_Issues.md`](Known_Issues.md). Append there when a ticket uncovers a new one.
A full per-module logic review (2026-07-02) — bugs, improvement backlog, and doc insights —
is captured in [`Code_Review_Notes.md`](Code_Review_Notes.md); its bugs are also logged in
`Known_Issues.md`.

## Next recommended ticket
Milestone 9 (data ingestion) is closed, and the structured-query-vs-detail split is now complete (T0009.10 bounded `query_clean_jobs`, T0009.11 `get_job_details`). T0010.1 and T0010.3 are closed; T0010.2 (non-string model content in SQL generation) and T0010.4 (offload the blocking SQL-generation LLM call off the event loop) remain the next T0010 sub-tickets. Recommended next: T0010.2 or T0010.4, then author tickets for the next milestone against `Full_Design_Document.md` / `MVP_Spec.md` §6 (resume/embedding retrieval, charts, evaluation harness), or address the lower-priority prompt-tuning follow-ups (freshness-honesty, hidden-salary phrasing, id-in-SQL nudge best-effort) logged in `Known_Issues.md`.

Remaining future phases (resume/embedding retrieval, charts, typed error contract, evaluation harness) still need tickets authored against `Full_Design_Document.md` / `MVP_Spec.md` §6 before implementation.
