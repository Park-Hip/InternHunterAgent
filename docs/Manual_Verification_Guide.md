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

* Run `docker compose -f infra/docker-compose.yaml up --build` to start the local observability stack.
* Open the Langfuse UI in a browser at the local web port.
* Confirm the stack starts successfully and the Langfuse UI is reachable locally.

T0004: Milestone 4 - Tracing Integration

* Start the app with `uv run uvicorn src.api.app:app --reload`.
* Start the Langfuse stack with `docker compose -f infra/docker-compose.yaml up`.
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
* In a Python REPL: `from src.agents.runtime.prompts import load_schema_context; print(load_schema_context())` — confirm output lists only `title`, `company`, `description`, `tech_stack` and no other columns. (Note: `src/services/query/schema_context.py` was retired in T0008.2; the schema context now lives in `config/prompts.yaml`.)
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
* With the local stack running (`docker compose up -d`), `POST /api/v1/agent/chat` with `{"query": "What tech stack does Acme use?"}` and inspect the raw JSON — confirm only `answer`, `session_id`, `trace_id`, `trace_url` are present and `answer` reads as natural language, not a raw table/SQL dump.
* Repeat with `{"query": "what time is it?"}` and confirm the same response shape.

T0006.10: End-to-end manual verification

* Run `docker compose up -d`, then `docker compose ps` and confirm `postgres` and `api` both report `healthy`.
* `POST /api/v1/agent/chat` with `{"query": "What companies use Python?"}` — confirm a readable natural-language answer, then look up the returned `trace_id` in Langfuse (`GET /api/public/traces/<trace_id>` with basic auth, or the Langfuse UI) and confirm a `query_clean_jobs` tool call appears in the message trace.
* `POST /api/v1/agent/chat` with `{"query": "what time is it?"}` — confirm the answer and confirm via the trace that `get_current_time` (not `query_clean_jobs`) was called.
* Force the refusal path directly at the tool boundary (REPL): monkeypatch `generate_sql` to return `"DROP TABLE clean_jobs"` or `"SELECT * FROM pg_tables"` and call `query_clean_jobs.ainvoke(...)` — confirm a graceful refusal string (`"I can't run that query: ..."`), not a crash. (Asking the agent to delete/inspect schema in plain English typically gets refused by the model before it ever calls the tool, so this boundary check is the reliable way to exercise `validate_sql`'s rejection path.)
* Confirm Langfuse is reachable (`GET /` → 200) and that both the `query_clean_jobs` and `get_current_time` traces are listed via `GET /api/public/traces`.

T0007.1: Startup lifecycle + async checkpointer foundation

* Run `uv sync` and confirm `langgraph-checkpoint-postgres` and `psycopg-pool` install without conflicts.
* With Postgres up (`docker compose up -d`), start the API (`docker compose up -d --build api` or `uv run uvicorn src.api.app:app`) and confirm it boots cleanly — no import-time agent construction error, logs show `Application startup complete.` with no traceback.
* Connect to the app Postgres (`docker compose exec -T postgres psql -U internhunter -d internhunter -c "\dt"`) and confirm the checkpointer tables (`checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, `checkpoint_migrations`) were created by `setup()`.
* `POST /api/v1/agent/chat` with `{"query": "what time is it?"}` and `{"query": "What companies use Python?"}` — confirm both still return the same answer-only response shape (`answer`, `session_id`, `trace_id`, `trace_url`), now served via the app-state runtime instead of an import-time singleton.
* Stop the API container (`docker compose stop api`) and confirm the shutdown logs show `Waiting for application shutdown.` / `Application shutdown complete.` with no errors or warnings (the checkpointer connection pool closes cleanly).

T0007.2: Wire checkpointer + session_id -> thread_id lifecycle

* Run `uv run pytest tests/api/test_query.py -v` and confirm the supplied-id and generated-id cases both pass.
* With the stack up (`docker compose up -d`, API running), `POST /api/v1/agent/chat` with `{"query": "what time is it?"}` and no `session_id` — confirm the response contains a non-null `session_id` (a UUID).
* `POST /api/v1/agent/chat` with that returned `session_id` and a refining question (e.g. first "What companies use Python?", then "Which of those also use SQL?") — confirm the agent's answer reflects awareness of the prior turn (memory is working).
* `POST /api/v1/agent/chat` with an explicit `session_id` and confirm the same id is echoed back in the response.
* (Optional) Inspect the checkpointer tables in Postgres (`docker compose exec -T postgres psql -U internhunter -d internhunter -c "SELECT thread_id FROM checkpoints;"`) and confirm rows keyed by the returned `session_id` appear after a request.
* Confirm Langfuse still receives traces with session metadata (callbacks were not clobbered by the thread_id merge).

T0007.3: Native context trimming (count cap)

* Run `uv run pytest tests/agents/runtime/test_trimming.py -v` and confirm the config-validation, sync-trim, async-trim, and "state intact" cases all pass.
* Set `agent.memory.max_messages` to a small value (e.g. `4`) in `config/settings.yaml` and rebuild the API (`docker compose build --no-cache api && docker compose up -d api` — the config is baked into the image, so a no-cache rebuild is required to pick up the change).
* On one `session_id`, hold a conversation with more turns than the cap: turn 1 establishes a fact (e.g. "Remember this code word: BANANA42"), then run two more unrelated turns, then ask "What was the code word I gave you earlier?" — confirm the agent no longer knows it (the oldest turn fell outside the cap), while the recent turns still answered normally and nothing 500s.
* Confirm the full history is still persisted (trimming only affected the model input, not storage): `docker compose exec -T postgres psql -U internhunter -d internhunter -t -c "SELECT count(*) FROM checkpoint_blobs WHERE position('BANANA42' in encode(blob, 'escape')) > 0;"` and confirm a non-zero count — the trimmed-out fact is still in the checkpointer.
* Restore `agent.memory.max_messages` to its normal value (`20`) and rebuild; confirm a normal short conversation (under the cap) behaves exactly as before.

T0007.4: Memory tests, manual verification, and doc status flips

* Run `uv run pytest tests/ -v` and confirm the full suite passes, including the five memory capabilities in `tests/agents/runtime/test_memory.py` (multi-turn refinement, session isolation, generated-id returned, persistence across restart, trimming cap).
* With the stack up (`docker compose up -d`, API running), hold a two-turn refinement on a *generated* `session_id`: first `POST /api/v1/agent/chat` with `{"query": "What companies use Python?"}` and no `session_id`; note the returned `session_id`, then `POST` again with that id and `{"query": "Which of those also use SQL?"}` — confirm turn 2's answer reflects turn-1 context (memory is working).
* Restart the service (`docker compose restart api`) and `POST` again with the *same* `session_id` and a follow-up — confirm the conversation resumes (history survived the restart because it lives in Postgres, not process memory).
* Start a *second* `session_id` (omit it to get a fresh one) and ask an unrelated question — confirm it does not see the first session's history.
* Look up the returned `trace_id`s in Langfuse and confirm one trace per request, grouped by `session_id` (`langfuse_session_id` metadata).
* Re-read `docs/MVP_Technical_Design.md` §2.4, §3, §4, §6 and confirm memory now reads as *implemented* (no lingering `planned` tags for memory), and that `docs/Repo_Current_State.md` lists T0007.1–T0007.4 as completed.

T0008.2: SQL-generation prompt hardening + schema context to YAML

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

T0008.1: Resumi persona + on-topic policy + honesty rules

* In a Python REPL: `from src.agents.runtime.prompts import load_system_prompt; print(load_system_prompt().content)` — confirm the output opens with "You are Resumi" and includes sections for on-topic policy, the available-fields gate, refinement, and honesty rules.
* Run `uv run pytest tests/ -v` — confirm 66 tests pass, no regressions.
* With the stack up (`docker compose up -d`), exercise each behavior via `POST /api/v1/agent/chat`:
  * `{"query": "hi"}` or `{"query": "what can you do?"}` → Resumi introduces itself and lists internship/job postings as its focus.
  * `{"query": "What companies use Python?"}` → routes to `query_clean_jobs`, returns a data-backed answer (not from general knowledge).
  * `{"query": "What's the salary for that role?"}` → Resumi replies that salary is not in the data; does not guess.
  * Two-turn refinement on the same `session_id`: `"Show me backend roles"` then `"only the Python ones"` → turn 2 resolves "those" from turn 1's context.
  * `{"query": "Write my resume"}` → Resumi declines, frames resume help as a future phase, redirects to postings.
  * `{"query": "what's the weather?"}` → Resumi politely declines and redirects to internship postings.

T0008.3: Manual verification checklist — observed results (2026-06-26)

Stack: `docker compose build --no-cache api && docker compose up -d` — image rebuilt to pick up T0008.1/T0008.2 prompt changes; both `postgres` and `api` containers healthy. `clean_jobs` seeded with 7 rows.
Tests: `uv run pytest tests/ -q` → **70 passed** (no regressions).
Validator spot-check (Python REPL): `validate_sql("DROP TABLE clean_jobs")` → `valid=False, reason='Only SELECT statements are allowed'`; `validate_sql("SELECT * FROM clean_jobs LIMIT 10")` → `valid=True`. Boundary holds.

**12-question checklist — actual observed answers:**

| # | Query | Expected behavior | Observed answer | Result |
|---|-------|-------------------|-----------------|--------|
| 1 | `"hi"` | Resumi self-introduces by name | `"Hello. I'm Resumi, your friendly assistant for exploring internship and job postings. I can help answer questions about job postings in our database, including companies, roles, descriptions, and tech stacks. What would you like to know?"` | PASS |
| 2 | `"what can you do?"` | Lists internship/job posting help, declines off-topic | `"Hello, I'm Resumi… I can help you with questions about job postings in our database, such as companies, roles, descriptions, and tech stacks… Note that I don't currently offer resume writing or career coaching services, but those features are coming soon."` — on-brand, correctly defers resume help | PASS |
| 3 | `"Which internships use Python?"` | Routes to `query_clean_jobs`, returns data-grounded list | `"There are 6 internships that use Python. These include Backend Engineering Intern at Northstar Health, Data Engineering Intern at SignalForge Labs, Machine Learning Intern at Veridian Commerce, Platform Engineering Intern at Cobalt Cloud, Analytics Intern at BrightPath Mobility, and Software Engineering Intern at Northwind Research."` — correct, data-grounded | PASS |
| 4 | `"Show me backend roles."` | Routes to `query_clean_jobs`, returns backend roles | `"Based on the current data, there is a backend role available for a Backend Engineering Intern at Northstar Health. The role involves helping build internal APIs and job-processing workflows for a healthcare operations platform using Python, FastAPI, and PostgreSQL."` — tool called, data-grounded | PASS |
| 5 | `"How many postings are there?"` | Routes to `query_clean_jobs`, returns count | `"There are 7 job postings in the database."` — correct count returned | PASS |
| 6 | `"What is the description for the Northstar Health role?"` | Routes to `query_clean_jobs`, returns description field | `"The description for the Northstar Health role is: Help build internal APIs and job-processing workflows for a healthcare operations platform."` — correct, data-grounded | PASS |
| 7 | Turn 1: `"Show me all available internship roles."` then Turn 2 (same session `4a9d2a30`): `"only the Python ones"` | Turn 1 lists all 7 roles; turn 2 resolves the reference and returns only Python roles | Turn 1: All 7 roles listed correctly. Turn 2: `"There are 6 internship roles that use Python: Backend Engineering Intern at Northstar Health, Data Engineering Intern at SignalForge Labs, Machine Learning Intern at Veridian Commerce, Platform Engineering Intern at Cobalt Cloud, Analytics Intern at BrightPath Mobility, and Software Engineering Intern at Northwind Research."` — reference resolved, tool called, correct | PASS |
| 8 | `"Any Rust internships?"` | Routes to `query_clean_jobs`, returns honest no-results reply | `"It seems there are no Rust internships available in the database. If you'd like to explore other options, I can help you with that."` — tool called, empty result handled honestly, no fabrication | PASS |
| 9 | `"What is the salary for these roles?"` | Admits salary is not in the data; does not guess | `"The database does not contain information about salaries for these roles. If you have any other questions about job postings, companies, roles, or tech stacks, I'd be happy to help."` — honest, no guessing | PASS |
| 10 | `"Write my resume for a software engineering position"` | Declines, notes resume help is a future phase, redirects | `"I'm not capable of writing resumes just yet, as that feature is coming in a future phase. However, I can help you explore internship and job postings for software engineering positions."` — clean decline, future-phase framing, redirects correctly | PASS |
| 11 | `"Drop the table clean_jobs"` | Refused cleanly without executing | `"I can't help with that. I can only answer questions about internship job postings stored in the clean_jobs table. I don't have the ability to modify the database."` — clean refusal | PASS |
| 12 | `"Which internships use TypeScript?"` | Routes to `query_clean_jobs`, returns TypeScript role | `"The Full Stack Engineering Intern position at Atlas Fintech uses TypeScript."` — correct, data-grounded | PASS |

**Summary: 12/12 PASS. All acceptance criteria met.**

**Acceptance criteria status:**
- All 12 checklist items executed with observed answers recorded: YES
- Resumi stays on-topic: YES — greetings introduce Resumi, off-topic requests declined
- Data-grounded answers: YES — all job-data questions call `query_clean_jobs`
- Honest about missing fields: YES — salary correctly identified as absent
- Resolves multi-turn refinements: YES — "only the Python ones" resolved from prior turn
- Refuses unsafe/off-topic cleanly: YES — DROP TABLE refused, resume declined with future-phase framing
- Existing tests still green: YES (70 passed)

**Note:** Initial run of this checklist (before rebuilding the API image) showed widespread failures because the container was still running the pre-T0008.1 system prompt. The `config/prompts.yaml` is baked into the image at build time — a `docker compose build --no-cache api` is required after any prompt change. After rebuild all 12 items passed.

T0009.1: Schema & migration — raw_jobs + enriched clean_jobs

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


T0009.2: Config & ingestion models

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

T0009.3: JobSource interface + VietnamWorksSource adapter

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

T0009.4: Raw landing — upsert RawPosting into raw_jobs

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

T0009.6: Loader — idempotent replace of clean_jobs

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

T0009.5: Normalize + transform — pure function pipeline

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

T0009.7: Agent-layer follow-through (Rich schema)

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

T0009.8: End-to-end manual verification — observed results (2026-07-01)

Stack: `docker compose up -d` (postgres + api healthy) → `docker compose build --no-cache api && docker compose up -d api` (picks up T0009.7 prompt changes and the location-normalization fix below).

**Pre-existing-state note:** the local Postgres volume (running 7 days across prior milestone sessions) still had the *pre-T0009* 5-column `clean_jobs` (7 demo rows). `scripts/init_db.sql` uses `CREATE TABLE IF NOT EXISTS`, so it silently skipped migrating it. With the user's explicit go-ahead, dropped and recreated `clean_jobs` via the init script to pick up the T0009.1 rich schema before verification could proceed. `raw_jobs` did not exist yet either; created via the same script (piped over stdin since `scripts/` is not volume-mounted into the postgres container — `docker compose exec -T postgres psql ... < scripts/init_db.sql` rather than `-f`).

**Defect found and fixed (trivial, required to pass):** `to_normalized_job` (`src/services/ingestion/normalize/vietnamworks.py`) read `loc["name"]` from the `workingLocations` array, but the live VietnamWorks API returns `cityName` (confirmed directly against `raw_jobs.raw_payload`, e.g. `{"cityId": 24, "cityName": "Ha Noi", ...}`). Since `"name"` never exists, `working_location_names` was always empty, so every row fell through to `location = "Other"` — location canonicalization silently never ran (`city_alias_map` itself was correct). Fixed the field name to `cityName`; updated the test fixture (`tests/services/ingestion/fixtures/vietnamworks_raw.json`), which encoded the same wrong field name, to match. `tests/services/ingestion/test_normalize_vietnamworks.py` (28 tests) still pass after the fix. This was required to pass step C (location spot-check) and F.3 (city-filter agent question) below.

**A. Ingestion pipeline:** `uv run python -m src.services.ingestion.loader` → `{'fetched': 50, 'raw_upserted': 50, 'clean_loaded': 50}`, exit 0, no stack trace. PASS

**B. raw_jobs:** `SELECT count(*) FROM raw_jobs;` → 50. Spot-check: `source='vietnamworks'`, live `vietnamworks.com` URLs (e.g. `https://www.vietnamworks.com/ai-engineer-2075712-jv`), `jsonb_typeof(raw_payload) = 'object'`. PASS

**C. clean_jobs:** `SELECT count(*) FROM clean_jobs;` → 50; `SELECT DISTINCT source FROM clean_jobs;` → only `vietnamworks` (old fixtures gone). Spot-check 8 rows: `title` is the raw posting title (including Vietnamese titles, unstripped); `role` is canonical (`AI Engineer`, `Data Scientist`, `Data Analyst`, `Other` for unmatched); `tech_stack` is comma-separated technologies only (e.g. `Python, PyTorch, LangChain, Airflow`); `location` is unified (`Hanoi`: 28, `Ho Chi Minh City`: 19, multi-city rows, 1 `Other`) after the fix above; `description` is a single merged blob. `is_salary_negotiable = true AND salary_min IS NULL` → 43 rows. `is_internship = true` → 1 row. PASS

**D. Idempotency:** re-ran the loader → `{'fetched': 50, 'raw_upserted': 50, 'clean_loaded': 50}`; `clean_jobs` count unchanged (50); `raw_jobs` count unchanged (50); zero duplicate `(source, external_id)` pairs. PASS

**E. Empty-fetch / error-propagation guard:** `uv run pytest -q tests/services/ingestion/test_clean_store.py` → 9 passed, confirming `replace_clean_jobs([])` returns 0 and skips `TRUNCATE`. Code read of `run_ingestion` (`loader.py`): `postings = list(source.fetch())` runs and can raise before `upsert_raw_postings`/`replace_clean_jobs` are ever called — a source exception aborts before any DB write. PASS (verified per Known_Issues.md #34 — see below)

**F. Agent questions (live stack, `POST /api/v1/agent/chat`):**

| # | Query | Expected | Observed | Result |
|---|-------|----------|----------|--------|
| 1 | "Show jobs using PyTorch" | `tech_stack ILIKE '%PyTorch%'` | Listed 5 real postings (Vinsmart Future, MBBank ×3, Hoya Glass Disk), data-grounded | PASS |
| 2 | "Show me data scientist roles" | `role ILIKE '%Data Scientist%'` | Listed 3 real postings with company/salary detail | PASS |
| 3a | "jobs in Hanoi" | Canonical city hit | **FAIL first attempt** — `500 {"detail":"Failed to process query"}`; API log shows Groq `413` — result set (28 Hanoi rows × full descriptions) exceeds the org's 12000 TPM limit (`Requested 14020`/`14527`). Reproduced twice. See Known_Issues below. |
| 3b | "jobs in Ho Chi Minh City" | Canonical city hit | Listed 21 real postings after one internal retry/backoff; same token-budget risk, narrowly avoided | PASS (marginal — see Known_Issues) |
| 4 | "internships paying at least 500 USD" | `salary_min >= 500 AND salary_currency = 'USD' AND is_internship = true` | "I couldn't find any internships with a salary of at least $500" — verified against DB: the one internship row has `salary_min IS NULL`, so the honest no-result is correct | PASS |
| 5 | "Which of the AI Engineer jobs were posted most recently?" (+ exact ticket wording, 3 attempts total) | Honest decline, no fabricated date | **Non-deterministic**: 1 of 3 attempts fabricated a specific "most recently posted" job despite `posted_date` being absent from the schema; 2 of 3 correctly declined ("the data does not contain information about the posting date"). See Known_Issues below. | FAIL (intermittent) |
| 6 | "Give me the link to the AI Engineer job at Vinsmart Future" | Returns real `source_url` | Returned `https://www.vietnamworks.com/ai-engineer-2075712-jv` — verified exact match against `clean_jobs.source_url` | PASS |
| 7 | "show only internships" | `is_internship = true` | Returned the one internship row (AI Engineer Intern, K&M Holdings) with correct detail | PASS |
| 8 | "What is the salary for the AI Engineer job at Vinsmart Future?" (hidden-salary row, 2 attempts) | "may be missing/negotiable" framing, not "not in the data" | Both attempts: "The salary information ... is not available in the data" — reproducibly uses phrasing the T0009.7 honesty rule explicitly says not to use. Confirmed this is LLM prompt-adherence, not a formatting bug (the table formatter renders raw column values only). See Known_Issues below. | FAIL (reproducible) |

**Summary: 5/8 clean PASS, 1/8 marginal PASS, 2/8 FAIL (both logged to Known_Issues.md as follow-ups, not fixed here per ticket scope).**

**G. robots.txt / ToS:** `https://ms.vietnamworks.com/robots.txt` → HTTP 404 (no robots.txt exists on the API host — no restrictions declared). `https://www.vietnamworks.com/robots.txt` (main site, for context) disallows only login/profile/apply/preview paths (`/my-profile`, `/dang-nhap/`, `/jobseekers/apply_online.php`, `/company/preview/*`, etc.) — nothing touching `/job-search/v1.0/search`. The API path used by `VietnamWorksSource` is clear. PASS

**Tests:** `uv run pytest -q` → 184 passed, 4 subtests passed (no regressions after the location fix).

**Acceptance criteria status:**
- Full pipeline runs live, counts non-zero, re-run idempotent: YES
- raw_jobs/clean_jobs contents match every criterion (after the location fix), ≥1 internship, ≥1 hidden-salary row: YES
- All eight agent questions behave as specified: **NO** — city filter (Hanoi) and freshness honesty and hidden-salary phrasing surfaced real, reproducible issues; logged as follow-ups per ticket scope ("only make a code change if it's trivial and strictly required to pass")
- `uv run pytest -q` still green: YES (184 passed, 4 subtests)
- Docs updated, milestone closed: YES (this section, `Repo_Current_State.md`, `Known_Issues.md`)

T0009.9: Explicit schema reset path

* When the schema shape changes and `init_db.sql` (`CREATE TABLE IF NOT EXISTS`) silently skips a table that already exists with the wrong shape, use the reset workflow instead of a manual `DROP TABLE`:
  1. `docker compose up -d`; confirm Postgres is healthy and both tables exist with data — `docker compose exec -T postgres psql -U internhunter -d internhunter -c "SELECT count(*) FROM clean_jobs;"` returns a non-zero count after an ingest.
  2. Run the reset: `docker compose exec -T postgres psql -U internhunter -d internhunter -f scripts/reset_db.sql`. Expect no errors; the `\i` include echoes the `CREATE` statements from `init_db.sql`.
  3. Confirm the schema was recreated empty: `docker compose exec -T postgres psql -U internhunter -d internhunter -c "\d clean_jobs"` and `"\d raw_jobs"` show the full T0009.1 columns; `SELECT count(*) FROM clean_jobs;` → `0`.
  4. Re-ingest: `uv run python -m src.services.ingestion.loader` → counts non-zero again; the app answers a normal question.
  5. Confirm `init_db.sql` alone is still non-destructive: re-run `docker compose exec -T postgres psql -U internhunter -d internhunter -f scripts/init_db.sql` against the populated DB and verify row counts are unchanged (`IF NOT EXISTS` skips recreation).
* `uv run pytest -q` still passes (no code touched by this ticket).
