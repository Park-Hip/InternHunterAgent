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

### T0009: Milestone 9 - Evaluation Harness
**Objective:** Promote the T0008.3 manual checklist into an automated, scored evaluation of the agent against a fixed question set covering the `MVP_Spec.md` §2/§3 capabilities, so every later change (prompts, RAG, larger dataset) is measured rather than guessed. The harness has three layers, each an independently mergeable sub-ticket: a deterministic in-repo runner is the spine and works alone; an LLM-as-judge layer grades fuzzy answer quality; and Langfuse Datasets/Experiments give run history and a UI. The eval calls the real model — it is non-deterministic and token-costing, so it is a separate `eval` command, never part of the standard unit-test CI gate. Depends on T0007 (multi-turn cases need memory) and T0008 (the persona/honesty behavior being evaluated). This is measurement only — no new agent capability, no new tool.
**In Scope:**
* A version-controlled case file describing questions, categories, and behavioral assertions for the Spec §2/§3 bar (grounding, correct filtering, honest missing-field handling, empty results, refusal, on-topic persona, multi-turn refinement).
* An in-repo runner that invokes the real agent and scores each case deterministically.
* An optional LLM-as-judge layer for answer-quality grading on fuzzy cases.
* Publishing the case set and scores to the self-hosted Langfuse stack.
* A documented command to run the eval and read the summary.
**Out of Scope:**
* A third-party eval framework (ragas/deepeval/promptfoo) or any new heavy dependency.
* Making the eval a blocking unit-test/CI gate (it is real-model, non-deterministic, and costs tokens).
* Any change to the agent, tools, prompts, or public contract (this milestone only observes).
* RAG, resume, charts, or dataset expansion (later milestones).

#### T0009.1: Eval dataset + in-repo deterministic runner
**Objective:** Build the spine — a fixed case set and a runner that invokes the real agent and scores behavioral pass/fail — that is useful on its own without the judge or Langfuse layers.
**In Scope:**
* Add an eval case file (e.g. `eval/cases.yaml`) with entries: `id`, `category`, `turns` (one or more user messages for multi-turn), and `assertions` (e.g. `must_refuse`, `must_contain_any`, `must_not_contain`, `says_no_results`, `names_real_company`).
* Add a standalone runner script `scripts/run_eval.py` (not a pytest/CI target) that calls the agent per case (driving a session for multi-turn cases), maps each assertion type to a deterministic check, and prints a scored summary with per-category counts.
* Cases covering: grounding, correct filtering (ILIKE on the CSV `tech_stack`), honest missing-field (salary/remote), empty result (Rust), refusal (drop table), on-topic persona (greeting, "what can you do", decline "write my resume"), and a two-turn refinement.
* README/`docs` note documenting the single command to run it.
**Out of Scope:**
* LLM-as-judge scoring (T0009.2).
* Langfuse dataset/experiment publishing (T0009.3).

#### T0009.2: LLM-as-judge scoring layer
**Objective:** Add an optional quality-grading layer for fuzzy cases where a deterministic substring check is too blunt, isolated so the deterministic runner still works without it.
**In Scope:**
* Add an `eval_judge` prompt block to `config/prompts.yaml` and a loader following the existing `load_*_prompt()` pattern.
* A judge function that calls a **distinct judge model** (configured under `eval.judge.*` in `config/settings.yaml` — its own model/provider/key, temperature 0, offline only; permitted because the single-provider law is serving-path-scoped per `Full_Design_Document.md` §7) to grade a case's answer against a rubric and return a score/verdict.
* Config flag to enable/disable the judge layer; when disabled, the deterministic runner is unaffected.
* Apply the judge only to a tagged subset of cases to control cost and flakiness.
**Out of Scope:**
* Replacing deterministic checks (the judge augments, never the sole gate).
* Any Langfuse integration (T0009.3).

#### T0009.3: Langfuse Datasets + Experiments integration
**Objective:** Give the eval run history and a UI by publishing the case set as a Langfuse dataset and attaching scores to the runs, reusing the already self-hosted stack.
**In Scope:**
* Push the eval case set to a Langfuse dataset; link each eval run's traces to its dataset items.
* Attach deterministic (and, if enabled, judge) scores to the run for per-case and aggregate views.
* Degrade to a no-op when Langfuse credentials/stack are absent — the in-repo eval must still run (same principle as the tracing layer).
**Out of Scope:**
* Moving the source of truth into Langfuse (the in-repo case file stays canonical).
* Any change to the request-path tracing already built in T0004.

### T0010: Milestone 10 - Larger Dataset (outline)
**Objective:** Replace the 7-row fixture sample with a larger curated **fixed** dataset on the same pipeline, so the evaluation harness and any future RAG/semantic work operate on realistic volume and variety. This remains a fixed sample — live or real-time ingestion stays a later phase.
**In Scope (provisional):**
* A larger curated `clean_jobs` seed (target ~50-150 rows) covering varied roles, companies, and tech stacks, loaded through the existing `scripts/init_clean_jobs.sql` path.
* Re-running the T0009 eval against the new data and updating any data-dependent assertions (e.g. expected company names).
**Out of Scope:**
* Live/real-time job ingestion (later phase).
* RAG/embeddings/semantic retrieval (separate future milestone).
**Open decision (resolve when this milestone is picked up, not before):**
* Keep the four columns (`title`, `company`, `description`, `tech_stack`) or enrich the schema with fields users actually ask about (location, remote/on-site, salary). Enriching lets the agent answer questions it currently declines, but expands the SQL validator, schema context, and the T0008 honesty rules — so it is a deliberate scope choice, not a default.
