# Streaming Implementation Plan — T0017 (Clickable Demo)

> **Status:** Research / pre-design (2026-07-13). Not an implementation plan and not a
> commitment to build. It answers one question asked before T0017 is scoped into
> sub-tickets: *how should the streaming phase be implemented in this project?* It feeds the
> T0017 sub-ticket split and the `docs/MVP_Technical_Design.md` streaming sections (§1
> lifecycle, §3 contract, §5 errors). Read alongside
> [`pre-deploy-refinement-plan.md`](pre-deploy-refinement-plan.md) §6j–§6k (the demo-surface
> and streaming decisions this elaborates) and `docs/Tickets.md` T0017.
>
> **Evidence over assumption.** Every version and API claim below was live-checked against
> the project `.venv` on 2026-07-13; the check is named inline. Web sources are listed in §9.

---

## 0. TL;DR

- **Streaming is three independent decisions, not one.** (1) how the *runtime* pulls tokens
  out of the ReAct loop, (2) the *no-leak filter* that guarantees no tool internals reach the
  user, (3) the *transport* to the browser. §1 disentangles them.
- **Runtime extraction (axis 1):** prefer `astream_events(version="v3")` typed message
  projections; fall back to `astream(stream_mode="messages")` + a manual two-gate filter if
  v3 is unstable in this repo. **On `langchain 1.3.1`, v3 emits a beta warning** — so the
  ticket should try v3, *measure*, and drop to the stable `astream` path if it is noisy. §2.
- **No-leak filter (axis 2) is the load-bearing part, and this repo has a subtlety generic
  tutorials miss:** the agent makes a *second, nested* LLM call (`generate_sql`) **inside**
  the `query_clean_jobs` tool, which emits the raw SQL string as text. Filtering "only text
  deltas" is therefore **not** a sufficient leak guard — the filter must scope to the outer
  agent's synthesis call (the graph's **`model`** node) and exclude both the `tools` node and
  tool-call chunks. §3.
- **Transport (axis 3): use FastAPI's native `EventSourceResponse`.** FastAPI **0.136.3** is
  installed (checked), which ships `fastapi.sse.EventSourceResponse` — automatic
  `X-Accel-Buffering: no`, `Cache-Control: no-cache`, 15 s keep-alive pings, and JSON
  encoding. **No `sse-starlette` dependency is needed** (it is not installed and would be
  redundant). §4.
- **The metadata-timing problem drives the event contract:** `session_id` is known before
  the stream, tokens during, and `trace_id`/`trace_url` only *after* the Langfuse flush. A
  typed SSE event stream (`session` → `token`* → `metadata` → `done`, plus `error`) carries
  all three cleanly; a plain-text stream cannot. §5.
- **Mid-stream errors cannot use HTTP status** (200 is already sent), so provider-busy/500
  must be surfaced in-band as an `event: error`. The existing `ProviderBusyError`/429 path
  only works for pre-stream failures. §6.

---

## 1. Streaming is three axes, not one flag

`agent.groq.streaming: False` in `config/settings.yaml` is only the *provider* switch — it
makes the Groq model emit token deltas. It does nothing user-visible on its own. A working
demo needs three separable decisions:

| Axis | Question | Layer it lives in |
|---|---|---|
| **1. Runtime extraction** | How does the runtime pull tokens out of the ReAct loop? | `src/agents/runtime/react_agent.py` |
| **2. No-leak filter** | How do we prove no tool name / arg / output / SQL reaches the user? | runtime (same file) |
| **3. Transport** | How do bytes reach the browser? | `src/api/routes/query.py` (+ service generator) |

Axis 3 (transport) does **nothing** for axis 2 (leaks): FastAPI streaming just moves bytes;
it has no opinion about whether those bytes are the final answer or leaked LangGraph
internals ([focused.io](https://focused.io/lab/streaming-agent-state-with-langgraph),
[LangChain streaming docs](https://docs.langchain.com/oss/python/langgraph/streaming)). The
leak guard is a runtime concern, which is also what keeps it inside the layer-isolation law
(CLAUDE.md §2 — the API never sees agent internals).

---

## 2. Axis 1 — runtime extraction (`astream_events v3` vs `astream messages`)

### What the two mechanisms are

- **`astream_events(version="v3")` — typed projections (preferred for new apps).** LangChain
  now recommends event streaming for new applications because it gives *typed, per-channel
  projections* over a content-block protocol (`message-start` / `content-block-delta` /
  `message-finish`), instead of parsing an undifferentiated chunk firehose
  ([LangChain event streaming](https://docs.langchain.com/oss/python/langchain/event-streaming),
  [Vadim: typed projections](https://vadim.blog/langgraph-v3-event-streaming-typed-projections)).
  You consume only the text projection:

  ```python
  async for message in stream.messages:
      async for token in message.text:     # text deltas only; .reasoning / .tool_calls are separate projections
          ...
  ```

- **`astream(stream_mode="messages")` — 2-tuples (stable, lower-level).** Yields
  `(message_chunk, metadata)` tuples; you filter manually. Documented and stable, but the
  example in the docs is exactly *why* the filter matters: the `messages` stream includes the
  model's tool-call-decision chunks and the `tools` node output before the final text
  ([LangGraph streaming](https://docs.langchain.com/oss/python/langgraph/streaming)).

### The repo decision: try v3, measure, fall back

**Verified 2026-07-13 (`.venv`):** `langchain 1.3.1`; the compiled agent (`agent_factory()`)
exposes **all of** `astream`, `astream_events`, and `stream_events`. Calling
`astream_events(version="v3")` locally **emits a beta warning** on this version.

> **Rule for T0017.1:** Prefer `astream_events(version="v3")` typed message projections if
> they behave cleanly here; otherwise fall back to `astream(stream_mode="messages")` with the
> two-gate filter (§3). The v3-vs-fallback choice is an **implementation finding made in the
> ticket** (try it, judge the beta-warning noise/stability), not a guess baked into the design
> doc. In both cases, a test must **prove** no tool internals leak (§3).

`stream_events` is the sync sibling; our async FastAPI path uses **`astream_events`**.

### T0017.1 implementation finding (2026-07-13)

T0017.1 shipped the stable `agent.astream(..., stream_mode="messages")` path with the
two-gate filter from §3 instead of `astream_events(version="v3")`. Reason: this project is
pinned to `langchain 1.3.1`, where v3 event streaming was already live-checked as emitting a
beta warning, while the `messages` stream exposes the required `langgraph_node` metadata
directly and keeps the no-leak guarantee deterministic. The runtime filter emits only
non-empty string chunks from `metadata["langgraph_node"] == "model"` and drops any chunk with
`tool_call_chunks`.

Live probe status: blocked in the coder sandbox because `GROQ_API_KEY` was absent and local
Postgres on `127.0.0.1:5433` was closed. The deterministic runtime tests cover the leak
shape by simulating a model tool-call chunk, a tools-node SQL/raw-output chunk, and final
model answer chunks; a maintainer with credentials should still run the live REPL probe from
`docs/Manual_Verification_Guide.md` T0017.1.

---

## 3. Axis 2 — the no-leak filter (the load-bearing part)

### Grounded fact: our agent's graph nodes

**Verified 2026-07-13:** `agent_factory().get_graph()` has nodes
`['__start__', 'model', 'tools', '__end__']`. The final answer streams from the **`model`**
node. But the `model` node runs on **every** LLM turn — including the turn where the model
*decides to call a tool* — so a pure node filter is necessary but not sufficient.

### The repo-specific subtlety generic tutorials miss

`query_clean_jobs` makes a **second, nested LLM call** (`generate_sql`,
`src/agents/tools/query_clean_jobs.py`) *inside* the tool to turn the NL question into SQL.
That call **emits the raw SQL string as text**. Two consequences most streaming guides never
hit (they have no LLM-inside-a-tool):

1. A filter of "stream only text deltas" (the naive reading of v3's `.text` projection) is
   **not** a leak guard here — it would stream the generated SQL, violating the
   answer-only contract (`MVP_Technical_Design.md` §3) and the layer law.
2. The correct scope is the **outer agent's synthesis call only** — the graph `model` node.
   The nested `generate_sql` runs under the **`tools`** node, so scoping to `model` excludes
   it automatically.

### The two-gate filter (for the `astream messages` fallback)

```
Gate 1 (node):     metadata["langgraph_node"] == "model"     # excludes the `tools` node → excludes generate_sql's SQL
Gate 2 (content):  chunk.content is non-empty                 # excludes the tool-decision turn (empty content)
                   AND not chunk.tool_call_chunks             # belt-and-suspenders: never emit a streamed tool name/arg
```

- Gate 1 alone removes all `tools`-node output **and** the nested SQL text.
- Gate 2 removes the tool-*decision* turn in the `model` node, which streams an
  `AIMessageChunk` whose `content` is empty and whose `tool_call_chunks` are populated
  ([LangGraph docs](https://docs.langchain.com/oss/python/langgraph/streaming);
  [discussion #2189](https://github.com/langchain-ai/langgraph/discussions/2189)).

For the **v3** path the equivalent guard is: consume `.text` **only from the outer agent's
model messages**, and never subscribe to the `.tool_calls` projection or the nested tool
run's messages. The node-scoping requirement does not go away in v3 — it just moves from a
metadata check to choosing which message stream you iterate.

### Acceptance test (mandatory, either mechanism)

A test that drives a query which *does* call `query_clean_jobs` and asserts the streamed
output contains **none of**: the tool name, the substring `SELECT`, any column/`WHERE`
fragment, or the tool's raw returned string before synthesis. This is the proof the CLAUDE.md
boundary holds under streaming.

---

## 4. Axis 3 — transport (native FastAPI SSE)

### Grounded fact: we already have the native helper

**Verified 2026-07-13:** `fastapi 0.136.3`, `starlette 1.1.0`; `from fastapi.sse import
EventSourceResponse, ServerSentEvent` **imports successfully**; `sse-starlette` is **not**
installed. FastAPI ≥ 0.135.0 ships native SSE
([FastAPI SSE tutorial](https://fastapi.tiangolo.com/tutorial/server-sent-events/)).

`ServerSentEvent` signature (introspected): `data, raw_data, event, id, retry, comment`.

### Why SSE over the alternatives

- **SSE** is one-directional (server→client) and carries *typed* events — an exact fit for
  "stream tokens, then send metadata." Native `EventSourceResponse` **auto-sets**
  `X-Accel-Buffering: no` + `Cache-Control: no-cache` (the #1 production pitfall — reverse
  proxies otherwise batch SSE and kill the real-time feel), auto-sends 15 s keep-alive pings,
  and JSON-encodes `data`.
- **Plain chunked text** — rejected: no place for the `trace_url` metadata (§5).
- **WebSocket** — rejected: full-duplex is wasted; we never need client→server mid-stream.

> **Decision: use native `fastapi.sse.EventSourceResponse`. Add no new SSE dependency.**

### Endpoint shape (illustrative, not final)

```python
from fastapi.sse import EventSourceResponse, ServerSentEvent

@router.post("/agent/chat/stream", response_class=EventSourceResponse)
async def stream_agent(payload: QueryRequest, request: Request) -> AsyncIterable[ServerSentEvent]:
    # pre-stream checks still use real HTTP status (empty query -> 400; rate-limit -> 429)
    async for ev in generate_agent_stream(...):   # service-layer async generator
        yield ev
```

The service layer (`src/agents/service.py`) becomes an **async generator** that adapts the
runtime's filtered token stream into `ServerSentEvent`s, preserving the layer boundary (the
route still knows nothing about LangChain).

**Open fork (unchanged from T0017 stub):** whether this is a **new** route
(`/agent/chat/stream`) alongside the existing JSON `/agent/chat`, or replaces it. Keeping both
is the low-risk MVP choice (the JSON route stays for non-UI callers / tests); decide at
scoping.

---

## 5. The event contract (driven by metadata timing)

The three response fields arrive at **different times**, which is the whole reason a typed
event stream beats plain text:

| Field | Known when | Carried by |
|---|---|---|
| `session_id` | **before** the stream (generated in `service.py:23` if absent) | first `meta` event |
| answer text | **during** the stream | `token` events |
| `trace_id`, `trace_url` | **after** the run (Langfuse flush, `react_agent.py:33-39`) | final `done` event |

Event sequence (canonical vocabulary owned by `MVP_Technical_Design.md` §9.4):

```
event: session   data: {"session_id": "..."}                    # first, so the client can pin the conversation
event: token     data: {"text": "There "}                       # streamed, gate-filtered final answer only
event: token     data: {"text": "are 5 "}
...
event: metadata  data: {"trace_id": "...", "trace_url": "..."}  # once, after the token stream ends
event: error     data: {"message": "The demo is busy…"}         # in place of further tokens on mid-run failure (§6)
event: done      data: {}                                        # terminal, always closes the stream
```

A terminal event is **mandatory**: without one, an `EventSource` client treats the closed
stream as a dropped connection and **reconnects, re-running the agent** — a documented
production footgun and a real cost concern on the Groq free tier
([focused.io](https://focused.io/lab/streaming-agent-state-with-langgraph)). The demo UI
should read the raw stream via `fetch()` rather than the auto-reconnecting `EventSource`
object, *or* send an explicit terminal event and stop — preferably both.

---

## 6. Mid-stream error handling

Once the first byte ships, the HTTP status is **already 200** — the existing
`ProviderBusyError → 429 BUSY_MESSAGE` and generic-`500` mapping in `routes/query.py:48-65`
**cannot fire** for a failure that happens mid-answer. So:

- **Pre-stream failures** (empty query → `InvalidQueryError`/400; `slowapi` rate limit → 429)
  still return real HTTP status, because they run before the generator yields. Keep them.
- **Mid-stream failures** (Groq 429/timeout after tokens started, or an exception in the
  ReAct loop) must be caught inside the generator and emitted as a terminal
  **`event: error`** with the friendly `BUSY_MESSAGE`/generic text, then the stream closes
  cleanly. No internals leak; the UI renders it as an error bubble.

This means the friendly-message logic (`src/core/errors.py`) is reused, but the *delivery
mechanism* forks by when the error happens. Worth an explicit line in
`MVP_Technical_Design.md` §5.

---

## 7. Environment facts (all live-checked 2026-07-13, project `.venv`)

| Fact | Value | How checked |
|---|---|---|
| langchain | **1.3.1** | `import langchain; langchain.__version__` |
| agent streaming methods | `astream`, `astream_events`, `stream_events` all present | `hasattr(agent_factory(), …)` |
| `astream_events(version="v3")` | works, **emits beta warning** | local call |
| agent graph nodes | `['__start__', 'model', 'tools', '__end__']` | `agent_factory().get_graph().nodes` |
| final-answer node | **`model`** | same |
| fastapi | **0.136.3** | `import fastapi; fastapi.__version__` |
| native SSE | `fastapi.sse.EventSourceResponse` present | import succeeds |
| `sse-starlette` | **not installed** (not needed) | `import sse_starlette` → ModuleNotFoundError |
| `ServerSentEvent` fields | `data, raw_data, event, id, retry, comment` | `inspect.signature` |
| provider streaming flag | `agent.groq.streaming: False` (must flip to `True`) | `config/settings.yaml` |

---

## 8. What this means for T0017 sub-tickets

- **T0017.1 — runtime streaming + no-leak filter (axes 1 & 2).** Flip
  `agent.groq.streaming: True`; implement the runtime stream (v3-first, `astream` fallback
  decided here); the two-gate filter; the **leak-proof acceptance test** (§3). Highest-risk,
  most design-dense; do first.
- **T0017.2 — SSE endpoint + service generator (axes 3, 5, 6).** Native `EventSourceResponse`
  route; service-layer async generator; the `meta`/`token`/`done`/`error` event contract;
  mid-stream error path. Depends on T0017.1.
- **(later) — UI, session-IDs, disclaimer, readiness probe, topology** per the T0017 stub.
  Out of scope for this streaming research.

**Open implementation questions carried into the ticket:** (a) v3 vs `astream` fallback
(decide by measuring the beta-warning noise); (b) new `/agent/chat/stream` route vs. replacing
the JSON route (recommend: keep both for the MVP).

---

## 9. Sources

- LangChain — [Event Streaming](https://docs.langchain.com/oss/python/langchain/event-streaming) · [Streaming](https://docs.langchain.com/oss/python/langchain/streaming) · [LangGraph Streaming](https://docs.langchain.com/oss/python/langgraph/streaming)
- Vadim — [LangGraph v3 Event Streaming: Typed Projections](https://vadim.blog/langgraph-v3-event-streaming-typed-projections)
- FastAPI — [Server-Sent Events (SSE) tutorial](https://fastapi.tiangolo.com/tutorial/server-sent-events/)
- focused.io — [Streaming LangGraph Agents: production patterns](https://focused.io/lab/streaming-agent-state-with-langgraph)
- dev.to — [Streaming AI Agent with FastAPI & LangGraph (2025-26 Guide)](https://dev.to/kasi_viswanath/streaming-ai-agent-with-fastapi-langgraph-2025-26-guide-1nkn)
- GitHub — [langgraph#2189 tool-call arg chunks](https://github.com/langchain-ai/langgraph/discussions/2189) · [langgraph#4653 tool executes before chunks](https://github.com/langchain-ai/langgraph/issues/4653)
