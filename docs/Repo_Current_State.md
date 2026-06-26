## Current branch
feature/t0008.3-prompt-manual-verification

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

## In progress
- None. T0008.3 closes Milestone 8. Further work (larger dataset, resume/embedding retrieval, charts) needs new tickets authored against `Full_Design_Document.md` / `MVP_Spec.md` §6.

## Current folder structure
```text
.
|-- config/
|   |-- prompts.yaml
|   `-- settings.yaml
|-- docker-compose.yml
|-- docker/
|   `-- Dockerfile
|-- infra/
|   `-- langfuse/
|       |-- docker-compose.yaml
|       `-- README.md
|-- scripts/
|   `-- init_clean_jobs.sql
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
|   |   `-- logger.py
|   `-- services/
|       `-- query/
|           |-- executor.py
|           |-- models.py
|           |-- schema_context.py
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

Notes on the reorg (commit `182aac0`): the Langfuse Docker stack moved from `docker/docker-compose.yaml` to `infra/langfuse/docker-compose.yaml` (with its own `README.md`), and the app-only Postgres compose file lives at the repo root (`docker-compose.yml`) on port `5433` to avoid colliding with the Langfuse stack's own Postgres. The `Manual_Verification_Guide.md` for T0003/T0004 still references the old `docker/docker-compose.yaml` path and should be updated to `infra/langfuse/docker-compose.yaml` in a follow-up.

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

Dev/test dependencies declared in `pyproject.toml` under `[dependency-groups] dev`:
- `pytest>=9.1.1`
- `pytest-asyncio>=1.4.0`
- `pytest-mock>=3.15.1`

`anyio` and `langsmith` are transitive (pulled in by `fastapi`/`langchain`), not declared directly.

## Available scripts
No package scripts or `tool.*.scripts` entries are defined in `pyproject.toml`.

Practical commands from the repository layout:
- `uv run uvicorn src.api.app:app --reload`
- `uv run pytest`
- `docker compose up -d` (root `docker-compose.yml`: Postgres + API, port `5433` host-side)
- `docker compose exec -T postgres psql -U internhunter -d internhunter -f scripts/init_clean_jobs.sql`
- `docker compose -f infra/langfuse/docker-compose.yaml up --build` (Langfuse observability stack)

## Build/test status
- Command run: `uv run pytest -q`
- Result: passed
- Summary: `70 passed in 1.55s`

## Known issues
- **Uncommitted stray edit**: `src/agents/tools/query_clean_jobs.py` currently has an untracked working-tree change appending a stray bare `1` (no trailing newline) after the `return _build_answer(table)` line. It's a harmless no-op statement but is clearly accidental editor/paste noise, not a real change — should be reverted before committing anything else on this branch.
- **Stray committed file at repo root**: a file literally named `s -ExecutionPolicy RemoteSigned) ; (& d:Data_Science_ProjectInternHunterAgent.venvScriptsActivate.ps1)` (~6.4 KB) is tracked in git at the repo root, evidently created by a botched PowerShell command whose output got redirected to a file instead of executing. It should be deleted in a follow-up cleanup commit.
- `Manual_Verification_Guide.md`'s T0003/T0004 sections still point at `docker/docker-compose.yaml` for the Langfuse stack; the actual file now lives at `infra/langfuse/docker-compose.yaml` after the `182aac0` reorg.
- The repository appears to rely on import-time loading in `src/core/config.py`, which makes startup sensitive to working directory and missing config files.
- `main.py` is only a placeholder and does not start the FastAPI app.
- `trace_url` is always returned as `None` in `src/agents/service.py`, so tracing metadata is incomplete.
- `src/api/routes/query.py` converts all exceptions into a generic 500 response, which makes client-side debugging harder.
- `docker-compose.yml` / `infra/langfuse/docker-compose.yaml` may still contain placeholder/`CHANGEME` secrets — verify before any non-local use.
- `DATABASE_URL` is required and must be set in the runtime environment before starting the app.
- `load_sql_generation_prompt()` returns a plain `str` rather than a `SystemMessage` like `load_system_prompt()`, since the SQL-generation flow combines it with `load_schema_context()` text before sending it to the model.
- Observed during T0006.10 verification: the agent sometimes calls `query_clean_jobs` twice in a row with identical arguments before producing its final answer (harmless — deterministic, no side effects — but wastes one round-trip). Candidate follow-up: investigate prompt/loop tuning to remove the redundant call.
- Context trimming caps only what the model sees per turn (`agent.memory.max_messages`, default `20`); the full thread keeps growing in the checkpointer by design. There is no storage-side pruning or token-based budgeting in this MVP (summarization/token budgeting are explicit non-goals).
- `config/settings.yaml` is `COPY`ed into the API image, so changing values like `agent.memory.max_messages` requires a `docker compose build --no-cache api` to take effect — a plain `--build` can reuse a cached `COPY config` layer and silently run stale config.
- Observed during T0007.2 manual verification: asking a refining follow-up about an attribute that has no corresponding column in `clean_jobs` (e.g. "Which of those are remote?" — there is no `remote`/`location` column exposed in the schema context) makes the agent stall for several seconds before it works out it cannot answer, rather than recognizing quickly that the attribute isn't queryable. The eventual answer is still correct/non-fabricated, but the latency suggests the system/SQL-generation prompt could more explicitly guide the model to recognize out-of-schema attributes faster. Candidate follow-up: tune the schema-context or system prompt so the model short-circuits on out-of-schema refinements instead of spending a full reasoning pass figuring it out.

## Next recommended ticket
None open. T0008.3 closes the MVP prompt-hardening work. The whole MVP backlog is built. Further work (future phases — larger/live dataset, resume/embedding retrieval, charts, typed error contract, evaluation harness) needs new tickets authored against `Full_Design_Document.md` / `MVP_Spec.md` §6 before implementation.
