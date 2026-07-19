# Manual Verification Guide

The **central, canonical home** for the manual-verification steps of every completed ticket. Do not assume a ticket works just because an automated build passes — run the checklist here to catch obvious breakage first.

Each ticket's own "Manual check" lines in [`Tickets.md`](Tickets.md) are the *planned* intent; this file collects them as runnable checklists. Full dated live-pass logs (observed answers, raw query output, defect narratives) live in [`archive/Manual_Verification_History.md`](archive/Manual_Verification_History.md). Paths and commands below are grounded against the repo as implemented.

## Milestone 0 — Foundation

* Run `uv run uvicorn src.api.app:app --reload` to boot the backend locally.
* Open `http://127.0.0.1:8000/health` in a browser or API client.
* Confirm the server starts cleanly and the health endpoint returns a successful JSON response.

## Milestone 1 — Runnable Request Flow

* Run `uv run pytest tests/api/test_query.py` to verify the request-flow tests.
* Open `http://127.0.0.1:8000/docs` in the browser.
* Send a `POST /api/v1/agent/chat` request with a JSON body.
* Confirm the API returns a structured response that includes the answer and request metadata.

## Milestone 2 — ReAct Agent Runtime

* Run `uv run pytest tests/agents/runtime/test_react_agent.py` to verify the runtime tests.
* Open `src/agents/runtime/react_agent.py` and inspect the agent execution wrapper.
* Confirm the runtime builds messages, calls the LangChain agent, and returns a readable final answer outside the API layer.

## Milestone 3 — Self-Hosted Langfuse

* Run `docker compose -f infra/docker-compose.yaml up --build` to start the local observability stack.
* Open the Langfuse UI in a browser at the local web port.
* Confirm the stack starts successfully and the Langfuse UI is reachable locally.

## Milestone 4 — Tracing Integration

* Start the app with `uv run uvicorn src.api.app:app --reload`.
* Start the Langfuse stack with `docker compose -f infra/docker-compose.yaml up`.
* Send one `POST /api/v1/agent/chat` request to the API.
* Open the Langfuse UI and confirm the request appears as a trace.
* Confirm the API response includes trace metadata when it is available.

## Milestone 5 — Hardening

* Run `uv run pytest` to verify the full test suite.
* Break one required config value locally and restart the app.
* Confirm the app fails clearly and surfaces a consistent error for the invalid configuration or provider failure.
* Confirm the happy-path tests still pass after the hardening changes.

## Milestone 6 — First Real SQL Tool

### T0006.1: DB Foundation

* Run `docker compose up -d` from the repository root.
* Confirm the Postgres container is healthy with `docker ps`.
* Seed the schema with `docker compose exec -T postgres psql -U internhunter -d internhunter -f scripts/init_clean_jobs.sql`.
* Query `clean_jobs` with `docker compose exec -T postgres psql -U internhunter -d internhunter -c "SELECT * FROM clean_jobs LIMIT 5;"`.
* Start the app with `DATABASE_URL=postgresql+psycopg://internhunter:internhunter@localhost:5433/internhunter` in the environment.
* Open `http://127.0.0.1:8000/api/v1/health` and confirm the API returns an online health response.

### T0006.2: Query result models

* Run `uv run pytest tests/services/query/test_models.py -v` and confirm 3 tests pass (`TableArtifact`, `QueryRefusal`, `QueryToolResult` serialization).
* Open `src/services/query/models.py` and confirm only whitespace/formatting changed, plus the `rows` type tightened to `list[list[object]]` to match the design doc — no field additions or behavioral changes.
* Run `uv run pytest -q` and confirm the full suite passes with no `ModuleNotFoundError` for `psycopg` or `langchain.messages` (these are now resolved by declaring `pytest`/`pytest-asyncio`/`pytest-mock` as dev dependencies in `pyproject.toml`).

### T0006.3: Deterministic table formatter

* Run `uv run pytest tests/services/query/test_table_formatter.py -v` and confirm empty / single-row / multi-row / missing-key tests pass.
* In a Python REPL: `from src.services.query.table_formatter import format_rows`, then call it with `[]`, a single dict, and rows where a later row omits a key present in the first row — confirm missing values render as `None`.

### T0006.4: Schema context + SQL-generation prompt

* Run `uv run pytest tests/services/query/test_schema_context.py tests/agents/runtime/test_prompts.py -v` and confirm all tests pass.
* In a Python REPL: `from src.agents.runtime.prompts import load_schema_context; print(load_schema_context())` — confirm output lists only `title`, `company`, `description`, `tech_stack` and no other columns. (Note: `src/services/query/schema_context.py` was retired in T0008.2; the schema context now lives in `config/prompts.yaml`.)
* With `DATABASE_URL` set in the environment, in a Python REPL: `from src.agents.runtime.prompts import load_sql_generation_prompt; print(load_sql_generation_prompt())` — confirm the SQL-generation prompt text (SELECT-only, no fences, LIMIT required).
* Temporarily blank the `sql_generation` block in `config/prompts.yaml`, re-run the REPL check, and confirm `load_sql_generation_prompt()` raises a clear `ValueError`; then restore the block.

### T0006.5: SQL validator (deterministic, read-only)

* Run `uv run pytest tests/services/query/test_sql_validator.py -v` and confirm all 13 tests pass.
* In a Python REPL: `from src.services.query.sql_validator import validate_sql`, then check:
  * `validate_sql("  SELECT title FROM clean_jobs LIMIT 10  ")` → `valid=True`.
  * `validate_sql("DROP TABLE clean_jobs")` → `valid=False` with a clear reason.
  * `validate_sql("SELECT * FROM clean_jobs; DELETE FROM clean_jobs")` → `valid=False` (multi-statement).
  * `validate_sql("SELECT * FROM pg_tables")` → `valid=False` (system table / not `clean_jobs`).
  * `validate_sql("SELECT title FROM clean_jobs -- comment")` → `valid=False` (comment injection).

### T0006.6: SQL executor (sync, threadpool-friendly)

* Run `uv run pytest tests/services/query/test_executor.py -v` and confirm all 6 tests pass (row mapping, read-only-transaction-first, `ExecutorError` on `OperationalError`/`DBAPIError`, session closed on success/failure).
* With Postgres running (`docker compose up -d`) and `clean_jobs` seeded, in a Python REPL: `from src.services.query.executor import execute_validated_sql; execute_validated_sql("SELECT title, company FROM clean_jobs LIMIT 5")` — confirm it returns a `list[dict]`.
* Stop the Postgres container (`docker compose stop postgres`) and re-run the same call — confirm it raises `ExecutorError` instead of crashing or leaking a raw SQLAlchemy traceback; then restart Postgres.

### T0006.7: query_clean_jobs LangChain tool adapter

* Run `uv run pytest tests/agents/tools/test_query_clean_jobs.py -v` and confirm all 4 tests pass (happy path, no-rows, validator-rejection, `ExecutorError`).
* With local Postgres running and `clean_jobs` seeded, in a Python REPL: `import asyncio; from src.agents.tools.query_clean_jobs import query_clean_jobs; asyncio.run(query_clean_jobs.ainvoke({"question": "What companies use Python?"}))` — confirm it returns a readable string, not a stack trace.
* Force a validator rejection (e.g. monkeypatch `generate_sql` to return `"DROP TABLE clean_jobs"`) and confirm the tool returns a refusal string (`"I can't run that query: ..."`) instead of raising.

### T0006.8: Register tool in agent runtime + strengthen system prompt

* Run `uv run pytest tests/agents/runtime/test_factory.py -v` and confirm the tool-registration test passes.
* Run `uv run pytest tests/ -v` and confirm no regressions across the full suite.
* In a Python REPL: `from src.agents.runtime.factory import agent_factory; agent = agent_factory()` — confirm it constructs without error and both `get_current_time` and `query_clean_jobs` are present among the agent's bound tools.
* With local Postgres running and `clean_jobs` seeded, ask the agent "What tech stack does Acme Corp use?" and confirm (via trace/tool-call log) it calls `query_clean_jobs` rather than answering from general knowledge.
* Ask the agent "What time is it?" and confirm the clock tool path is unaffected.

### T0006.9: Keep public API answer-only

* Run `uv run pytest tests/api/test_query.py -v` and confirm all 3 tests pass (clock-tool path, job-data path, service-failure path) — both response-shape tests assert the exact key set `{answer, session_id, trace_id, trace_url}` with no `sql`/`table` keys.
* With the local stack running (`docker compose up -d`), `POST /api/v1/agent/chat` with `{"query": "What tech stack does Acme use?"}` and inspect the raw JSON — confirm only `answer`, `session_id`, `trace_id`, `trace_url` are present and `answer` reads as natural language, not a raw table/SQL dump.
* Repeat with `{"query": "what time is it?"}` and confirm the same response shape.

### T0006.10: End-to-end manual verification

* Run `docker compose up -d`, then `docker compose ps` and confirm `postgres` and `api` both report `healthy`.
* `POST /api/v1/agent/chat` with `{"query": "What companies use Python?"}` — confirm a readable natural-language answer, then look up the returned `trace_id` in Langfuse (`GET /api/public/traces/<trace_id>` with basic auth, or the Langfuse UI) and confirm a `query_clean_jobs` tool call appears in the message trace.
* `POST /api/v1/agent/chat` with `{"query": "what time is it?"}` — confirm the answer and confirm via the trace that `get_current_time` (not `query_clean_jobs`) was called.
* Force the refusal path directly at the tool boundary (REPL): monkeypatch `generate_sql` to return `"DROP TABLE clean_jobs"` or `"SELECT * FROM pg_tables"` and call `query_clean_jobs.ainvoke(...)` — confirm a graceful refusal string (`"I can't run that query: ..."`), not a crash. (Asking the agent to delete/inspect schema in plain English typically gets refused by the model before it ever calls the tool, so this boundary check is the reliable way to exercise `validate_sql`'s rejection path.)
* Confirm Langfuse is reachable (`GET /` → 200) and that both the `query_clean_jobs` and `get_current_time` traces are listed via `GET /api/public/traces`.

## Milestone 7 — Conversation Memory

### T0007.1: Startup lifecycle + async checkpointer foundation

* Run `uv sync` and confirm `langgraph-checkpoint-postgres` and `psycopg-pool` install without conflicts.
* With Postgres up (`docker compose up -d`), start the API (`docker compose up -d --build api` or `uv run uvicorn src.api.app:app`) and confirm it boots cleanly — no import-time agent construction error, logs show `Application startup complete.` with no traceback.
* Connect to the app Postgres (`docker compose exec -T postgres psql -U internhunter -d internhunter -c "\dt"`) and confirm the checkpointer tables (`checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, `checkpoint_migrations`) were created by `setup()`.
* `POST /api/v1/agent/chat` with `{"query": "what time is it?"}` and `{"query": "What companies use Python?"}` — confirm both still return the same answer-only response shape (`answer`, `session_id`, `trace_id`, `trace_url`), now served via the app-state runtime instead of an import-time singleton.
* Stop the API container (`docker compose stop api`) and confirm the shutdown logs show `Waiting for application shutdown.` / `Application shutdown complete.` with no errors or warnings (the checkpointer connection pool closes cleanly).

### T0007.2: Wire checkpointer + session_id -> thread_id lifecycle

* Run `uv run pytest tests/api/test_query.py -v` and confirm the supplied-id and generated-id cases both pass.
* With the stack up (`docker compose up -d`, API running), `POST /api/v1/agent/chat` with `{"query": "what time is it?"}` and no `session_id` — confirm the response contains a non-null `session_id` (a UUID).
* `POST /api/v1/agent/chat` with that returned `session_id` and a refining question (e.g. first "What companies use Python?", then "Which of those also use SQL?") — confirm the agent's answer reflects awareness of the prior turn (memory is working).
* `POST /api/v1/agent/chat` with an explicit `session_id` and confirm the same id is echoed back in the response.
* (Optional) Inspect the checkpointer tables in Postgres (`docker compose exec -T postgres psql -U internhunter -d internhunter -c "SELECT thread_id FROM checkpoints;"`) and confirm rows keyed by the returned `session_id` appear after a request.
* Confirm Langfuse still receives traces with session metadata (callbacks were not clobbered by the thread_id merge).

### T0007.3: Native context trimming (count cap)

* Run `uv run pytest tests/agents/runtime/test_trimming.py -v` and confirm the config-validation, sync-trim, async-trim, and "state intact" cases all pass.
* Set `agent.memory.max_messages` to a small value (e.g. `4`) in `config/settings.yaml` and rebuild the API (`docker compose build --no-cache api && docker compose up -d api` — the config is baked into the image, so a no-cache rebuild is required to pick up the change).
* On one `session_id`, hold a conversation with more turns than the cap: turn 1 establishes a fact (e.g. "Remember this code word: BANANA42"), then run two more unrelated turns, then ask "What was the code word I gave you earlier?" — confirm the agent no longer knows it (the oldest turn fell outside the cap), while the recent turns still answered normally and nothing 500s.
* Confirm the full history is still persisted (trimming only affected the model input, not storage): `docker compose exec -T postgres psql -U internhunter -d internhunter -t -c "SELECT count(*) FROM checkpoint_blobs WHERE position('BANANA42' in encode(blob, 'escape')) > 0;"` and confirm a non-zero count — the trimmed-out fact is still in the checkpointer.
* Restore `agent.memory.max_messages` to its normal value (`20`) and rebuild; confirm a normal short conversation (under the cap) behaves exactly as before.

### T0007.4: Memory tests, manual verification, and doc status flips

* Run `uv run pytest tests/ -v` and confirm the full suite passes, including the five memory capabilities in `tests/agents/runtime/test_memory.py` (multi-turn refinement, session isolation, generated-id returned, persistence across restart, trimming cap).
* With the stack up (`docker compose up -d`, API running), hold a two-turn refinement on a *generated* `session_id`: first `POST /api/v1/agent/chat` with `{"query": "What companies use Python?"}` and no `session_id`; note the returned `session_id`, then `POST` again with that id and `{"query": "Which of those also use SQL?"}` — confirm turn 2's answer reflects turn-1 context (memory is working).
* Restart the service (`docker compose restart api`) and `POST` again with the *same* `session_id` and a follow-up — confirm the conversation resumes (history survived the restart because it lives in Postgres, not process memory).
* Start a *second* `session_id` (omit it to get a fresh one) and ask an unrelated question — confirm it does not see the first session's history.
* Look up the returned `trace_id`s in Langfuse and confirm one trace per request, grouped by `session_id` (`langfuse_session_id` metadata).
* Re-read `docs/MVP_Technical_Design.md` §2.4, §3, §4, §6 and confirm memory now reads as *implemented* (no lingering `planned` tags for memory), and that `docs/Repo_Current_State.md` lists T0007.1–T0007.4 as completed.

## Milestone 8 — System Prompt & Persona Refinement

> The dated live-pass observed-results log (T0008.3) is archived in [`archive/Manual_Verification_History.md`](archive/Manual_Verification_History.md).

### T0008.1: Resumi persona + on-topic policy + honesty rules

* In a Python REPL: `from src.agents.runtime.prompts import load_system_prompt; print(load_system_prompt().content)` — confirm the output opens with "You are Resumi" and includes sections for on-topic policy, the available-fields gate, refinement, and honesty rules.
* Run `uv run pytest tests/ -v` — confirm 66 tests pass, no regressions.
* With the stack up (`docker compose up -d`), exercise each behavior via `POST /api/v1/agent/chat`:
  * `{"query": "hi"}` or `{"query": "what can you do?"}` → Resumi introduces itself and lists internship/job postings as its focus.
  * `{"query": "What companies use Python?"}` → routes to `query_clean_jobs`, returns a data-backed answer (not from general knowledge).
  * `{"query": "What's the salary for that role?"}` → Resumi replies that salary is not in the data; does not guess.
  * Two-turn refinement on the same `session_id`: `"Show me backend roles"` then `"only the Python ones"` → turn 2 resolves "those" from turn 1's context.
  * `{"query": "Write my resume"}` → Resumi declines, frames resume help as a future phase, redirects to postings.
  * `{"query": "what's the weather?"}` → Resumi politely declines and redirects to internship postings.

### T0008.2: SQL-generation prompt hardening + schema context to YAML

* `grep -rn "schema_context" src/ tests/` — confirm only `src/agents/runtime/prompts.py` and `tests/agents/runtime/test_prompts.py` appear; no reference to the deleted `src/services/query/schema_context.py`.
* In a Python REPL:
  ```python
  from src.agents.runtime.prompts import load_schema_context, load_sql_generation_prompt
  print(load_schema_context())   # must mention clean_jobs, title, company, description, tech_stack, comma-separated
  print(load_sql_generation_prompt())  # must mention ILIKE and tech_stack
  ```
* Temporarily blank `prompts.schema_context` in `config/prompts.yaml` (set to empty string) and confirm `load_schema_context()` raises `ValueError`; restore afterward.
* `uv run pytest tests/ -v` — confirm 70 tests pass, including all six `LoadSchemaContextTests` in `tests/agents/runtime/test_prompts.py`.
* With the stack up and `clean_jobs` seeded (`docker compose up -d`), ask `POST /api/v1/agent/chat` with `{"query": "What internships use Python?"}` — inspect the Langfuse trace and confirm the generated SQL uses `tech_stack ILIKE '%Python%'`, not `tech_stack = 'Python'`, and that results are returned correctly.

## Milestone 9 — Data Ingestion (VietnamWorks)

> The dated live-pass observed-results log (T0009.8) is archived in [`archive/Manual_Verification_History.md`](archive/Manual_Verification_History.md).

### T0009.1: Schema & migration — raw_jobs + enriched clean_jobs

1. Start Postgres:
   docker compose up -d
   Confirm: `docker compose ps` shows postgres healthy.

2. Run init script:
   docker compose exec -T postgres psql -U internhunter -d internhunter -f scripts/init_db.sql
   Confirm: no errors printed; output shows `CREATE TABLE` twice.

3. Inspect raw_jobs schema:
   docker compose exec -T postgres psql -U internhunter -d internhunter -c "\d raw_jobs"
   Confirm columns: id (bigint, identity PK), source (text not null), external_id (text not null),
   source_url (text nullable), raw_payload (jsonb not null), content_hash (text not null),
   fetched_at (timestamptz not null default now()).
   Confirm UNIQUE constraint on (source, external_id).

4. Inspect clean_jobs schema:
   docker compose exec -T postgres psql -U internhunter -d internhunter -c "\d clean_jobs"
   Confirm columns: id (bigint, identity PK), source, external_id, source_url, title, company,
   role (not null), description (nullable), tech_stack (nullable), job_level (nullable),
   location (nullable), posted_date (date nullable), is_internship (boolean not null default false),
   salary_min (numeric nullable), salary_max (numeric nullable), salary_currency (text nullable),
   is_salary_negotiable (boolean not null default false).
   Confirm UNIQUE constraint on (source, external_id).
   Confirm NO salary/requirement/benefits text columns.

5. Confirm tables are empty:
   docker compose exec -T postgres psql -U internhunter -d internhunter -c "SELECT count(*) FROM clean_jobs;"
   Expected: 0
   docker compose exec -T postgres psql -U internhunter -d internhunter -c "SELECT count(*) FROM raw_jobs;"
   Expected: 0

6. Re-run init script (idempotency):
   docker compose exec -T postgres psql -U internhunter -d internhunter -f scripts/init_db.sql
   Confirm: no errors (CREATE TABLE IF NOT EXISTS is a no-op on the second run).

7. Verify import — no DB connection triggered:
   python -c "import src.services.ingestion.models; print('import OK')"
   Confirm: prints "import OK" with no connection error, even when DATABASE_URL is unset.

8. Run tests:
   uv run pytest -q
   Confirm: 70 passed, 0 failed.

### T0009.2: Config & ingestion models

1. Verify ingestion.yaml parses and is reachable via settings:
   uv run python -c "
   from src.core.config import settings
   i = settings.ingestion_yaml
   print(len(i['queries']), 'queries')
   print('job_function:', i['job_function'])
   print(len(i['tech_dictionary']), 'techs')
   print('roles:', list(i['role_taxonomy'].keys()))
   print('api url:', i['api']['url'])
   "
   Expected: 8 queries, job_function: {'parent_id': 5, 'child_ids': [27]}, ~69 techs,
   6 canonical roles (AI Engineer / Data Scientist / Data Engineer / Data Analyst /
   ML Engineer / Software Developer), correct API URL.

2. Verify Pydantic models expose the right fields with no DB connection:
   uv run python -c "
   from src.services.ingestion.models import RawPosting, NormalizedJob
   print(list(RawPosting.model_fields.keys()))
   print(list(NormalizedJob.model_fields.keys()))
   "
   Expected RawPosting fields: source, external_id, source_url, raw_payload, content_hash
   Expected NormalizedJob fields: source, external_id, source_url, title, company, role,
   description, tech_stack, job_level, location, posted_date, is_internship,
   salary_min, salary_max, salary_currency, is_salary_negotiable

3. Quick instantiation check — no DB connection triggered:
   uv run python -c "
   from src.services.ingestion.models import RawPosting, NormalizedJob
   r = RawPosting(source='vietnamworks', external_id='1', source_url=None, raw_payload={}, content_hash='x')
   n = NormalizedJob(source='vietnamworks', external_id='1', title='Data Engineer',
       company='Acme', role='Data Engineer', is_internship=False, is_salary_negotiable=False)
   print('RawPosting:', r.source, r.external_id)
   print('NormalizedJob:', n.title, n.role)
   "
   Confirm both print without error and no database connection is opened.

4. Confirm existing agent: block in settings.yaml is unchanged:
   uv run python -c "
   from src.core.config import settings
   print(settings.config_yaml['agent']['provider'])
   "
   Expected: groq

5. Run tests:
   uv run pytest -q
   Confirm: 70 passed, 0 failed.

### T0009.3: JobSource interface + VietnamWorksSource adapter

1. Verify clean import — no network call at import time:
   uv run python -c "from src.services.ingestion.sources.vietnamworks import VietnamWorksSource; print('import ok')"
   Expected: "import ok" with no error and no outbound HTTP.

2. Run the adapter unit tests (no live network):
   uv run pytest -q tests/services/ingestion/
   Expected: 14 passed.

3. Run the full suite to confirm no regressions:
   uv run pytest -q
   Expected: 84 passed.

4. (Optional live smoke — requires network; not part of CI)
   uv run python -c "
   from src.services.ingestion.sources.vietnamworks import VietnamWorksSource
   source = VietnamWorksSource()
   for i, p in enumerate(source.fetch()):
       print(p.external_id, p.source_url, p.content_hash[:12])
       if i >= 4:
           break
   "
   Expected: 5 RawPosting lines, each with a real external_id, a vietnamworks.com URL,
   and a non-empty content_hash prefix. Re-run on the same payload → identical hash.

5. Confirm spike is unchanged:
   git diff HEAD -- scripts/scrape_spike.py
   Expected: no output (file untouched).

6. Confirm config/ingestion.yaml has no new keys:
   uv run python -c "
   from src.core.config import settings
   print(sorted(settings.ingestion_yaml.keys()))
   "
   Expected: same keys as after T0009.2 (api, city_alias_map, job_function, max_jobs,
   queries, role_taxonomy, tech_dictionary).

### T0009.4: Raw landing — upsert RawPosting into raw_jobs

1. Run unit tests (no DB required):
   uv run pytest -q tests/services/ingestion/test_raw_store.py
   Expected: 9 passed.

2. Run the full suite to confirm no regressions:
   uv run pytest -q
   Expected: 93 passed.

3. Verify import triggers no DB connection:
   uv run python -c "from src.services.ingestion.raw_store import upsert_raw_postings; print('import ok')"
   Expected: "import ok" with no error, even when DATABASE_URL is unset or Postgres is down.

4. (Live idempotency check — requires Postgres)
   Start Postgres and init schema:
     docker compose up -d
     docker compose exec -T postgres psql -U internhunter -d internhunter -f scripts/init_db.sql

   In a Python REPL (with DATABASE_URL set):
     from src.services.ingestion.models import RawPosting
     from src.services.ingestion.raw_store import upsert_raw_postings

     postings = [
         RawPosting(source="vietnamworks", external_id="job-001", source_url="https://example.com/1",
                    raw_payload={"title": "Intern A"}, content_hash="hash-a"),
         RawPosting(source="vietnamworks", external_id="job-002", source_url="https://example.com/2",
                    raw_payload={"title": "Intern B"}, content_hash="hash-b"),
     ]
     print(upsert_raw_postings(postings))   # expect: 2

   Confirm row count:
     docker compose exec -T postgres psql -U internhunter -d internhunter -c "SELECT count(*) FROM raw_jobs;"
     Expected: 2

5. Confirm idempotency — re-run with identical postings:
   print(upsert_raw_postings(postings))   # expect: 2 (returns count, no duplicate key error)
   docker compose exec -T postgres psql -U internhunter -d internhunter -c "SELECT count(*) FROM raw_jobs;"
   Expected: still 2

### T0009.5: Normalize + transform — pure function pipeline

1. Run unit tests (no DB, no network required):
   uv run pytest -q tests/services/ingestion/
   Expected: 100 passed (adapter + raw_store + transform + normalize tests).

2. Verify clean import — no DB or network side effects:
   uv run python -c "from src.services.ingestion.normalize.vietnamworks import to_normalized_job; print('import ok')"
   Expected: "import ok" with no error, even when DATABASE_URL is unset or Postgres is down.

3. REPL smoke-test against the fixture:
   uv run python -c "
   import json; from pathlib import Path
   from src.services.ingestion.normalize.vietnamworks import to_normalized_job
   jobs = {j['jobId']: j for j in json.loads(Path('tests/services/ingestion/fixtures/vietnamworks_raw.json').read_text(encoding='utf-8'))['data']}

   j1 = to_normalized_job(jobs[1001])
   print('role:', j1.role)               # expect: Data Scientist
   print('location:', j1.location)       # expect: Ho Chi Minh City, Hanoi (multi-city)
   print('tech_stack:', j1.tech_stack)   # expect: Python, SQL (comma-separated canonical names)
   print('salary:', j1.salary_min, j1.salary_max, j1.salary_currency)  # expect: 1500.0 2500.0 USD
   print('negotiable:', j1.is_salary_negotiable)  # expect: False
   print('posted_date:', j1.posted_date)           # expect: None
   print()

   j2 = to_normalized_job(jobs[1002])   # hidden-salary Marketing Manager
   print('hidden salary_min:', j2.salary_min)      # expect: None
   print('hidden negotiable:', j2.is_salary_negotiable)  # expect: True
   print()

   j3 = to_normalized_job(jobs[1003])   # intern Data Engineer
   print('intern is_internship:', j3.is_internship)  # expect: True
   print('intern role:', j3.role)                     # expect: Data Engineer

   j4 = to_normalized_job(jobs[1004])
   print('PM role:', j4.role)          # expect: Other (no taxonomy keyword match)
   "
   Confirm each expected value printed above.

4. Confirm transform functions work standalone:
   uv run python -c "
   from src.services.ingestion.transform import (
       html_to_text, find_tech_stack, classify_role, normalize_location, derive_is_internship
   )
   print(html_to_text('<p>Hello &amp; World</p>'))  # Hello & World
   print(find_tech_stack('Python', 'uses Airflow and Docker'))  # Python, Airflow, Docker
   print(find_tech_stack('Experience with Keras'))  # Keras — NOT R (word-boundary guard)
   print(classify_role('Machine Learning Engineer', None))  # ML Engineer
   print(classify_role('Product Owner', None))              # Other
   print(normalize_location('TPHCM'))                       # Ho Chi Minh City
   print(normalize_location('Hồ Chí Minh', 'Hà Nội'))     # Ho Chi Minh City, Hanoi
   print(normalize_location('Unknown City'))                # Other
   print(derive_is_internship('Intern', None))              # True
   print(derive_is_internship('Senior', 'Chuyên viên'))     # False
   "

5. Confirm fixture extension is additive (adapter tests still pass):
   uv run pytest -q tests/services/ingestion/test_vietnamworks.py
   Expected: 14 passed (the new benefits/workingLocations fields in job 1001 are
   reflected equally in both posting.raw_payload and the fixture expectation, so
   test_raw_payload_is_verbatim still holds).

6. Confirm update on changed payload:
   changed = [
       RawPosting(source="vietnamworks", external_id="job-001", source_url="https://example.com/1",
                  raw_payload={"title": "Intern A UPDATED"}, content_hash="hash-a-v2"),
   ]
   print(upsert_raw_postings(changed))   # expect: 1

   docker compose exec -T postgres psql -U internhunter -d internhunter \
     -c "SELECT external_id, raw_payload->>'title', content_hash, fetched_at FROM raw_jobs ORDER BY external_id;"
   Expected:
     - job-001: title = "Intern A UPDATED", content_hash = "hash-a-v2", fetched_at advanced
     - job-002: unchanged
     - count still 2

### T0009.6: Loader — idempotent replace of clean_jobs

1. Run unit tests (no DB, no network):
   uv run pytest -q tests/services/ingestion/test_clean_store.py tests/services/ingestion/test_loader.py
   Expected: 14 passed.

2. Run the full suite to confirm no regressions:
   uv run pytest -q
   Expected: 184 passed, 4 subtests passed.

3. Verify import triggers no DB or network connection:
   uv run python -c "from src.services.ingestion.loader import run_ingestion; print('import ok')"
   Expected: "import ok" with no error, even when DATABASE_URL is unset or Postgres is down.

4. (Live end-to-end — requires Postgres + network)
   Start Postgres and init schema:
     docker compose up -d
     docker compose exec -T postgres psql -U internhunter -d internhunter -f scripts/init_db.sql

   Run the full pipeline:
     uv run python -m src.services.ingestion.loader
   Expected: prints something like {'fetched': N, 'raw_upserted': N, 'clean_loaded': N} with N > 0.

5. Confirm clean_jobs is populated:
   docker compose exec -T postgres psql -U internhunter -d internhunter -c "SELECT count(*) FROM clean_jobs;"
   Expected: N > 0 (matches fetched count)
   docker compose exec -T postgres psql -U internhunter -d internhunter -c "SELECT count(*) FROM raw_jobs;"
   Expected: N > 0

6. Spot-check a row:
   docker compose exec -T postgres psql -U internhunter -d internhunter \
     -c "SELECT source, role, location, tech_stack, is_salary_negotiable, salary_min FROM clean_jobs LIMIT 3;"
   Confirm: source = 'vietnamworks'; role is a canonical value (e.g. Data Scientist / Data Engineer / Other);
   location is a canonical city name or "Other"; tech_stack is comma-separated or NULL;
   rows with hidden salary show is_salary_negotiable = true and NULL salary_min.

7. Confirm idempotency — re-run loader:
   uv run python -m src.services.ingestion.loader
   docker compose exec -T postgres psql -U internhunter -d internhunter -c "SELECT count(*) FROM clean_jobs;"
   Expected: same count as after first run (replace is atomic; row count identical after re-run).

8. Confirm raw_jobs accumulates (never truncated):
   docker compose exec -T postgres psql -U internhunter -d internhunter -c "SELECT count(*) FROM raw_jobs;"
   Expected: same count (or more if any hashes changed); raw rows are never deleted.

9. Confirm empty-fetch guard — clean_jobs untouched if source returns nothing:
   In Python REPL (with DB up):
     from src.services.ingestion.clean_store import replace_clean_jobs
     result = replace_clean_jobs([])
     print(result)   # 0
   Then confirm clean_jobs still has the same row count as step 5 (TRUNCATE was NOT executed).

### T0009.7: Agent-layer follow-through (Rich schema)

1. Run targeted prompt tests:
   uv run pytest -q tests/agents/runtime/test_prompts.py
   Expected: 10 passed.

2. Run the full suite to confirm no regressions:
   uv run pytest -q
   Expected: 184 passed, 4 subtests passed.

3. (Live stack — requires Postgres + clean_jobs populated via T0009.6 loader)
   docker compose up -d
   docker compose exec -T postgres psql -U internhunter -d internhunter -f scripts/init_db.sql
   uv run python -m src.services.ingestion.loader
   uv run uvicorn src.api.app:app --reload

   Then POST to http://127.0.0.1:8000/api/v1/agent/chat with the queries below.
   For each, confirm the tool is called and the answer is grounded in the DB.

   a. "Show me Data Scientist roles in Ho Chi Minh City"
      Expected: SQL uses `role ILIKE '%Data Scientist%'` AND `location ILIKE '%Ho Chi Minh%'`; returns matching rows or honest "none found."

   b. "Which postings pay over 1000 USD?"
      Expected: SQL uses `salary_min >= 1000 AND salary_currency = 'USD'`; returns rows or honest "none found."

   c. "Any internships available?"
      Expected: SQL uses `is_internship = true`; returns internship rows.

   d. "What's the salary for [a posting where salary is NULL or negotiable]?"
      Expected: agent says salary may be missing or negotiable for some postings — does NOT say "not in the data" and does NOT fabricate a number.

4. Confirm the agent never references a non-existent column (posted_date, remote, id):
   Ask: "What date was this job posted?" or "Are any jobs remote?"
   Expected: agent says the information is not available in the data — does not attempt a SQL query for posted_date or remote.

### T0009.9: Explicit schema reset path

* When the schema shape changes and `init_db.sql` (`CREATE TABLE IF NOT EXISTS`) silently skips a table that already exists with the wrong shape, use the reset workflow instead of a manual `DROP TABLE`:
  1. `docker compose up -d`; confirm Postgres is healthy and both tables exist with data — `docker compose exec -T postgres psql -U internhunter -d internhunter -c "SELECT count(*) FROM clean_jobs;"` returns a non-zero count after an ingest.
  2. Run the reset: `docker compose exec -T postgres psql -U internhunter -d internhunter -f scripts/reset_db.sql`. Expect no errors; the `\i` include echoes the `CREATE` statements from `init_db.sql`.
  3. Confirm the schema was recreated empty: `docker compose exec -T postgres psql -U internhunter -d internhunter -c "\d clean_jobs"` and `"\d raw_jobs"` show the full T0009.1 columns; `SELECT count(*) FROM clean_jobs;` → `0`.
  4. Re-ingest: `uv run python -m src.services.ingestion.loader` → counts non-zero again; the app answers a normal question.
  5. Confirm `init_db.sql` alone is still non-destructive: re-run `docker compose exec -T postgres psql -U internhunter -d internhunter -f scripts/init_db.sql` against the populated DB and verify row counts are unchanged (`IF NOT EXISTS` skips recreation).
* `uv run pytest -q` still passes (no code touched by this ticket).

## Milestone 10 — Pre-deploy correctness fixes

### T0010.1: Graceful answer + minimal typed error contract

* Run `uv run pytest tests/api/test_query.py -v` and confirm: a `None`/empty runtime answer returns `200` with the safe fallback message (not a 500); an internal failure returns a safe generic message with no leaked internals/stack trace; the answer-only response shape (`answer`, `session_id`, `trace_id`, `trace_url`) is unchanged.
* With the stack up (`docker compose up -d`), `POST /api/v1/agent/chat` with a normal question (e.g. `{"query": "What companies use Python?"}`) and confirm a natural-language answer is returned.
* Force an internal failure (e.g. stop Postgres with `docker compose stop postgres`, then `POST` a job-data question) and confirm the client receives a clean generic error message — no raw SQL, no internals, no stack trace — while the server-side log still records the full error. Restart Postgres afterward.

### T0010.2: Tolerate non-string model content in SQL generation

* Run `uv run pytest tests/agents/tools/test_query_clean_jobs.py -v` and confirm the mocked list-style-content case yields the expected SQL string without error, and the existing `str`-content path still passes.
* Run `uv run mypy` and confirm the `src/agents/tools/query_clean_jobs.py` `union-attr` error is gone (down to the 2 known benign residuals).

### T0010.3: Enforce a true single-table allowlist in the SQL validator

* Run `uv run pytest tests/services/query/test_sql_validator.py -v` and confirm: `clean_jobs`-only `SELECT`s (including `WHERE`/`ORDER BY`/`LIMIT`) still pass; a `JOIN raw_jobs`, a comma `FROM clean_jobs, raw_jobs`, and a bare `SELECT * FROM raw_jobs` are all rejected.
* In a Python REPL: `from src.services.query.sql_validator import validate_sql`, then check:
  * `validate_sql("SELECT title FROM clean_jobs LIMIT 10")` → `valid=True`.
  * `validate_sql("SELECT * FROM clean_jobs JOIN raw_jobs USING (source, external_id)")` → `valid=False` with a clear reason.
  * `validate_sql("SELECT * FROM clean_jobs, raw_jobs")` → `valid=False`.
  * `validate_sql("SELECT * FROM raw_jobs")` → `valid=False`.
* With the stack up, ask the agent a question that would tempt a join to `raw_jobs` (e.g. "show me the raw payload for the AI Engineer job") and confirm the tool refuses rather than returning raw-payload columns.

### T0010.4: Offload the blocking SQL-generation LLM call off the event loop

* Run `uv run pytest tests/agents/tools/test_query_clean_jobs.py -v` and confirm the async tool still returns the expected result on the normal path and existing tests pass.
* With the app running (`docker compose up -d`), fire two concurrent `POST /api/v1/agent/chat` job-data requests (e.g. run two `curl`/HTTP calls in parallel) and, during them, hit `GET /api/v1/health` — confirm the health probe still responds promptly and does not stall for the LLM round-trip duration.

### T0010.5: Honest match-count / truncation notice for `query_clean_jobs`

* Run `uv run pytest tests/services/query/test_row_bound.py tests/services/query/test_table_formatter.py tests/agents/tools/test_query_clean_jobs.py -v` and confirm all pass (the `+1`-sentinel truncation semantics and the `TableArtifact.truncated` flag).
* With the stack up and `clean_jobs` holding more rows than `agent.query.max_rows` (default 20), ask a broad question that matches more than the cap (e.g. "show me every job") and confirm the answer says *"Showing the first N results — there are more matches. Narrow your search…"* rather than implying N is the total.
* Ask a narrow question that matches fewer than the cap and confirm the answer reads *"Found N result(s)…"* with no truncation notice. A `COUNT(*)`/scalar question is unaffected.

### T0010.6: Word-boundary matching in `normalize_location`

* Run `uv run pytest tests/services/ingestion/test_transform.py tests/services/ingestion/test_normalize_vietnamworks.py -v` and confirm the new `normalize_location` word-boundary cases and the existing location tests pass.
* In a Python REPL: `from src.services.ingestion.transform import normalize_location`, then check:
  * `normalize_location("12 Nguyen Hue, District 1, Ho Chi Minh City")` → `"Ho Chi Minh City"`.
  * `normalize_location("Some Street, Ba Dinh, HN")` → `"Hanoi"`.
  * A false-positive probe — a word containing `hn`/`hcm` but no real city (e.g. `normalize_location("john technology park")`) → `"Other"`.
  * `normalize_location("Hà Nội")` → `"Hanoi"` (exact clean token still works); two cities in one string → both present, deterministic (leftmost-match) order.

### T0010.7: Honor explicit user-requested result counts (LIMIT intent)

* Run `uv run pytest tests/services/query/test_row_bound.py tests/agents/tools/test_query_clean_jobs.py -v` and confirm: `resolve_bounds` honors an explicit `LIMIT <= max_rows` exactly; the honored-explicit-count tool test answers "Found N result(s)" with no truncation notice; the unbounded-truncation test is unchanged.
* In a Python REPL: `from src.services.query.row_bound import resolve_bounds`, then confirm `resolve_bounds("SELECT title FROM clean_jobs LIMIT 3", 20)` returns SQL ending in `LIMIT 3` with `display_cap == 3`, while a query with no `LIMIT` falls back to a `max_rows + 1` fetch with `display_cap == max_rows`.
* With the stack up, ask "show me the top 3 AI Engineer jobs" and confirm exactly 3 rows come back with a "Found 3 result(s)" wording (no truncation notice); ask an unbounded broad query and confirm the truncation notice still appears when matches exceed the cap.

## Milestone 11 — Model Evaluation Harness

**Note:** the eval harness scores against a **separate seeded fixture DB** (`internhunter_eval` on `localhost:5433`), never live `clean_jobs`. `evals/conftest.py` redirects `DATABASE_URL` to `eval.fixture.database_url` for the eval test session, so eval runs do not touch prod data.

### T0011.1: Judge JSON-reliability spike + DeepEval harness scaffold

* Confirm the chosen judge is recorded in `config/settings.yaml` under `eval.judge.*` (`provider`, `model`) — currently `provider: groq`, `model: openai/gpt-oss-120b`.
* Run `uv run deepeval test run evals/test_judge_scaffold.py` and confirm it exits 0 and prints one passing metric — i.e. the judge returns schema-valid JSON end-to-end on a trivial `LLMTestCase` without a `ValueError`.
* (If the judge spike script under `scripts/` is retained) run it and confirm its output names the chosen judge and shows a valid JSON verdict.

### T0011.2: Seeded eval fixture DB + versioned golden dataset

* With Postgres up (`docker compose up -d`), build the fixture DB from scratch: `uv run python -m evals.fixtures.loader` — confirm it prints `COUNT(*) = 22` and exits 0.
* Run `uv run pytest evals/fixtures/test_fixture_counts.py evals/test_goldens_load.py -v` and confirm the pinned distribution holds: total = 22; `role='AI Engineer'` = 5; `role='Data Scientist'` = 4; `tech_stack ILIKE '%Python%'` = 12; `tech_stack ILIKE '%Python%' AND location ILIKE '%Hanoi%'` = 7; `COBOL` = 0; and the golden JSON parses/loads as a DeepEval dataset.
* Confirm the reset path works: `uv run python -c "from evals.fixtures.loader import reset_fixture; reset_fixture()"` drops and rebuilds the fixture tables without error, and re-running the count check above still returns 22.

### T0011.3: Three-seam instrumentation + metric stack

* Confirm the config-forward change is behavior-preserving: `uv run pytest tests/agents/tools/test_query_clean_jobs.py -v` stays green with the forwarded `config` optional and defaulting to a no-op (the tool imports no eval code).
* With Postgres up and the fixture DB built (T0011.2), run `uv run deepeval test run evals/test_three_seams.py` and confirm: the full golden set executes, a score prints per metric per seam per case (report-only — the run does not fail on low scores, per T0011.5 owning gating), and the output shows a **distinct span/score for the nested `generate_sql` (seam 2) SQL generation** — i.e. `generate_sql (seam 2) span SQL: …` is printed for retrieval cases, proving the hidden NL→SQL call is observable via config forwarding, not `@observe`.
* Spot-check one printed case: `tools_called` reflects the routed tool, the seam-2 SQL is a read-only `clean_jobs` statement, and seam-3 metrics (task completion / faithfulness / honesty) each produced a numeric score or a captured error string (never a silent blank).

### T0011.4: Langfuse score writeback

* Run the no-network unit tests: `uv run pytest evals/test_writeback.py -v` and confirm all pass — every non-None score is written as `NUMERIC` with a seam-prefixed name (`{seam}/{metric}`); None-scored metrics are skipped; a `None` `trace_id` and a disabled-Langfuse (no creds) both no-op to `0` without raising; the same metric name across two seams gets **distinct** `score_id`s (`{trace_id}-{seam}-{metric}`); `flush()` is called exactly once when scores are written.
* **Live (requires Langfuse creds + Postgres + the fixture DB):** run `uv run deepeval test run evals/test_three_seams.py`. Each case that produced a trace prints `scores written to trace <trace_id>: <n>` (n > 0). Open one of those `trace_id`s in the Langfuse UI and confirm the eval scores appear **on the same trace** as the raw tool-call spans, each named `{seam}/{metric}` (e.g. `seam2_nl_to_sql/Argument Correctness`).
* **Idempotency:** re-run the same golden and confirm the scores on that trace are **updated in place, not duplicated** — the stable `score_id` (`{trace_id}-{seam}-{metric}`) means a re-run overwrites rather than appending a second copy.
* **Graceful no-op:** with Langfuse creds absent from the environment, run the harness and confirm it still completes, `scores_written` is `0`, and nothing crashes (writeback silently skips when `get_langfuse_handler()` returns `None`).
* Confirm the request path is untouched: `src/agents/tracing/langfuse.py` was not modified by this ticket — writeback reuses its accessors only (`get_langfuse_client` / `get_langfuse_handler`) and never runs on a live `POST /api/v1/agent/chat` request.

### T0011.6: Gemini judge provider (Groq-load relief)

* `uv sync` resolves with `langchain-google-genai` added (`pyproject.toml`).
* `uv run pytest evals/ -v` with **no** `GOOGLE_API_KEY` set: the harness still imports (the `google` branch's import is local to `build_judge()`), and every unit test that doesn't need a live judge stays green.
* With `GOOGLE_API_KEY` in `.env` and `config/settings.yaml` `eval.judge.provider: google` (the shipped default): `uv run python -c "from evals.judge import build_judge; print(build_judge().get_model_name())"` prints `google/gemini-2.5-flash`.
* JSON-reliability smoke (same bar T0011.1 held Groq to): `uv run pytest evals/test_judge_scaffold.py -v` exits 0 — the Gemini judge returns schema-valid JSON on the trivial `GEval` case without a `ValueError`. Note: `gemini-2.5-flash` is a "thinking" model that spends part of its token budget on internal reasoning before the visible JSON; `evals/judge.py`'s `google` branch sets `max_tokens=4096` (vs the Groq branch's `1024`) so the JSON is never truncated — confirmed by 3 consecutive live passes.
* Flip `provider: groq` in `config/settings.yaml`, re-run the model-name check above → prints `groq/openai/gpt-oss-120b`, confirming the Groq path is byte-for-byte unchanged. Flip back to `provider: google` afterward (the shipped default).
* **Judge-agreement gate:** see `docs/Known_Issues.md` → Evaluation harness (T0011.6) for the live comparison result and its caveats (Groq/Google free-tier availability at the time of the run).
* **Judge RPM throttle (rate-limit relief follow-up, 2026-07-05):** `config/settings.yaml` `eval.judge.rpm: 8` paces judge calls under Gemini's ~10 RPM free-tier cap instead of firing all ~119 judge calls for the 17 goldens back-to-back. Verify: `python -c "from evals.judge import _RpmThrottle; import time; t=_RpmThrottle(2); s=time.monotonic(); [t.wait() for _ in range(3)]; print(time.monotonic()-s)"` prints `~60` (the 3rd call waits for the window to free up). Live: `PYTHONUTF8=1 uv run deepeval test run evals/test_three_seams.py -k "A1 or A3"` should show a visible pause (~7.5s at `rpm=8`) between consecutive judge calls in the output instead of an immediate burst.

## Milestone 12 — Hardening & Known-Issue Fixes

### T0012.4: Populate trace_url in the agent response

* Run `uv run pytest tests/agents/runtime/test_react_agent.py tests/agents/test_service.py tests/api/test_query.py -v` and confirm all pass — `AgentRuntime.ainvoke` now returns a `trace_url` key alongside `answer`/`trace_id`, and `service.py`/the API response shape (`{answer, session_id, trace_id, trace_url}`) is unchanged.
* **With Langfuse creds set** (`docker compose up -d`, app restarted with `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` set): `POST /api/v1/agent/chat` with `{"query": "What companies use Python?"}`. Confirm `trace_url` in the JSON response is a real URL and opening it in a browser lands on the Langfuse UI trace whose id matches the response's `trace_id`.
* **With Langfuse creds unset**: restart the app, repeat the same request. Confirm the response is still `200` and `trace_url` is `null` (tracing disabled degrades gracefully, no 500).

### T0012.5: Graceful fallback instead of a 500 on an empty agent answer

1. Unit-level, no network:
   ```
   uv run python -c "import asyncio; from unittest.mock import AsyncMock, patch; \
   import src.agents.runtime.react_agent as r; \
   from src.agents.service import generate_agent_response, FALLBACK_ANSWER; \
   fa=AsyncMock(); fa.ainvoke.return_value={'messages': []}; \
   rt=r.AgentRuntime(agent=fa); \
   [p.start() for p in (patch.object(r,'build_langfuse_config',return_value={}), patch.object(r,'get_langfuse_handler'), patch.object(r,'get_langfuse_client',return_value=None))]; \
   print(asyncio.run(generate_agent_response(query='hi', runtime=rt))['answer'] == FALLBACK_ANSWER)"
   ```
   Confirm: prints `True` — an empty-messages runtime response now degrades to the fallback answer instead of raising.
2. Run `uv run pytest tests/agents/runtime/test_react_agent.py tests/agents/test_service.py tests/api/test_query.py -v` and confirm all pass, including the three new `_extract_answer` "returns empty string" cases and the `generate_agent_response` fallback case.
3. (Optional, live stack) With Docker + Groq creds available: `docker compose up -d`, `POST /api/v1/agent/chat` with a normal question and confirm a real answer still returns `200`. There is no reliable way to force a live empty answer post-T0012.2 (reasoning-leak fix raised `max_tokens` and hides `<think>` content), so the deterministic unit proof above is the primary evidence.

### T0012.6: Coerce non-str model content before `.strip()` in `generate_sql`

1. Coercion proof, no network:
   ```
   uv run python -c "from src.agents.tools.query_clean_jobs import _content_to_text; \
   print(_content_to_text([{'type':'text','text':'SELECT '},{'type':'text','text':'1'}]).strip() == 'SELECT 1'); \
   print(_content_to_text('  SELECT 1  ').strip() == 'SELECT 1')"
   ```
   Confirm: prints two `True` lines — list-content flattening and the unchanged `str` fast path.
2. Run `uv run pytest tests/agents/tools/test_query_clean_jobs.py -q` and confirm all pass (8 existing + 3 new `generate_sql` content-coercion tests).
3. Run `uv run mypy` and confirm 2 residuals remain (`src/core/checkpointer.py:25`, `src/agents/runtime/middleware.py:48`) — the `query_clean_jobs.py` union-attr residual is gone.
4. (Optional, live) With Groq creds + DB available: ask a normal job-data question end-to-end and confirm SQL generation still returns clean bare SQL — Groq returns `str` content today, so no behavior change is expected.

### T0012.7: Keep live-API eval tests out of plain pytest collection

1. Plain suite skips live tests, no network:
   ```
   uv run pytest -q
   ```
   Confirm the summary shows `... deselected` and completes in seconds (no multi-minute hang, no Groq/Gemini call). Observed: `254 passed, 18 deselected, 4 subtests passed` (18 = 1 `test_judge_scaffold` + 17 `test_three_seams` parametrized cases).
2. Live tests are still selectable:
   ```
   uv run pytest -m eval --collect-only -q
   ```
   Confirm it lists exactly `evals/test_judge_scaffold.py::test_judge_scaffold` and the 17 `evals/test_three_seams.py::test_three_seams[...]` node ids (A1–E2) — and nothing from `tests/`. Observed: `18/272 tests collected (254 deselected)`.
3. Marker is registered (no "unknown marker" warning):
   ```
   uv run pytest -m eval --collect-only -q 2>&1 | grep -i "PytestUnknownMarkWarning" || echo "marker registered, no warning"
   ```
   Confirm: `marker registered, no warning`. (`pyproject.toml` also sets `--strict-markers`, which would hard-fail collection on any unregistered marker — the full suite stays green with it on.)
4. deepeval path (if creds + fixture DB available): `deepeval test run` inherits `addopts` and deselects eval tests by default — pass `-m eval` to select them:
   ```
   PYTHONUTF8=1 uv run deepeval test run evals/test_three_seams.py -m eval
   ```
   Without `-m eval`, this reports "No test cases found, please try again" (0 selected) — confirmed live. With `-m eval`, confirmed live against `evals/test_judge_scaffold.py -m eval` that the test is actually selected and run (it failed only on missing judge credentials in this sandbox, not on deselection — `1 total tests`, `0% pass rate` due to `error=None`/no judge response, not "no test cases found").

### T0012.8: Convert `generate_sql` to native async

1. Run `uv run pytest tests/agents/tools/test_query_clean_jobs.py -v` and confirm all 10 pass — the thread-offload test is gone (removed, not skipped) and the three `GenerateSqlContentCoercionTests` cases now show as async (`IsolatedAsyncioTestCase`).
2. Confirm no thread-offload remains for `generate_sql`:
   ```
   grep -n "to_thread" src/agents/tools/query_clean_jobs.py
   ```
   Confirm: exactly one hit, the `execute_validated_sql` line — none for `generate_sql`.
3. Confirm the signature changed:
   ```
   grep -n "async def generate_sql" src/agents/tools/query_clean_jobs.py
   ```
   Confirm: one hit.
4. Run `uv run pytest -q` (full suite) and confirm no regressions.
5. Run `uv run mypy src` and confirm the same 2 pre-existing residuals as before this ticket (`src/core/checkpointer.py:25`, `src/agents/runtime/middleware.py:48`) — no new errors introduced.
6. (Optional, live) With Groq creds + DB available: ask a normal job-data question end-to-end and confirm `query_clean_jobs` still returns the same SQL-backed answer and a `generate_sql` span still appears in Langfuse. Not exercised in this sandbox — state explicitly if skipped.

### T0012.10: Reduce eval judge cost & rate-limit exposure (thinking-budget cap + drop redundant metric)

1. Plain suite stays green, no live judge/agent call:
   ```
   uv run pytest -q
   ```
   Confirm the summary shows the same pass count as before plus the one new test (`evals/test_judge.py::test_build_judge_forwards_thinking_budget_for_google`), with the eval-marked tests still deselected — completes in seconds, no Groq/Gemini call.
2. Import sanity, no network:
   ```
   uv run python -c "from evals.judge import build_judge"
   uv run python -c "from evals.harness import seam3_metrics"
   ```
   Confirm both import cleanly (`harness.py` still imports fine with the `FaithfulnessMetric` import removed).
3. Confirm `FaithfulnessMetric` is gone from seam 3:
   ```
   grep -n "FaithfulnessMetric" evals/harness.py
   ```
   Confirm: no hits.
4. (Creds present — `GOOGLE_API_KEY` + Groq creds + fixture DB) Live judge-agreement spot-check: run 2–3 goldens including at least one honesty probe (C1, C3, or C5) with the thinking cap in place:
   ```
   PYTHONUTF8=1 uv run deepeval test run evals/test_three_seams.py -m eval
   ```
   Confirm it completes and the seam-3 result set no longer contains a `Faithfulness` key. Compare the `Honesty`/`Task Completion` verdicts against a pre-cap run (`thinking_budget` temporarily reverted to a nonzero value) and confirm no material divergence. If creds aren't available in the coder environment, mark this step BLOCKED and log it as a follow-up in `docs/Known_Issues.md` rather than skipping silently.

## Milestone 14 — Pre-Deploy Known-Issue Fixes

### T0014.1: Graceful startup & config-load robustness

* Run `uv run pytest tests/core/test_config.py -v` and confirm the non-project-CWD load, clear missing-env error, and import-safety tests all pass.
* Run `uv run pytest tests/api/test_startup_config.py tests/api/test_query.py -v` and confirm startup config failures surface during FastAPI lifespan while the query route tests still pass.
* Run `uv run pytest -q` and confirm the broader suite still passes with the repo's existing eval-marker behavior unchanged.
* Manual non-project-CWD check:
  * `cd C:\tmp`
  * `uv run --directory D:\Data_Science_Project\InternHunterAgent python -c "from src.core.config import load_settings; s = load_settings(); print(sorted(s.config_yaml.keys()))"`
  * Confirm it prints the repo config keys instead of failing on the current working directory.
* Missing-env startup check in a subprocess only (do not unset anything permanently in your shell):
  * `uv run python -c "import os; os.environ.pop('GROQ_API_KEY', None); os.environ['DATABASE_URL']='postgresql+psycopg://internhunter:internhunter@localhost:5433/internhunter'; os.environ['LANGFUSE_SECRET_KEY']='x'; os.environ['LANGFUSE_PUBLIC_KEY']='y'; import src.core.config as c; c.Settings.model_config['env_file']=None; c.load_settings(force_reload=True)"`
  * Confirm it raises `ConfigLoadError` with a message naming the missing required env var, not an `ImportError` traceback.

### T0014.2: Known-Issues register housekeeping

* Run `git diff -- docs/Known_Issues.md docs/Resolved_Issues.md docs/Repo_Current_State.md docs/Completion_Reports.md docs/Manual_Verification_Guide.md` and confirm only documentation/register files changed for this ticket.
* Run `rg -n "13-column|job_level hidden|qwen agent-model|T0014.2|T0016|Deploy Hardening" docs` and confirm the old 13-column/`job_level` drift item is not reintroduced as open, T0014.2 is recorded as complete, and T0016/T0017 deploy-hardening items remain deferred.
* Run `uv run pytest -q tests/core/test_config.py tests/api/test_startup_config.py` and confirm the T0014.1 config/startup smoke tests still pass after the docs-only sweep.

## Milestone 16 — Security Posture

### T0016.1: CORS middleware (config-driven, credential-less)

* Run the focused API tests:
  * `uv run pytest -q tests/api/test_cors.py tests/api/test_query.py tests/api/test_startup_config.py`
  * Confirm all tests pass.
* Confirm `config/settings.yaml` keeps `api.cors.allow_credentials: false`.
* Set a local allowed origin in `config/settings.yaml`, for example `http://localhost:5173`, then start the app:
  * `uv run uvicorn src.api.app:app --reload`
* In another terminal, send an allowed-origin preflight request:
  * `curl -i -X OPTIONS "http://127.0.0.1:8000/api/v1/agent/chat" -H "Origin: http://localhost:5173" -H "Access-Control-Request-Method: POST"`
  * Confirm the response includes `access-control-allow-origin: http://localhost:5173`.
* Send the same preflight request from a disallowed origin:
  * `curl -i -X OPTIONS "http://127.0.0.1:8000/api/v1/agent/chat" -H "Origin: http://evil.example" -H "Access-Control-Request-Method: POST"`
  * Confirm the response does not include `access-control-allow-origin`.

### T0016.2: Per-IP rate limiting + graceful 429/quota degradation

* Run the focused API tests:
  * `uv run pytest -q tests/api/test_rate_limit.py tests/api/test_query.py tests/api/test_cors.py tests/api/test_startup_config.py`
  * Confirm the chat limit, friendly provider-busy response, generic 500 path, health route, CORS, and startup-config tests all pass.
* Start the API locally:
  * `uv run uvicorn src.api.app:app --reload`
* Send more than 15 chat requests from the same machine within one minute:
  * `POST http://127.0.0.1:8000/api/v1/agent/chat`
  * Confirm the excess request returns HTTP 429 with `{"detail": "The demo is busy right now. Please try again in a moment."}`.
* Call health repeatedly:
  * `GET http://127.0.0.1:8000/api/v1/health`
  * Confirm it remains HTTP 200 and is not rate-limited.
* If provider credentials are available, simulate or trigger provider timeout/rate-limit pressure and confirm provider-busy failures return friendly HTTP 429/503 while unrelated bugs still return `{"detail": "Failed to process query"}` with HTTP 500.

### T0016.3: Request input hardening (length cap)

* Run the focused API tests:
  * `uv run pytest -q tests/api/test_query.py tests/api/test_rate_limit.py tests/api/test_cors.py tests/api/test_startup_config.py`
  * Confirm normal, blank, over-limit, rate-limit, CORS, and startup-config API paths all pass.
* Start the API locally:
  * `uv run uvicorn src.api.app:app --reload`
* Send a normal request:
  * `curl -X POST http://127.0.0.1:8000/api/v1/agent/chat -H "Content-Type: application/json" -d "{\"query\":\"What companies use Python?\"}"`
  * Confirm the request is accepted and returns the usual `answer` / `session_id` / `trace_id` / `trace_url` response shape.
* Send a whitespace-only request:
  * `curl -X POST http://127.0.0.1:8000/api/v1/agent/chat -H "Content-Type: application/json" -d "{\"query\":\"   \"}"`
  * Confirm it still returns HTTP 400 with `{"detail": "Query must not be empty."}`.
* Send a request with more than 2000 characters in `query`.
  * Confirm it is rejected with HTTP 422 and a `string_too_long` validation detail for `body.query`.
  * Confirm no agent/runtime work is performed for the rejected request.
* Confirm `api.max_query_chars: 2000` in `config/settings.yaml` still matches `DEFAULT_MAX_QUERY_CHARS = 2000` in `src/api/schemas.py`; this ticket uses a static schema constant mirrored in config, not a dynamically loaded schema value.

### T0016.4: `/docs` exposure decision + minimal security headers

* Run the focused API tests:
  * `uv run pytest -q tests/api/test_docs_exposure.py tests/api/test_cors.py tests/api/test_rate_limit.py tests/api/test_query.py tests/api/test_startup_config.py`
  * Confirm the docs-on/docs-off checks and the existing CORS, rate-limit, query, and startup-config paths all pass.
* Confirm the default shipping config in `config/settings.yaml` keeps:
  * `api.docs_enabled: true`
* Start the API locally:
  * `uv run uvicorn src.api.app:app --reload`
* Open these URLs and confirm they are reachable with the default config:
  * `http://127.0.0.1:8000/docs`
  * `http://127.0.0.1:8000/redoc`
  * `http://127.0.0.1:8000/openapi.json`
* Temporarily set the locked-down alternative in `config/settings.yaml`:
  * `api.docs_enabled: false`
* Restart the API and confirm these now return HTTP 404:
  * `http://127.0.0.1:8000/docs`
  * `http://127.0.0.1:8000/redoc`
  * `http://127.0.0.1:8000/openapi.json`
* Restore `api.docs_enabled: true`.
* Confirm this ticket does not add `X-Frame-Options`, CSP, or any other security-header middleware because FastAPI still serves API responses only and no same-origin HTML UI in this repo state.

## Milestone 17 — Streaming Response Delivery

### T0017.1: Runtime streaming + no-leak filter

* Run the focused runtime tests:
  * `uv run pytest tests/agents/runtime/test_react_agent.py -q`
  * Confirm all runtime tests pass, including the streaming token-order test and the no-leak test.
* Run the full standard suite:
  * `uv run pytest -q`
  * Confirm the non-eval suite stays green.
* Live REPL probe (requires `GROQ_API_KEY` and local Postgres with `clean_jobs` reachable):
  ```python
  import asyncio
  from src.agents.runtime.react_agent import AgentRuntime

  async def main():
      rt = AgentRuntime()
      async for ev in rt.astream("list 3 data engineer jobs", session_id="demo"):
          print(ev)

  asyncio.run(main())
  ```
  Confirm the stream contains `{"type": "token", ...}` events forming a natural-language final answer, with no `SELECT`, `clean_jobs`, tool names, tool args, or raw rows, followed by exactly one `{"type": "metadata", ...}` event.
* Confirm `git diff -- src/agents/runtime/react_agent.py` shows `ainvoke`, `_build_messages`, and `_extract_answer` unchanged except for the new sibling `astream` method.

### T0017.2: Streaming service + SSE endpoint

* Run the focused streaming API tests:
  * `uv run pytest tests/api/test_stream.py -q`
  * Confirm the happy path yields `session`, one or more `token` events, `metadata`, and `done`; the empty-answer fallback emits a fallback `token` before `metadata`; mid-stream failures return HTTP 200 with `error` then `done`; and blank queries return HTTP 400 before the runtime stream starts.
* Run the broader API route suite:
  * `uv run pytest tests/api -q`
  * Confirm the existing one-shot `/api/v1/agent/chat` tests still pass.
* Start the API locally with Groq credentials and a seeded Postgres:
  * `uv run uvicorn src.api.app:app --reload`
* Stream a live tool-using query:
  ```bash
  curl -N -X POST http://127.0.0.1:8000/api/v1/agent/chat/stream \
    -H "Content-Type: application/json" \
    -d "{\"query\":\"list 3 data engineer jobs\"}"
  ```
  Confirm the first event is `session`, token events render the natural-language answer incrementally, the trailing `metadata` event carries the trace URL when Langfuse is configured, and the terminal event is `done`. Confirm no `SELECT`, `clean_jobs`, tool names, tool args, or raw rows appear in token events.
* Confirm blank-query validation stays pre-stream:
  ```bash
  curl -i -N -X POST http://127.0.0.1:8000/api/v1/agent/chat/stream \
    -H "Content-Type: application/json" \
    -d "{\"query\":\"  \"}"
  ```
  Expect HTTP 400 with `{"detail":"Query must not be empty."}`.
* Confirm response headers on the streaming endpoint include `content-type: text/event-stream`, `cache-control: no-cache`, and `x-accel-buffering: no`.

## Milestone 18 — Clickable Demo (UI + go-live)

### T0018.1: Go-live glue - server session IDs, data disclaimer, DB readiness probe

* Run the focused go-live glue tests:
  * `uv run pytest -q tests/agents/test_service.py tests/api/test_ready.py tests/api/test_stream.py`
  * Confirm one-shot and streaming requests without `session_id` return a valid UUID4, `/api/v1/ready` surfaces the configured snapshot date, readiness failure maps to HTTP 503, and readiness is not rate-limited.
* Run the broader API route suite:
  * `uv run pytest -q tests/api`
  * Confirm existing chat, stream, rate-limit, CORS, docs, and readiness routes pass together.
* Start the API with local Postgres running:
  * `docker compose up -d postgres`
  * `uv run uvicorn src.api.app:app --reload`
* Check liveness remains unchanged:
  * `curl -i http://127.0.0.1:8000/api/v1/health`
  * Confirm HTTP 200 with the existing health JSON shape.
* Check readiness:
  * `curl -i http://127.0.0.1:8000/api/v1/ready`
  * Confirm HTTP 200 with `{"status":"ok","data_snapshot_date":"2026-07-14"}` or the current configured date in `config/settings.yaml`.
* Stop Postgres or point `DATABASE_URL` at an unreachable database, restart the API, and call `/api/v1/ready` again.
  * Confirm it returns HTTP 503 with `{"status":"error"}`.
* Call `/api/v1/ready` repeatedly faster than `api.rate_limit`.
  * Confirm readiness remains unthrottled; only chat routes should be limited.
* For demo session behavior, send a first chat or stream request without `session_id`, note the returned server-issued UUID4, then reuse that value on the next turn.
  * Confirm the server accepts the reused id and preserves the normal response/stream shape.

### T0018.2: Same-origin static serving + frame protection

* Run the focused static-serving tests:
  * `uv run pytest tests/api/test_static_serving.py -q`
  * Confirm `/` serves the placeholder page, `/docs` is not shadowed, `/api/v1/ready` is not shadowed, and `/` includes `X-Frame-Options: DENY`.
* Run the streaming regression test:
  * `uv run pytest tests/api/test_stream.py -q`
  * Confirm the SSE endpoint still returns the expected event sequence, proving the frame-guard middleware does not buffer or break streaming.
* Run the broader API route suite:
  * `uv run pytest tests/api -q`
  * Confirm existing chat, stream, rate-limit, CORS, docs, readiness, and static routes pass together.
* Start the API with local Postgres running:
  * `docker compose up -d postgres`
  * `uv run uvicorn src.api.app:app --reload`
* Open `http://127.0.0.1:8000/`.
  * Confirm the page shows the `InternHunter` placeholder and says the streaming chat interface ships in T0018.3.
* Inspect the frame-protection header:
  * `curl -sI http://127.0.0.1:8000/ | grep -i x-frame-options`
  * Confirm it shows `x-frame-options: DENY`.
* Open `http://127.0.0.1:8000/docs`.
  * Confirm Swagger UI still loads and is not shadowed by the static mount.
* Check readiness still resolves under `/api/v1`:
  * `curl -s http://127.0.0.1:8000/api/v1/ready`
  * Confirm it still returns the readiness JSON.
* Stream a live tool-using query:
  ```bash
  curl -N -X POST http://127.0.0.1:8000/api/v1/agent/chat/stream \
    -H "Content-Type: application/json" \
    -d "{\"query\":\"How many AI Engineer jobs need Python?\"}"
  ```
  Confirm tokens still stream, proving the pure-ASGI frame guard did not regress SSE.

### T0018.3: Editorial streaming chat UI (vanilla)

* Run the static-serving regression (the UI keeps the `InternHunter` string the route test asserts):
  * `uv run pytest tests/api/test_static_serving.py -q`
  * Confirm `GET /` still returns 200 and its body contains `InternHunter`.
* Run the broader API suite:
  * `uv run pytest tests/api -q` — confirm green (route precedence, headers, streaming unaffected; the UI is static assets only).
* Start the API with local Postgres and real streaming creds:
  * `docker compose up -d postgres` (local Postgres on port 5433)
  * `uv run uvicorn src.api.app:app --reload`
* Open `http://127.0.0.1:8000/`.
  * Confirm the Editorial page renders: `InternHunter` masthead, italic standfirst, four suggested-question chips, and a question box.
  * Confirm the dateline reads exactly `Demo data · snapshot 2026-07-14 · public listings, may be inaccurate.` (the date comes from `GET /api/v1/ready`; if the DB is down it degrades to `Demo data · public listings, may be inaccurate.` with no `undefined`).
* Click the **Freshness** chip ("Which job was posted most recently?").
  * Confirm the input, send button, and all chips disable while the stream runs, tokens append one-by-one into the answer (marked by the vermilion left rule), a thin vermilion cursor blinks during streaming, and everything re-enables on `done`.
  * Confirm the answer gives the freshness caveat rather than inventing a posting date.
* Trace link (Langfuse-dependent):
  * If Langfuse is configured, confirm a `View the trace →` link appears under the answer after the `metadata` event and opens the trace.
  * If Langfuse is off locally (`trace_url` is `null`), confirm **no** link and no broken element appears.
* Multi-turn memory:
  * After the first answer, type a follow-up (e.g. `and which pays most?`) and send.
  * In DevTools → Network, open the second `chat/stream` request and confirm its JSON body includes the same `session_id` the first turn's `session` event returned (turn 1's request omits `session_id`).
* Pre-stream failure toast:
  * Click a chip more than 15 times within a minute (or `POST` an empty query).
  * Confirm a friendly toast appears from the `detail` string (429 busy message / 400), the answer bubble degrades gracefully, and the page does not crash.
* Confirm the API surface is not shadowed by the `/`-mount:
  * `http://127.0.0.1:8000/docs` still loads; `curl -s http://127.0.0.1:8000/api/v1/ready` still returns JSON.
* Confirm the frame header is intact:
  * `curl -sI http://127.0.0.1:8000/ | grep -i x-frame-options` → `x-frame-options: DENY`.
* Mid-stream `error`-event bubble (**manual-only / code-inspection**): forcing a genuine mid-stream `error` event locally is impractical (it requires the provider to fail *after* the 200 opens). Verify by inspection that `app.js` routes an `error` event to `showErrorBubble` and stops without reconnecting; logged as a manual-only path in `docs/Known_Issues.md`.

## Backend hotfix — Split ReAct-agent and SQL-generation LLM configs

* Confirm `config/settings.yaml` has independent `agent.react` and `agent.sql_generation` blocks, each with `model`, `temperature`, `max_tokens`, `timeout`, `max_retries`, `streaming`, `reasoning_format`, and `reasoning_effort`.
* Confirm `agent.query` still contains `max_rows` and `max_detail_ids`, and no longer contains `sql_generation_reasoning_effort`.
* Confirm `src/agents/runtime/factory.py` builds the conversational agent with `AgentProvider().build_model("react")`.
* Confirm `src/agents/tools/query_clean_jobs.py::generate_sql()` builds the nested SQL-generation model with `AgentProvider().build_model("sql_generation")`.
* Run `uv run pytest tests/agents/runtime/test_provider.py tests/agents/tools/test_query_clean_jobs.py -q` and confirm the focused provider/tool tests pass.
* With maintainer Groq credentials and a seeded `clean_jobs` database, run a live SQL-generation probe:
  ```python
  import asyncio
  from src.agents.tools.query_clean_jobs import generate_sql

  print(asyncio.run(generate_sql("List the AI Engineer jobs that require Python, sorted by salary descending.")))
  ```
  Confirm it returns a bare `SELECT` query and does not expose reasoning text.
* Confirm no prompt, schema, eval fixture, API route, service-layer, streaming transport, or static UI changes were made as part of this config split.

## T0018.4 — Deploy topology + first public deploy

Verify against the live public URL: **https://internhunteragent.onrender.com**

* **Cold hit:** open the URL after it's been idle. Expect a ~1–2 min first load (Render + Neon both waking); the Editorial page then renders.
* **UI serves:** the masthead, honesty prompt chips, and composer render; `curl -s -o /dev/null -w "%{http_code}" https://internhunteragent.onrender.com/` → `200`.
* **Streaming works:** click a canned prompt (or `curl -N -X POST .../api/v1/agent/chat/stream -H 'Content-Type: application/json' -d '{"query":"How many AI Engineer jobs need Python?"}'`). Confirm SSE events arrive in order `session` → `token`* → `metadata` → `done`, and the answer streams token-by-token.
* **Neon query works:** the answer reflects the loaded corpus (e.g. a real count, not an error/empty).
* **Trace link resolves:** the `metadata` event carries a non-null `trace_url` (`https://jp.cloud.langfuse.com/...`); the UI's "view trace" link opens the Langfuse trace.
* **Disclaimer:** the disclaimer line shows the snapshot date read from `GET /api/v1/ready` (`{"status":"ok","data_snapshot_date":"2026-07-14"}`). On a cold first load it may briefly degrade to the dateless sentence — refresh once.
* **Multi-turn memory:** ask a follow-up in the same session; confirm it remembers context (the UI omits `session_id` on turn 1, then reuses the server-issued uuid4).
* **API surface intact:** `https://internhunteragent.onrender.com/docs` loads; `curl .../api/v1/health` → `200`.
* **Frame protection:** `curl -sI https://internhunteragent.onrender.com/ | grep -i x-frame-options` → `x-frame-options: DENY`.
* **Deploy hygiene:** Render env vars hold all five secrets + `PORT=8000` (none baked into the image); Render is deploying branch `feature/t0018.4-deploy`.

### T0019.2: Alembic adoption

**A — build the schema from empty (scratch DB)**
```
docker compose exec -T postgres psql -U internhunter -d postgres -c "CREATE DATABASE internhunter_scratch;"
ALEMBIC_DATABASE_URL="postgresql+psycopg://internhunter:internhunter@localhost:5433/internhunter_scratch" uv run alembic upgrade head
docker compose exec -T postgres psql -U internhunter -d internhunter_scratch -c "\d clean_jobs"
```
Expect: 19 columns in the documented order, `id` as `generated always as identity`, unique constraint on `(source, external_id)`.

**B — round-trip test**
```
SCRATCH_DATABASE_URL="postgresql+psycopg://internhunter:internhunter@localhost:5433/internhunter_scratch" uv run pytest tests/migrations -v
```
Expect: passes. Then re-run `uv run pytest tests/migrations -v` with the var unset → skipped, not failed.

**C — no-op on the real local DB**
```
uv run alembic stamp head          # one-time adoption of the existing local DB
uv run alembic current             # shows the baseline revision, "(head)"
uv run alembic upgrade head        # clean no-op, no DDL
docker compose exec -T postgres psql -U internhunter -d internhunter -c "SELECT COUNT(*) FROM clean_jobs;"
```
Expect: row count unchanged from before the stamp.

**D — app still works**
```
uv run uvicorn src.api.app:app --reload
```
Hit `/api/v1/ready`, then ask the UI a question that returns rows ("how many jobs are there?"). Expect a normal answer — this ticket changed no read path.

**E — full suite**
```
uv run pytest && uv run ruff check . && uv run mypy
```

**F — Neon adoption (document only; maintainer runs this deliberately, not the coder)**
```
ALEMBIC_DATABASE_URL="postgresql+psycopg://<user>:<pw>@<neon-DIRECT-non-pooled-host>/<db>?sslmode=require" uv run alembic stamp head
```
Use the direct, non-pooled Neon endpoint (per `research/deployment-research-plan.md`) — migrations must never run through the `-pooler` hostname. `stamp` (not `upgrade`) is correct here since it adopts an already-populated Neon DB into Alembic's version tracking without touching its schema. Run once, deliberately, by the maintainer.

**Cleanup:** `DROP DATABASE internhunter_scratch;` when done.

### T0019.3: Accumulate load semantics + hidden lifecycle columns

**A — migrate + inspect schema**
```
uv run alembic upgrade head
docker compose exec -T postgres psql -U internhunter -d internhunter -c "\d clean_jobs"
```
Expect: `is_active boolean not null default true`, `first_seen_at`/`last_seen_at timestamp with time zone not null default now()` appended after `is_salary_negotiable`.

**B — backfill used real fetched_at, not migration run time**
```
docker compose exec -T postgres psql -U internhunter -d internhunter -c "SELECT COUNT(*) FROM clean_jobs WHERE first_seen_at > now() - interval '1 minute';"
```
Expect: `0`.

**C — row count never shrinks across repeated loads**
Run the loader twice against the local Docker DB (a live VietnamWorks fetch, or two direct `upsert_clean_jobs` calls with the same batch), then:
```
docker compose exec -T postgres psql -U internhunter -d internhunter -c "SELECT COUNT(*) FROM clean_jobs;"
```
Expect: count unchanged/growing, never smaller than before the second run.

**D — no false expiry on a fresh double-run**
```
docker compose exec -T postgres psql -U internhunter -d internhunter -c "SELECT COUNT(*) FROM clean_jobs WHERE is_active = false;"
```
Expect: `0`.

**E — time-based expiry, then re-seen flips back active**
```
docker compose exec -T postgres psql -U internhunter -d internhunter -c "UPDATE clean_jobs SET last_seen_at = now() - interval '8 days' WHERE source='vietnamworks' AND external_id='<pick one>';"
```
Re-run the ingestion loader (or call `expire_stale_clean_jobs(7)` directly) → that row now has `is_active = false`, still exists, and its data still selects normally. Re-seed the same posting (re-run ingestion, or `upsert_clean_jobs` with that row again) → `is_active` flips back to `true`.

**F — hidden-column guard**
```
uv run pytest tests/agents/runtime/test_prompts.py -q
```
Expect: green — `schema_context` never mentions `is_active`, `first_seen_at`, or `last_seen_at`.

**G — agent answers unchanged (Docker `api` service — native Windows `uv run uvicorn` hangs on the pre-existing `ProactorEventLoop`/async-psycopg issue, see `Known_Issues.md`)**
```
docker compose up -d --build api
curl -s http://127.0.0.1:8000/api/v1/ready
curl -s -X POST http://127.0.0.1:8000/api/v1/agent/chat -H "Content-Type: application/json" -d "{\"query\":\"How many AI Engineer jobs are there?\"}"
```
Expect: a normal answer with a plain count, no mention of `is_active`/`first_seen_at`/`last_seen_at` in the answer text or (via the Langfuse trace link) the generated SQL.

**H — full suite**
```
uv run pytest -q
uv run ruff check .
uv run mypy
```

### T0019.4: Source resilience — per-page try/continue + retry/backoff

**A — full suite green**
```
uv run pytest && uv run ruff check . && uv run mypy
```
Expect: all pass; the two `mypy` errors in `checkpointer.py`/`middleware.py` are pre-existing and unrelated (see `Known_Issues.md`).

**B — resilience tests specifically**
```
uv run pytest tests/services/ingestion/test_vietnamworks.py -v
```
Expect the seven new `VietnamWorksResilienceTests` cases, all passing, finishing in well under a second (if a run takes several seconds, `time.sleep` isn't patched and real backoff delays are firing).

**C — the summary line carries `pages_failed` (no network)**
Write a throwaway script (do not commit it) that builds a `VietnamWorksSource` with a mock client where one page raises a 500 three times then a later page succeeds, run `list(src.fetch())`, and print `src.pages_failed` plus the posting count. Expect surviving pages present, `pages_failed == 1`, and an `ingestion.page_failed` JSON warning line on stderr showing the query and page number.

**D — end-to-end summary shape**
```
uv run python -c "
from unittest.mock import patch
from src.services.ingestion.loader import run_ingestion
from src.services.ingestion.sources.base import JobSource
class S(JobSource):
    source = 'vietnamworks'
    pages_failed = 2
    def fetch(self):
        return iter([])
with patch('src.services.ingestion.loader.upsert_raw_postings', return_value=0), \
     patch('src.services.ingestion.loader.upsert_clean_jobs', return_value=0), \
     patch('src.services.ingestion.loader.expire_stale_clean_jobs', return_value=0):
    print(run_ingestion(source=S()))
"
```
Expect a dict containing `'pages_failed': 2` alongside `fetched`, `raw_upserted`, `clean_loaded`, `skipped`, `expired_count`.

**E — real ingestion against the local DB is unaffected**
If you have a local Docker Postgres with data, run the ingestion loader end to end and confirm nothing regresses: it completes, `pages_failed` is `0` under normal conditions, and `SELECT COUNT(*) FROM clean_jobs;` does not shrink. Only against local Docker — never Neon.

### T0019.5: Unattended-run safety

**A — suite green**
```
uv run pytest && uv run ruff check . && uv run mypy
```
Expect: all pass; the two pre-existing `mypy` errors in `checkpointer.py`/`middleware.py` are unrelated (see `Known_Issues.md`).

**B — green run against a correct local DB**
With Docker Postgres up and `HEALTHCHECKS_URL` unset:
```
uv run python -m src.services.ingestion.loader
```
Expect: an `ingestion.schema_ok` line, then `ingestion.completed` carrying all six numbers (`fetched`, `raw_upserted`, `clean_loaded`, `skipped`, `expired_count`, `pages_failed`), then `ingestion.ping_skipped`. Exit code `0` (`echo $?`). Paste the summary line.

**C — drift is caught, and nothing is written**
Against a scratch database only (never the real local DB, never Neon):
```
docker compose exec -T postgres psql -U internhunter -d postgres -c "CREATE DATABASE internhunter_drift TEMPLATE internhunter;"
docker compose exec -T postgres psql -U internhunter -d internhunter_drift -c "ALTER TABLE clean_jobs RENAME COLUMN location TO location_old;"
DATABASE_URL="postgresql+psycopg://internhunter:internhunter@localhost:5433/internhunter_drift" uv run python -m src.services.ingestion.loader; echo "exit=$?"
```
Expect: `ingestion.schema_drift` naming `location` as missing and `location_old` as unexpected, then `ingestion.aborted`, `exit=1` — no fetch happened at all (no page-level log lines, and it returns fast). Then confirm the table was untouched:
```
docker compose exec -T postgres psql -U internhunter -d internhunter_drift -c "SELECT COUNT(*) FROM clean_jobs;"
```
Cleanup: `docker compose exec -T postgres psql -U internhunter -d postgres -c "DROP DATABASE internhunter_drift;"`

**D — yield floor blocks the clean write**
Temporarily set `safety.min_yield` in `config/ingestion.yaml` above the run's actual yield, against the local DB:
```
uv run python -m src.services.ingestion.loader; echo "exit=$?"
```
Expect: `ingestion.yield_floor_breached` with both numbers, `exit=1`, no `ingestion.completed` line. `SELECT COUNT(*) FROM clean_jobs;` is unchanged from before, and `SELECT COUNT(*) FROM raw_jobs;` grew or held (raw landing is allowed to proceed). Revert `min_yield` to `20` afterwards — confirm you did.

**E — the ping path, without a real healthchecks.io account**
```
HEALTHCHECKS_URL="https://httpbin.org/status/200" uv run python -m src.services.ingestion.loader
```
Expect `ingestion.ping_sent` after the summary line. Then point it at a URL that fails (`https://httpbin.org/status/500` or an unroutable host) and confirm `ingestion.ping_failed` is logged as a warning while the process still exits `0`.

Do not run any of these against Neon. Local Docker only.

### T0019.7: Windowed keep-alive ping + Neon idle-pool verification

**Doc-only ticket — no code changed.** This section is a runbook for the maintainer to execute by hand on cron-job.org and to observe over ~24 h. Nothing here is run by a coder session. It closes the open question left in `docs/Known_Issues.md` (cold-start entry, `[HIGH · OPEN]` 750-hour entry) and `research/deployment-research-plan.md` §1a: **does the LangGraph checkpointer's idle Postgres pool alone keep Neon awake, regardless of which endpoint is pinged?** `src/core/checkpointer.py::build_checkpointer_pool` opens an `AsyncConnectionPool` with no `min_size`/`max_idle` override, so `psycopg_pool`'s default `min_size=4` holds four connections open at all times once the app starts — whether that idle-but-open state reads as active Neon compute is exactly what Part B measures.

#### Part A — Setup runbook (cron-job.org)

Follow once, in order:

1. Create a free account at [cron-job.org](https://cron-job.org) (or sign in if one already exists).
2. **Before entering any schedule**, open Account Settings and check the account's configured timezone.
   - If it is already `Asia/Ho_Chi_Minh` (UTC+7), enter the schedule in Step 5 using the **ICT** hours (`07:00`–`23:00`).
   - If it is anything else (commonly UTC by default), either change it to `Asia/Ho_Chi_Minh`, **or** leave it and enter the schedule using the **UTC** hours instead (`00:00`–`16:00`). Do not mix the two — entering ICT-intended hours into a UTC-configured account silently shifts the whole window 7 hours, which would ping straight through the Vietnamese night and burn instance-hours for no visitor benefit. This is the single easiest mistake in this ticket.
3. Click **Create cronjob**.
4. **Title:** `InternHunterAgent keep-alive` (or similar — cosmetic only).
5. **URL:** `https://internhunteragent.onrender.com/api/v1/health`
   - **Never** `https://internhunteragent.onrender.com/api/v1/ready` — `/ready` runs `SELECT 1` against Postgres (`src/api/routes/health.py:40-46`) and would hold Neon awake on every ping, defeating the entire point. `/health` (`health.py:13-21`) returns a static `{"api": "online"}` and touches no database — confirmed by reading the route, not assumed.
6. **Schedule:** use the custom/advanced schedule editor (not the simple "every N minutes" preset — that preset has no hour restriction and would run 24/7, triggering the 750-hour cliff below). Set:
   - **Minutes:** every 12 minutes (`*/12`) — inside the required 10–14 min range.
   - **Hours:** `7-22` if the account timezone is `Asia/Ho_Chi_Minh`, or `0-15` if entering UTC directly (both cover `07:00`–`22:59` ICT, i.e. the intended ~16 h window; the schedule naturally stops before `23:00`).
   - **Days:** every day.
   - **A 15-minute interval is not safe.** Render's idle timer is exactly 15 minutes. Any scheduler jitter — cron-job.org's own queueing delay, network latency, a slightly-late trigger — can push a single ping past the 15-minute mark, and the instance spins down anyway, defeating the ping that was supposed to prevent it. The 10–14 min range (12 used above) exists specifically to absorb that jitter.
7. Save the job. **Record the enable date/time** (e.g. in this file's Part B "Before enabling" column, or a note wherever the maintainer tracks it) — the 24-hour observation in Part B starts from this moment.
8. **Expected request volume**, for sanity-checking cron-job.org's own execution history afterwards: ~12 min interval × 16 h window ≈ 5 requests/hour × 16 h ≈ **~80 requests/day**.
9. **One honest caveat, carried forward from `research/deployment-research-plan.md` §1a's policy check:** Render's Acceptable Use Policy has no written rule against keep-alive pings, but one clause has a foothold — *"intentionally misuse the Service to avoid payment or financial responsibility"* — since a keep-alive obtains behavior Render sells at $7/mo (Starter). The §1a policy check reads this as low-risk and unsupported rather than prohibited (the windowed, non-24/7 shape is part of that argument). If the maintainer would rather not sit in that tension at all, decision-rule branch (c) below (Render Starter, $7/mo) removes it outright by making the ping unnecessary.

#### Part B — Measurement template

Fill in after enabling. Read Neon numbers from **Neon Console → project → Monitoring** (or **Usage**); read Render numbers from **Render Dashboard → service → Metrics** (or **Billing** for workspace-wide instance-hours). Neon's usage meter can lag — take the "after ~24 h" reading with a little slack (e.g. at +24–26 h) rather than at exactly +24 h.

| Metric | Before enabling | After ~24 h | Expected if healthy |
|---|---|---|---|
| Neon compute (CU-hours, last 24 h) | | | well under ~4 CU-h/day — see arithmetic below |
| Neon — does the compute show suspension gaps? | | | yes, gaps between pings |
| Render instance-hours (month to date) | | | tracking ≈16 h/day |
| Demo cold start during window | | | loads immediately, no blank tab |
| Demo after 23:00 ICT + 15 min | | | spins down as before |

**The arithmetic that makes this unambiguous:**
- The ping window is ~16 h/day (07:00–23:00 ICT). `/health` itself touches no database, so the *only* way pinging could keep Neon awake is the checkpointer's idle pool (4 connections, opened once at app startup and never touched by the ping request itself).
- **If Neon suspends properly** between pings (its own idle timer is 5 min — see §3 of `deployment-research-plan.md`), 24-hour compute should be a **small fraction** of the 16-hour window — the pool's presence doesn't matter if Neon still suspends on inactivity. This is the "well under ~4 CU-h/day" row.
- **If the idle pool holds Neon awake** for the full time Render is up, compute becomes **16 h × 0.25 CU = 4 CU-h/day**, which annualizes to **≈122 CU-h/month** — over the 100 CU-h/month free cap (see Part C's trigger below).
- A reading that lands clearly in one bucket or the other (near-zero vs. ≈4 CU-h/day) is the whole point of this measurement — it should not require judgment calls.

#### Part C — Decision rule (pre-written; apply in this order)

▎ **Trigger:** if the 24-hour reading shows Neon compute consistent with staying awake through the window (**≈4 CU-h/day, no suspension gaps**) → projected **≈122 CU-h/month against the 100 CU-h cap** → apply the rule below, in order.

1. **(a) Shed idle pool connections first.** Configure the checkpointer's psycopg pool with `min_size=0` and/or an idle-connection lifetime, with the new params added to `config/settings.yaml` (per this project's "parameters live in config" rule) — **this is a code change and is its own ticket**, not part of T0019.7. Neon resumes in ~300–500 ms (p95 ~2.6 s per §3), so the added per-request latency on a cold Neon connection is acceptable. **Re-run Part B for another 24 h after applying (a)** to confirm the fix actually reduced compute — do not assume it worked.
2. **(b) If (a) is insufficient:** shrink the ping window. Example: a 12 h/day window ≈ 3 CU-h/day ≈ **91 CU-h/month** — back under the 100 CU-h cap — at the cost of a cold start returning during the trimmed hours.
3. **(c) If neither works:** move to **Render Starter, $7/mo**, and drop the ping entirely. This sits inside the project's documented $10/month ceiling (`deployment-research-plan.md` §10) and removes the problem at the root — no spin-down means no keep-alive is needed, means no Neon pressure from this mechanism at all. This is also the clean way to sidestep the Render AUP tension noted in Part A step 9, if the maintainer would rather not carry it.

If the trigger does **not** fire (compute stays low, suspension gaps are visible), no action is needed — the ping is safe to leave running as configured.

#### Part D — Rollback

To disable: open the job on cron-job.org and **pause** it (no need to delete). Expect the status quo to return — Render spins down after 15 min idle again, and the next cold visitor after an idle gap waits ~60 s for the page itself, same as before T0019.7 was enabled.
