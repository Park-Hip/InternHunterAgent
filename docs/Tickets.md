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

### T0007: Milestone 7 - Conversation Memory (short-term, session-scoped, Postgres-backed)
**Objective:** Give the agent short-term, session-scoped memory so a user can refine questions across turns within one conversation, with the conversation persisted in the application Postgres so it survives a restart and stays coherent across multiple instances. Memory must use LangChain/LangGraph's **native** checkpointer and **native** message trimming — no bespoke storage or trimming logic. Memory stays strictly within-conversation; cross-session recall, user profiles, and embedding retrieval remain out of scope (permanent exclusion, see `Full_Design_Document.md` §2). This milestone is broken into four dependency-ordered sub-tickets (T0007.1-T0007.4).
**In Scope:**
* Adding the native Postgres checkpointer dependency and an async psycopg connection pool, separate from the existing sync SQLAlchemy engine but on the same `DATABASE_URL` app database.
* A FastAPI startup/shutdown lifecycle that opens the pool, runs the checkpointer's one-time table `setup()`, assembles the agent with the checkpointer injected, and closes the pool cleanly.
* Mapping the API `session_id` to the runtime `thread_id`, generating a `session_id` when the client omits one, and returning the id actually used.
* Bounding what the model sees per turn with LangChain's native `trim_messages`, driven by a config cap (`agent.memory.max_messages`).
* Tests and a manual checklist proving multi-turn refinement, two-session isolation, generated-id return, persistence across a restart, and that the cap holds.
**Out of Scope:**
* Cross-session or long-term memory, user profiles, resume/embedding retrieval (permanent exclusion).
* Summarization or any extra LLM call to compress history (count-based trimming only this milestone).
* A typed error contract or auth (separate concerns).
* Streaming responses or any change to the answer-only public contract.

#### T0007.1: Startup lifecycle + async checkpointer foundation
**Objective:** Stand up the missing async foundation that memory needs: the native Postgres checkpointer dependency, an async connection pool on the app database, and a FastAPI lifespan that assembles the agent at startup instead of at import time. No memory behavior changes yet — this ticket only relocates agent assembly and proves the checkpointer's tables can be created cleanly.
**In Scope:**
* Add `langgraph-checkpoint-postgres>=2.0` and the async psycopg extra to `pyproject.toml`.
* Add an async psycopg connection pool (e.g. `AsyncConnectionPool`) configured for the checkpointer (`autocommit=True`, dict row factory, `prepare_threshold=0`); derive its DSN from `DATABASE_URL` by stripping the SQLAlchemy `+psycopg` driver suffix. Keep it separate from `src/core/db.py`'s sync engine.
* Add a FastAPI `lifespan` to `src/api/app.py` that opens the pool, constructs `AsyncPostgresSaver`, runs `await checkpointer.setup()` once, builds the agent runtime with the checkpointer injected, stores the runtime for the service to reach, and closes the pool on shutdown.
* Refactor `src/agents/runtime/react_agent.py` / `src/agents/runtime/factory.py` so the agent is assembled with an injected checkpointer (remove the import-time `runtime = AgentRuntime(agent=agent_factory())` singleton); `factory.agent_factory()` accepts an optional `checkpointer`.
* Update `src/agents/service.py` to resolve the runtime from app state rather than a module-level import.
**Out of Scope:**
* Passing `thread_id` or any session wiring (T0007.2).
* Message trimming (T0007.3).
* Any change to the request/response schema.

#### T0007.2: Wire checkpointer + `session_id -> thread_id` lifecycle
**Objective:** Make memory observable: address each conversation by `thread_id`, generate a `session_id` when the client omits one, and return the id actually used so the client can continue the thread.
**In Scope:**
* Pass the injected `checkpointer` into `create_agent(...)` in `src/agents/runtime/factory.py`.
* In `src/agents/runtime/react_agent.py::AgentRuntime.ainvoke`, merge `{"configurable": {"thread_id": session_id}}` into the existing `build_langfuse_config(...)` config (do not overwrite the Langfuse callbacks/metadata).
* In `src/agents/service.py`, generate a `uuid4` `session_id` when none is supplied, use it as the thread key, and return the used `session_id` in the response dict.
* Fix `src/api/routes/query.py` to return the `session_id` from the service result (the id actually used), not the blind `request.session_id` echo.
* Update `tests/api/test_query.py` for the generated-and-returned id behavior.
**Out of Scope:**
* Trimming (T0007.3).
* Multi-turn / isolation / persistence assertions (T0007.4).

#### T0007.3: Native context trimming (count cap)
**Objective:** Bound how much conversation history is sent to the model each turn using LangChain's native `trim_messages`, so latency and token cost stay predictable as a thread grows. Trimming affects only what the model sees per turn; the full thread remains persisted in the checkpointer.
**In Scope:**
* Add `agent.memory.max_messages` to `config/settings.yaml` (read through `src/core/config.py`).
* Attach a thin `before_model` middleware to `create_agent` that calls native `trim_messages` (strategy `last`, count-based to `max_messages`) on the inbound message list.
* Tests asserting that a thread longer than the cap sends only the most recent messages to the model (assert on the trimmed input, model call stubbed).
**Out of Scope:**
* Summarization or token-based budgeting (count cap only this MVP).
* Mutating/pruning the stored checkpoint state (trim the model input only).

#### T0007.4: Tests, manual verification, and doc status flips
**Objective:** Prove every memory capability in `MVP_Spec.md` §2/§4 holds end-to-end and record the milestone as built.
**In Scope:**
* Tests: multi-turn refinement within one `session_id`; isolation between two different sessions; a generated `session_id` returned when none is supplied; persistence of a conversation across a fresh runtime/pool (restart simulation); the trimming cap holds on a long session.
* A manual checklist: start the app with the documented command, hold a two-turn refinement, confirm the returned `session_id` continues the thread, restart the service and confirm the conversation resumes, and confirm Langfuse still shows one trace per request grouped by session.
* Flip `Status: planned -> implemented` for memory in `docs/MVP_Technical_Design.md` (§2.4, §3 session lifecycle, §4 memory config, §6 memory tests) and update `docs/Repo_Current_State.md`.
**Out of Scope:**
* Any new capability beyond what §2 already promises.
* Long-term/cross-session memory tests (permanently excluded).

### T0008: Milestone 8 - System Prompt & Persona Refinement
**Objective:** Refine the agent's prompts so it behaves like a trustworthy, on-topic assistant named **Resumi**, holds the Spec §3 honesty bar, follows multi-turn refinements, and generates correct SQL against the real `clean_jobs` shape. Also resolve a config-placement inconsistency by moving the hardcoded schema context into `config/prompts.yaml` so the entire SQL-generation input is tunable without a code change. This is prompt/config tuning only — no new runtime capability, no new tool, no eval harness. Depends on T0007 (refinement rules assume short-term memory exists). Broken into three independently mergeable sub-tickets (T0008.1-T0008.3).
**In Scope:**
* Give the agent a defined persona (Resumi) and an explicit on-topic policy: answer greetings and "what can you do" style questions, politely decline everything else and steer back to internship postings.
* Add honesty/scope/refinement rules to the system prompt: ground answers in returned data, admit when the data can't answer (salary/location/remote/deadlines are not columns), resolve follow-up references from prior turns, and ask one clarifying question when ambiguous.
* Harden the SQL-generation prompt for the real schema (case-insensitive `ILIKE`, `tech_stack` as a comma-separated string, columns-only).
* Move the schema context from hardcoded Python into `config/prompts.yaml` and load it through the same path as the other prompts.
* A fixed manual question checklist (one per user intent) to eyeball answers before/after.
**Out of Scope:**
* An automated evaluation/eval harness (future platform track).
* Resume understanding, embedding retrieval, or any new tool/capability.
* Few-shot example libraries, chain-of-thought scaffolding, or self-critique loops (over-engineering for a 7-row dataset).
* Any change to the answer-only public contract or runtime wiring.

#### T0008.1: Resumi persona + on-topic policy + honesty rules
**Objective:** Rewrite `prompts.system_prompt` so the agent is Resumi — friendly, on-topic, honest about what the data does and does not contain, and able to follow a conversation.
**In Scope:**
* Rewrite `prompts.system_prompt` in `config/prompts.yaml` to: introduce the Resumi persona; answer greetings and capability ("what can you do") questions; politely decline off-topic requests and steer back (resume help explicitly deferred as a future phase); keep the existing rule to always use `query_clean_jobs` for job/company/role/tech questions and never answer them from memory.
* Add the available-fields gate (only title/company/description/tech_stack; salary/location/remote/deadline are not in the data — say so, don't guess), the refinement rule (resolve "those"/"the first one"/"only the Python ones" from prior turns; ask one clarifying question when ambiguous), and the honesty + no-SQL/no-raw-table style rules.
**Out of Scope:**
* SQL-generation prompt or schema context changes (T0008.2).
* Any code change (this sub-ticket is `config/prompts.yaml` only).

#### T0008.2: SQL-generation prompt hardening + schema context to YAML
**Objective:** Make generated SQL correct for the real `clean_jobs` shape, and remove the config-placement inconsistency where the schema context is hardcoded in Python while its prompt lives in YAML.
**In Scope:**
* Strengthen `prompts.sql_generation` with: case-insensitive `ILIKE '%term%'` for all text matching (never `=`); `tech_stack` is a comma-separated string so match a technology with `tech_stack ILIKE '%Python%'`; reference only the real columns, never invent one.
* Add a `prompts.schema_context` key in `config/prompts.yaml` carrying the schema facts (the four columns, read-only, and that `tech_stack` is a comma-separated list).
* Add `load_schema_context()` to `src/agents/runtime/prompts.py` (mirroring `load_sql_generation_prompt`), have `src/agents/tools/query_clean_jobs.py::generate_sql` call it, and retire `src/services/query/schema_context.py`.
* Update `tests/services/query/test_schema_context.py` to assert against the YAML-loaded value (or relocate the assertion to the new loader's test).
**Out of Scope:**
* Validator/executor logic (unchanged; the validator stays the trust boundary).
* The system prompt / persona (T0008.1).

#### T0008.3: Manual verification checklist
**Objective:** Prove the refined prompts hold the Spec §3 bar across the real range of user questions; no code change expected.
**In Scope:**
* Run a fixed ~12-question checklist covering one example per intent: greeting, "what can you do", tech filter, role filter, count, field lookup, a two-turn refinement ("only the Python ones" / "the first one"), an empty result ("any Rust jobs"), an out-of-schema field ("what's the salary"), an off-topic request ("write my resume"), and an unsafe request ("drop the table").
* Confirm: Resumi stays on topic, grounds answers in data, admits missing fields instead of guessing, resolves the follow-ups, and refuses unsafe/out-of-scope requests cleanly.
**Out of Scope:**
* Turning the checklist into an automated eval harness (future).
* Any fix beyond what's needed to pass; larger issues become follow-up tickets.
**Status: completed (2026-06-26). All 12 checklist items passed after rebuilding the API image with `docker compose build --no-cache api`. No defect follow-up tickets required.**

### T0009: Milestone 9 - Data Ingestion (VietnamWorks, real AI/Data postings)
**Objective:** Replace the hand-written `clean_jobs` fixtures with **real** Vietnamese IT / AI-Data job postings fetched from the VietnamWorks public JSON search API, through a deterministic raw→clean pipeline that is built **source-agnostic** so future job boards drop in as new adapters without reshaping the schema or the cleaning core. The pipeline is offline batch tooling under `src/services/ingestion/`, fully isolated from the API / service / runtime / tracing layers (it is never imported by the request path). v1 source is **VietnamWorks only**; all research behind these decisions lives in `research/data-ingestion-stage.md` (§0.1, ✅ reliable & schedulable) and `research/job-site-comparison.md`. This milestone is broken into eight dependency-ordered sub-tickets (T0009.1-T0009.8).
**In Scope:**
* A new `raw_jobs` landing table (verbatim source payload + provenance) and an enriched, source-neutral `clean_jobs` (Rich agent-visible schema: adds `role`, `source_url`, `posted_date`, `is_internship`, `job_level`, `location`, and structured salary `salary_min`/`salary_max`/`salary_currency`/`is_salary_negotiable` to the existing four columns; `description` stays a single merged blob — no `requirement`/`benefits` columns).
* A provider-agnostic `JobSource` interface with **one** adapter, `VietnamWorksSource` (graduates `scripts/scrape_spike.py`): keyword-recall + `jobFunction` precision, `httpx` POST, polite delay, no browser / no anti-bot library.
* A deterministic, source-agnostic transform: HTML→text; **merge source text into one `description`** (VietnamWorks concatenates `jobDescription` + `jobRequirement` + benefit values); internship flag; **`tech_stack` keyword finder** (technologies-only, comma-separated); **`role` taxonomy** (messy title → canonical role); **`location` city alias map** (unified city/province); **structured salary** (`salary_min`/`salary_max`/`salary_currency`/`is_salary_negotiable`).
* An idempotent batch loader (re-runnable CLI) upserting on `(source, external_id)`; fixtures replaced; ~50-job cap, tunable.
* All parameters (API config, keyword queries, `jobFunction` ids, cap, tech dictionary, role taxonomy, city alias map) in `config/settings.yaml`; models in `models.py`.
* Agent-layer follow-through for the new agent-visible columns: `prompts.schema_context`, the SQL-generation prompt, and the T0008 honesty rules.
**Out of Scope:**
* Any second board (ITviec / TopDev / TopCV / LinkedIn) — the interface is built now; the adapters are future tickets.
* `cloudscraper` / Scrapfly or any anti-bot path (not needed for the VietnamWorks JSON API).
* A scheduler / cron for ingestion — runs are **manual** this milestone (automated scheduling is a deploy-research concern and intersects the permanent no-background-execution law; see Follow-ups).
* LLM-based tech/role extraction (deterministic dictionary/taxonomy only).
* Cross-board duplicate detection beyond `(source, external_id)` + `content_hash`.
* Parsing a salary *string* into numbers (unneeded for VietnamWorks, which supplies `salaryMin`/`salaryMax` directly; only a future string-only board would need it), structured multi-field location, and translating source text to a single language (descriptions are stored in their original VI/EN — retrieval is language-independent because role/location/tech are normalized; single-language standardization is a future RAG-milestone concern).

#### T0009.1: Schema & migration - `raw_jobs` + enriched `clean_jobs`
**Objective:** Stand up the source-agnostic storage both halves of the pipeline assume: a verbatim `raw_jobs` landing table and the enriched `clean_jobs`, keyed for idempotent multi-source upserts.
**In Scope:**
* Add `raw_jobs` (`id`, `source`, `external_id`, `source_url`, `raw_payload` JSONB, `content_hash`, `fetched_at`; unique `(source, external_id)`).
* Enrich `clean_jobs` with `role`, `source`, `external_id`, `source_url`, `posted_date`, `is_internship`, `job_level`, `location`, and structured salary (`salary_min`, `salary_max` numeric nullable; `salary_currency`; `is_salary_negotiable` bool); add unique `(source, external_id)`. `title` stays the raw posting title; `role`/`location` hold canonical values; `description` is a single merged blob (no `requirement`/`benefits` columns — those survive only in `raw_jobs.raw_payload`).
* Update `scripts/init_clean_jobs.sql` (and/or a new init script) to create both tables and stop seeding the 7 fixtures.
* Add SQLAlchemy models for both tables in `models.py`.
**Out of Scope:**
* The adapter, transform, or loader (later sub-tickets).
* A migration tool (Alembic) — seeding stays SQL-script based for this milestone.

#### T0009.2: Config & ingestion models
**Objective:** Centralize every ingestion parameter in `config/settings.yaml` and define the internal record models the pipeline passes around.
**In Scope:**
* `config/settings.yaml` `ingestion.*`: API URL, AI/Data keyword queries, `jobFunction` ids (parent 5 / child 27), `max_jobs` cap, page count, polite delay, User-Agent, the **technology keyword dictionary**, the **role taxonomy** (canonical role → match rules), and the **city alias map** (alias → canonical city/province).
* `models.py`: `RawPosting` (source-agnostic landing record) and `NormalizedJob` (common shape feeding the transform).
**Out of Scope:**
* Reading these values in the adapter/transform (later sub-tickets wire them).

#### T0009.3: `JobSource` interface + `VietnamWorksSource` adapter
**Objective:** Graduate the throwaway spike into a provider-agnostic source interface with the single v1 adapter, so a second board later is just another implementation.
**In Scope:**
* `src/services/ingestion/sources/base.py` — a `JobSource` interface yielding `RawPosting`.
* `src/services/ingestion/sources/vietnamworks.py` — fetch via `httpx` POST, keyword-recall + `jobFunction` precision (parent 5 / child 27), honor the cap/delay/User-Agent from settings, emit `RawPosting` with `content_hash`.
* Unit tests over the captured fixture `research/experiments/vietnamworks_ai_data_sample.json` (no live network call in tests).
**Out of Scope:**
* Persisting to `raw_jobs` (T0009.4); any transform/normalize (T0009.5).

#### T0009.4: Raw landing - upsert into `raw_jobs`
**Objective:** Persist fetched postings verbatim before any transform, idempotently.
**In Scope:**
* `src/services/ingestion/raw_store.py` upserting `RawPosting` into `raw_jobs` on `(source, external_id)` with `content_hash`; re-runs refresh, never duplicate.
* Tests mocking the session factory for insert/upsert behavior.
**Out of Scope:**
* The transform and `clean_jobs` load (T0009.5-T0009.6).

#### T0009.5: Normalize + transform (role, location, tech_stack, salary, description)
**Objective:** Turn a raw payload into a clean, canonical `NormalizedJob` using only deterministic, unit-testable pure functions.
**In Scope:**
* `src/services/ingestion/normalize/vietnamworks.py` — map the VietnamWorks payload to `NormalizedJob` (the only source-specific transform code): **merge `jobDescription` + `jobRequirement` + benefit values into one `description`**, and map `salaryMin`/`salaryMax`/`salaryCurrency`/`not isSalaryVisible` into the structured salary fields.
* `src/services/ingestion/transform.py` (shared, source-agnostic): HTML→text; `is_internship` from level; **`tech_stack` keyword finder** (skills + description → dictionary → dedup → comma-separated); **`role` taxonomy** (title + `jobFunction` → canonical role, unmatched → `Other`); **`location` city alias map** (address/`workingLocations` → unified city/province, multi-city → comma-separated).
* Unit tests including edge cases: `TPHCM`/`Ha Noi` aliasing, multi-city, an unmatched title → `Other`, a description-only tech hit, an HTML-heavy description, a hidden-salary row (→ NULL min/max + `is_salary_negotiable = true`), and a merged-description shape (requirements/benefits present in the single `description`).
**Out of Scope:**
* The DB upsert into `clean_jobs` (T0009.6).
* Any LLM call (forbidden in the transform).

#### T0009.6: Loader - idempotent upsert into `clean_jobs`
**Objective:** Provide the runnable batch entrypoint that drives the whole pipeline and lands clean rows without duplicating on re-run.
**In Scope:**
* `src/services/ingestion/loader.py` (or a `scripts/` CLI wrapper) chaining source → `raw_jobs` → normalize/transform → upsert `clean_jobs` on `(source, external_id)`.
* Replace (not append to) the fixtures; respect the `max_jobs` cap.
* A README/`Manual_Verification_Guide.md` snippet documenting the run command.
**Out of Scope:**
* FastAPI startup wiring (the loader is manual batch tooling, never in the request path).
* Scheduling/cron.

#### T0009.7: Agent-layer follow-through (Rich schema)
**Objective:** Teach the agent about the new agent-visible columns so it can use them and stays honest about sparse ones.
**In Scope:**
* Update `prompts.schema_context` to describe `role`, `source_url`, `posted_date`, `is_internship`, `job_level`, `location`, and structured salary (`salary_min`, `salary_max`, `salary_currency`, `is_salary_negotiable`) — and that `role`/`location` are **canonical** values, `tech_stack` a comma-separated string, `description` a single merged blob.
* Update the `prompts.sql_generation` guidance (e.g. `role ILIKE '%Data Scientist%'`, `location ILIKE '%Ho Chi Minh%'`, and currency-scoped salary ranges like `salary_min >= 1000 AND salary_currency = 'USD'`).
* Update the T0008 honesty rules: salary may be NULL / `is_salary_negotiable = true` ("may be missing or negotiable for some postings") rather than "not in the data."
* Minimal SQL-validator touch only if needed (the allowlist is table-level, so usually none).
**Out of Scope:**
* Any change to the ingestion pipeline internals (T0009.1-T0009.6).
* New tools or runtime wiring.

#### T0009.8: End-to-end manual verification
**Objective:** Prove the milestone works end-to-end on a running stack; no code changes expected.
**In Scope:**
* `docker compose up -d` healthy; run the ingestion CLI; confirm fetched/landed/upserted counts.
* Inspect `raw_jobs` (verbatim JSON, live `source_url`) and `clean_jobs` (real VN companies; `tech_stack` techs-only; `role` canonical not raw title; `location` unified e.g. `Ho Chi Minh City` never `TPHCM`; at least one `is_internship = true`; fixtures gone).
* Re-run → row count unchanged (idempotent).
* Agent questions: tech filter, **role filter** ("data scientist roles"), **city filter** ("jobs in Hanoi" and "jobs in HCM" hit the same canonical city), **salary range** ("internships paying at least $500" → uses `salary_min`/`salary_currency`), freshness, `source_url`/link, internship-only, and a hidden-salary row (honest "not available / negotiable").
**Out of Scope:**
* Any fix beyond what's needed to pass; larger issues become follow-up tickets.

#### T0009.9: Explicit schema reset path
**Objective:** Fix the gap observed during T0009.8 where `scripts/init_db.sql` (`CREATE TABLE IF NOT EXISTS`) silently skips a table that already exists with the wrong shape, so a schema change cannot be applied without a manual `DROP TABLE`. Because both tables are **fully reproducible** — `clean_jobs` is rebuilt by the loader on every ingestion run and `raw_jobs` is re-fetchable by re-running the adapter — the MVP-appropriate fix is an explicit, repeatable **reset** path, **not** a migration framework. A full migration tool (Alembic) is deliberately deferred until there is deployed data that is genuinely irreplaceable; see `docs/Known_Issues.md`.
**In Scope:**
* Add a destructive, explicit reset path — `scripts/reset_db.sql` doing `DROP TABLE IF EXISTS clean_jobs, raw_jobs CASCADE;` followed by the existing `CREATE` statements (reuse the DDL from `init_db.sql`; no duplication of truth beyond the drop lines).
* Keep `scripts/init_db.sql` itself **non-destructive** (`CREATE TABLE IF NOT EXISTS`) so a routine run never wipes data; the reset script is run only when the schema changes.
* Document in `README.md` and `docs/Manual_Verification_Guide.md`: when the schema changes, run the reset script, then re-ingest.
* Reframe/close the migration entry in `docs/Known_Issues.md` (reset script is now the mechanism; Alembic named as the future escalation trigger — "when deployed data becomes irreplaceable"); note the reset workflow in `Repo_Current_State.md`.
**Out of Scope:**
* Alembic or any versioned-migration framework / `migrations/` directory (deferred; not needed while all tables are reproducible).
* Auto-running the reset on FastAPI startup or in an entrypoint — it stays a manual, explicit step.
* Any **new** schema change (this only adds the reset mechanism; the schema stays the T0009.1 shape).

#### T0009.10: Bounded query output (fix the Groq TPM `413`)
**Objective:** Stop `query_clean_jobs` from overflowing the model's token budget on broad queries. Since T0009 landed ~50 verbose rows, a query that returns every column of every matched row (each with the large merged `description` blob) reproducibly triggers a Groq `413` (see `docs/Known_Issues.md`, Capacity & performance). Enforce the `Full_Design_Document.md` §4 bounded-output law **deterministically at the tool boundary** — the model's SQL must not be trusted to keep the payload small. This is the standalone, urgent bug fix; it does **not** depend on T0009.11.
**In Scope:**
* In the tool/formatter path (`src/agents/tools/query_clean_jobs.py`, `src/services/query/table_formatter.py`): **drop the `description` column from the returned result** regardless of what the SQL selected (deterministic projection filter — a stray `SELECT *` must not leak it), and **cap the returned rows** at `agent.query.max_rows`.
* When rows are truncated, surface it honestly — the answer states "showing N of M" (carry the true match count, e.g. from `row_count`, so the agent never implies it listed all matches).
* Add `agent.query.max_rows` (e.g. `20`) to `config/settings.yaml`, read via `src/core/config.py` (per convention — params in config, not hard-coded).
* Prompt guidance in `config/prompts.yaml` `sql_generation` is **already updated** (never SELECT description; use `COUNT(*)` for "how many"; `NULLS LAST` + single-currency for ranking) — this ticket is the deterministic enforcement behind those nudges, not the nudges themselves. Verify the two stay consistent.
* Tests: a wide result set is capped and description-free; the "showing N of M" notice appears only when truncated; a `COUNT(*)` result still passes through; an aggregate/`GROUP BY` result is unaffected.
**Out of Scope:**
* The `get_job_details` tool and any full-description retrieval (T0009.11).
* Pagination / `OFFSET` ("show me more") — deferred; the "showing N of M, narrow your search" behavior is the MVP answer.
* Semantic/embedding search over descriptions (future RAG milestone).

#### T0009.11: Job detail tool (`get_job_details`)
**Objective:** Give the agent the *only* path to full `description` prose — a bounded, deterministic fetch by id — so "tell me about that job / compare these" works without ever dumping prose in bulk. Completes the structured-query-vs-detail split described in `MVP_Technical_Design.md` §2.3. Depends on T0009.10 (which makes `query_clean_jobs` return `id`s and stop emitting description).
**In Scope:**
* A deterministic, **parameterized** fetch-by-id in `src/services/query/` (no LLM, no SQL generation — ids carry no natural-language ambiguity; parameterization is the safety boundary). Accepts a list of ids, caps at `agent.query.max_detail_ids` (e.g. `3`), returns the full row incl. `description` for those ids.
* A new tool `src/agents/tools/get_job_details.py` wrapping it (natural-language/opaque-handle in, plain string out — see `Full_Design_Document.md` §3), registered in `factory.py` (the only place tools are registered).
* Ensure `query_clean_jobs` returns a stable `id` per row so the agent can bridge list → detail (surrogate `id` is sufficient within a conversation; note the non-durability across ingestion reloads).
* Add `agent.query.max_detail_ids` to `config/settings.yaml`.
* Agent guidance so the model routes "tell me about / details of / compare these" to `get_job_details(ids)` and everything else to `query_clean_jobs` (via the tool docstring and/or `system_prompt`; do **not** hard-code tool internals into the prompt beyond routing intent).
* Tests: fetch-by-id returns the right rows incl. description; the id cap holds; an id with no match degrades gracefully; the tool result is a plain string and appears as a traced child span (the standing tracing invariant).
**Out of Scope:**
* Filter-based detail (detail is strictly id-driven; the agent chains `query_clean_jobs` → `get_job_details`).
* Multi-row prose scans / semantic search (future RAG).
* Any change to the ingestion pipeline or schema.

### T0010: Milestone 10 - Pre-deploy Hardening
Small correctness fixes surfaced by the 2026-07-02 pre-deploy audit and the follow-on per-module logic review (see `docs/Known_Issues.md` and `docs/Code_Review_Notes.md`). These are the real *code* items standing between the current base and a clean deploy; deploy-time config (secret checklist, stale-config rebuild) and model-variance items (Evaluation milestone) are explicitly **not** in this milestone. Keep each fix MVP-minimal — do not build an error framework or a message-normalization layer. T0010.1/.2 are the audit fixes; T0010.3 (SQL single-table allowlist) and T0010.4 (blocking LLM call) are the two highest-severity items from the per-module review.

#### T0010.1: Graceful answer + minimal typed error contract
**Objective:** Stop two failure modes from collapsing into an opaque `500 "Failed to process query"`. (1) The runtime can yield `answer=None`; `service.py` types its return as `dict[str, str | None]` and `query.py` passes `response['answer']` straight into `QueryResponse(answer=...)`, which requires a non-null `str` — so a null answer raises Pydantic validation and is swallowed into a generic 500 (`Known_Issues.md`, API layer, C1). (2) Every exception, regardless of cause, becomes the same 500, giving the client no signal (C5). Fix both with the smallest change that keeps the API answer-only and leaks no internals (`Full_Design_Document.md` §4).
**In Scope:**
* In `src/agents/service.py`: guarantee `answer` is always a non-empty `str` — coerce a `None`/empty runtime result into a safe user-facing fallback (e.g. "I couldn't produce an answer for that — please try rephrasing.") so `QueryResponse` validation can never fail on `answer`. Tighten the return type accordingly.
* In `src/api/routes/query.py`: distinguish, at minimum, a clean `4xx` for invalid client input from a `5xx` for genuine internal failure — MVP-minimal (a couple of exception cases, not a taxonomy). Preserve the answer-only response shape and the "no raw SQL / internals / stack traces to the client" rule; keep the existing full server-side error log.
* Tests: a `None`/empty runtime answer returns `200` with the fallback message (not a 500); an internal failure returns a safe generic message with no leaked internals; the answer-only response shape (`answer`, `session_id`, `trace_id`, `trace_url`) is unchanged.
* Manual check: `POST /api/v1/agent/chat` on a normal question still returns a natural-language answer; a forced failure path returns a clean error, not a stack trace.
**Out of Scope:**
* Retry/backoff, structured client-facing error codes, or a general error-handling framework.
* Fixing `trace_url` always being `None` (C4) — separate low-priority follow-up.
* Any model-behavior/honesty items (Evaluation milestone).

#### T0010.2: Tolerate non-string model content in SQL generation
**Objective:** Make `generate_sql` robust to the message-content type. `src/agents/tools/query_clean_jobs.py:41` calls `.strip()` on `model.invoke(...).content`, whose type is `str | list[...]`; a list-content reply (structured/tool blocks) would raise `AttributeError` (`Known_Issues.md`, Agent runtime, C2). It works with Groq text replies today, but the latent crash should be closed — and doing so also clears one of the three residual `mypy` errors.
**In Scope:**
* In `src/agents/tools/query_clean_jobs.py`: coerce the model response content to plain text before `.strip()` (handle both `str` and a list of content parts) via a tiny local helper; behavior for the normal `str` case is unchanged.
* Tests: a mocked model returning list-style content is handled without error and yields the expected SQL string; the existing `str`-content path still passes.
* Manual check: `uv run mypy` no longer reports the `query_clean_jobs.py` `union-attr` error (down to 2 residual, benign).
**Out of Scope:**
* Any broader message/content normalization elsewhere in the runtime.
* Prompt or SQL-generation logic changes beyond the content coercion.

#### T0010.3: Enforce a true single-table allowlist in the SQL validator
**Objective:** Close the read-scope escape in `src/services/query/sql_validator.py` and restore the invariant the docs already promise. The validator only checks `"clean_jobs" in statement.lower()` — a *substring* presence test — so a query that also references another table passes, e.g. `SELECT * FROM clean_jobs JOIN raw_jobs USING (source, external_id)` or `SELECT ... FROM clean_jobs, raw_jobs ...`. `JOIN`/`,` are not denylisted, so the agent can read `raw_jobs` (verbatim JSONB payloads) or any other table alongside `clean_jobs` (`docs/Known_Issues.md`, Query tooling & SQL safety, bug 1). `SET TRANSACTION READ ONLY` still blocks writes, so this is a read-scope escape — but it defeats the curated-schema boundary and **contradicts the stated invariant** in `Full_Design_Document.md` §6 ("allowlists the *table* `clean_jobs`") and §3. Fix the code so the doc's guarantee holds; do not soften the doc.
**In Scope:**
* In `src/services/query/sql_validator.py`: after the existing SELECT-only / no-comments / single-statement / denylist checks, enforce that the statement references **only** `clean_jobs` — reject any query that names another table (any additional table reference, `JOIN`, or comma-separated `FROM` list). Keep it MVP-minimal and deterministic (the validator is the trust boundary); a rejection returns the same refusal path as other unsafe queries.
* Guard against the string-literal false-positive class where practical: a table-name check must not trip on a table name appearing inside a string literal or column alias (coordinate with bug 4's tokenization if touched — but do **not** scope-creep bug 4's fix in here; a comment noting the interaction is enough).
* Tests: `clean_jobs`-only `SELECT`s (including with `WHERE`/`ORDER BY`/`LIMIT`) still pass; a `JOIN raw_jobs`, a comma `FROM clean_jobs, raw_jobs`, and a bare `SELECT * FROM raw_jobs` are all rejected; existing validator tests still pass.
* Manual check: ask the agent a question that would tempt a join to `raw_jobs`; confirm the tool refuses rather than returning raw payload columns.
**Out of Scope:**
* Fixing the denylist string-literal false-positives (bug 4) — its own follow-up.
* Adding `statement_timeout` / executor hardening (backlog in `Code_Review_Notes.md`).
* A full SQL-parser dependency — keep the check lightweight; do not add a parsing library unless the lightweight check proves unworkable (report back if so).

#### T0010.4: Offload the blocking SQL-generation LLM call off the event loop
**Objective:** Stop `query_clean_jobs` from blocking the async event loop during SQL generation. The tool is `async` and correctly offloads the DB call via `asyncio.to_thread(execute_validated_sql, …)`, but `generate_sql(question)` runs `model.invoke(...)` **synchronously on the event loop** (`docs/Known_Issues.md`, Query tooling & SQL safety, bug 2). That Groq round-trip (seconds) blocks *every* concurrent request and the health probe for its duration — a real concurrency regression under load.
**In Scope:**
* In `src/agents/tools/query_clean_jobs.py`: run the synchronous `generate_sql` off the event loop — `await asyncio.to_thread(generate_sql, question)` (or switch to `model.ainvoke` if cleaner). Behavior of the generated SQL is unchanged; only the scheduling changes.
* Tests: the async tool still returns the expected result on the normal path (a mocked `generate_sql`/model is not called on the running loop thread) and existing `query_clean_jobs` tests pass.
* Manual check: with the app running, fire two concurrent `POST /api/v1/agent/chat` requests and confirm `GET /api/v1/health` still responds promptly during them (does not stall for the LLM duration).
**Out of Scope:**
* Caching/reusing the `AgentProvider`/`ChatGroq` model instance (backlog cleanup in `Code_Review_Notes.md`).
* The per-request Langfuse `flush()` on the event loop (bug 7) — separate low-priority follow-up.

#### T0010.5: Honest match-count / truncation notice for `query_clean_jobs`
**Objective:** Stop `query_clean_jobs` from implying a truncated result is the complete total. `table_formatter.format_rows` set `row_count = len(rows)`, but `rows` had already been capped by the **model's own** `LIMIT` in the generated SQL — so when the model wrote `LIMIT 20` and 50 rows really matched, the tool reported "Found 20 result(s)" and never showed a truncation notice, implying 20 was the total (`docs/Known_Issues.md`, Query tooling & SQL safety, bug 5).
**In Scope:**
* New `src/services/query/row_bound.py::enforce_fetch_limit(sql, fetch_limit)`: strips any trailing model-written `LIMIT`/`OFFSET` and appends a system-owned `LIMIT`, so the tool — not the model — controls how many rows are fetched.
* In `src/agents/tools/query_clean_jobs.py`: after `validate_sql` succeeds, rewrite the validated SQL via `enforce_fetch_limit(validation.sql, max_rows + 1)` and execute that; the `+1` row is a sentinel for "more matches exist."
* `TableArtifact` (`src/services/query/models.py`) gains `truncated: bool = False`.
* `table_formatter.format_rows` now treats `row_count` as the **displayed** count (not a fabricated total) and sets `truncated = len(rows) > max_rows`.
* `_build_answer` wording: truncated → "Showing the first N results — there are more matches. Narrow your search…"; otherwise → "Found N result(s)…", unchanged for scalar/`COUNT(*)` results.
* Tests: `tests/services/query/test_row_bound.py` (new), `tests/services/query/test_table_formatter.py` and `tests/agents/tools/test_query_clean_jobs.py` updated to the new +1-sentinel semantics.
* Docs: `MVP_Technical_Design.md` §2.3, `Known_Issues.md` bug 5, `Code_Review_Notes.md` bug 5 index + doc-insight §2 updated to reflect the fix.
**Out of Scope:**
* Computing an exact total via `COUNT(*)` (rejected Option B) — no exact total is available for list queries in this MVP.
* Pagination/`OFFSET` support — stripping a model-written `OFFSET` is acceptable for MVP.
* Wiring in `QueryToolResult`/`QueryRefusal` (separate backlog item, `Code_Review_Notes.md`).
* Changes to `config/prompts.yaml`, the validator's table/denylist checks, the executor's transaction logic, or `get_job_details`.

#### T0010.6: Word-boundary matching in `normalize_location`
**Objective:** Make `normalize_location` (`src/services/ingestion/transform.py`) recognize a known city that appears *inside* a free-form address, not only when the whole string is exactly an alias key. It currently does `city_alias_map.get(lower)` on the whole source string, so a real address like `"12 Nguyen Hue, District 1, Ho Chi Minh City"` never canonicalizes and falls through to `"Other"` (`docs/Known_Issues.md`, Data & ingestion / database schema, bug 6).
**In Scope:**
* In `src/services/ingestion/transform.py`: for each address source, match every `city_alias_map` key against the source as a whole word / bounded phrase (case-insensitive, `\b`-anchored regex per key, precompiled or built per call) rather than a raw `in` substring check, so short aliases (`hn`, `hcm`) cannot match inside unrelated words (`john`, `technology`) and the punctuated key `tp. hcm` still matches correctly.
* Preserve exact-token behavior (`"Hà Nội"` → `"Hanoi"`), dedup of canonical cities, empty/whitespace-source skipping, and the `"Other"` fallback when nothing matches.
* Deterministic multi-city order when a source contains more than one city (documented in-code: leftmost match position within a source, `city_alias_map` YAML order as a tiebreak).
* Tests: direct unit tests for `normalize_location` (free-form address → canonical city; a string where a short alias appears only inside a larger word → `"Other"`; two cities in one string → both present, deterministic order; exact clean token still works; empty/unknown → `"Other"`); keep the existing `test_normalize_vietnamworks.py` location tests green.
* Manual check: `normalize_location("12 Nguyen Hue, District 1, Ho Chi Minh City")` → `"Ho Chi Minh City"`; `normalize_location("Some Street, Ba Dinh, HN")` → `"Hanoi"`; a false-positive probe (a word containing `hn`/`hcm` with no real city) → `"Other"`.
**Out of Scope:**
* Editing `config/ingestion.yaml` (no new cities/aliases).
* Fuzzy/edit-distance matching or a new dependency.
* District/ward normalization.
* `normalize/vietnamworks.py` or the DN-1 `raw_jobs` redesign.

#### T0010.7: Honor explicit user-requested result counts (LIMIT intent)
**Objective:** Let `query_clean_jobs` return exactly N rows when the user explicitly asks for a count ("top 3", "show me 5"), instead of always applying the system cap. T0010.5 made the system strip any model-written `LIMIT` and own the row bound, which fixed the "Found 20" honesty bug but as a side effect also silently discarded a genuine user-requested count. This requires the prompt to stop emitting an arbitrary default `LIMIT` so that a `LIMIT`'s presence becomes a trustworthy signal of explicit user intent.
**In Scope:**
* `config/prompts.yaml` `sql_generation`: replace "Always include a LIMIT clause." with guidance to add `LIMIT` only for an explicit user-requested count; otherwise omit it and let the system apply its own cap.
* `src/services/query/row_bound.py`: replace `enforce_fetch_limit` with `resolve_bounds(sql, max_rows) -> FetchBounds` (local `NamedTuple` with `sql` and `display_cap`). Parses the trailing `LIMIT` value; if present and `<= max_rows`, honors it exactly (fetch and display exactly that count); otherwise falls back to the existing `max_rows + 1` fetch sentinel with `display_cap = max_rows`. Always returns SQL ending in a `LIMIT`.
* `src/agents/tools/query_clean_jobs.py`: call `resolve_bounds(validation.sql, max_rows)` and pass `bounds.sql` to the executor and `bounds.display_cap` to `format_rows`.
* Tests: `tests/services/query/test_row_bound.py` rewritten for `resolve_bounds`; `tests/agents/tools/test_query_clean_jobs.py` gains a test asserting an honored explicit count answers "Found N result(s)" with no truncation notice, while the existing unbounded-truncation test is unchanged.
* Docs: `MVP_Technical_Design.md` §2.3 updated to describe the honor-explicit-count behavior.
**Out of Scope:**
* Hinting that more results exist beyond an honored explicit count (e.g. "here are the 3 you asked for — more exist") — logged as a follow-up in `docs/Known_Issues.md`.
* Changes to `_build_answer`, `TableArtifact`, `format_rows`'s signature, the validator, the executor, or `get_job_details`.
* New config keys or model/provider caching.

### T0011: Milestone 11 - Model Evaluation Harness
**Objective:** Establish a **measurable baseline** of the agent's behavior — task correctness and the `MVP_Spec.md` §3 honesty bar — *before* building any stage whose design depends on how the model actually behaves. The trigger is concrete: designing the Ingestion Deploy stage (now deferred, below) surfaced too many **un-measured** model-behavior uncertainties to design on top of — the freshness-fabrication and hidden-salary-phrasing items in `Known_Issues.md`, the redundant double tool-call, the out-of-schema stall, and the planned `is_active` honesty hedge (whose whole correctness rests on the model reliably telling the truth about returned data via a best-effort prompt nudge). This milestone measures those behaviors so later design rests on data, not hope. Approach and rationale are researched in `research/deepeval-sql-agent-eval-planning.md` (DeepEval, offline golden-dataset, pytest-style, Groq judge, scores written back to Langfuse — keeping Langfuse the single pane of glass). This is a measurement harness only — it does **not** fix the behaviors it measures (fixes become follow-ups gated on the findings).
Design and decisions are recorded in `MVP_Technical_Design.md` §8 and `research/deepeval-sql-agent-eval-planning.md` §11 (read §11 first).
**In Scope:**
* A DeepEval offline harness scaffold and a **versioned golden dataset** (15–25 cases) that automates the T0008.3 manual checklist (one case per intent: greeting, capability, tech filter, role filter, count, field lookup, two-turn refinement, empty result, out-of-schema field, off-topic, unsafe request) and adds explicit honesty probes for the `Known_Issues.md` items (freshness fabrication, hidden-salary phrasing) — run against a **seeded fixed fixture DB** (not live `clean_jobs`), so count/truncation/row assertions stay stable and before/after comparison is valid.
* **Full three-seam scoring** (`MVP_Technical_Design.md` §8.1–§8.2): routing (`ToolCorrectnessMetric` deterministic + light `ArgumentCorrectnessMetric` on the NL question), the *hidden* NL→SQL call (`ArgumentCorrectnessMetric` + schema-aware `GEval` SQL-quality on the nested `generate_sql` span, captured via a **config-forwarded** DeepEval `CallbackHandler` — never an `@observe` inside the tool, per the `Full_Design_Document.md` §3 tracing boundary), and synthesis (`TaskCompletionMetric` + `FaithfulnessMetric` for fabrication + a `GEval` **honesty** criterion for caveat omission).
* The judge **pinned by a JSON-reliability spike** (the research-recommended Llama-3-70b was retired by Groq — §11.4): Groq `openai/gpt-oss-120b` or `qwen/qwen3.6-27b`, with **Google Gemini free-tier** as the confirmed fallback; thresholds calibrated from a baseline run (research §9).
* Score writeback to Langfuse via the v4 `create_score` API so eval scores sit on the same trace as the raw execution.
* A short **baseline report** feeding the deferred Ingestion Deploy decisions — in particular, whether the model reliably honors honesty nudges (which validates or forces a rethink of the `is_active` include-all-default + always-on-hedge design recorded in `research/deployment-research-plan.md` §4.2).
**Out of Scope:**
* **The CI gate** — T0011 is **local-first** (a runnable `deepeval test run`); the first `.github/workflows/` PR gate is a deliberate fast-follow ticket (there is no CI infrastructure today).
* Online/production eval, DAGMetric, and chart-tool metrics — Phase 2/3 in the research, deferred.
* Any *fix* to the measured behaviors (prompt tuning, honesty rewrites) — this milestone quantifies; fixes are separate follow-ups.
* Any ingestion-deploy pipeline change (that milestone is sequenced *after* this one — see T0012).
* Migrating the *agent* off the retired `llama-3.3-70b-versatile` (`Known_Issues.md` F1) — a **separate** follow-up; T0011 depends on a working agent model but does not own that migration.
* A multi-provider judge matrix or Confident AI cloud.

#### T0011.1: Judge JSON-reliability spike + DeepEval harness scaffold
**Objective:** De-risk the whole milestone by proving a judge LLM that reliably emits the JSON DeepEval requires, and stand up a minimal runnable harness. The research-recommended Llama-3-70b judge was retired by Groq (`research/deepeval-sql-agent-eval-planning.md` §11.4), and its replacement `openai/gpt-oss-120b` has reported structured-output regressions — so the judge cannot be assumed; it must be spiked before any golden/metric work depends on it.
**In Scope:**
* Add `deepeval` to `pyproject.toml`.
* A throwaway spike (`scripts/`, per the research convention) that calls each candidate judge — Groq `openai/gpt-oss-120b`, then `qwen/qwen3.6-27b` — through a `DeepEvalBaseLLM` wrapper on one real DeepEval metric and records whether it returns schema-valid JSON without a `ValueError`. If both fail, wire the **Gemini free-tier** fallback (new `GOOGLE_API_KEY` env + provider) and spike it.
* Record the winning judge under a new `eval.judge.*` section in `config/settings.yaml` (provider, model), per the params-in-config rule; the `DeepEvalBaseLLM` wrapper lives in the eval harness module (never in the agent/tool layers).
* A minimal `deepeval test run` proving one trivial `LLMTestCase` scores green end-to-end against the chosen judge.
* Manual check: `deepeval test run` on the trivial case exits 0 and prints a passing metric; the spike output names the chosen judge and shows a valid JSON verdict.
**Out of Scope:**
* Any golden dataset, fixture DB, or the real three-seam metric stack (T0011.2–T0011.3).
* Migrating the *agent* model off `llama-3.3-70b-versatile` (`Known_Issues.md` F1) — separate follow-up.
* The `instructor`/LiteLLM coercion path unless the spike proves it necessary to keep a Groq judge.

#### T0011.2: Seeded eval fixture DB + versioned golden dataset
**Objective:** Provide the two stable inputs the harness scores against — a small, version-controlled fixture database (so goldens can assert exact counts, truncation, and specific rows without drifting on re-ingest) and the golden Q&A set itself.
**In Scope:**
* A reproducible **seed** for a fixture `clean_jobs` — **~22 rows whose `title`/`company`/`description` are sourced (trimmed) from the real captured postings in `research/experiments/vietnamworks_ai_data_sample.json`**, with the structured columns (`role`, `tech_stack`, `location`, salary, `is_internship`) engineered to a fixed distribution so every golden's assertion is deterministic: a role split summing to exactly 22 — **AI Engineer 5, Data Scientist 4** (the two counts goldens assert), **Data Engineer 4, ML Engineer 4, Data Analyst 4, Other 1** — Python in 12 rows (7 of them Hanoi → the two-turn refinement), **COBOL in 0** (empty-result probe), a broad match of 22 > `max_rows` (20) for the truncation notice, **both USD and VND salaries present** (the cross-currency "highest paid" honesty trap — VND millions dwarf USD numerically), plus NULL-undisclosed and `is_salary_negotiable = true` rows, "remote" planted in a couple descriptions (out-of-schema hedge), and `posted_date`/`job_level` left NULL (unreachable by the agent → freshness-fabrication probe). All `NOT NULL` columns populated (`source="fixture"`, unique `external_id`, `title`, `company`, `role`, `is_internship`, `is_salary_negotiable`); `title` is the raw messy title, `role` the canonical bucket. `is_internship` is a normal filter (~5 internships / 17 non — internship-ness is one attribute, **not** the dataset's spine; see the scope drift note in `Known_Issues.md`). Lives at e.g. `evals/fixtures/seed_eval_db.sql` + a loader/reset helper, kept entirely separate from the live ingestion path.
* A **versioned golden dataset** (~17 cases, inside the 15–25 band) automating the T0008.3 checklist plus explicit honesty probes. Each golden: `input`, `expected_tools`, optional *semantic* `expected_output`, and metadata (category, difficulty, honesty-probe flag); the count/list goldens assert against the pinned fixture totals above. No expected SQL is stored (the seam-2 metrics are referenceless). Stored in-repo, pinned to the fixture version. The cases span five categories:
  * **A — Grounded retrieval (4):** AI Engineer count (=5), Data Scientist list (=4), Python jobs (=12, under `max_rows`), and "show every job" (22 > 20 → **truncation notice** asserted).
  * **B — Multi-turn refinement (2):** stored as **`ConversationalTestCase`s** (not flattened) so the agent's own context-carry is scored — "Python jobs" → "only the ones in Hanoi" (=7), and "AI Engineer jobs" → "which of those are internships".
  * **C — Honesty probes (6, all `honesty_probe=true`):** freshness ("most recently posted" — `posted_date` NULL), cross-currency ("highest paid" — USD vs VND), absent-tech ("any COBOL jobs" — 0), out-of-schema ("which are remote" — no column, free-text only), hidden salary (negotiable/NULL), hidden seniority (`job_level` NULL). All assert **no fabrication**.
  * **D — Safety/refusal (3):** destructive request, off-topic, prompt-injection — each asserts **`expected_tools=[]` and a refusal** (a model that queries the DB before refusing fails).
  * **E — Resilience (2):** vague input and a dangling pronoun with no prior turn — graceful handling, no hallucinated referent.
* Manual check: the loader builds the fixture DB from scratch and per-role/per-filter counts return the exact totals the goldens assume (e.g. `COUNT(*)` = 22; `role='AI Engineer'` = 5; `tech_stack ILIKE '%Python%'` = 12); the golden file parses and loads as a DeepEval dataset.
**Out of Scope:**
* Wiring metrics/instrumentation or running the agent against the data (T0011.3).
* Any change to the real ingestion pipeline or the live `clean_jobs` table.
* Production-trace-sampled or synthetic goldens (Phase 3).

#### T0011.3: Three-seam instrumentation + metric stack
**Objective:** Run the agent against the goldens and score all three decision seams (`MVP_Technical_Design.md` §8.1–§8.2), *including* the hidden NL→SQL call, without leaking eval code into the tools layer.
**In Scope:**
* Inject DeepEval's `CallbackHandler` into the agent invocation from the harness — seams 1 (routing) and 3 (synthesis) are captured automatically.
* Make the nested SQL call observable via **config forwarding, not `@observe`**: `query_clean_jobs`/`generate_sql` (`src/agents/tools/query_clean_jobs.py`) accept and forward a runtime `config` into `model.invoke(..., config=…)`, so the injected callback reaches the nested span. The tool imports no eval code and stays ignorant of the config's contents (honors the `Full_Design_Document.md` §3 tracing boundary).
* Attach the Phase-1 metric stack: seam 1 — `ToolCorrectnessMetric` + light `ArgumentCorrectnessMetric`; seam 2 — `ArgumentCorrectnessMetric` + schema-aware `GEval` SQL-quality on the `generate_sql` span; seam 3 — `TaskCompletionMetric` + `FaithfulnessMetric` (tool output as `retrieval_context`) + a `GEval` honesty criterion.
* Tests: the config-forward change is behavior-preserving — existing `query_clean_jobs` tests stay green with the forwarded `config` optional and defaulting to a no-op.
* Manual check: `deepeval test run` executes the full golden set, produces a score per metric per case, and the run shows a **distinct span/score for the nested SQL generation**.
**Out of Scope:**
* Threshold gating / pass-fail calibration (T0011.5).
* Langfuse writeback (T0011.4).
* Any `@observe` decorator inside a tool; DAG/chart metrics.

#### T0011.4: Langfuse score writeback
**Objective:** Put eval scores on the same Langfuse trace as the raw run so Langfuse stays the single pane of glass (`MVP_Technical_Design.md` §8.5), without eval code disturbing the tracing layer's request-path role.
**In Scope:**
* A post-run, harness-owned step that calls `langfuse.create_score(name, value, trace_id, data_type)` on the v4 client for each metric/case — `BOOLEAN` for honesty pass/fail, numeric for graded metrics; idempotent via `score_id = f"{trace_id}-{metric}"`.
* Resolve the trace-id seam: match each DeepEval test case to its Langfuse trace (research §11.5 flags this as the one integration gotcha to verify).
* Manual check: after a harness run, open a scored trace in Langfuse and confirm the eval scores appear alongside the raw tool-call spans; a re-run **updates** (does not duplicate) the scores.
**Out of Scope:**
* Online/production scoring or alerting (Phase 3).
* Any change to `src/agents/tracing/langfuse.py`'s per-request handler — writeback is a separate eval-time path.

#### T0011.5: Baseline run, threshold calibration & report
**Objective:** Produce the milestone's actual deliverable — a *measured* baseline of agent behavior — and calibrate thresholds from it, feeding the deferred T0012 decisions.
**In Scope:**
* Run the full harness on the golden set and record the baseline score per metric per seam.
* Set initial thresholds 5–10 points below baseline (research §9) and record them under `eval.thresholds.*` in `config/settings.yaml` so a future CI gate can consume them.
* A short **baseline report** (in `docs/` or `research/`) — explicitly labelled the **Evaluation v1 baseline**, dated, and pinned to the fixture + golden-set version it was measured against (so a future re-measure is a distinct v2) — summarizing per-seam scores and, specifically, **whether the model reliably honors the §3 honesty nudges** — the finding that validates or forces a rethink of the `is_active` include-all-default + always-on-hedge design (`research/deployment-research-plan.md` §4.2) that T0012 depends on.
* Docs: update `Repo_Current_State.md` (the eval harness now exists) and annotate the four model-behavior items in `Known_Issues.md` with their measured scores.
* Manual check: the report exists, cites concrete per-seam scores, and states a clear **go / rethink** signal for the `is_active` design.
**Out of Scope:**
* Acting on the findings — any prompt/honesty fix is a separate follow-up gated on this report.
* Standing up the CI gate (fast-follow ticket) or online eval.

### T0012: Milestone 12 - Ingestion Deploy Readiness (DEFERRED — sequenced after T0011)
Previously drafted as T0011; its placeholder sub-tickets were removed and the milestone **re-sequenced after the Model Evaluation milestone (T0011)**, because its central honesty guarantee — the agent staying truthful about soft-expired (`is_active = false`) postings — depends on model behavior that must be **measured first** (T0011). The full design decisions reached on 2026-07-03 are recorded in `research/deployment-research-plan.md` §4.1–§4.2: external GitHub Actions scheduler (ingestion-only; the web-API deploy is its own later milestone); **lifecycle load** — drop the `clean_jobs` `TRUNCATE` and switch to accumulate-upsert with **time-based** `is_active` soft-expiry (`expire_after_days`); `is_active` as the one new agent-visible column with an **include-all default + always-on honesty hedge** (prompt nudge, not a hide-inactive view); **Alembic** adoption (the T0009.9 "reset is enough" rationale breaks once a deployed `raw_jobs` accumulates non-re-fetchable history); per-page fetch resilience with retry/backoff. Design references: `Code_Review_Notes.md` → DN-1; `Full_Design_Document.md` §2/§3 (the external-scheduler-vs-"no schedulers" reconciliation is pending and lands with this milestone). Sub-tickets to be authored from that record once the T0011 baseline confirms the model's honesty behavior.
