# Full Design Document

> **This document is the permanent contract** for InternHunterAgent — the system invariants and layer laws that hold regardless of which ticket is in flight or which features exist yet. It deliberately contains no ticket scope, build status, MVP capability list, or implementation walkthroughs. For how it relates to the other docs and what belongs where, see the [documentation map](README.md).

## 1. System Overview & Strategic Intent

InternHunterAgent is a FastAPI service that turns a chat request into a traced, tool-augmented LangChain ReAct agent response, backed by a self-hosted Langfuse observability stack.

Every request follows one fixed pipeline, with no branch points or alternate paths:

```
QueryRequest -> API (routes/query.py) -> Service (agents/service.py) -> Agent Runtime
(LangChain ReAct loop: factory.py, react_agent.py, provider.py, prompts.py)
-> Tracing wrap (agents/tracing/langfuse.py) -> QueryResponse{answer, session_id, trace_id, trace_url}
```

Design philosophy: every layer must be replaceable in isolation without forcing a rewrite of its neighbors. At any point in the project's life, the correctness of the layer contract matters more than how many features are implemented behind it.

## 2. Permanent Scope Exclusions

These are deliberate, permanent decisions — not gaps to be closed by a future ticket:

- **Single LLM provider** (Groq, via `AgentProvider`) — no multi-provider routing or model-selection logic.
- **No multi-agent routing**, sub-agents, or agent-to-agent delegation.
- **No autonomous or background execution** — no cron jobs, queues, or schedulers.
- **No cross-session or long-term memory.** Conversation memory is permanently limited to **session-scoped, short-term** context — what the agent needs to follow refinements within a single conversation. This memory may be *persisted* (so a conversation survives a restart and stays coherent across instances), but it is never shared across sessions and never accumulates into user profiles or a long-term store. Long-term recall — user history, resume understanding, embedding/similarity retrieval — is the excluded capability, regardless of how it might be stored.
- **No authentication/authorization layer.**

(The boundary between permitted short-term memory and excluded long-term memory is enforced architecturally — see §3, runtime layer.)

## 3. Architectural Layer Matrix

**API layer** (`src/api/app.py`, `src/api/routes/`, `src/api/schemas.py`) — Owns HTTP transport and Pydantic validation only (`QueryRequest` in, `QueryResponse` out). It calls exactly one function, `generate_agent_response()`, and must never import LangChain, construct prompts, or know how the agent is built. The response contract is fixed to `answer`, `session_id`, `trace_id`, `trace_url`.

**Service layer** (`src/agents/service.py`) — The sole caller of the agent runtime. Owns request-level orchestration: invoking `AgentRuntime.ainvoke()`, translating runtime/tool failures into a safe response, and shaping the dict the API layer serializes. It holds no LangChain or database knowledge of its own; it delegates everything to the runtime.

**Agent runtime layer** (`src/agents/runtime/factory.py`, `react_agent.py`, `provider.py`, `prompts.py`) — The only place permitted to construct the LangChain agent. `factory.py` builds the agent via `create_agent()` with the registered tool list; `provider.py`'s `AgentProvider` wraps `ChatGroq` and is the single point where model configuration (temperature, timeout, retries) lives; `prompts.py` loads the system prompt from `config/prompts.yaml`; `react_agent.py`'s `AgentRuntime.ainvoke()` executes the loop and extracts the final answer. Two responsibilities are owned exclusively here and nowhere else: **tool registration** (no other layer may add a tool to the agent) and **conversation memory** (the runtime owns the session-scoped short-term memory mechanism; the API and service layers pass a session identity through but never manage memory themselves).

**Tools layer** (`src/agents/tools/`) — Each tool is a self-contained `@tool` adapter (e.g. `time.py`'s `get_current_time` and `query_clean_jobs.py`'s `query_clean_jobs`, both registered in `factory.py`). Tools may call internal services freely (e.g. `src/services/query/` for SQL generation, validation, execution, and formatting) but the LLM itself never receives a raw execution primitive — no direct SQL, no direct DB session. A tool's only public surface is natural-language-in, natural-language-out.

**Tracing layer** (`src/agents/tracing/langfuse.py`) — The only module allowed to import the Langfuse SDK. It builds the `CallbackHandler` and exposes `build_langfuse_config()`, consumed by the runtime when invoking the agent. If Langfuse credentials are absent or initialization fails, tracing degrades to a no-op — it must never raise and never block a request.

**Core layer** (`src/core/config.py`, `logger.py`, `db.py`) — Cross-cutting primitives only: settings (`GROQ_API_KEY`, `DATABASE_URL`, `LANGFUSE_*`), structured JSON logging, and the SQLAlchemy engine/session factory. Core holds no business logic and depends on nothing else in the system; every other layer may depend on Core, never the reverse.

## 4. Cross-Boundary Invariants

Some types and data structures are permitted *inside* a layer but must never cross out of it. These are the standing "never leak" laws:

- **Raw SQL and tool-internal data structures stop at the tools layer.** Internal DTOs (e.g. `src/services/query/models.py`'s `TableArtifact`, `QueryToolResult`) may be used freely within tools and services, but must collapse to a plain string before the result leaves the tool.
- **Langfuse SDK objects stop at the tracing layer.** No route, service, or tool touches a Langfuse client directly.
- **LangChain types** (messages, runnables, agent objects) **stop at the runtime layer.** The service and API layers never see them.
- **The API response is answer-only.** No raw SQL, table rows, or tool internals may ever appear in a `QueryResponse`, regardless of which tools exist behind the runtime.

If a change requires passing one of these types across its boundary, the change is wrong, not the rule.

## 5. Observability Contract

Two Postgres instances exist and must never be conflated: the app's own `DATABASE_URL` Postgres holds domain data (e.g. `clean_jobs`) queried by tools — and, where session memory is persisted, its checkpoint state — while Langfuse's internal Postgres holds Langfuse's own trace/project metadata. They have different lifecycles, different owners, and no schema overlap. The self-hosted Langfuse stack lives under `infra/langfuse/`; its operational composition is an infrastructure concern, not part of this contract.

Tracing integration follows one pattern: a single `CallbackHandler` is built once in `src/agents/tracing/langfuse.py` and injected into the agent invocation through `build_langfuse_config()` — no route, service, or tool builds its own Langfuse client. The standing invariant for every request is **one trace per request, with every tool invocation appearing as a child span underneath it.** This invariant is the verification bar for all future tools, not just the ones that exist today — a new tool that doesn't show up as a traced span is an incomplete tool, regardless of whether it returns the right answer.

## 6. Engineering Principles

The system is built infra-and-reliability-first: a stable, traced, hardened request path is proven *before* any tool is added, so tool work never gets to skip validation, configuration checking, or tracing. (The concrete ticket sequence that followed this principle lives in `Tickets.md`.)

"Never over-engineer" is enforced concretely, not aspirationally:

- **SQL is LLM-generated, then deterministically validated.** The tool calls the model to *propose* a `SELECT`, but a deterministic, hand-rolled validator (allowlist/denylist checks, read-only execution) is the safety boundary that must approve it before execution. The generator is untrusted; the validator — not the model — is what makes the path safe. There is no LLM-driven query-planning or execution layer.
- **One model provider abstraction** (`AgentProvider`/`ChatGroq`), with no provider-swap matrix built in advance of needing one.
- **No post-tool narration.** A tool returns a single deterministic answer string; there is no second LLM call to summarize or re-narrate what a tool already produced. (This is distinct from the SQL-generation call *inside* the tool, which produces the query, not the answer.)
- **Internal richness, external simplicity.** Tools and services may use structured data freely for efficiency and traceability, but that richness must collapse to a plain string by the time it crosses the API boundary — internal complexity is allowed, external leakage is not.
