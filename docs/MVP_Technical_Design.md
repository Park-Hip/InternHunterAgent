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

  1. `config/prompts.yaml::prompts.schema_context` (loaded via `src/agents/runtime/prompts.py::load_schema_context()`) supplies the table shape to the model.
  2. A dedicated model call (`generate_sql`, using `prompts.sql_generation` via `load_sql_generation_prompt()`) turns the question into a candidate `SELECT`.
  3. `src/services/query/sql_validator.py::validate_sql` is the **security boundary** — a deterministic, hand-rolled read-only validator (SELECT-only, allowlist/denylist checks). Generation is untrusted; validation is what makes the path safe.
  4. Only validated SQL reaches `src/services/query/executor.py::execute_validated_sql`, run in a read-only transaction off the event loop via `asyncio.to_thread`.
  5. Rows are shaped by `src/services/query/table_formatter.py::format_rows` into an internal `TableArtifact` (`src/services/query/models.py`), then collapsed to a plain answer string before returning.

  **Read-only invariants:** `SELECT` only; any non-SELECT or unsafe SQL is refused before execution with a natural-language message; DB errors (including timeouts) are caught and returned as a safe message, never crashing the process. The LLM only *proposes* SQL — the deterministic validator must approve it — which is why an LLM-generation step is acceptable without granting raw execution capability.

  > Design note: an earlier draft specified parameterized tools exposing typed arguments (`title`, `tech_stack`). The shipped design uses NL → validated-SQL because the validator, not the tool signature, is the trust boundary.

### 2.4 Memory

*Status: implemented*

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

*Status: implemented*

The API exchanges two Pydantic models (`src/api/schemas.py`):

- **`QueryRequest`** — `query: str`, optional `session_id`, optional `user_id`.
- **`QueryResponse`** — `answer: str`, `session_id`, `trace_id`, `trace_url`.

The response is **answer-only**: no SQL, table rows, or tool internals ever appear, regardless of which tools run. Internal richness (e.g. `TableArtifact`) must collapse to a plain string before crossing the API boundary.

**`session_id` lifecycle.** `session_id` is the conversation key: when a request omits it, the system **generates one and returns it** (`src/agents/service.py`) so the client can continue the thread, and the response carries the id actually used — not a blind echo.

*Provisional:* the answer-only shape is an MVP choice, not a permanent law. The future charting capability (a chart is not a string) will revisit it.

*Deferred, documented:* `trace_url` is currently always `null`, and errors are not yet a typed contract (see §5).

---

## 4. Data & Configuration

*Status: implemented*

- **Dataset.** The MVP runs on a small fixed sample of internship postings in the `clean_jobs` table (`scripts/init_clean_jobs.sql`). Columns: `id` (Integer PK), `title` (Text), `company` (Text), `description` (Text), `tech_stack` (Text — a comma-separated list, **not** a SQL array; filters must treat it as a string). A larger and then live dataset are future phases.
- **Database.** PostgreSQL via SQLAlchemy; the engine and session factory live in `src/core/db.py` (`pool_pre_ping=True`). This app database is entirely separate from Langfuse's internal Postgres — different owners, lifecycles, and schemas.
- **Required environment.** `DATABASE_URL`, `GROQ_API_KEY`, and the `LANGFUSE_*` keys (tracing degrades gracefully if the Langfuse keys are absent).
- **Tunable parameters** live in `config/settings.yaml` (read through `src/core/config.py`): `agent.groq.*` for the model, and `agent.memory.*` (`max_messages`) for memory. Per project convention, parameters are configured here, not hard-coded.

**Schema evolution.** *Status: planned (T0010).* The current four columns are a deliberately simple stand-in for the eventual real job-posting schema; the design keeps growth cheap (the permanent principle is in `Full_Design_Document.md` §6):

- **Adding a column is free in code.** The SQL validator allowlists the *table* `clean_jobs`, not its columns, and `executor.py`/`table_formatter.py` are key-driven, so a new column reaches the answer with no code change — only the schema description the model reads (`schema_context`) and, where relevant, the honesty rules need an edit.
- **Adding tables, joins, or renames is the boundary** where this stops being free: it crosses the validator's single-table allowlist. Staying single-table is the design choice that keeps evolution cheap.
- **Multi-value fields.** `tech_stack` is a comma-separated string today; the path for the real dataset is a Postgres `TEXT[]` or `JSONB`, adopted only when the data demands it — not on the throwaway sample.
- **Migrations deferred.** The schema is seeded by `scripts/init_*.sql`; a migration tool (e.g. Alembic) is intentionally not adopted until the schema stops being a fixed sample (i.e. real ingestion).
- **Open decision (T0010).** Whether T0010 adds real-posting columns (location, remote, salary) or only grows the row count on the current four is deliberately left open until that milestone is picked up — both are supported by the cheap-growth design above, and because honesty is derived from the documented schema, either choice stays consistent without rework elsewhere.

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
- **Memory behavior (implemented).** Multi-turn refinement within one `session_id`; isolation between two different sessions; a generated `session_id` returned when none is supplied; persistence of a conversation across a restart (simulated by rebuilding the runtime against the same checkpointer); and that the history cap holds on long sessions. See `tests/agents/runtime/test_memory.py`.

The bar: every capability in `MVP_Spec.md` §2 maps to at least one observable test here.

> The scored, real-model **capability evaluation** is a separate offline concern — see §7 — distinct from this CI test suite. Unit and integration tests here stay deterministic and model-free; the eval harness deliberately runs the real model outside CI.

---

## 7. Evaluation Harness

*Status: planned (T0009)*

Evaluation is an **offline consumer** of the system, not a new internal layer: it drives the same service seam the API uses (`generate_agent_response`) from outside, and never reaches into the runtime or tools. The permanent boundary rules it relies on — a distinct judge model, direct Langfuse use, and exemption from no-post-tool-narration — are set in `Full_Design_Document.md` §7.

- **Case set (canonical, in-repo).** A version-controlled file (e.g. `eval/cases.yaml`) of questions, each tagged with a category and behavioral assertions. Assertions split in two: **data-independent** (refusal, honest missing-field handling, persona/on-topic — survive a dataset swap) and **data-dependent** (names a real company — re-baselined when T0010 changes the data). This split keeps the larger-dataset milestone from invalidating the whole suite.
- **Runner (standalone script).** A documented command (e.g. `scripts/run_eval.py`) invokes the real agent per case — driving a session for multi-turn cases — maps each assertion to a deterministic check, and prints a scored summary. It is **not** part of the pytest/CI gate: it calls the real model, costs tokens, and is non-deterministic, so it asserts on *behavior*, not exact strings, and pins eval temperature to 0 for stability.
- **LLM-as-judge (distinct model).** A tagged subset of fuzzy-quality cases is graded by a separate judge model, configured under `eval.judge.*` in `config/settings.yaml` (its own model/provider/key, used only offline — permitted because the single-provider law is serving-path-scoped). The judge prompt lives in `config/prompts.yaml`. The deterministic runner works fully without the judge; the judge augments, never replaces it.
- **Langfuse mirror.** The case set is published as a Langfuse dataset and runs link to it, with deterministic and judge scores attached for history and a UI. The in-repo case file stays the source of truth; if Langfuse is absent the in-repo eval still runs (the same degrade-to-no-op principle as serving-path tracing).
- **Config.** An `eval.*` block in `config/settings.yaml` holds the judge model settings, enable/disable flags, and the Langfuse dataset name.

This harness is what lets every later change — T0008 prompt tuning, the T0010 dataset, future RAG — be measured against the `MVP_Spec.md` §2/§3 bar rather than eyeballed.
