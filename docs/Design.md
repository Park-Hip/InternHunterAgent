# InternHunterAgent Design

> **Last verified:** 2026-08-20.

> **Eviction:** Replace a section when its owning implementation or decision changes.

This is the maintained design source for product scope, architecture, serving, offline pipelines,
operations, and the technology stack.
The schema contract, agent behavior, operational procedures, and durable decisions remain in their
specialist documents.

## Product and MVP bar

InternHunterAgent is a conversational front door to verified VietnamWorks AI and data job postings.
It helps Vietnamese job seekers ask, refine, and understand job questions in Vietnamese.
Every answer must be grounded in the stored corpus or clearly state its limitation.

The MVP must answer job questions, refresh its corpus unattended, retain a session conversation,
stay read-only, refuse unsafe or unanswerable requests, and make each interaction observable.
The service is done only when those behaviors are observable, including a successful scheduled
ingestion run and a documented startup command.

Trustworthiness is more important than a plausible answer.
An absent field, unavailable fact, zero result, vague question, or backend fault must yield an
honest, understandable response instead of invention or an internal error.

The MVP deliberately excludes resume upload, personalized matching, embeddings or RAG, charts,
accounts, continuous multi-source collection, global ATS aggregation, fine tuning, and multi-agent
orchestration.
The product can grow in those directions only through a later decision and measured design work.

## Request path and layer laws

The normal request path is:

```text
Browser -> FastAPI route -> application service -> agent runtime -> tools -> read-only data
                                                    |
                                                    +-> localized Langfuse tracing
```

The API layer owns HTTP transport, validation, static same-origin files, and the public response.
It calls the application service and does not construct LangChain objects, prompts, tools, or
tracing clients.

The application service is the sole caller of the agent runtime.
It translates runtime and tool failures into safe public responses without acquiring database or
LangChain knowledge of its own.

The agent runtime owns provider construction, prompt loading, tool registration, session-scoped
memory, the ReAct loop, and final answer extraction.
Only this layer may construct a LangChain agent or add a tool.

Tools are self-contained adapters that accept natural-language requests or opaque identifiers and
return bounded plain strings.
The model never receives a raw SQL primitive, database session, internal DTO, or unbounded data
payload.
SQL is model-proposed but deterministically validated as read-only before execution.

The tracing layer is the only place that imports the Langfuse SDK.
It injects a callback into a runtime invocation and degrades to a no-op if credentials or
initialization are absent.
Each request has one trace and each tool invocation is a child span.

Core owns settings, structured logging, and database primitives without business logic.
Every other layer may depend on Core, but Core depends on none of them.

## Boundary invariants

- LangChain messages, runnables, and agent objects stop at the runtime layer.
- Langfuse objects stop at the tracing layer.
- Raw SQL, table rows, and internal tool DTOs stop at the tools layer.
- The API returns the answer and documented metadata only, never reasoning or tool internals.
- Session memory is short-term and session-scoped, although it may persist across restarts.
- The request path never imports the ingestion or evaluation packages.
- A tool bounds result rows and field lengths by construction, not by a prompt instruction.

The production request path has one selected serving provider per profile.
It has no provider-routing matrix, in-request scheduler, background queue, long-term memory,
authentication layer, or agent-to-agent delegation.

## Serving contract

The browser sends chat requests with `fetch()` and reads typed SSE events through `ReadableStream`.
The server uses FastAPI's native SSE response.
It emits session, token, metadata, error, and done events as the relevant information becomes
available.

A two-gate stream filter permits only final agent content and excludes empty chunks.
This prevents internal reasoning and tool payloads from reaching the browser.
Once a response begins, failures are emitted as a friendly in-band error event and the stream ends
cleanly.

The demo is an editorial vanilla HTML, CSS, and JavaScript interface served from the same FastAPI
origin.
It has no client build toolchain.
The serving surface also has frame protection, conservative CORS configuration, per-IP rate limits,
request-size limits, deliberate API-documentation exposure, separate liveness and readiness checks,
and a documented health target.

## Agent runtime and data contract

The runtime uses a versioned system prompt, an `AgentProvider`, read-only job tools, and a complete
turn memory window.
Provider keys are validated only for the selected branch so a checkout need not hold credentials for
an unused provider.
DeepSeek is the default serving provider and the Groq branch remains selectable.
SQL generation is separately configured for deterministic sampling.

The agent reads the normalized `clean_jobs` table through a single-table allowlist.
Its frozen agent-visible columns are owned by [Schema Contract](Schema_Contract.md).
Source `createdOn` data is preserved, posting dates are never invented, and listing expiry comes
from the truthful source expiry field.
`is_active` exists in the data layer but is not exposed to the agent until behavior evidence supports
an honest presentation.

Alembic owns schema changes.
The application database owns domain data and persisted checkpoint state, while Langfuse Cloud owns
traces and project metadata.
Those stores have separate lifecycles and no shared schema.

## Ingestion pipeline

Ingestion is an offline batch process that writes the data later read by the serving path.
It runs as a command or externally scheduled GitHub Actions workflow, never inside an API request.
VietnamWorks is the selected first source under the recorded robots and terms decision.

```text
VietnamWorks adapter -> raw_jobs -> source normalizer -> deterministic transform -> clean_jobs
```

Raw postings are retained with source provenance and a content hash.
Normalization maps source data into common fields, including canonical role and location, internship
status, structured salary, and a merged text description.
The transform is deterministic, unit-tested, and contains no LLM or network call.
It uses a configurable technology vocabulary, role taxonomy, and city-alias map.

Upserts use `(source, external_id)` so a new run accumulates and refreshes records rather than
truncating a healthy corpus.
Configuration, keywords, limits, delays, source headers, and transforms live in the appropriate
configuration files rather than hard-coded application behavior.

Unattended runs perform a schema assertion before fetching, enforce a minimum yield before clean
writes or expiry, and send a dead-man-switch ping only after a fully successful run.
A failed or implausibly small fetch therefore preserves diagnostic raw evidence without shrinking
the served corpus.

## Evaluation and evidence

Offline evaluation treats the agent as a black box through its public entrypoint and the tracing
callback seam.
It evaluates routing, nested natural-language-to-SQL generation, and final answer synthesis as
separate seams.
Deterministic checks enforce exact contracts, while a separate-provider judge can assess semantic
quality.

The scenario registry owns scenario identifiers, expected tool behavior, and reference facts.
Versioned fixtures make result comparisons meaningful despite corpus churn.
Committed replays are replayed in CI without a model call and preserve the evidence needed to
reproduce a verdict: inputs, outputs, called tools, generated SQL, and deterministic outcomes.
They intentionally exclude per-turn telemetry and trace identifiers.

Evaluation measures behavior before remediation work changes it.
Online scoring, production-sampled goldens, judge matrices, and chart metrics are deferred.

## Operations and deployment

Render runs the Docker web service and Neon supplies PostgreSQL.
Render runtime environment variables hold production secrets, and Langfuse Cloud in Japan provides
observability.
GitHub Actions provides CI and the external ingestion workflow.

The production image is slim and runs as a non-root user.
The demo uses Render's same-origin subdomain, so no cross-origin frontend is required.
Operational topology, environment variables, database procedures, deploy flow, cron activation,
and incident response are owned by [Operations](Operations.md).

## Technology stack

| Layer | Choice | Where configured |
|---|---|---|
| Language and package manager | Python 3.12 and uv | `.python-version`, `pyproject.toml` |
| API | FastAPI and uvicorn | `src/api/` |
| Agent | LangChain ReAct with DeepSeek default and Groq option | `src/agents/`, `config/` |
| Data | PostgreSQL, SQLAlchemy, psycopg, Alembic | `src/services/`, `alembic/` |
| Tracing | Langfuse Cloud | `src/agents/tracing/` |
| Evaluation | DeepEval and Gemini judge | `evals/`, `config/` |
| Hosting | Render Docker web service and Neon Postgres | `render.yaml`, `docker/` |

<!-- deps:begin -->

| Dependency |
|---|
| `alembic` |
| `beautifulsoup4` |
| `cloudscraper` |
| `deepeval` |
| `fastapi` |
| `httpx` |
| `langchain` |
| `langchain-deepseek` |
| `langchain-google-genai` |
| `langchain-groq` |
| `langfuse` |
| `langgraph-checkpoint-postgres` |
| `lxml` |
| `mypy` |
| `psycopg` |
| `pydantic-settings` |
| `pytest` |
| `pytest-asyncio` |
| `pytest-mock` |
| `ruff` |
| `slowapi` |
| `sqlalchemy` |
| `structlog` |
| `uvicorn` |

<!-- deps:end -->

`pyproject.toml` is authoritative for exact dependency versions.
The product deliberately does not use RAG, fine tuning, a hardcoded technology allowlist,
self-hosted Langfuse, a JavaScript framework, Celery or Redis, or browser `EventSource`.
