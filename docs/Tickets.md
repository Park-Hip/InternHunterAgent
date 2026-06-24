### T0000: Milestone 0 - Foundation
**Objective:** Establish the stable local base for the MVP by wiring FastAPI, config loading, logging, and a health check. This ticket proves the application can boot locally with a minimal, inspectable foundation.
**In Scope:** 
* Update `pyproject.toml` with the minimum runtime and test dependencies needed for FastAPI, Uvicorn, config loading, logging, and tests.
* Write `src/api/app.py` to create the FastAPI app and include the API routers.
* Write `src/api/routes/health.py` to expose `GET /health`.
* Write `src/core/config.py` to load environment settings and secrets.
* Write `src/core/logger.py` to configure structured logging.
* Update `README.md` with local run instructions for the app and health endpoint.
**Out of Scope:** 
* `POST /api/v1/agent/chat`
* Any LangChain agent runtime
* Any tool use, SQL, memory, retrieval, or multi-agent routing
* Any Langfuse Docker stack or tracing callbacks
* Auth, background jobs, and frontend work

### T0001: Milestone 1 - Runnable Request Flow
**Objective:** Prove one end-to-end request path from FastAPI into an application service and back to the API. This ticket should return a structured answer payload without introducing tools or additional agent complexity.
**In Scope:** 
* Update `src/api/schemas.py` to define the request and response models for the chat endpoint.
* Update `src/api/routes/query.py` to expose `POST /api/v1/agent/chat`.
* Write `src/agents/service.py` to own request orchestration and call the runtime.
* Update `src/api/app.py` to mount the versioned route prefix.
* Update or add tests under `tests/api/test_query.py` for the success and failure response shape.
**Out of Scope:** 
* ReAct runtime internals
* Tool calling of any kind
* SQL execution or database connectivity
* Langfuse tracing integration beyond returning placeholder metadata
* Memory, retrieval, auth, or multi-agent behavior

### T0002: Milestone 2 - ReAct Agent Runtime
**Objective:** Add the ReAct-shaped agent runtime behind the request flow so the model execution lives outside the API layer. This ticket should make prompt and provider wiring easy to inspect without adding real tools yet.
**In Scope:** 
* Write or update `src/agents/runtime/factory.py` to build the LangChain agent.
* Write or update `src/agents/runtime/react_agent.py` to execute the agent runtime.
* Write or update `src/agents/runtime/provider.py` for the single model provider abstraction.
* Write or update `src/agents/runtime/prompts.py` for the system prompt loading logic.
* Update tests under `tests/agents/runtime/test_react_agent.py` to cover the runtime shape and answer extraction.
**Out of Scope:** 
* Real tool execution
* SQL tools or any database access
* Memory or thread persistence
* Langfuse deployment or tracing callbacks
* Route-layer agent logic or prompt construction

### T0003: Milestone 3 - Self-Hosted Langfuse
**Objective:** Stand up a local Langfuse stack so tracing can be added without depending on external infrastructure. This ticket establishes the self-hosted observability baseline for local development.
**In Scope:** 
* Write `docker/docker-compose.yaml` for Langfuse web, worker, Postgres, ClickHouse, Redis, and object storage.
* Add `.env.example` entries for Langfuse host URLs and API keys.
* Update `README.md` with startup instructions for the observability stack.
* Update any Docker support files needed to run the stack locally.
**Out of Scope:** 
* Application-side tracing callbacks
* SQL tooling or any agent feature work
* Memory, retrieval, auth, or UI work
* Production deployment hardening or scaling

### T0004: Milestone 4 - Tracing Integration
**Objective:** Attach Langfuse tracing to the agent execution path so each request can produce a visible trace. The tracing layer should stay isolated from the API route layer as much as possible.
**In Scope:** 
* Update `src/agents/tracing/langfuse.py` to build the Langfuse callback handler and trace metadata helper.
* Update `src/agents/runtime/react_agent.py` to pass tracing config into the agent call path.
* Update `src/agents/service.py` to surface trace metadata in the response object.
* Update `src/api/routes/query.py` and `src/api/schemas.py` to include trace fields in the API response.
* Update tests under `tests/api/test_query.py` and `tests/agents/runtime/test_react_agent.py` for trace behavior.
**Out of Scope:** 
* SQL tool execution
* Memory or conversation threading
* Additional tracing providers or custom analytics
* Multi-agent routing or background jobs

### T0005: Milestone 5 - Hardening
**Objective:** Make the MVP predictable by tightening error handling, timeouts, configuration checks, and test coverage. This ticket should improve developer feedback without changing the app's overall shape.
**In Scope:** 
* Update `src/core/config.py` and related runtime code to fail clearly on invalid configuration.
* Update `src/api/routes/query.py` and `src/agents/service.py` to produce consistent error handling and response behavior.
* Add timeout handling in the agent runtime where the model call is executed.
* Add or update integration tests under `tests/api/test_query.py` and `tests/agents/runtime/test_react_agent.py`.
* Add any small shared error helpers needed under `src/core/`.
**Out of Scope:** 
* SQL tools
* Memory
* New agent capabilities or extra tools
* Auth, frontend work, or deployment pipelines

### T0006: Milestone 6 - First Real SQL Tool
**Objective:** Give the ReAct agent its first production tool: a read-only `query_clean_jobs` tool that answers real questions against a Postgres `clean_jobs` table. SQL execution must stay isolated under `src/agents/tools/`, the LLM must never get raw SQL execution, and the public API must remain answer-only. This milestone is broken into ten independently mergeable sub-tickets (T0006.1-T0006.10), ordered by dependency.
**In Scope:**
* Standing up local Postgres (docker-compose) plus a SQLAlchemy session factory and `DATABASE_URL` config.
* Internal query DTOs, a deterministic table formatter, and a hardcoded `clean_jobs` schema context.
* A deterministic, read-only SQL validator (allowlist `clean_jobs`, denylist write statements and multi-statements).
* A sync SQL executor wrapped for async tool use, raising a custom `ExecutorError` instead of crashing the process.
* The `query_clean_jobs` LangChain tool adapter (question in, natural-language answer string out).
* Registering the tool in the agent runtime/factory and strengthening the system prompt to force its use for job-data questions.
* An audit confirming the public API response stays answer-only (no SQL/table leakage).
* End-to-end manual verification across the full stack.
**Out of Scope:**
* Giving the LLM direct/raw SQL execution.
* Write operations of any kind (INSERT/UPDATE/DELETE/DDL).
* A second LLM call to narrate results (deterministic answer string only, this milestone).
* Memory, retrieval, auth, or multi-agent routing.
* Schema columns beyond `title`, `company`, `description`, `tech_stack`.

#### T0006.1: DB Foundation - Postgres, dependencies, settings, session factory
**Objective:** Stand up the missing database foundation that later sub-tickets assume exists: a local Postgres instance, SQLAlchemy/psycopg dependencies, `DATABASE_URL` config, a session factory, and a seeded `clean_jobs` table.
**In Scope:**
* Add `sqlalchemy>=2.0` and `psycopg[binary]>=3.2` to `pyproject.toml`.
* Add `docker-compose.yml` at repo root with a single `postgres:16` service (port 5432, db `internhunter`, env-based user/password).
* Add required `DATABASE_URL` to `src/core/config.py` `Settings`; update `.env.example`.
* Create `src/core/db.py` exposing `engine` and `session_factory` (sync `sessionmaker`), no eager connections at import time.
* Create `scripts/init_clean_jobs.sql` creating `clean_jobs` (`id`, `title`, `company`, `description`, `tech_stack`) and seeding 5-10 rows.
* README snippet for `docker compose up -d` + running the init script.
**Out of Scope:**
* Query DTOs, validator, executor, or tool adapter (later sub-tickets).
* Any agent runtime or prompt changes.

#### T0006.2: Query result models
**Objective:** Verify and lock down the internal query result DTOs that the formatter, executor, and tool adapter will share.
**In Scope:**
* Review `src/services/query/models.py` (`TableArtifact`, `QueryRefusal`, `QueryToolResult`) against the design doc; trim whitespace/cleanup only.
* Add `tests/services/query/test_models.py` with one serialization test per model.
**Out of Scope:**
* New fields or models beyond what the design doc already specifies.
* Formatter, validator, or executor logic.

#### T0006.3: Deterministic table formatter
**Objective:** Finish the deterministic row-to-table format

* Implement/finish `format_rows(rows: list[dict]) -> TableArtifact` in `src/services/query/table_formatter.py`.
* Handle empty input, column-order stability from the first row's keys, and missing-key tolerance via `row.get(col)`.
* Tests at `tests/services/query/test_table_formatter.py` covering empty, single-row, multi-row, and missing-key cases.
**Out of Scope:**
* Schema context, validator, or executor work.
* Any LLM-facing prompt changes.

#### T0006.4: Schema context + SQL-generation prompt
**Objective:** Give the LLM a fixed, hardcoded description of the `clean_jobs` schema and a dedicated prompt for generating SQL from it, so SQL generation stays scoped to the four advertised columns.
**In Scope:**
* Create `src/services/query/schema_context.py` with `build_clean_jobs_schema_context()` describing `title`, `company`, `description`, `tech_stack` only.
* Add a `sql_generation` block to `config/prompts.yaml` (single read-only SELECT, no markdown fences, no commentary, always include LIMIT).
* Add `load_sql_generation_prompt()` to `src/agents/runtime/prompts.py`.
**Out of Scope:**
* The validator, executor, or tool adapter.
* Changes to the main agent system prompt (T0006.8).

#### T0006.5: SQL validator (deterministic, read-only)
**Objective:** Add a deterministic safety gate that rejects unsafe or out-of-scope SQL before it ever reaches the database.
**In Scope:**
* Create `src/services/query/sql_validator.py` exposing `validate_sql(sql: str) -> ValidationResult` (`valid`, `sql`, `reason`).
* Enforce: SELECT-only, no multi-statements, denylist of write/DDL keywords and comment-injection, must reference `clean_jobs`, denylist of system tables (`pg_*`, `information_schema`).
* Tests at `tests/services/query/test_sql_validator.py` covering at least 6 cases (allowed SELECT, each rejected statement type, multi-statement, unknown table, comment injection, leading whitespace).
**Out of Scope:**
* Actual SQL execution.
* Schema/prompt work from T0006.4.

#### T0006.6: SQL executor (sync, threadpool-friendly)
**Objective:** Execute validator-approved SQL against Postgres in a read-only transaction and translate database failures into a tool-friendly error instead of a process crash.
**In Scope:**
* Create `src/services/query/executor.py` with `execute_validated_sql(sql: str) -> list[dict]`, using `session_factory` and a read-only transaction.
* Wrap `OperationalError`/`DBAPIError` into a custom `ExecutorError`.
* Tests at `tests/services/query/test_executor.py` mocking `session_factory`, asserting result mapping and `ExecutorError` on DB failure.
**Out of Scope:**
* The LangChain tool adapter itself (T0006.7).
* Async wrapping (handled inside the tool, not the executor).

#### T0006.7: `query_clean_jobs` LangChain tool adapter
**Objective:** Wire schema context, SQL generation, validation, execution, and formatting into a single `@tool`-decorated adapter that returns a plain-string answer to the agent.
**In Scope:**
* Create `src/agents/tools/query_clean_jobs.py` following the `@tool` pattern in `src/agents/tools/time.py`; input `question: str`, output a natural-language answer string.
* Pipeline: build schema context -> generate SQL via `AgentProvider().build_model()` -> validate -> execute (via `asyncio.to_thread`) -> format -> build a boring deterministic answer string.
* Graceful refusal strings for validator rejection and `ExecutorError`.
* Tests at `tests/agents/tools/test_query_clean_jobs.py` covering happy path, validator-rejects, and executor-raises cases (mocking `generate_sql`, `validate_sql`, `execute_validated_sql`).
**Out of Scope:**
* Registering the tool in the agent factory (T0006.8).
* A second LLM call to narrate the answer.

#### T0006.8: Register tool in agent runtime + strengthen system prompt
**Objective:** Make `query_clean_jobs` available to the agent and force its use for job-data questions, while leaving the clock tool path untouched.
**In Scope:**
* Add `query_clean_jobs` to the `tools=[...]` list in `src/agents/runtime/factory.py`.
* Update the agent's system prompt in `config/prompts.yaml` with an explicit rule to call `query_clean_jobs` for job/company/role/tech-stack questions and never answer those from memory.
**Out of Scope:**
* Any change to the tool's internal pipeline (T0006.7).
* New tools beyond `query_clean_jobs` and the existing clock tool.

#### T0006.9: Keep public API answer-only
**Objective:** Gate-check that the public API still returns only `answer`, `trace_id`, and `trace_url` with no SQL or table leakage, now that a real data tool exists.
**In Scope:**
* Audit `src/agents/service.py` and `tests/api/test_query.py` for response shape.
* Fix only if leakage is found; otherwise no code change.
**Out of Scope:**
* Any new endpoint or response field.
* Tool, validator, or executor changes.

#### T0006.10: End-to-end manual verification
**Objective:** Prove the full milestone works end-to-end on a running stack; no code changes expected.
**In Scope:**
* Verify `docker compose up -d` brings up healthy Postgres and the API starts cleanly.
* Verify a job-data question returns a natural-language answer via `query_clean_jobs`, and a time question still uses `get_current_time`.
* Verify the refusal path (unsafe generated SQL) and confirm Langfuse shows one trace per request with tool invocations visible.
**Out of Scope:**
* Any fix beyond what's needed to make the checklist pass; larger issues become follow-up tickets.
