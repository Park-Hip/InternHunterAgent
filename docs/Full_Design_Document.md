# Full Design Document

## 1. System Overview & Strategic Intent
InternHunterAgent is a FastAPI service that turns a chat request into a traced, tool-augmented LangChain ReAct agent response, backed by a self-hosted Langfuse observability stack.

Every request follows one fixed pipeline, with no branch points or alternate paths:

```
ChatRequest -> API (routes/query.py) -> Service (agents/service.py) -> Agent Runtime
(LangChain ReAct loop: factory.py, react_agent.py, provider.py, prompts.py)
-> Tracing wrap (agents/tracing/langfuse.py) -> QueryResponse{answer, session_id, trace_id, trace_url}
```

The following are permanent scope exclusions, not gaps to be closed by a future ticket:
- A single LLM provider (Groq, via `AgentProvider`) — no multi-provider routing or model-selection logic.
- No multi-agent routing, sub-agents, or agent-to-agent delegation.
- No autonomous or background execution (cron jobs, queues, schedulers).
- No persistent conversation memory or transcript store across requests.
- No authentication/authorization layer.

Design philosophy: every layer must be replaceable in isolation without forcing a rewrite of its neighbors. At any point in the project's life, the correctness of the layer contract matters more than how many features are implemented behind it.

## 2. Architectural Layer Matrix

**API layer** (`src/api/app.py`, `src/api/routes/`, `src/api/schemas.py`) — Owns HTTP transport and Pydantic validation only (`QueryRequest` in, `QueryResponse` out). It calls exactly one function, `generate_agent_response()`, and must never import LangChain, construct prompts, or know how the agent is built. The response contract is fixed to `answer`, `session_id`, `trace_id`, `trace_url` — no raw SQL, table rows, or tool internals may ever appear in an API response, regardless of which tools exist behind the runtime.

**Service layer** (`src/agents/service.py`) — The sole caller of the agent runtime. Owns request-level orchestration: invoking `AgentRuntime.ainvoke()`, translating runtime/tool failures into a safe response, and shaping the dict the API layer serializes. It holds no LangChain or database knowledge of its own; it delegates everything to the runtime.

**Agent runtime layer** (`src/agents/runtime/factory.py`, `react_agent.py`, `provider.py`, `prompts.py`) — The only place permitted to construct the LangChain agent. `factory.py` builds the agent via `create_agent()` with the registered tool list; `provider.py`'s `AgentProvider` wraps `ChatGroq` and is the single point where model configuration (temperature, timeout, retries) lives; `prompts.py` loads the system prompt from `config/prompts.yaml`; `react_agent.py`'s `AgentRuntime.ainvoke()` executes the loop and extracts the final answer. Tools are registered here and nowhere else — no other layer may add a tool to the agent.

**Tools layer** (`src/agents/tools/`) — Each tool is a self-contained `@tool` adapter (e.g. `time.py`'s `get_current_time`, and the planned `query_clean_jobs`). Tools may call internal services freely (e.g. `src/services/query/` for SQL generation, validation, execution, and formatting) but the LLM itself never receives a raw execution primitive — no direct SQL, no direct DB session. A tool's only public surface is natural-language-in, natural-language-out.

**Tracing layer** (`src/agents/tracing/langfuse.py`) — The only module allowed to import the Langfuse SDK. It builds the `CallbackHandler` and exposes `build_langfuse_config()`, consumed by the runtime when invoking the agent. If Langfuse credentials are absent or initialization fails, tracing degrades to a no-op — it must never raise and never block a request.

**Core layer** (`src/core/config.py`, `logger.py`, `db.py`) — Cross-cutting primitives only: settings (`GROQ_API_KEY`, `DATABASE_URL`, `LANGFUSE_*`), structured JSON logging, and the SQLAlchemy engine/session factory. Core holds no business logic and depends on nothing else in the system; every other layer may depend on Core, never the reverse.

**Never leak across boundaries:** raw SQL and tool-internal data structures stop at the tools layer; Langfuse SDK objects stop at the tracing layer; LangChain types (messages, runnables, agent objects) stop at the runtime layer. If a change requires passing one of these types across a layer boundary, the change is wrong, not the rule.

## 3. Telemetry & Local Observability Stack

The system runs two distinct Postgres instances that must never be conflated: the app's own `DATABASE_URL` Postgres holds domain data (e.g. `clean_jobs`) queried by tools, while Langfuse's internal Postgres (inside `docker/docker-compose.yaml`) holds Langfuse's own trace/project metadata. They have different lifecycles, different owners, and no schema overlap.

The self-hosted Langfuse stack (`docker/docker-compose.yaml`) is composed of:
- **langfuse-web / langfuse-worker** — the UI and the asynchronous trace-ingestion processor.
- **postgres:17** — Langfuse's relational metadata store.
- **clickhouse** — column-oriented storage for trace/event analytics at volume.
- **redis:7** — queueing and cache between web and worker.
- **minio** — S3-compatible object storage for large trace payloads.

This stack exists so the project has zero dependency on an external SaaS observability vendor during the MVP phase.

Tracing integration follows one pattern: a single `CallbackHandler` is built once in `src/agents/tracing/langfuse.py` and injected into the agent invocation through `build_langfuse_config()` — no route, service, or tool builds its own Langfuse client. The standing invariant for every request is one trace per request, with every tool invocation appearing as a child span underneath it. This invariant is the verification bar for all future tools, not just the ones that exist today — a new tool that doesn't show up as a traced span is an incomplete tool, regardless of whether it returns the right answer.

## 4. Engineering Trade-offs & Sequencing Strategy

The sequencing actually followed by this project is infra-and-reliability-first: skeleton (T0000) → runnable request flow (T0001) → agent runtime (T0002) → self-hosted observability infra (T0003) → tracing wiring (T0004) → hardening (T0005) → real tools (T0006+). Every tool-bearing ticket assumes a stable, traced, hardened request path already exists underneath it — tool work never gets to skip validation, configuration checking, or tracing because those were proven first.

"Never over-engineer" is enforced concretely, not aspirationally:
- SQL safety is a deterministic, hand-rolled validator and executor (allowlist/denylist regex checks, read-only transactions) — not an LLM-driven query-planning layer.
- There is exactly one model provider abstraction (`AgentProvider`/`ChatGroq`), with no provider-swap matrix built in advance of needing one.
- Tool output is returned as a single deterministic answer string; there is no second LLM call to narrate or summarize what a tool already produced.

Trade-off on internal richness vs. external leakage: tools and services may use internal DTOs and structured data freely for efficiency and traceability (e.g. `src/services/query/models.py`'s `TableArtifact`, `QueryToolResult`), but that richness must collapse to a plain string by the time it crosses the API boundary — internal complexity is allowed, external leakage is not.

This document encodes only the stable contract described above. Ticket-by-ticket scope, current branch, and completion status belong in `docs/Tickets.md` and `docs/Repo_Current_State.md`, not here — if a future change to this document starts describing what a specific ticket does rather than what the system permanently guarantees, that content belongs in one of those files instead.
