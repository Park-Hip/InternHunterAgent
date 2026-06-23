## Current branch
feature/t0006.4-schema-context

## Completed tickets
- T0000: Milestone 0 - Foundation (FastAPI, logging, health endpoint)
- T0001: Milestone 1 - Runnable Request Flow (POST /api/v1/agent/chat)
- T0002: Milestone 2 - ReAct Agent Runtime
- T0003: Milestone 3 - Self-Hosted Langfuse (Docker Compose)
- T0004: Milestone 4 - Tracing Integration
- T0005: Milestone 5 - Hardening (Error handling, timeouts, integration tests)
- T0006.1: DB Foundation (Postgres, dependencies, settings, session factory)
- T0006.2: Query result models (`TableArtifact`, `QueryRefusal`, `QueryToolResult` locked down + serialization tests)
- T0006.3: Deterministic table formatter (`format_rows` in `src/services/query/table_formatter.py` + empty/single/multi/missing-key tests)
- T0006.4: Schema context + SQL-generation prompt (`build_clean_jobs_schema_context()`, `sql_generation` prompt block, `load_sql_generation_prompt()`)

## Current folder structure
```text
.
|-- config/
|   |-- prompts.yaml
|   `-- settings.yaml
|-- docker-compose.yml
|-- docker/
|   |-- Dockerfile
|   `-- docker-compose.yaml
|-- scripts/
|   `-- init_clean_jobs.sql
|-- docs/
|-- src/
|   |-- agents/
|   |   |-- runtime/
|   |   |-- tools/
|   |   `-- tracing/
|   |-- api/
|   |   `-- routes/
|   |-- core/
|   `-- services/
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

## Installed dependencies
Runtime dependencies declared in `pyproject.toml`:
- `fastapi>=0.136.3`
- `langchain>=1.3.1`
- `langchain-groq>=1.1.2`
- `langfuse>=4.6.1`
- `pydantic-settings>=2.14.1`
- `psycopg[binary]>=3.2`
- `sqlalchemy>=2.0`
- `structlog>=25.5.0`
- `uvicorn>=0.48.0`

Dev/test dependencies are now declared in `pyproject.toml` under `[dependency-groups] dev`:
- `pytest>=9.1.1`
- `pytest-asyncio>=1.4.0`
- `pytest-mock>=3.15.1`

`anyio` and `langsmith` are transitive (pulled in by `fastapi`/`langchain`), not declared directly.

## Available scripts
No package scripts or `tool.*.scripts` entries are defined in `pyproject.toml`.

Practical commands from the repository layout:
- `uv run uvicorn src.api.app:app --reload`
- `uv run pytest`
- `docker compose up -d`
- `docker compose exec -T postgres psql -U internhunter -d internhunter -f scripts/init_clean_jobs.sql`
- `docker compose -f docker/docker-compose.yaml up --build`

## Build/test status
- Command run: `uv run pytest -q`
- Result: passed
- Summary: `20 passed in 1.57s`

## Known issues
- The repository appears to rely on import-time loading in `src/core/config.py`, which makes startup sensitive to working directory and missing config files.
- `main.py` is only a placeholder and does not start the FastAPI app.
- `trace_url` is always returned as `None` in `src/agents/service.py`, so tracing metadata is incomplete.
- `src/api/routes/query.py` converts all exceptions into a generic 500 response, which makes client-side debugging harder.
- `docker/docker-compose.yaml` still contains several `CHANGEME` secrets and placeholder credentials.
- `DATABASE_URL` is now required and must be set in the runtime environment before starting the app.
- Previously, `pytest`/`pytest-asyncio`/`pytest-mock` were not declared as project dependencies. `uv run pytest` silently fell back to a global `pytest.exe` on `PATH` (a different Python install entirely), which lacked `psycopg` and had an older `langchain` without `langchain.messages`, causing spurious `ModuleNotFoundError`s in `tests/core/test_db.py`, `tests/agents/runtime/test_react_agent.py`, and `tests/api/test_query.py`. Fixed by adding them to `[dependency-groups] dev` via `uv add --dev pytest pytest-asyncio pytest-mock`, so `uv run pytest` now resolves inside the project `.venv`.
- `load_sql_generation_prompt()` (T0006.4) returns a plain `str` rather than a `SystemMessage` like `load_system_prompt()`, since the SQL-generation flow needs to combine it with `build_clean_jobs_schema_context()` text before sending it to the model (T0006.7). Flagging in case the tool-adapter ticket expects a different shape.

## Next recommended ticket
T0006.5: SQL validator (deterministic, read-only)
