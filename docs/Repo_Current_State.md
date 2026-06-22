## Current branch
feature/t0006.1-db-foundation

## Completed tickets
- T0000: Milestone 0 - Foundation (FastAPI, logging, health endpoint)
- T0001: Milestone 1 - Runnable Request Flow (POST /api/v1/agent/chat)
- T0002: Milestone 2 - ReAct Agent Runtime
- T0003: Milestone 3 - Self-Hosted Langfuse (Docker Compose)
- T0004: Milestone 4 - Tracing Integration
- T0005: Milestone 5 - Hardening (Error handling, timeouts, integration tests)
- T0006.1: DB Foundation (Postgres, dependencies, settings, session factory)

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
|   `-- api/
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

Dev/test dependencies are not declared separately in `pyproject.toml`; the current environment provides:
- `pytest`
- `pytest-asyncio`
- `pytest-mock`
- `anyio`
- `langsmith`

## Available scripts
No package scripts or `tool.*.scripts` entries are defined in `pyproject.toml`.

Practical commands from the repository layout:
- `uv run uvicorn src.api.app:app --reload`
- `uv run pytest`
- `docker compose up -d`
- `docker compose exec -T postgres psql -U internhunter -d internhunter -f scripts/init_clean_jobs.sql`
- `docker compose -f docker/docker-compose.yaml up --build`

## Build/test status
- Command run: `uv run --with pytest python -m pytest -q`
- Result: passed
- Summary: `7 passed in 2.02s`

## Known issues
- The repository appears to rely on import-time loading in `src/core/config.py`, which makes startup sensitive to working directory and missing config files.
- `main.py` is only a placeholder and does not start the FastAPI app.
- `trace_url` is always returned as `None` in `src/agents/service.py`, so tracing metadata is incomplete.
- `src/api/routes/query.py` converts all exceptions into a generic 500 response, which makes client-side debugging harder.
- `docker/docker-compose.yaml` still contains several `CHANGEME` secrets and placeholder credentials.
- `DATABASE_URL` is now required and must be set in the runtime environment before starting the app.
- `pytest` is still provided by the local environment in this repo snapshot, so the most reliable verification command is `uv run --with pytest python -m pytest -q`.

## Next recommended ticket
T0006: Milestone 6 - First Real SQL Tool
