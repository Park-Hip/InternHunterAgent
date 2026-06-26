# MVP Technical Design — The Agent

> **What this doc is.** The technical blueprint for *how* the InternHunterAgent MVP is realized — its components, their interfaces, and the key technical decisions. It is the bridge between `MVP_Spec.md` (what the MVP must do, and why) and `Tickets.md` (in what order it gets built).
>
> **What this doc is not.** It does not restate the permanent architectural laws — layer isolation, boundary rules, what may never cross a layer. Those live in `Full_Design_Document.md` and are the single source of truth; this doc *applies* them but never re-derives them. It also does not track current build status — that is `Repo_Current_State.md`. For the full index of docs and what each owns, see the [documentation map](README.md).
>
> **Status tags.** Subsections that describe planned-but-not-yet-built design carry a `Status:` tag so the blueprint never implies something exists before it does. Untagged sections describe the system as built today.

---

## 1. Request Lifecycle

The MVP serves one endpoint, `POST /api/v1/agent/query` (`src/api/routes/query.py`), and every request follows one fixed path:

```
QueryRequest
  -> API route (src/api/routes/query.py)          # validate, log, no agent knowledge
  -> Service (src/agents/service.py)               # the sole caller of the runtime
  -> Agent runtime (src/agents/runtime/react_agent.py::AgentRuntime.ainvoke)
       -> ReAct loop over the assembled agent (model + prompt + tools + memory)
       -> tracing wrap (src/agents/tracing/langfuse.py::build_langfuse_config)
  -> QueryResponse
```

There are no branch points or alternate paths. The route knows nothing about LangChain; the service owns request-level orchestration; the runtime is the only place the agent is constructed and executed. (Layer-isolation rationale: see `Full_Design_Document.md` §2.)

---

## 2. The Agent — Technical Anatomy

The agent is the assembled whole built in `src/agents/runtime/factory.py::agent_factory()` via `create_agent(model, tools, system_prompt)`. The sections below describe its parts. The factory is the **only** place tools are registered and the agent is assembled.

### 2.1 Model provider

*Status: implemented*

A single Groq chat model, wrapped by `src/agents/runtime/provider.py::AgentProvider`. This is the one place model configuration lives; no other layer constructs a model. Configuration is read from `config/settings.yaml` under `agent.groq.*` — `model`, `temperature`, `max_tokens`, `timeout`, `max_retries`, `streaming` — with the API key from `settings.GROQ_API_KEY`. There is deliberately no multi-provider abstraction; `build_model()` raises on any provider other than `groq`.

### 2.2 System prompt & reasoning

*Status: implemented*

The agent runs a ReAct-style loop: the model reasons about the user's question, decides whether to call a tool, consumes the tool's result, and produces a final natural-language answer. The system prompt is loaded from `config/prompts.yaml` (`prompts.system_prompt`) by `src/agents/runtime/prompts.py::load_system_prompt()` and steers the model to use the job-data tool for any question that depends on `clean_jobs`, rather than answering job questions from its own parameters. The runtime extracts the final answer from the last message and returns it as a plain string (`react_agent.py::AgentRuntime._extract_answer`).

### 2.3 Tools — the capability surface

*Status: implemented*

Tools are how the agent acts on the world. Every tool obeys one contract: **natural language in, natural language out.** The model never receives a raw execution primitive — no SQL string, no DB session, no internal data structure. A tool may use rich internal services and DTOs freely, but its only public surface to the model is text. Tools are registered exclusively in the factory.

The MVP ships two tools:

- **`get_current_time`** (`src/agents/tools/time.py`) — returns the current time. Trivial; exists to prove the multi-tool path.
- **`query_clean_jobs`** (`src/agents/tools/query_clean_jobs.py`) — answers questions about internship postings. It runs a fixed, deterministic pipeline rather than handing SQL power to the model:

  1. `src/services/query/schema_context.py::build_clean_jobs_schema_context()` supplies the table shape to the model.
  2. A dedicated model call (`generate_sql`, using `prompts.sql_generation` via `load_sql_generation_prompt()`) turns the question into a candidate `SELECT`.
  3. `src/services/query/sql_validator.py::validate_sql` is the **security boundary** — a deterministic, hand-rolled read-only validator (SELECT-only, allowlist/denylist checks). Generation is untrusted; validation is what makes the path safe.
  4. Only validated SQL reaches `src/services/query/executor.py::execute_validated_sql`, run in a read-only transaction off the event loop via `asyncio.to_thread`.
  5. Rows are shaped by `src/services/query/table_formatter.py::format_rows` into an internal `TableArtifact` (`src/services/query/models.py`), then collapsed to a plain answer string before returning.

  **Read-only invariants:** `SELECT` only; any non-SELECT or unsafe SQL is refused before execution with a natural-language message; DB errors (including timeouts) are caught and returned as a safe message, never crashing the process. The LLM only *proposes* SQL — the deterministic validator must approve it — which is why an LLM-generation step is acceptable without granting raw execution capability.

  > Design note: an earlier draft specified parameterized tools exposing typed arguments (`title`, `tech_stack`). The shipped design uses NL → validated-SQL because the validator, not the tool signature, is the trust boundary.

### 2.4 Memory

*Status: planned*

Short-term, session-scoped memory is one component of the agent — it lets a user refine questions across turns within a conversation. It is **not** the whole agent, and it is deliberately scoped:

- **Abstraction.** Memory uses the runtime's native thread mechanism: a conversation is a *thread*, and the API's `session_id` maps to the thread key (`session_id -> thread_id`). The agent code is unchanged by the choice of storage behind this.
- **Storage.** Memory is **Postgres-backed and persistent**, so conversations survive a service restart and remain coherent when more than one instance runs. The checkpoint tables live in the **application database** (`DATABASE_URL`) — alongside `clean_jobs`, never in Langfuse's separate Postgres. The exact checkpointer library is an implementation choice deferred to the ticket that builds this.
- **What "remembering" actually is.** On each turn, the prior messages of the thread are replayed into the model's context; the model uses that context to reformulate its next tool call (e.g. "only the Python ones" becomes a refined `query_clean_jobs` question). There is no special memory-reasoning code — refinement quality is a function of the model and prompt, not a bespoke feature.
- **Bound.** A configurable cap (`config/settings.yaml`, e.g. `agent.memory.max_messages`) trims how many recent messages are sent to the model. This trims *what the model sees per turn*; the stored thread may still retain fuller history. The cap protects latency and token cost; message trimming — not long-term memory — is the intended first optimization if context grows.
- **Boundary.** This is short-term, within-conversation memory only. Cross-session recall, user profiles, and resume/embedding retrieval are **long-term memory**, a distinct mechanism and an explicit future phase (see `MVP_Spec.md` §6) — they must not be bolted onto the thread checkpointer.

### 2.5 Tracing

*Status: implemented*

Tracing is built once in `src/agents/tracing/langfuse.py` and injected into the agent invocation via `build_langfuse_config()`, which the runtime passes to `agent.ainvoke()`. No route, service, or tool builds its own Langfuse client. The standing invariant is **one trace per request**, with every tool call appearing as a child span; `session_id` and `user_id` are attached as trace metadata (`langfuse_session_id`, `langfuse_user_id`), so traces group into per-conversation timelines. If credentials are absent or initialization fails, tracing degrades to a no-op — it never raises and never blocks a request.

---

## 3. Public Contract

*Status: implemented (session_id lifecycle: planned)*

The API exchanges two Pydantic models (`src/api/schemas.py`):

- **`QueryRequest`** — `query: str`, optional `session_id`, optional `user_id`.
- **`QueryResponse`** — `answer: str`, `session_id`, `trace_id`, `trace_url`.

The response is **answer-only**: no SQL, table rows, or tool internals ever appear, regardless of which tools run. Internal richness (e.g. `TableArtifact`) must collapse to a plain string before crossing the API boundary.

**`session_id` lifecycle (planned).** Today `session_id` is a passive echo. Once memory exists it becomes the conversation key: when a request omits it, the system **generates one and returns it** so the client can continue the thread, and the response carries the id actually used — not a blind echo.

*Provisional:* the answer-only shape is an MVP choice, not a permanent law. The future charting capability (a chart is not a string) will revisit it.

*Deferred, documented:* `trace_url` is currently always `null`, and errors are not yet a typed contract (see §5).

---

## 4. Data & Configuration

*Status: implemented (memory config: planned)*

- **Dataset.** The MVP runs on a small fixed sample of internship postings in the `clean_jobs` table (`scripts/init_clean_jobs.sql`). Columns: `id` (Integer PK), `title` (Text), `company` (Text), `description` (Text), `tech_stack` (Text — a comma-separated list, **not** a SQL array; filters must treat it as a string). A larger and then live dataset are future phases.
- **Database.** PostgreSQL via SQLAlchemy; the engine and session factory live in `src/core/db.py` (`pool_pre_ping=True`). This app database is entirely separate from Langfuse's internal Postgres — different owners, lifecycles, and schemas.
- **Required environment.** `DATABASE_URL`, `GROQ_API_KEY`, and the `LANGFUSE_*` keys (tracing degrades gracefully if the Langfuse keys are absent).
- **Tunable parameters** live in `config/settings.yaml` (read through `src/core/config.py`): `agent.groq.*` for the model, and `agent.memory.*` (e.g. `max_messages`) for memory once built. Per project convention, parameters are configured here, not hard-coded.

---

## 5. Error Handling & Resilience

*Status: target design (partially implemented)*

The Spec's quality bar (`MVP_Spec.md` §3) requires that imperfect input or a backend hiccup yields a clean response, never a crash and never a leaked internal error. The target behavior:

- **Tool/DB failures** are caught inside the tool and returned as a safe natural-language message (implemented for `query_clean_jobs`: validator refusals and `ExecutorError` both degrade gracefully).
- **Tracing failures** never affect the request path — tracing is a no-op when unavailable (implemented).
- **Unexpected runtime failures** are mapped by the service/route to a safe response without exposing internals.

*Deferred, documented:* the route currently collapses every failure into a generic `500`, so a bad request body, a model timeout, and an internal bug are indistinguishable to the client. A **typed error contract** (distinguishing client-input errors from server/provider errors, with a consistent response shape) is a recognized refinement, not part of this MVP. It is recorded here so the gap is intentional, not forgotten.

---

## 6. Testing Strategy

*Status: target design*

Tests prove the Spec's capabilities, not implementation trivia. The strategy spans four layers (the concrete test list and counts live in `Repo_Current_State.md`):

- **Unit — deterministic internals.** The SQL validator (safe/unsafe cases, SELECT-only enforcement), the table formatter (empty/single/multi/missing-key), and result-model serialization. These are the safety- and correctness-critical pure functions.
- **Tool path.** `query_clean_jobs` end to end with the model call stubbed: a success path (validated SQL → rows → answer) and a refusal path (validator rejects unsafe SQL before execution).
- **Request integration.** A `POST /api/v1/agent/query` happy path returning a well-formed answer-only response, and a failure path proving the process degrades cleanly.
- **Memory behavior (planned).** Multi-turn refinement within one `session_id`; isolation between two different sessions; a generated `session_id` returned when none is supplied; persistence of a conversation across a restart; and that the history cap holds on long sessions.

The bar: every capability in `MVP_Spec.md` §2 maps to at least one observable test here.
