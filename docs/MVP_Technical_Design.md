# MVP Technical Design — The Agent

> **What this doc is.** The technical blueprint for *how* the InternHunterAgent MVP is realized —
> its components, their interfaces, and the key technical decisions. It is the bridge between
> `MVP_Spec.md` (what the MVP must do, and why) and `Tickets.md` (in what order it gets built).
>
> **What this doc is not.** It does not restate the permanent architectural laws — layer isolation,
> boundary rules, what may never cross a layer. Those live in `Full_Design_Document.md` and are the
> single source of truth; this doc *applies* them but never re-derives them. It also does not track
> current build status — that is `Repo_Current_State.md`. For the full index of docs and what each
> owns, see the [documentation map](README.md).
>
> **Status tags.** Subsections that describe planned-but-not-yet-built design carry a `Status:` tag
> so the blueprint never implies something exists before it does. Untagged sections describe the
> system as built today.

---

## 1. Request Lifecycle

The MVP serves one endpoint, `POST /api/v1/agent/chat` (`src/api/routes/query.py`), and every
request follows one fixed path:

```
QueryRequest
  -> API route (src/api/routes/query.py)          # validate, log, no agent knowledge
  -> Service (src/agents/service.py)               # the sole caller of the runtime
  -> Agent runtime (src/agents/runtime/react_agent.py::AgentRuntime.ainvoke)
       -> ReAct loop over the assembled agent (model + prompt + tools + memory)
       -> tracing wrap (src/agents/tracing/langfuse.py::build_langfuse_config)
  -> QueryResponse
```

There are no branch points or alternate paths. The route knows nothing about LangChain; the service
owns request-level orchestration; the runtime is the only place the agent is constructed and
executed. (Layer-isolation rationale: see `Full_Design_Document.md` §2.)

*Status note (T0017, implemented):* a second, parallel path — streaming token-by-token delivery — is
built and specified in §9. It reuses the same route → service → runtime layering (the runtime
driving `agent.astream` instead of `ainvoke`) and does not replace the one-shot path above.

---

## 2. The Agent — Technical Anatomy

The agent is the assembled whole built in `src/agents/runtime/factory.py::agent_factory()` via
`create_agent(model, tools, system_prompt)`. The sections below describe its parts. The factory is
the **only** place tools are registered and the agent is assembled.

### 2.1 Model provider

*Status: implemented*

Groq chat models are wrapped by `src/agents/runtime/provider.py::AgentProvider`. This is the one
place model construction lives; no other layer constructs a model. Configuration is read from
`config/settings.yaml` under two explicit profiles with the same fields: `agent.react.*` for the
outer conversational ReAct agent, and `agent.sql_generation.*` for the nested SQL-generation call
inside `query_clean_jobs`. Each profile carries `model`, `temperature`, `max_tokens`, `timeout`,
`max_retries`, `streaming`, `reasoning_format`, and optional `reasoning_effort`; the API key still
comes from `settings.GROQ_API_KEY`. There is deliberately no multi-provider abstraction;
`build_model(...)` raises on any provider other than `groq`.

### 2.2 System prompt & reasoning

*Status: implemented*

The agent runs a ReAct-style loop: the model reasons about the user's question, decides whether to
call a tool, consumes the tool's result, and produces a final natural-language answer. The system
prompt is loaded from `config/prompts.yaml` (`prompts.system_prompt`) by
`src/agents/runtime/prompts.py::load_system_prompt()` and steers the model to use the job-data tool
for any question that depends on `clean_jobs`, rather than answering job questions from its own
parameters. The runtime extracts the final answer from the last message and returns it as a plain
string (`react_agent.py::AgentRuntime._extract_answer`).

### 2.3 Tools — the capability surface

*Status: implemented*

Tools are how the agent acts on the world. Every tool obeys one contract: **natural language in,
natural language out.** The model never receives a raw execution primitive — no SQL string, no DB
session, no internal data structure. A tool may use rich internal services and DTOs freely, but its
only public surface to the model is text. Tools are registered exclusively in the factory.

The MVP ships three tools — `get_current_time` and `query_clean_jobs` (below), plus
`get_job_details`, the detail-fetch tool described under *Bounded retrieval*:

- **`get_current_time`** (`src/agents/tools/time.py`) — returns the current time. Trivial; exists to
  prove the multi-tool path.
- **`query_clean_jobs`** (`src/agents/tools/query_clean_jobs.py`) — answers questions about
  internship postings. It runs a fixed, deterministic pipeline rather than handing SQL power to the
  model:

  1. `config/prompts.yaml::prompts.schema_context` (loaded via
     `src/agents/runtime/prompts.py::load_schema_context()`) supplies the table shape to the model.
  2. A dedicated model call (`generate_sql`, using `prompts.sql_generation` via
     `load_sql_generation_prompt()`) turns the question into a candidate `SELECT`.
  3. `src/services/query/sql_validator.py::validate_sql` is the **security boundary** — a
     deterministic, hand-rolled read-only validator (SELECT-only, allowlist/denylist checks).
     Generation is untrusted; validation is what makes the path safe.
  4. Only validated SQL reaches `src/services/query/executor.py::execute_validated_sql`, run in a
     read-only transaction off the event loop via `asyncio.to_thread`.
  5. Rows are shaped by `src/services/query/table_formatter.py::format_rows` into an internal
     `TableArtifact` (`src/services/query/models.py`), then collapsed to a plain answer string
     before returning.

  **Read-only invariants:** `SELECT` only; any non-SELECT or unsafe SQL is refused before execution
  with a natural-language message; DB errors (including timeouts) are caught and returned as a safe
  message, never crashing the process. The LLM only *proposes* SQL — the deterministic validator
  must approve it — which is why an LLM-generation step is acceptable without granting raw execution
  capability.

  > Design note: an earlier draft specified parameterized tools exposing typed arguments (`title`,
  > `tech_stack`). The shipped design uses NL → validated-SQL because the validator, not the tool
  > signature, is the trust boundary.

  **Bounded retrieval: structured query vs. detail fetch.** *Status: implemented
  (T0009.10–T0009.11).* Real ingestion (T0009) turned `clean_jobs` into ~50 verbose rows, each
  carrying a large merged `description` blob. A single tool that returned every column of every
  matched row then overflowed the model's token budget on broad queries (the Groq TPM `413` recorded
  in `Known_Issues.md`). The fix is architectural, not a bigger model — it splits retrieval along
  the **intent** the user actually has:

  - **`query_clean_jobs`** (structured query — list, count, aggregate). Runs the LLM→validated-SQL
    pipeline above, but the tool boundary enforces two deterministic guarantees the model cannot
    override (the `Full_Design_Document.md` §4 bounded-output law): it **never projects the
    `description` blob** into its result, and it **caps result rows** at `agent.query.max_rows`
    (config). The fetch bound is system-owned, not model-owned:
    `src/services/query/row_bound.py::resolve_bounds(sql, max_rows)` inspects any trailing `LIMIT`
    the model wrote and treats it as a signal of *explicit user intent* — the prompt
    (`config/prompts.yaml` `sql_generation`) only asks the model to emit a `LIMIT` when the user
    explicitly requested a specific count (e.g. "top 5"). If that `LIMIT` is within the safety cap
    (`<= max_rows`), it is honored exactly: the tool fetches and displays exactly that many rows,
    with no truncation notice. Otherwise (no `LIMIT`, or one above the cap) the tool falls back to
    fetching `max_rows + 1` rows as a truncation sentinel and displays `max_rows`, so
    unbounded/broad queries still get an honest "there are more matches — narrow your search"
    notice. It deliberately does **not** compute an exact total for list queries (a precise count
    would require a separate `COUNT(*)` — rejected as unnecessary MVP complexity). It serves
    scalar/aggregate results (`COUNT`, `AVG`, `MIN/MAX`, small `GROUP BY`) as naturally as row
    lists, passing those through untouched (no truncation notice applies to scalar results).
  - **`get_job_details(ids)`** (detail — full prose). A **deterministic, parameterized** fetch by id
    (no LLM, no SQL generation — ids carry no natural-language ambiguity), returning the full
    `description` for a **few** jobs (`agent.query.max_detail_ids`). This is the *only* path that
    surfaces description prose to the model.

  This makes the **`description` field three-moded**: *filter-only* inside `query_clean_jobs`
  (Postgres reads it via `ILIKE` server-side; the text never reaches the model), *full-text* only
  via `get_job_details`, and *never listed* in bulk. The bridge between the two tools is the row
  `id` that `query_clean_jobs` returns, which the agent passes back into `get_job_details` for "tell
  me about that one" follow-ups. (Surrogate ids are stable within a conversation; they are not
  stable across an ingestion reload — the durable handle, if ever needed, is `(source,
  external_id)`. *Status note: **T0019.3** drops the `TRUNCATE`-and-reinsert that causes that
  instability, so ids become stable across runs for any row that persists. Treat this as a
  **consequence, not a guarantee** — nothing should start depending on cross-run id stability,
  because `(source, external_id)` remains the durable handle and a re-seeded local DB still
  renumbers.*)

  **Question coverage & the one deferred gap.** Every question resolves on two axes — *does it need
  the description's prose?* and *does it want a scalar, a list, or a few full records?* Structured
  filters/counts/rankings (including literal keyword hits inside `description` via `ILIKE`) are
  served by `query_clean_jobs`; "tell me about / compare these" is served by `get_job_details`. The
  single uncovered cell is **semantic search over the whole corpus** ("which postings are
  beginner-friendly?" by *meaning*, not keyword) — that needs embeddings and is the future RAG
  milestone, not this design. The honest MVP behavior there is to answer literal keywords and say
  plainly that it cannot yet search postings by meaning.

  **Attributes not backed by a column** (remote, mentorship, visa sponsorship) are answered by
  keyword-matching the `description` text, with an honesty hedge that the match is based on posting
  wording and may be imperfect — the same "promote hot text into a real column at ingestion" path
  that produced `role`/`location`/`tech_stack` is the escalation when one becomes a common filter.
  Salary ranking guidance (`NULLS LAST`, mandatory single-currency scoping) and the "count, don't
  list" rule for *how-many* questions live in `prompts.sql_generation`.

### 2.4 Memory

*Status: implemented*

Short-term, session-scoped memory is one component of the agent — it lets a user refine questions
across turns within a conversation. It is **not** the whole agent, and it is deliberately scoped:

- **Abstraction.** Memory uses the runtime's native thread mechanism: a conversation is a *thread*,
  and the API's `session_id` maps to the thread key (`session_id -> thread_id`). The agent code is
  unchanged by the choice of storage behind this.
- **Storage.** Memory is **Postgres-backed and persistent**, so conversations survive a service
  restart and remain coherent when more than one instance runs. The checkpoint tables live in the
  **application database** (`DATABASE_URL`) — alongside `clean_jobs`, never in Langfuse's separate
  Postgres. The exact checkpointer library is an implementation choice deferred to the ticket that
  builds this.
- **What "remembering" actually is.** On each turn, the prior messages of the thread are replayed
  into the model's context; the model uses that context to reformulate its next tool call (e.g.
  "only the Python ones" becomes a refined `query_clean_jobs` question). There is no special
  memory-reasoning code — refinement quality is a function of the model and prompt, not a bespoke
  feature.
- **Bound.** A configurable cap (`config/settings.yaml`, e.g. `agent.memory.max_messages`) trims how
  many recent messages are sent to the model. This trims *what the model sees per turn*; the stored
  thread may still retain fuller history. The cap protects latency and token cost; message trimming
  — not long-term memory — is the intended first optimization if context grows.
- **Boundary.** This is short-term, within-conversation memory only. Cross-session recall, user
  profiles, and resume/embedding retrieval are **long-term memory**, a distinct mechanism and an
  explicit future phase (see `MVP_Spec.md` §6) — they must not be bolted onto the thread
  checkpointer.

### 2.5 Tracing

*Status: implemented*

Tracing is built once in `src/agents/tracing/langfuse.py` and injected into the agent invocation via
`build_langfuse_config()`, which the runtime passes to `agent.ainvoke()`. No route, service, or tool
builds its own Langfuse client. The standing invariant is **one trace per request**, with every tool
call appearing as a child span; `session_id` and `user_id` are attached as trace metadata
(`langfuse_session_id`, `langfuse_user_id`), so traces group into per-conversation timelines. If
credentials are absent or initialization fails, tracing degrades to a no-op — it never raises and
never blocks a request.

---

## 3. Public Contract

*Status: implemented*

The API exchanges two Pydantic models (`src/api/schemas.py`):

- **`QueryRequest`** — `query: str`, optional `session_id`, optional `user_id`.
- **`QueryResponse`** — `answer: str`, `session_id`, `trace_id`, `trace_url`.

The response is **answer-only**: no SQL, table rows, or tool internals ever appear, regardless of
which tools run. Internal richness (e.g. `TableArtifact`) must collapse to a plain string before
crossing the API boundary.

**`session_id` lifecycle.** `session_id` is the conversation key: when a request omits it, the
system **generates one and returns it** (`src/agents/service.py`) so the client can continue the
thread, and the response carries the id actually used — not a blind echo.

*Provisional:* the answer-only shape is an MVP choice, not a permanent law. The future charting
capability (a chart is not a string) will revisit it, as does **streaming delivery (T0017, §9)** —
which keeps the same answer-only *content* but delivers it as a sequence of typed SSE events rather
than a single JSON body.

*Implemented:* `trace_url` is populated from the Langfuse trace when tracing is configured
(T0012.4); it is `null` only when tracing is disabled. A minimal typed error contract landed in
T0010.1 (see §5) — a blank/whitespace-only `query` returns a clean `400`, distinct from the generic
`500` for internal failures.

---

## 4. Data & Configuration

*Status: implemented*

- **Dataset.** The MVP began on a small fixed sample of internship postings in the original 4-column
  `clean_jobs` table. *Status: real ingestion implemented (T0009)* — `clean_jobs` now lands live
  VietnamWorks AI/Data postings (via `scripts/init_db.sql` + `src/services/ingestion/`) with the
  enriched schema described in §7; the old fixture seed script and its 4-column shape are retired.
- **Database.** PostgreSQL via SQLAlchemy; the engine and session factory live in `src/core/db.py`
  (`pool_pre_ping=True`). This app database is entirely separate from Langfuse's internal Postgres —
  different owners, lifecycles, and schemas.
- **Required environment.** `DATABASE_URL`, `GROQ_API_KEY`, and the `LANGFUSE_*` keys (tracing
  degrades gracefully if the Langfuse keys are absent).
- **Tunable parameters** live in `config/settings.yaml` (read through `src/core/config.py`):
  `agent.react.*` for the outer ReAct model, `agent.sql_generation.*` for the nested SQL-generation
  model, and `agent.memory.*` (`max_messages`) for memory. Per project convention, parameters are
  configured here, not hard-coded.

**Schema evolution.** *Status: implemented (T0009 enriched `clean_jobs`; T0013 froze the v1 contract
at its current 16 agent-visible columns — see `Schema_Contract.md`).* The schema grew from the
original four-column sample into the real job-posting shape exactly along the cheap-growth path
below (the permanent principle is in `Full_Design_Document.md` §6):

- **Adding a column is free in code.** The SQL validator allowlists the *table* `clean_jobs`, not
  its columns, and `executor.py`/`table_formatter.py` are key-driven, so a new column reaches the
  answer with no code change — only the schema description the model reads (`schema_context`) and,
  where relevant, the honesty rules need an edit.
- **Adding tables, joins, or renames is the boundary** where this stops being free: it crosses the
  validator's single-table allowlist. Staying single-table is the design choice that keeps evolution
  cheap.
- **Multi-value fields.** `tech_stack` is a comma-separated string today; the path for the real
  dataset is a Postgres `TEXT[]` or `JSONB`, adopted only when the data demands it — not on the
  throwaway sample.
- **Migrations deferred — *both deferral conditions have now fired* (2026-07-16).** The schema is
  seeded by `scripts/init_*.sql`; a migration tool (e.g. Alembic) was intentionally not adopted
  until the schema stopped being a fixed sample (i.e. real ingestion) **and** deployed data became
  irreplaceable. T0009 met the first; T0018.4 (live Neon) plus T0019's accumulating `raw_jobs` —
  which holds postings that have dropped out of search and can no longer be re-fetched — meet the
  second. *Status: Alembic adoption scoped as **T0019.2** (baseline migration + env wiring), with
  `reset_db.sql` demoted to local-dev-only.* Note that migrations are only half the problem: `CREATE
  TABLE IF NOT EXISTS` silently no-ops on a table whose columns drifted **out-of-band**, which
  Alembic does not detect — hence the separate pre-flight column assertion in **T0019.5**
  (`Known_Issues.md`, schema-drift `[HIGH · OPEN]`).
- **Open decision (T0010) — now answered by T0009.** The question of whether to add real-posting
  columns (location, salary) vs. only grow the row count is **resolved by T0009**, which enriches
  `clean_jobs` (adds `role`, `source_url`, `created_on`, `listing_expires_on`, `is_internship`,
  `job_level`, `location`, and structured salary: `salary_min`, `salary_max`, `salary_currency`,
  `is_salary_negotiable`) while landing real data. (T0009 originally added `posted_date`; T0013 left
  it NULL/hidden and superseded it with `created_on`/`listing_expires_on` for freshness —
  `Schema_Contract.md`.) The cheap-growth design above is exactly what makes that enrichment
  column-cheap. The original open T0010 question is therefore closed. Schema *tooling* is handled
  lightly by **T0009.9** (an explicit `reset_db.sql` drop-and-recreate path, appropriate because
  every table is reproducible from a re-ingest); a full migration framework (Alembic) is deferred
  until deployed data becomes irreplaceable — which it now has; see *Migrations deferred* above.

---

## 5. Error Handling & Resilience

*Status: implemented (T0010.1, T0012.5)*

The Spec's quality bar (`MVP_Spec.md` §3) requires that imperfect input or a backend hiccup yields a
clean response, never a crash and never a leaked internal error. The target behavior:

- **Tool/DB failures** are caught inside the tool and returned as a safe natural-language message
  (implemented for `query_clean_jobs`: validator refusals and `ExecutorError` both degrade
  gracefully).
- **Tracing failures** never affect the request path — tracing is a no-op when unavailable
  (implemented).
- **Client-input errors** are distinguished from server/provider errors (implemented, T0010.1):
  `src/api/routes/query.py` raises `InvalidQueryError` (`src/core/errors.py`) for a
  blank/whitespace-only `payload.query`, mapped to a `400 "Query must not be empty."`; genuine
  internal failures still map to the generic `500 "Failed to process query"` with no internals
  leaked.
- **A `None`/empty runtime answer** is coerced to a safe fallback string (`FALLBACK_ANSWER` in
  `src/agents/service.py`) rather than failing Pydantic validation — implemented, T0010.1.

*Status note (T0017, implemented):* the status-code mapping above holds only for the one-shot path.
Under streaming, once the first byte is sent the response is already `200` and mid-run failures are
delivered as in-band SSE `error` events instead of status codes — see §9.5. Pre-stream failures
(empty query, provider-busy before the first token) keep the status-code behavior described here.

*Scope note:* the typed error contract above is intentionally minimal (a single `4xx`/`5xx` split,
not a broader error taxonomy), matching the MVP scope. The empty-answer path is now closed
(T0012.5): `react_agent._extract_answer` returns `""` on empty/unreadable final content, so the
`FALLBACK_ANSWER` coercion in `service.py` fires and an empty agent answer returns `200` with the
fallback string, not a `500`.

---

## 6. Testing Strategy

*Status: implemented.*

Tests prove the Spec's capabilities, not implementation trivia. The strategy spans four layers (the
concrete test list and counts live in `Repo_Current_State.md`):

- **Unit — deterministic internals.** The SQL validator (safe/unsafe cases, SELECT-only
  enforcement), the table formatter (empty/single/multi/missing-key), and result-model
  serialization. These are the safety- and correctness-critical pure functions.
- **Tool path.** `query_clean_jobs` end to end with the model call stubbed: a success path
  (validated SQL → rows → answer) and a refusal path (validator rejects unsafe SQL before
  execution).
- **Request integration.** A `POST /api/v1/agent/chat` happy path returning a well-formed
  answer-only response, and a failure path proving the process degrades cleanly.
- **Memory behavior (implemented).** Multi-turn refinement within one `session_id`; isolation
  between two different sessions; a generated `session_id` returned when none is supplied;
  persistence of a conversation across a restart (simulated by rebuilding the runtime against the
  same checkpointer); and that the history cap holds on long sessions. See
  `tests/agents/runtime/test_memory.py`.

The bar: every capability in `MVP_Spec.md` §2 maps to at least one observable test here.

These are **deterministic capability tests** — they prove a feature exists and behaves on fixed
inputs. The distinct question of *behavioral quality under model non-determinism* — task correctness
and the `MVP_Spec.md` §3 honesty rules, which no assert-equality test can pin — is measured
separately by the offline **Evaluation Harness (§8)**, not here.

---

## 7. Data Ingestion Pipeline (offline)

*Status: implemented*

Ingestion is **offline batch tooling** under `src/services/ingestion/`, isolated from the request
pipeline — it is never imported by the API, service, runtime, tools, or tracing layers (the layer
law is in `Full_Design_Document.md` §3). It runs as a manual, re-runnable CLI, not on a schedule.
The deep research behind every decision here is `research/archive/data-ingestion-stage.md` (§0.1,
the ✅
reliable & schedulable VietnamWorks experiment) and `research/job-site-comparison.md`; do not
re-derive it.

> **Status: live-DB operation built (T0019.1–.5, .7, .8); scheduling not yet landed (T0019.6).** The
> nightly cron's workflow file exists in the working tree but is **not committed** and its
> documentation was lost to a concurrent-session collision (see the T0019.7 completion report) —
> treat T0019.6 as open, not done, until it is committed with a completion report and its two human
> gates are cleared. Everything in §7 describes the pipeline as built and stays accurate. T0019
> changed three things about *how it runs*, none of which reshape the dataflow or tables above: (a)
> ✅ load semantics are now **accumulate-never-wipe** — the `TRUNCATE` in `clean_store.py` is dropped
> and the `(source, external_id)` upsert below is live code (`upsert_clean_jobs`), joined by hidden
> `is_active`/`first_seen_at`/`last_seen_at` lifecycle columns and a time-based expiry pass
> (**T0019.3**); (b) ⏳ an **external, out-of-band GitHub Actions cron** is intended to invoke the
> same CLI nightly against the live Neon DB (**T0019.6**, hard-gated on a robots.txt/ToS check,
> **T0019.1**, whose **recommended** verdict is favorable — *maintainer ratification in a tracked
> document is still outstanding*, so the gate is not yet cleared). The cron's `schedule:` trigger
> stays **dormant** regardless: GitHub only fires `schedule:` from the default branch, so it cannot
> run until the branch chain merges to `main`. Coverage and detail-visibility follow-ups are scoped
> as **T0019.9** and **T0019.10** (`docs/Tickets.md`); neither is implemented. This does **not**
> relax the §7 layer law or the `Full_Design_Document.md` §2 no-schedulers exclusion — the cron runs
> on GitHub's runner, never in the API process, and §2's exclusion is amended to name what it always
> meant: *in-request* background execution; (c) unattended-run safety — pre-flight schema assertion,
> pre-write yield floor, dead-man's-switch ping (**T0019.5**). Scope and sequencing:
> `docs/Tickets.md` T0019. Rationale: `research/archive/ingestion-milestone-plan.md`.
>
> ✅ **Production-DSN freeze lifted (2026-07-19, T0019.3).** The former rule here — *"do not run this
> CLI against the production DSN"* — no longer applies. `clean_store.replace_clean_jobs` has been
> renamed `upsert_clean_jobs` and its `TRUNCATE` is gone, so a run against Neon accumulates via the
> `(source, external_id)` upsert instead of rebuilding the live table. `Repo_Current_State.md`
> carries the same lift.

**Design intent: source-agnostic.** v1 ingests **VietnamWorks only**, but the schema, cleaning, and
interfaces are built so a future board is just a new adapter + normalizer with **no table reshape**.
Only two components ever know a source's specifics — the **adapter** (fetch) and the **normalizer**
(payload → common shape). Everything downstream is shared.

**Dataflow.**

```
JobSource (VietnamWorksSource) --RawPosting--> raw_jobs (verbatim landing, upsert on (source, external_id))
   -> Normalizer (source-specific: payload -> NormalizedJob)
   -> Transform (SHARED, deterministic, no LLM, no network):
        HTML->text · is_internship · tech_stack keyword finder · role taxonomy · location city-alias map
   -> Loader: upsert into clean_jobs on (source, external_id)
```

**Tables.**

- **`raw_jobs`** — verbatim landing: `id`, `source`, `external_id`, `source_url`, `raw_payload`
  (JSONB), `content_hash`, `fetched_at`; unique `(source, external_id)`. Never lossy. Lives in the
  application `DATABASE_URL` Postgres alongside `clean_jobs` (never Langfuse's Postgres).
- **`clean_jobs`** (enriched, agent-facing) — the original `title`, `company`, `description`,
  `tech_stack` plus `role`, `source`, `external_id`, `source_url`, `posted_date`, `is_internship`,
  `job_level`, `location`, and structured salary (`salary_min`, `salary_max`, `salary_currency`,
  `is_salary_negotiable`). `title` stays the raw posting title; `role` and `location` hold canonical
  normalized values. **`description` is a single merged free-text blob** (job description +
  requirements + benefits) — there are deliberately **no `requirement`/`benefits` columns**, because
  that is the common shape across all boards (most return one blob; VietnamWorks'
  separately-provided `jobRequirement`/`benefits` are concatenated back in its normalizer, and
  survive verbatim in `raw_jobs`). Unique `(source, external_id)`.

**Deterministic cleaning** (all pure, unit-tested, no LLM — keeps ingestion testable and aligned
with the project's "no over-engineering" rule; LLM extraction is a deferred future enhancement):

- **`tech_stack`** — a keyword finder matches the source skills array + the description text against
  a curated **technology dictionary** (`config/settings.yaml`), keeps technologies only
  (role/category labels dropped), dedups, emits the comma-separated string the SQL agent already
  expects.
- **`role`** — a **role taxonomy** maps the messy title into a fixed canonical set (AI Engineer,
  Data Scientist, Data Engineer, Data Analyst, ML Engineer, Software Developer), using
  keyword/pattern rules with the source `jobFunction` as a tiebreaker; unmatched titles fall to
  `Other` (never dropped).
- **`location`** — a **city alias map** collapses messy location text to a unified city/province
  (`Ha Noi`/`Hanoi` → `Hanoi`; `HCM`/`TPHCM`/`Ho Chi Minh`/`hcm` → `Ho Chi Minh City`); multi-city →
  comma-separated canonical set; street address discarded.
- **`description`** — source text is merged into **one free-text blob** (HTML stripped).
  VietnamWorks arrives pre-split, so its normalizer concatenates `jobDescription` + `jobRequirement`
  + benefit values back together; the other boards already return a single blob. This keeps one
  shape across all sources and one field for the agent to read.
- **salary** — mapped into **structured** fields rather than a display string, so the agent can
  range-filter and sort (the core "pay ≥ X" query): `salary_min`, `salary_max` (numeric, nullable),
  `salary_currency` (e.g. USD/VND — required whenever a number is present, since VietnamWorks mixes
  currencies), and `is_salary_negotiable` (bool). VietnamWorks maps
  `salaryMin`/`salaryMax`/`salaryCurrency` directly and sets `is_salary_negotiable = not
  isSalaryVisible`; a future string-only board parses its salary string deterministically, else
  leaves min/max NULL with `is_salary_negotiable = true`.

**Identity & idempotency.** Upsert on `(source, external_id)` with a `content_hash` for change
detection; re-running refreshes rather than duplicating. The fixtures are replaced; a tunable
`max_jobs` cap (~50) bounds a run.

**Configuration.** Everything tunable lives in `config/settings.yaml` `ingestion.*`: API URL,
AI/Data keyword queries, `jobFunction` ids, cap, delay, User-Agent, the technology dictionary, the
role taxonomy, and the city alias map. Internal records (`RawPosting`, `NormalizedJob`) and the
table models live in `models.py`, per project convention.

**Agent-layer impact.** Because the new `clean_jobs` columns are agent-visible, T0009 also updates
`prompts.schema_context`, the SQL-generation prompt, and the T0008 honesty rules (notably: salary is
numeric and currency-scoped — filter within a `salary_currency` — and may be NULL /
`is_salary_negotiable = true` → "may be missing or negotiable for some postings", not "not in the
data"). This is the column-cheap schema growth §4 describes, applied.

### 7.1 Unattended-run safety

*Status: implemented (T0019.5).*

Once the CLI runs unattended on a schedule (T0019.6) against the live DB, "it failed and someone
noticed" stops being a reliable control. `src/services/ingestion/safety.py` supplies three checks,
and `loader.py::run_ingestion` orders them so that **every abort happens before the write it
protects**:

- **`assert_clean_jobs_schema()` — pre-flight, before anything is fetched.** Queries live
  `information_schema.columns` for `clean_jobs` and compares against `{c.name for c in
  CleanJob.__table__.columns}`. The expected set is **derived from the ORM, never hand-maintained**
  — that is the whole point, since a hand-copied column list is exactly the artifact that drifts. It
  reports both directions (missing *and* unexpected) and treats an empty column set as "table
  absent" with its own message rather than listing every column as missing. It runs **first in
  `run_ingestion`** — before the source is constructed — so a drifted schema costs zero fetches and
  zero writes. This is the *detection* half of the schema-drift problem; Alembic (§4) is the
  *correction* half. Migrations cannot detect a database altered out-of-band, which is the incident
  that motivated both (`Known_Issues.md`, schema-drift entry).
- **`assert_min_yield(fetched, min_yield)` — after the raw upsert, before the clean upsert.** Raises
  when a run returns implausibly few postings (`ingestion.safety.min_yield`). The placement is
  deliberate and load-bearing in two ways: `raw_jobs` is written *first*, so a bad run still
  preserves its evidence for diagnosis; and the abort lands *before both* the clean upsert **and**
  the expiry pass — which matters, because `expire_stale_clean_jobs` ages rows on `last_seen_at`.
  Aborting after a skipped clean write but before expiry would let a single bad fetch mark the
  entire healthy corpus inactive.
- **`send_dead_man_ping(url)` — last, and only on a fully green run.** POSTs to a healthchecks.io
  URL (`HEALTHCHECKS_URL`, optional). It never raises: an unset URL logs `ingestion.ping_skipped`
  and returns `False` (the normal local path, not an error), and any HTTP failure logs
  `ingestion.ping_failed` and returns `False`. **The signal is the withheld ping, not a sent alert**
  — the monitor alerts on *silence*, which is what makes it a dead man's switch rather than one more
  thing that can fail quietly.

The library/process split is kept clean: `run_ingestion` stays library code and lets
`IngestionSafetyError` propagate; `main()` owns the process contract, catching it, logging
`ingestion.aborted`, and exiting non-zero. Nothing in this module imports or is imported by the
request path.

**Deferred.** Other boards, anti-bot scrapers, ~~a scheduler/cron~~ (*scoped 2026-07-16 as T0019.6 —
see the status note at the top of §7*), LLM extraction, parsing a salary *string* into numbers (not
needed for VietnamWorks, which supplies the numbers directly), translating source text to a single
language, and cross-board dedup are out of scope (see `Tickets.md` T0009 Out of Scope and
`research/job-site-comparison.md`).

---

## 8. Evaluation Harness (offline)

*Status: implemented (T0011–T0012) — **Evaluation v1 (Phase 1)**.*

This is the **first version** of the project's evaluation phase: a deliberately-scoped offline
harness whose deliverable is the **v1 baseline** — the first measured snapshot of agent behavior
against a pinned fixture and golden set. It is intentionally minimal (offline only, no CI gate, no
online/production scoring, no chart/DAG metrics — those are later phases, §8.7). Everything
downstream that cites "the baseline" means this v1 baseline, and the T0011.5 report records it as
such (dated, tied to the fixture + golden version it was measured against). A later re-measure
produces a v2 baseline; the two are only comparable because the fixture is version-pinned (§8.3).

The evaluation harness is **offline quality tooling**, isolated from the request pipeline exactly
like §7 ingestion — it is never imported by the API, service, runtime, tools, or tracing layers, and
it runs on demand (`deepeval test run`), never on a schedule and (for now) never as a CI gate. Its
job is to establish a **measurable baseline** of the agent's task-correctness and its `MVP_Spec.md`
§3 honesty bar *before* any stage whose design depends on measured model behavior is built (the
`is_active` honesty hedge in Ingestion Deploy Readiness — renumbered **`Tickets.md` T0019**, scoped
2026-07-16).

> **This dependency did its job — by blocking (2026-07-16).** The T0011.5 baseline never ran (still
> blocked on maintainer credentials), so the gate the hedge's design set for itself is unmet, and
> the evidence that does exist is adverse (`Known_Issues.md` § Agent runtime & prompts:
> hidden-salary honesty violated 2/2, freshness fabricates 1/3). T0019 therefore **cut the hedge
> from its scope** rather than shipping it unmeasured: the `is_active` lifecycle *mechanics* ship as
> hidden DDL columns (no prompt surface, no eval dependency), and the *agent exposure* is deferred
> behind T0011.5 → prompt-v2 few-shot pass → a targeted recalibration delta. The harness's stated
> purpose — measure before building on measured behavior — is what produced that split
> (`research/archive/ingestion-milestone-plan.md` §1B). The full grounding — DeepEval mechanics, the
> 2026
> version-pinned facts, and the InternHunter-specific findings — is
> `research/archive/deepeval-sql-agent-eval-planning.md`; **read its §11 first.** Do not re-derive
> it here.

### 8.1 What it measures — three seams

The agent is not one LLM call. `query_clean_jobs` takes a **natural-language question**, and a
*separate, nested* `generate_sql` model call (`src/agents/tools/query_clean_jobs.py`) turns it into
SQL that deterministic code then validates and runs. So a single agent run has three distinct
decision points, and the harness scores each:

| Seam | What the model decides | Metric attaches to |
|---|---|---|
| 1. Routing | which tool + the NL question passed to it | the agent tool-call span |
| 2. NL→SQL | the SQL string (**invisible** to the ReAct trace) | the nested `generate_sql` LLM span |
| 3. Synthesis | the final user-facing answer | the final output |

Seam 2 is the point the generic research (§3) calls "most failure-prone," and it is **not** on the
tool call — it is inside the nested `generate_sql`. Capturing it is a tracing concern, so per the
`Full_Design_Document.md` §2 tracing-boundary law it must **not** be met by hard-coding a DeepEval
`@observe` inside the tools layer. Instead the harness threads its DeepEval `CallbackHandler` in
through **runtime config** — the same injection seam Langfuse tracing already uses (§2.5) — so the
nested call surfaces as its own span without eval concerns leaking into tool code. Whether
`generate_sql` needs a small config-propagation parameter to receive that callback is the one **open
implementation question** carried into T0011.

### 8.2 Metric stack (Phase 1)

Deterministic checks for everything exact; LLM-judge checks for everything semantic (research §3):

- **Seam 1 — Routing.** `ToolCorrectnessMetric` (deterministic — was `query_clean_jobs` /
  `get_job_details` / `get_current_time` the right choice, in the right order?) plus a light
  referenceless `ArgumentCorrectnessMetric` on the **NL question** the agent passed.
- **Seam 2 — NL→SQL.** `ArgumentCorrectnessMetric` plus a schema-aware `GEval` ("does this SQL
  respect the `clean_jobs` schema and answer the question?") on the `generate_sql` span.
  Referenceless — no expected SQL string is stored.
- **Seam 3 — Synthesis.** `TaskCompletionMetric` (did the user get what they asked?) plus
  **`FaithfulnessMetric`** with the tool's returned string as `retrieval_context` — this catches
  *fabrication* (invented freshness, hidden-salary claims not in the data) — plus a **`GEval`
  honesty** criterion for *omission* (the truncation caveat is emitted deterministically by
  `_build_answer`; the risk is the agent stripping it when it rewrites the answer for the user).

Thresholds are **calibrated after the first baseline run**, not pre-set (research §9): a threshold
above the baseline blocks every build; below it, nothing signals.

### 8.3 Golden dataset & the seeded eval database

- **~17 versioned goldens** (inside the 15–25 band), stored in-repo alongside the harness,
  automating the `T0008.3` manual honesty checklist plus **explicit probes** for the recorded
  model-behavior risks — freshness fabrication and hidden-salary phrasing (`Known_Issues.md`,
  agent-runtime section). Each golden carries: NL input, `expected_tools`, an optional *semantic*
  `expected_output`, and metadata (category, difficulty, honesty-probe flag). The expected SQL is
  deliberately **not** stored — the seam-2 metrics are referenceless. They span five categories: **A
  grounded retrieval** (count/list/truncation, asserting the fixture's pinned totals), **B
  multi-turn refinement** (stored as `ConversationalTestCase`s so the agent's own context-carry is
  what gets scored, not a pre-flattened turn), **C honesty probes** (freshness, cross-currency
  "highest paid", absent-tech, out-of-schema "remote", hidden salary, hidden seniority), **D
  safety/refusal** (unsafe/off-topic/injection — asserting `expected_tools=[]` **and** a refusal, so
  a model that queries the DB before refusing still fails), and **E resilience** (vague input,
  dangling pronoun with no prior turn). **6 of the ~17 are flagged `honesty_probe`** — the subset
  the T0011.5 go/rethink verdict on the `is_active` design rests on.
- **The harness runs against a small (~22-row), version-controlled seeded fixture database, not live
  `clean_jobs`.** This is what lets honesty goldens assert exact counts, truncation notices, and
  specific rows, and what makes before/after comparison valid (research §6: a golden's baseline is
  only meaningful against a fixed dataset version). The fixture is versioned with the goldens;
  changing it changes the baseline. Its free text (`title`/`company`/`description`) is drawn from
  the real captured postings in `research/experiments/vietnamworks_ai_data_sample.json` so answers
  read authentically, while the structured columns are *engineered* to a fixed distribution that
  pins every golden. The role split sums to exactly 22 — AI Engineer 5 and Data Scientist 4 (the two
  counts goldens assert), plus Data Engineer / ML Engineer / Data Analyst 4 each and 1 Other;
  overlaid pins are Python in 12 rows (7 of them Hanoi → the two-turn refinement), COBOL in 0, both
  USD and VND salaries present, and `posted_date`/`job_level` NULL on all 22. Internship-ness is one
  filterable attribute among many — the corpus (and the fixture, ~5 of 22 rows) is mostly
  non-internship AI/Data postings, matching the real live data (see `Known_Issues.md` scope-drift
  note).

### 8.4 Judge LLM

- The generic research (§5) recommended Llama-3-70b, which Groq **retired** (research §11.4). The
  primary judge for T0011 is its Groq replacement (`openai/gpt-oss-120b` or `qwen/qwen3.6-27b`),
  **pinned by a live JSON-reliability spike** — DeepEval hard-fails without schema-valid JSON, and
  `gpt-oss-120b` has reported structured-output regressions.
- **Confirmed fallback: Google Gemini free-tier** (adds a `GEMINI`/`GOOGLE_API_KEY` and a second LLM
  provider). Beyond de-risking the JSON problem, a Gemini judge **decouples judge load from Groq** —
  today the agent *and* a Groq judge would share one free-tier limit — which makes Gemini the
  natural *primary* if/when the CI gate lands. The judge is wrapped in a `DeepEvalBaseLLM`;
  `instructor`/LiteLLM coercion is adopted only if a Groq judge is kept and needs it. Eval quality
  is bounded by judge quality (research §5) — 70B-class is the floor.

### 8.5 Score writeback to Langfuse

A post-run step calls `langfuse.create_score(name=metric, value=score, trace_id=…, data_type=…)` on
the v4 (OTEL) client — `BOOLEAN` for honesty pass/fail, numeric for graded metrics — so eval scores
land on the same trace as the raw run and Langfuse stays the single pane of glass (it does **not**
replace Langfuse's role, per §2.5). Re-runs are idempotent via `score_id = f"{trace_id}-{metric}"`.
The one integration seam to verify in implementation is threading the Langfuse `trace_id` onto the
DeepEval test case (research §11.5).

### 8.6 How it runs, and its boundaries

- **On-demand, local-first.** T0011 delivers a runnable `deepeval test run` (pytest-integrated) plus
  the dataset, metrics, and writeback. It is **not** wired into CI — the first `.github/workflows/`
  PR gate is a deliberate **fast-follow ticket**, matching the deferred-deploy posture and avoiding
  standing up CI + Groq-in-CI rate-limit handling before it is needed.
- **Layer isolation.** The harness treats the agent as a black box via its public entrypoint plus
  the injected `CallbackHandler`; the only touch inside the agent boundary is the config seam that
  lets the `generate_sql` span be observed (§8.1), which carries no eval logic and is inert in
  production.
- **No online eval.** Production-trace scoring, `DAGMetric`, chart metrics, and production-sampled
  goldens are out of scope (research §§4, 8) — this milestone measures the offline baseline only.

### 8.7 Prerequisite & deferred

- **Prerequisite (not owned here):** the agent must run on a **non-retired model** for the baseline
  to mean anything — `config/settings.yaml` still pins the agent to `llama-3.3-70b-versatile`, which
  Groq shuts down 2026-08-16 (`Known_Issues.md`, F1). That migration is a **separate** follow-up,
  deliberately not folded into T0011.
- **Deferred:** the CI gate, online/production eval, `DAGMetric`, Phase-2 chart metrics,
  production-sampled goldens, and any judge-matrix / Confident-AI cloud. And, by design, **fixing**
  a measured behavior — T0011 *measures*; remediation is separate work.

---

## 9. Streaming Response Delivery

*Status: implemented (T0017).*

The MVP as built answers in one shot: the runtime runs the agent to completion
(`react_agent.py::AgentRuntime.ainvoke`), and the route returns a single finished `QueryResponse`.
The user waits on a spinner for the whole 5–15 s run, then the entire answer appears at once.
Streaming changes the **delivery contract** — from "return one finished value" to "yield the answer
token-by-token as the model produces it" — so the first words appear in ~1 s and the answer grows
live. This is the clickable-demo's single largest perceived-latency win, and it is the reason T0017
exists. It does **not** change *what* the agent computes, only *how the result is delivered*.

This section is the streaming design as shipped. It revises three earlier sections that describe the
one-shot system: §1 (adds the branch point that section says does not exist), §3 (the response is no
longer a single JSON body), and §5 (mid-run errors are delivered differently). Those sections carry
forward-reference notes; this section is the source of truth for the streaming path. Grounded
mechanics — pinned versions, the empirically verified node names, and the SSE API surface (all
live-checked 2026-07-13) — live in `research/archive/streaming-implementation-plan.md` and are not
restated
here.

### 9.1 The contract shift — return-once to yield-many

A one-shot function `return`s a value once; a streaming function `yield`s pieces over time (a Python
`async` generator). The defining constraint is that **this shape must hold through every layer**:
route → service → runtime. A single layer that collects the whole stream into a value before passing
it on collapses streaming back into one-shot — silently, while still "working" in a naive test. So
streaming is not a runtime-local change; it is a new end-to-end path that runs *alongside* the
one-shot path, which is retained (§9.6).

Each layer keeps its existing responsibility (the `Full_Design_Document.md` §2 layer-isolation law
is unchanged):

- **Runtime** gains a streaming method beside `ainvoke`. It drives the agent's streamed extraction —
  **`astream_events(version="v3")` typed message projections preferred, falling back to
  `astream(stream_mode="messages")` + the §9.2 filter** — and yields small transport-agnostic event
  dicts (`{"type": "token", ...}`), not HTTP or SSE constructs, so the runtime still knows nothing
  about the wire. On the pinned `langchain 1.3.1`, `v3` emits a beta warning (verified 2026-07-13),
  so the v3-vs-fallback choice is an implementation finding made *in the ticket*, not fixed here;
  both mechanisms owe the same §9.2 no-leak guarantee. (See
  `research/archive/streaming-implementation-plan.md` §2.)
- **Service** gains a streaming sibling of `generate_agent_response` that mints the `session_id` up
  front (still known before the run), passes runtime events through, and owns fallback/error
  *policy* — but now delivers that policy as yielded events, not exceptions.
- **Route** gains a streaming endpoint that is the **only** layer aware of the wire format; it
  adapts the service's event dicts into SSE bytes.

### 9.2 The no-leak filter — the one hard problem

One-shot delivery enforces the answer-only law (§3, `Full_Design_Document.md` §4) for free:
`_extract_answer` takes only the final message, so the ReAct loop's intermediate reasoning, tool
calls, and raw rows are discarded before anything crosses the API boundary. Streaming forfeits that
freebie — `agent.astream(stream_mode="messages")` emits **every** token from every node, including
the tools node's raw `query_clean_jobs` / `get_job_details` output and any model reasoning that
precedes a tool call. Streaming therefore has to **re-earn** the no-leak guarantee with an explicit
filter.

The agent (`factory.py::agent_factory`) is a standard two-node ReAct graph: a **model node** (the
LLM) and a **tools node** (executes tools, returns raw data). Each streamed chunk carries
`metadata["langgraph_node"]`. The filter is **two gates**:

1. **Node gate** — emit only chunks from the model node; drop the tools node entirely. This kills
   the worst leaks: the tools node's raw rows, **and the raw SQL emitted by the nested
   `generate_sql` LLM call that runs *inside* `query_clean_jobs`** (it executes under the tools
   node, so the node gate excludes it automatically). This is exactly why a naive "stream only text
   deltas" filter — including v3's `.text` projection consumed globally — is *insufficient* here:
   `generate_sql` produces text too, so scoping to the model node, not "any text," is the actual
   guarantee.
2. **Tool-call gate** — within the model node, drop chunks that carry `tool_call_chunks` (the
   tool-invocation plumbing, which normally rides an empty-content chunk).

What survives both gates is model-authored answer text. **Residual risk:** if the model narrates
reasoning *as content* on the same turn it calls a tool ("Let me look that up…"), that text streams
before the tool-call gate can fire. This is model- and prompt-dependent. It is handled at MVP scope
by (a) a system-prompt instruction not to narrate before tool calls, and (b) — load-bearing — a
**leak test** that runs a tool-invoking query and asserts no SQL, tool name, or row data ever
appears in the streamed tokens. Heavier machinery (buffering a whole turn to be certain) is
rejected: it would defeat streaming on the final turn, the one turn that most needs to stream.

**The model-node name is verified, not assumed.** `create_agent` and the older `create_react_agent`
differ (`"model"` vs `"agent"`), and node names can change across versions. Verified 2026-07-13
against the compiled agent: `agent_factory().get_graph()` has nodes `['__start__', 'model', 'tools',
'__end__']`, so the answer streams from the **`model`** node
(`research/archive/streaming-implementation-plan.md` §3). Re-confirm with a `(langgraph_node,
content,
has_tool_call)` probe if the langchain version or the factory changes.

### 9.3 Metadata timing — trace data trails the answer

`trace_id` / `trace_url` only exist **after** the run completes and Langfuse flushes
(`react_agent.py` resolves them post-`ainvoke`). They cannot lead the stream. So the event order is
fixed: **tokens first, then a single trailing `metadata` event** once the trace link is resolvable,
then a terminal `done`. The UI shows the answer immediately and the "view trace" link appears a beat
later. `session_id`, by contrast, is known before the run and is emitted as the **first** event so
the client can pin the conversation key immediately.

### 9.4 Transport — SSE

Server-Sent Events (SSE): a long-lived `text/event-stream` HTTP response of typed `event:`/`data:`
blocks. Chosen over the two alternatives: plain chunked text has no structure (nowhere clean to put
the trailing trace metadata or an in-band error, so it grows an ad-hoc protocol anyway); WebSocket
is a bidirectional persistent connection and is overkill for a one-directional server→client token
stream. SSE's typed events map exactly onto this section's two problems — the trailing-metadata
ordering (§9.3) and in-band errors (§9.5) — and are natively consumable in the browser.

The event vocabulary:

| Event | Payload | When |
|---|---|---|
| `session`  | `{session_id}` | first, before any token |
| `token`    | `{text}` | each surviving chunk (§9.2), many |
| `metadata` | `{trace_id, trace_url}` | once, after the token stream ends |
| `error`    | `{message}` | in place of further tokens on mid-run failure (§9.5) |
| `done`     | `{}` | terminal, always closes the stream |

Each token is **JSON-wrapped** (`data: {"text": "…"}`), not raw, because SSE is newline-framed and
LLM tokens contain newlines; JSON escaping keeps one token to one safe `data:` line. **No new
dependency is needed: FastAPI 0.136.3 (the pinned version, verified 2026-07-13) ships a native
`fastapi.sse.EventSourceResponse`** for `text/event-stream` responses. Implementation finding from
T0017.2: direct `EventSourceResponse(async_generator)` does not auto-encode yielded
`ServerSentEvent` objects in this installed version, while the route-level SSE producer path
conflicts with the required pre-stream blank-query `400`; therefore this endpoint explicitly
JSON-frames the small `event:`/`data:` blocks and sets the anti-buffering headers (`Cache-Control:
no-cache`, `X-Accel-Buffering: no`) on the response. This still avoids `sse-starlette` and keeps the
API layer limited to wire-format translation. (`research/archive/streaming-implementation-plan.md`
§4;
`sse-starlette` is not installed and not required.)

*Browser-consumption note (for the T0017 UI phase, not this doc's scope):* the native `EventSource`
API is GET-only, but the endpoint is `POST` with a JSON body — so the UI either consumes the stream
via `fetch()` + a reader, or the endpoint offers a GET variant. This is a UI-layer decision recorded
in §9's follow-on UI design, not a backend constraint.

### 9.5 Error handling under a stream

One-shot error handling (§5) maps failures to HTTP status codes (`400` empty query, `429` provider
busy, `500` internal). Streaming splits this at a hard line: **the moment the first event is sent,
the response status is already `200`** and can no longer carry an error. Because the **`session`
event is emitted first** — before the agent runs (§9.3) — that line is crossed immediately, so the
model call (and any provider-busy it raises) is always *after* it.

- **Pre-stream failures use status codes; there is exactly one.** Empty-query validation happens
  before the generator starts, so it still returns a clean `400`. (The per-IP rate limiter also
  rejects with `429` before the route body runs — but that is middleware, not this path.)
  **Provider-busy cannot be a pre-stream status here:** it can only be known once the model runs,
  which is *after* the `session` event has committed the `200`. So — unlike the one-shot path, which
  maps `ProviderBusyError` to a `429` — under streaming a provider-busy is delivered in-band (next
  bullet). This is a deliberate consequence of session-first ordering, not an oversight.
- **All runtime failures are in-band `error` events.** Once the stream has started, a provider
  hiccup or internal failure is delivered as an `event: error` with a safe message (`BUSY_MESSAGE`;
  the existing `classify_provider_busy_error` policy still runs, e.g. for logging — only the
  *delivery* changes from raised exception to yielded event), followed by `done`. No `str(exc)` ever
  crosses the boundary. The UI renders it as a chat bubble.
- **Empty-answer fallback moves to stream end.** The one-shot path coerces an empty answer to
  `FALLBACK_ANSWER` after the run. In the stream, emptiness is only known when the token stream
  closes with nothing emitted, so the fallback is decided at end-of-stream and sent as a single
  `token`.

### 9.6 What is retained, and scope boundaries

- **The one-shot path stays.** `ainvoke` / `generate_agent_response` / `POST /api/v1/agent/chat`
  remain as the non-streaming fallback and keep the existing integration tests (§6) green. The
  streaming method wraps the same agent, so the two paths share all agent internals; only delivery
  differs.
- **In scope (T0017):** the `astream` runtime method + two-gate filter + leak test, the streaming
  service generator, the SSE route and event vocabulary, and the anti-buffering headers.
- **Out of scope (over-engineering for a demo):** resumable/replayable streams,
  retry-from-last-token, multi-node progress indicators ("searching… reading…"), and per-tool
  streamed status. These are explicitly excluded; the demo streams the final answer only.
- **Sequencing note:** the demo is intended to showcase honesty behavior, which the evaluation
  baseline (§8) measures and which has recorded gaps; streaming makes any honesty regression *more*
  visible, not less, so the streamed answer must still route through the same tool/prompt path the
  eval scores — streaming adds no bypass.

---

## 10. Public-Endpoint Hardening

*Status: implemented (T0016.1–.4).*

Everything above describes an agent reachable from a trusted caller. Exposing it publicly (T0018.4)
adds a distinct concern: the endpoint must survive an untrusted internet without a WAF, an API
gateway, or an auth layer — none of which the MVP has or needs. Four narrow controls, all assembled
in `src/api/app.py::create_app` and all configured under `api.*` in `config/settings.yaml`, carry
that load. They are deliberately not an auth system: the demo is public by design, and these bound
*abuse*, not *access*.

**Middleware nesting is verified, not assumed.** Starlette's `add_middleware` does
`user_middleware.insert(0, …)`, so the **last** registered middleware is the **outermost**.
Confirmed against the built app: the stack is `FrameGuardMiddleware` → `CORSMiddleware` → routes.
`FrameGuardMiddleware` being outermost is what makes §11.2's header apply to *every* response — API,
static asset, docs page, and error alike — rather than only to responses that reach the router.

### 10.1 CORS

`CORSMiddleware` is configured from `api.cors.*` (`allowed_origins`, `allow_credentials`,
`allowed_methods`, `allowed_headers`), read through a defensive `_load_cors_config()` that tolerates
a missing or malformed `api` block rather than failing startup.

Two decisions are recorded here because the config alone reads as an oversight:

- **`allow_credentials: false` is permanent.** The API has no cookies or sessions to carry;
  credential-less CORS is the safe default and there is no requirement pushing against it.
- **`allowed_origins: []` is deliberate, not unfinished.** T0018.2 serves the UI from the same
  origin as the API (§11.1), so no cross-origin request exists to permit. The empty list is
  therefore the *correct* production value, and the middleware is effectively inert. It is retained
  — rather than deleted — because a future separately-hosted frontend is a config change, not a code
  change, which is exactly the property worth keeping.

### 10.2 Per-IP rate limiting

`slowapi`'s `Limiter(key_func=get_remote_address)` keys on client IP, with the limit string from
`api.rate_limit` (default `"15/minute"`). It is applied to the chat routes and **not** to
health/readiness — an uptime probe must never be throttled, and §11.3's endpoints exist precisely to
be polled.

`RateLimitExceeded` is handled by `_rate_limit_exceeded_handler`, returning `429` with
`BUSY_MESSAGE` — **the same body the provider-busy path returns**. This is intentional: a visitor
who is rate-limited and a visitor who arrived during Groq pressure both see one honest "busy, try
again" message, and neither learns which internal condition fired.

> **The limiter is in-process, which couples this section to the deploy topology.** Counters live in
> the worker's memory, so with *n* workers the effective limit is *n* × the configured value. The
> deployment runs `WEB_CONCURRENCY=1`, which makes the configured number the real number. **Scaling
> past one worker silently multiplies the limit** and is the point at which this must become a
> shared-store limiter (Redis) or move to an edge/CDN layer. A single-instance free tier is the
> reason the simple version is adequate today — not an argument that it generalizes.

### 10.3 Request length cap

`QueryRequest.query` carries a Pydantic `max_length`, so an oversized prompt is rejected at
validation with a `422` before reaching the agent — bounding both token spend and the checkpointer
row a long input would write.

> **Known deviation from the config convention.** `api.max_query_chars: 2000` is recorded in
> `config/settings.yaml`, but `src/api/schemas.py` enforces a *static* `DEFAULT_MAX_QUERY_CHARS =
> 2000` — the Pydantic field constraint is evaluated at class-definition time and does not read the
> YAML. The two agree today by hand, not by construction, which contradicts the project's
> "parameters live in `settings.yaml`" rule (`CLAUDE.md` §1). **Changing one without the other
> silently does nothing.** Closing it means either a config-backed schema loader or dropping the
> unused YAML key; the deviation is recorded rather than quietly tolerated. Also tracked in
> `Repo_Current_State.md`.

### 10.4 API documentation exposure

`api.docs_enabled` gates `/docs`, `/redoc`, and `/openapi.json` **together**, applied at
`FastAPI(...)` construction by passing `None` for each URL when disabled — so the routes are never
registered, rather than registered and then blocked.

Keeping them public is a deliberate portfolio choice: the demo's audience includes people evaluating
the API design, and the schema reveals nothing that the answer-only contract (§3) does not already
imply. The single flag exists so that judgement can be reversed in one line if the endpoint is ever
reused in a context where it does not hold.

---

## 11. Demo Surface

*Status: implemented (T0018.1–.3).*

The API needed a face before it could be shown to anyone. This section covers how the browser demo
is served and the two endpoints added to support it. It is **not** a UI design document — the visual
system, its rationale, and the interaction details belong to the T0018.3 record in
`Completion_Reports.md`.

### 11.1 Same-origin static serving

`create_app` mounts `src/api/static/` at `/` with `StaticFiles(html=True)`. Serving the UI from the
API process — rather than a separate static host — is what makes `api.cors.allowed_origins: []`
correct (§10.1) and removes an entire class of cross-origin and preflight problems from a demo that
gains nothing from being split.

> **Mount ordering is a correctness constraint, not style.** The `/` mount is registered **after**
> both routers, and must stay there. A mount at `/` matches every path, so registering it earlier
> would shadow `/api/v1/*` and the docs routes, and the failure looks like a `404` from the API
> rather than a routing mistake. Verified route match order: `/openapi.json`, `/docs`, `/redoc`,
> `/api/v1/agent/chat`, `/api/v1/agent/chat/stream`, `/api/v1/health`, `/api/v1/ready`, then the
> catch-all `Mount`. Treat the position of the `app.mount(...)` line in `create_app` as
> load-bearing.

### 11.2 Frame protection

`FrameGuardMiddleware` is a **pure-ASGI** middleware that injects `X-Frame-Options: DENY` by
wrapping the `http.response.start` message. Being outermost in the stack (§10), it covers every
response the app can emit.

It is hand-written rather than pulled from a library, and pure-ASGI rather than a
`BaseHTTPMiddleware` subclass, for one specific reason: **`BaseHTTPMiddleware` buffers the response
body**, which would break the §9 SSE token stream — the single feature the demo exists to show. A
middleware that touches only the response-start message leaves the streaming body untouched. This is
the same constraint that shaped §9.4's anti-buffering headers, and any future response middleware
inherits it.

### 11.3 Health versus readiness

Two endpoints with deliberately different contracts, both outside the chat rate limiter (§10.2):

- **`GET /api/v1/health`** — static liveness. Touches no dependency and always returns `200`. This
  is what the platform's health check polls; making it depend on the database would let a transient
  DB blip trigger an instance restart that cannot possibly fix it.
- **`GET /api/v1/ready`** — real readiness. Executes `SELECT 1` through `session_factory`, off the
  event loop via `asyncio.to_thread` (the same discipline §2.3 applies to query execution), and
  returns `503` on any failure. On success it also returns `data_snapshot_date`, which the UI
  renders as its corpus-age disclaimer.

The liveness/readiness split is what lets the demo degrade honestly: the page can load and explain
that data is unavailable, instead of appearing healthy while every query fails.

> ✅ **`data_snapshot_date` is derived from data state (T0019.8, 2026-07-20).** It was a
> hand-maintained static config value that had to be edited whenever the shipped corpus changed —
> with T0019.3's accumulate semantics landed, the corpus could advance nightly while that string did
> not, making the disclaimer the one part of the UI that could silently lie.
> `get_data_snapshot_date()` in `src/api/routes/health.py` now runs `SELECT MAX(last_seen_at)::date
> FROM clean_jobs` and returns the ISO date, falling back to `api.demo.data_snapshot_date` when the
> table is empty or the query fails. The endpoint and UI contracts are unchanged; only the value's
> source moved.
>
> **`last_seen_at`, not `fetched_at`** — an earlier draft of this section named `SELECT
> MAX(fetched_at)`, which is wrong under T0019.3: `fetched_at` lives on `raw_jobs` (§7), whereas
> `last_seen_at` is the per-row freshness signal on `clean_jobs` that the upsert refreshes on every
> run. The disclaimer describes the *served* corpus, so it must read the served table.
>
> **The fallback is deliberately silent to the caller and loud in the logs.** `last_seen_at` only
> exists after T0019.3's migration; against an un-migrated database the query raises, the fallback
> fires, and `/ready` still returns `200` with a stale-but-plausible date. That keeps a readiness
> probe from flapping on a cosmetic field, but it means schema drift is invisible from the response
> body alone — it is recoverable only from the `snapshot_date_query_failed_using_config_fallback`
> warning (logged with `exc_info`). Tracked in `Known_Issues.md`.

The two DB round trips are separate on purpose: `SELECT 1` runs first and a failure short-circuits
to `503` **before** the date query is attempted, so the two failure modes stay independently
observable and the 503 path costs exactly one query.

### 11.4 The browser client

`src/api/static/` holds `index.html`, `styles.css`, and `app.js` — vanilla, no build step, no
framework, no bundler. It consumes §9's SSE contract via `fetch()` plus a `ReadableStream` reader
rather than the native `EventSource`, because `EventSource` is GET-only and the streaming endpoint
is a `POST` with a JSON body (the constraint anticipated in §9.4).

The client is a **consumer of the public contract and nothing more**: it holds the server-minted
`session_id` and returns it on later turns (§3), renders `token` events as they arrive, shows a
trace link only when `metadata` carries a non-null `trace_url`, and renders an in-band `error` event
as a normal chat bubble (§9.5). It knows nothing about the agent, the tools, or the schema — the
answer-only law (§3, `Full_Design_Document.md` §4) is what makes such a thin client sufficient.
