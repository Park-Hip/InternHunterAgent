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

- **Dataset.** The MVP began on a small fixed sample of internship postings in the `clean_jobs` table (`scripts/init_clean_jobs.sql`). Columns: `id` (Integer PK), `title` (Text), `company` (Text), `description` (Text), `tech_stack` (Text — a comma-separated list, **not** a SQL array; filters must treat it as a string). *Status: real ingestion is planned (T0009)* — it replaces the fixtures with live VietnamWorks AI/Data postings and enriches the schema (see §7).
- **Database.** PostgreSQL via SQLAlchemy; the engine and session factory live in `src/core/db.py` (`pool_pre_ping=True`). This app database is entirely separate from Langfuse's internal Postgres — different owners, lifecycles, and schemas.
- **Required environment.** `DATABASE_URL`, `GROQ_API_KEY`, and the `LANGFUSE_*` keys (tracing degrades gracefully if the Langfuse keys are absent).
- **Tunable parameters** live in `config/settings.yaml` (read through `src/core/config.py`): `agent.groq.*` for the model, and `agent.memory.*` (`max_messages`) for memory. Per project convention, parameters are configured here, not hard-coded.

**Schema evolution.** *Status: planned (T0010).* The current four columns are a deliberately simple stand-in for the eventual real job-posting schema; the design keeps growth cheap (the permanent principle is in `Full_Design_Document.md` §6):

- **Adding a column is free in code.** The SQL validator allowlists the *table* `clean_jobs`, not its columns, and `executor.py`/`table_formatter.py` are key-driven, so a new column reaches the answer with no code change — only the schema description the model reads (`schema_context`) and, where relevant, the honesty rules need an edit.
- **Adding tables, joins, or renames is the boundary** where this stops being free: it crosses the validator's single-table allowlist. Staying single-table is the design choice that keeps evolution cheap.
- **Multi-value fields.** `tech_stack` is a comma-separated string today; the path for the real dataset is a Postgres `TEXT[]` or `JSONB`, adopted only when the data demands it — not on the throwaway sample.
- **Migrations deferred.** The schema is seeded by `scripts/init_*.sql`; a migration tool (e.g. Alembic) is intentionally not adopted until the schema stops being a fixed sample (i.e. real ingestion).
- **Open decision (T0010) — now answered by T0009.** The question of whether to add real-posting columns (location, salary) vs. only grow the row count is **resolved by T0009**, which enriches `clean_jobs` (adds `role`, `source_url`, `posted_date`, `is_internship`, `job_level`, `location`, and structured salary: `salary_min`, `salary_max`, `salary_currency`, `is_salary_negotiable`) while landing real data. The cheap-growth design above is exactly what makes that enrichment column-cheap. T0010 is consequently re-scoped (see `Tickets.md`).

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

---

## 7. Data Ingestion Pipeline (offline)

*Status: planned (T0009)*

Ingestion is **offline batch tooling** under `src/services/ingestion/`, isolated from the request pipeline — it is never imported by the API, service, runtime, tools, or tracing layers (the layer law is in `Full_Design_Document.md` §3). It runs as a manual, re-runnable CLI, not on a schedule. The deep research behind every decision here is `research/data-ingestion-stage.md` (§0.1, the ✅ reliable & schedulable VietnamWorks experiment) and `research/job-site-comparison.md`; do not re-derive it.

**Design intent: source-agnostic.** v1 ingests **VietnamWorks only**, but the schema, cleaning, and interfaces are built so a future board is just a new adapter + normalizer with **no table reshape**. Only two components ever know a source's specifics — the **adapter** (fetch) and the **normalizer** (payload → common shape). Everything downstream is shared.

**Dataflow.**

```
JobSource (VietnamWorksSource) --RawPosting--> raw_jobs (verbatim landing, upsert on (source, external_id))
   -> Normalizer (source-specific: payload -> NormalizedJob)
   -> Transform (SHARED, deterministic, no LLM, no network):
        HTML->text · is_internship · tech_stack keyword finder · role taxonomy · location city-alias map
   -> Loader: upsert into clean_jobs on (source, external_id)
```

**Tables.**

- **`raw_jobs`** — verbatim landing: `id`, `source`, `external_id`, `source_url`, `raw_payload` (JSONB), `content_hash`, `fetched_at`; unique `(source, external_id)`. Never lossy. Lives in the application `DATABASE_URL` Postgres alongside `clean_jobs` (never Langfuse's Postgres).
- **`clean_jobs`** (enriched, agent-facing) — the original `title`, `company`, `description`, `tech_stack` plus `role`, `source`, `external_id`, `source_url`, `posted_date`, `is_internship`, `job_level`, `location`, and structured salary (`salary_min`, `salary_max`, `salary_currency`, `is_salary_negotiable`). `title` stays the raw posting title; `role` and `location` hold canonical normalized values. **`description` is a single merged free-text blob** (job description + requirements + benefits) — there are deliberately **no `requirement`/`benefits` columns**, because that is the common shape across all boards (most return one blob; VietnamWorks' separately-provided `jobRequirement`/`benefits` are concatenated back in its normalizer, and survive verbatim in `raw_jobs`). Unique `(source, external_id)`.

**Deterministic cleaning** (all pure, unit-tested, no LLM — keeps ingestion testable and aligned with the project's "no over-engineering" rule; LLM extraction is a deferred future enhancement):

- **`tech_stack`** — a keyword finder matches the source skills array + the description text against a curated **technology dictionary** (`config/settings.yaml`), keeps technologies only (role/category labels dropped), dedups, emits the comma-separated string the SQL agent already expects.
- **`role`** — a **role taxonomy** maps the messy title into a fixed canonical set (AI Engineer, Data Scientist, Data Engineer, Data Analyst, ML Engineer, Software Developer), using keyword/pattern rules with the source `jobFunction` as a tiebreaker; unmatched titles fall to `Other` (never dropped).
- **`location`** — a **city alias map** collapses messy location text to a unified city/province (`Ha Noi`/`Hanoi` → `Hanoi`; `HCM`/`TPHCM`/`Ho Chi Minh`/`hcm` → `Ho Chi Minh City`); multi-city → comma-separated canonical set; street address discarded.
- **`description`** — source text is merged into **one free-text blob** (HTML stripped). VietnamWorks arrives pre-split, so its normalizer concatenates `jobDescription` + `jobRequirement` + benefit values back together; the other boards already return a single blob. This keeps one shape across all sources and one field for the agent to read.
- **salary** — mapped into **structured** fields rather than a display string, so the agent can range-filter and sort (the core "pay ≥ X" query): `salary_min`, `salary_max` (numeric, nullable), `salary_currency` (e.g. USD/VND — required whenever a number is present, since VietnamWorks mixes currencies), and `is_salary_negotiable` (bool). VietnamWorks maps `salaryMin`/`salaryMax`/`salaryCurrency` directly and sets `is_salary_negotiable = not isSalaryVisible`; a future string-only board parses its salary string deterministically, else leaves min/max NULL with `is_salary_negotiable = true`.

**Identity & idempotency.** Upsert on `(source, external_id)` with a `content_hash` for change detection; re-running refreshes rather than duplicating. The fixtures are replaced; a tunable `max_jobs` cap (~50) bounds a run.

**Configuration.** Everything tunable lives in `config/settings.yaml` `ingestion.*`: API URL, AI/Data keyword queries, `jobFunction` ids, cap, delay, User-Agent, the technology dictionary, the role taxonomy, and the city alias map. Internal records (`RawPosting`, `NormalizedJob`) and the table models live in `models.py`, per project convention.

**Agent-layer impact.** Because the new `clean_jobs` columns are agent-visible, T0009 also updates `prompts.schema_context`, the SQL-generation prompt, and the T0008 honesty rules (notably: salary is numeric and currency-scoped — filter within a `salary_currency` — and may be NULL / `is_salary_negotiable = true` → "may be missing or negotiable for some postings", not "not in the data"). This is the column-cheap schema growth §4 describes, applied.

**Deferred.** Other boards, anti-bot scrapers, a scheduler/cron, LLM extraction, parsing a salary *string* into numbers (not needed for VietnamWorks, which supplies the numbers directly), translating source text to a single language, and cross-board dedup are out of scope (see `Tickets.md` T0009 Out of Scope and `research/job-site-comparison.md`).
