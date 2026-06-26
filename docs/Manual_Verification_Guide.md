Manual Verification Guide

This document contains the required active verification steps for completed tickets. Do not assume a ticket works just because an automated build passes. Always execute manual checklists to catch obvious breakage before moving forward.

T0000: Milestone 0 - Foundation

* Run `uv run uvicorn src.api.app:app --reload` to boot the backend locally.
* Open `http://127.0.0.1:8000/health` in a browser or API client.
* Confirm the server starts cleanly and the health endpoint returns a successful JSON response.

T0001: Milestone 1 - Runnable Request Flow

* Run `uv run pytest tests/api/test_query.py` to verify the request-flow tests.
* Open `http://127.0.0.1:8000/docs` in the browser.
* Send a `POST /api/v1/agent/chat` request with a JSON body.
* Confirm the API returns a structured response that includes the answer and request metadata.

T0002: Milestone 2 - ReAct Agent Runtime

* Run `uv run pytest tests/agents/runtime/test_react_agent.py` to verify the runtime tests.
* Open `src/agents/runtime/react_agent.py` and inspect the agent execution wrapper.
* Confirm the runtime builds messages, calls the LangChain agent, and returns a readable final answer outside the API layer.

T0003: Milestone 3 - Self-Hosted Langfuse

* Run `docker compose -f docker/docker-compose.yaml up --build` to start the local observability stack.
* Open the Langfuse UI in a browser at the local web port.
* Confirm the stack starts successfully and the Langfuse UI is reachable locally.

T0004: Milestone 4 - Tracing Integration

* Start the app with `uv run uvicorn src.api.app:app --reload`.
* Start the Langfuse stack with `docker compose -f docker/docker-compose.yaml up`.
* Send one `POST /api/v1/agent/chat` request to the API.
* Open the Langfuse UI and confirm the request appears as a trace.
* Confirm the API response includes trace metadata when it is available.

T0005: Milestone 5 - Hardening

* Run `uv run pytest` to verify the full test suite.
* Break one required config value locally and restart the app.
* Confirm the app fails clearly and surfaces a consistent error for the invalid configuration or provider failure.
* Confirm the happy-path tests still pass after the hardening changes.

T0006.1: DB Foundation

* Run `docker compose up -d` from the repository root.
* Confirm the Postgres container is healthy with `docker ps`.
* Seed the schema with `docker compose exec -T postgres psql -U internhunter -d internhunter -f scripts/init_clean_jobs.sql`.
* Query `clean_jobs` with `docker compose exec -T postgres psql -U internhunter -d internhunter -c "SELECT * FROM clean_jobs LIMIT 5;"`.
* Start the app with `DATABASE_URL=postgresql+psycopg://internhunter:internhunter@localhost:5433/internhunter` in the environment.
* Open `http://127.0.0.1:8000/api/v1/health` and confirm the API returns an online health response.

T0006.2: Query result models

* Run `uv run pytest tests/services/query/test_models.py -v` and confirm 3 tests pass (`TableArtifact`, `QueryRefusal`, `QueryToolResult` serialization).
* Open `src/services/query/models.py` and confirm only whitespace/formatting changed, plus the `rows` type tightened to `list[list[object]]` to match the design doc — no field additions or behavioral changes.
* Run `uv run pytest -q` and confirm the full suite passes with no `ModuleNotFoundError` for `psycopg` or `langchain.messages` (these are now resolved by declaring `pytest`/`pytest-asyncio`/`pytest-mock` as dev dependencies in `pyproject.toml`).

T0006.3: Deterministic table formatter

* Run `uv run pytest tests/services/query/test_table_formatter.py -v` and confirm empty / single-row / multi-row / missing-key tests pass.
* In a Python REPL: `from src.services.query.table_formatter import format_rows`, then call it with `[]`, a single dict, and rows where a later row omits a key present in the first row — confirm missing values render as `None`.

T0006.4: Schema context + SQL-generation prompt

* Run `uv run pytest tests/services/query/test_schema_context.py tests/agents/runtime/test_prompts.py -v` and confirm all tests pass.
* In a Python REPL: `from src.services.query.schema_context import build_clean_jobs_schema_context; print(build_clean_jobs_schema_context())` — confirm output lists only `title`, `company`, `description`, `tech_stack` and no other columns.
* With `DATABASE_URL` set in the environment, in a Python REPL: `from src.agents.runtime.prompts import load_sql_generation_prompt; print(load_sql_generation_prompt())` — confirm the SQL-generation prompt text (SELECT-only, no fences, LIMIT required).
* Temporarily blank the `sql_generation` block in `config/prompts.yaml`, re-run the REPL check, and confirm `load_sql_generation_prompt()` raises a clear `ValueError`; then restore the block.

T0006.5: SQL validator (deterministic, read-only)

* Run `uv run pytest tests/services/query/test_sql_validator.py -v` and confirm all 13 tests pass.
* In a Python REPL: `from src.services.query.sql_validator import validate_sql`, then check:
  * `validate_sql("  SELECT title FROM clean_jobs LIMIT 10  ")` → `valid=True`.
  * `validate_sql("DROP TABLE clean_jobs")` → `valid=False` with a clear reason.
  * `validate_sql("SELECT * FROM clean_jobs; DELETE FROM clean_jobs")` → `valid=False` (multi-statement).
  * `validate_sql("SELECT * FROM pg_tables")` → `valid=False` (system table / not `clean_jobs`).
  * `validate_sql("SELECT title FROM clean_jobs -- comment")` → `valid=False` (comment injection).

T0006.6: SQL executor (sync, threadpool-friendly)

* Run `uv run pytest tests/services/query/test_executor.py -v` and confirm all 6 tests pass (row mapping, read-only-transaction-first, `ExecutorError` on `OperationalError`/`DBAPIError`, session closed on success/failure).
* With Postgres running (`docker compose up -d`) and `clean_jobs` seeded, in a Python REPL: `from src.services.query.executor import execute_validated_sql; execute_validated_sql("SELECT title, company FROM clean_jobs LIMIT 5")` — confirm it returns a `list[dict]`.
* Stop the Postgres container (`docker compose stop postgres`) and re-run the same call — confirm it raises `ExecutorError` instead of crashing or leaking a raw SQLAlchemy traceback; then restart Postgres.

T0006.7: query_clean_jobs LangChain tool adapter

* Run `uv run pytest tests/agents/tools/test_query_clean_jobs.py -v` and confirm all 4 tests pass (happy path, no-rows, validator-rejection, `ExecutorError`).
* With local Postgres running and `clean_jobs` seeded, in a Python REPL: `import asyncio; from src.agents.tools.query_clean_jobs import query_clean_jobs; asyncio.run(query_clean_jobs.ainvoke({"question": "What companies use Python?"}))` — confirm it returns a readable string, not a stack trace.
* Force a validator rejection (e.g. monkeypatch `generate_sql` to return `"DROP TABLE clean_jobs"`) and confirm the tool returns a refusal string (`"I can't run that query: ..."`) instead of raising.

T0006.8: Register tool in agent runtime + strengthen system prompt

* Run `uv run pytest tests/agents/runtime/test_factory.py -v` and confirm the tool-registration test passes.
* Run `uv run pytest tests/ -v` and confirm no regressions across the full suite.
* In a Python REPL: `from src.agents.runtime.factory import agent_factory; agent = agent_factory()` — confirm it constructs without error and both `get_current_time` and `query_clean_jobs` are present among the agent's bound tools.
* With local Postgres running and `clean_jobs` seeded, ask the agent "What tech stack does Acme Corp use?" and confirm (via trace/tool-call log) it calls `query_clean_jobs` rather than answering from general knowledge.
* Ask the agent "What time is it?" and confirm the clock tool path is unaffected.

T0006.9: Keep public API answer-only

* Run `uv run pytest tests/api/test_query.py -v` and confirm all 3 tests pass (clock-tool path, job-data path, service-failure path) — both response-shape tests assert the exact key set `{answer, session_id, trace_id, trace_url}` with no `sql`/`table` keys.
* With the local stack running (`docker compose up -d`), `POST /api/v1/agent/query` with `{"query": "What tech stack does Acme use?"}` and inspect the raw JSON — confirm only `answer`, `session_id`, `trace_id`, `trace_url` are present and `answer` reads as natural language, not a raw table/SQL dump.
* Repeat with `{"query": "what time is it?"}` and confirm the same response shape.

T0006.10: End-to-end manual verification

* Run `docker compose up -d`, then `docker compose ps` and confirm `postgres` and `api` both report `healthy`.
* `POST /api/v1/agent/query` with `{"query": "What companies use Python?"}` — confirm a readable natural-language answer, then look up the returned `trace_id` in Langfuse (`GET /api/public/traces/<trace_id>` with basic auth, or the Langfuse UI) and confirm a `query_clean_jobs` tool call appears in the message trace.
* `POST /api/v1/agent/query` with `{"query": "what time is it?"}` — confirm the answer and confirm via the trace that `get_current_time` (not `query_clean_jobs`) was called.
* Force the refusal path directly at the tool boundary (REPL): monkeypatch `generate_sql` to return `"DROP TABLE clean_jobs"` or `"SELECT * FROM pg_tables"` and call `query_clean_jobs.ainvoke(...)` — confirm a graceful refusal string (`"I can't run that query: ..."`), not a crash. (Asking the agent to delete/inspect schema in plain English typically gets refused by the model before it ever calls the tool, so this boundary check is the reliable way to exercise `validate_sql`'s rejection path.)
* Confirm Langfuse is reachable (`GET /` → 200) and that both the `query_clean_jobs` and `get_current_time` traces are listed via `GET /api/public/traces`.

T0007.1: Startup lifecycle + async checkpointer foundation

* Run `uv sync` and confirm `langgraph-checkpoint-postgres` and `psycopg-pool` install without conflicts.
* With Postgres up (`docker compose up -d`), start the API (`docker compose up -d --build api` or `uv run uvicorn src.api.app:app`) and confirm it boots cleanly — no import-time agent construction error, logs show `Application startup complete.` with no traceback.
* Connect to the app Postgres (`docker compose exec -T postgres psql -U internhunter -d internhunter -c "\dt"`) and confirm the checkpointer tables (`checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, `checkpoint_migrations`) were created by `setup()`.
* `POST /api/v1/agent/query` with `{"query": "what time is it?"}` and `{"query": "What companies use Python?"}` — confirm both still return the same answer-only response shape (`answer`, `session_id`, `trace_id`, `trace_url`), now served via the app-state runtime instead of an import-time singleton.
* Stop the API container (`docker compose stop api`) and confirm the shutdown logs show `Waiting for application shutdown.` / `Application shutdown complete.` with no errors or warnings (the checkpointer connection pool closes cleanly).

T0007.2: Wire checkpointer + session_id -> thread_id lifecycle

* Run `uv run pytest tests/api/test_query.py -v` and confirm the supplied-id and generated-id cases both pass.
* With the stack up (`docker compose up -d`, API running), `POST /api/v1/agent/query` with `{"query": "what time is it?"}` and no `session_id` — confirm the response contains a non-null `session_id` (a UUID).
* `POST /api/v1/agent/query` with that returned `session_id` and a refining question (e.g. first "What companies use Python?", then "Which of those also use SQL?") — confirm the agent's answer reflects awareness of the prior turn (memory is working).
* `POST /api/v1/agent/query` with an explicit `session_id` and confirm the same id is echoed back in the response.
* (Optional) Inspect the checkpointer tables in Postgres (`docker compose exec -T postgres psql -U internhunter -d internhunter -c "SELECT thread_id FROM checkpoints;"`) and confirm rows keyed by the returned `session_id` appear after a request.
* Confirm Langfuse still receives traces with session metadata (callbacks were not clobbered by the thread_id merge).

T0007.3: Native context trimming (count cap)

* Run `uv run pytest tests/agents/runtime/test_trimming.py -v` and confirm the config-validation, sync-trim, async-trim, and "state intact" cases all pass.
* Set `agent.memory.max_messages` to a small value (e.g. `4`) in `config/settings.yaml` and rebuild the API (`docker compose build --no-cache api && docker compose up -d api` — the config is baked into the image, so a no-cache rebuild is required to pick up the change).
* On one `session_id`, hold a conversation with more turns than the cap: turn 1 establishes a fact (e.g. "Remember this code word: BANANA42"), then run two more unrelated turns, then ask "What was the code word I gave you earlier?" — confirm the agent no longer knows it (the oldest turn fell outside the cap), while the recent turns still answered normally and nothing 500s.
* Confirm the full history is still persisted (trimming only affected the model input, not storage): `docker compose exec -T postgres psql -U internhunter -d internhunter -t -c "SELECT count(*) FROM checkpoint_blobs WHERE position('BANANA42' in encode(blob, 'escape')) > 0;"` and confirm a non-zero count — the trimmed-out fact is still in the checkpointer.
* Restore `agent.memory.max_messages` to its normal value (`20`) and rebuild; confirm a normal short conversation (under the cap) behaves exactly as before.
