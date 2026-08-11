# Streaming Implementation Plan: Decision Record (archived)

> Archived 2026-08-11. M17 shipped. Outcome owned by
> `docs/MVP_Technical_Design.md` section 9 and D-005 through D-009.
> Preserved for the reasoning and rejected alternatives; not implementation guidance.

## Decisions taken

- D-005: Mid-stream failures are in-band error events.
- D-006: The stream has typed terminal events.
- D-007: Streaming uses FastAPI's native SSE response.
- D-008: Streaming uses a two-gate filter to prevent internal token leakage.
- D-009: Stream extraction tries event v3 and keeps a message fallback.

## 2. Axis 1 - runtime extraction (`astream_events v3` vs `astream messages`)

### The repo decision: try v3, measure, fall back

**Verified 2026-07-13 (`.venv`):** `langchain 1.3.1`; the compiled agent (`agent_factory()`)
exposes **all of** `astream`, `astream_events`, and `stream_events`.
Calling `astream_events(version="v3")` locally **emits a beta warning** on this version.

> **Rule for T0017.1:** Prefer `astream_events(version="v3")` typed message projections if
> they behave cleanly here; otherwise fall back to `astream(stream_mode="messages")` with the
> two-gate filter (section 3).

`stream_events` is the sync sibling; the async FastAPI path uses **`astream_events`**.
The v3-vs-fallback choice is an implementation finding made in the ticket, not a guess baked into
the design document.
In both cases, a test must prove no tool internals leak.

### T0017.1 implementation finding (2026-07-13)

T0017.1 shipped the stable `agent.astream(..., stream_mode="messages")` path with the
two-gate filter from section 3 instead of `astream_events(version="v3")`.
The runtime filter emits only non-empty string chunks from
`metadata["langgraph_node"] == "model"` and drops any chunk with `tool_call_chunks`.

## 3. Axis 2 - the no-leak filter (the load-bearing part)

### Grounded fact: our agent's graph nodes

**Verified 2026-07-13:** `agent_factory().get_graph()` has nodes
`['__start__', 'model', 'tools', '__end__']`.
The final answer streams from the **`model`** node.

The `model` node runs on every LLM turn, including the turn where the model decides to call a
tool, so a pure node filter is necessary but not sufficient.
`query_clean_jobs` makes a second nested LLM call inside the tool to turn the natural-language
question into SQL.
That call emits raw SQL as text, so a generic "stream only text deltas" rule would leak it.

### The two-gate filter (for the `astream messages` fallback)

```
Gate 1 (node):     metadata["langgraph_node"] == "model"
Gate 2 (content):  chunk.content is non-empty
                   AND not chunk.tool_call_chunks
```

- Gate 1 alone removes all `tools`-node output **and** the nested SQL text.
- Gate 2 removes the tool-decision turn in the `model` node, which streams an
  `AIMessageChunk` whose `content` is empty and whose `tool_call_chunks` are populated.

### Acceptance test (mandatory, either mechanism)

A test drives a query that calls `query_clean_jobs` and asserts the streamed output contains none
of the tool name, the substring `SELECT`, any column or `WHERE` fragment, or the tool's raw
returned string before synthesis.
This is the proof that the answer-only boundary holds under streaming.

## 4. Axis 3 - transport (native FastAPI SSE)

### Why SSE over the alternatives

- **SSE** is one-directional (server to client) and carries *typed* events - an exact fit for
  "stream tokens, then send metadata."
- **Plain chunked text** - rejected: no place for the `trace_url` metadata (section 5).
- **WebSocket** - rejected: full-duplex is wasted; we never need client to server mid-stream.

Native SSE sets anti-buffering headers, sends keep-alive pings, and JSON-encodes data.
Those transport details are why a separate SSE dependency was unnecessary.

> **Decision: use native `fastapi.sse.EventSourceResponse`. Add no new SSE dependency.**

The service layer becomes an async generator that adapts the runtime's filtered token stream into
`ServerSentEvent` values, preserving the layer boundary.
The route still knows nothing about LangChain.

The JSON endpoint remains available for non-UI callers and tests.
The streaming route is a sibling rather than a replacement, which keeps the MVP change low risk.

## 5. The event contract (driven by metadata timing)

The three response fields arrive at **different times**, which is the whole reason a typed
event stream beats plain text.

```
event: session   data: {"session_id": "..."}
event: token     data: {"text": "There "}
event: metadata  data: {"trace_id": "...", "trace_url": "..."}
event: error     data: {"message": "The demo is busy..."}
event: done      data: {}
```

A terminal event is **mandatory**: without one, an `EventSource` client treats the closed
stream as a dropped connection and **reconnects, re-running the agent**.

The `session_id` is known before the stream, answer text during the stream, and trace metadata
after the Langfuse flush.
That timing is why the event contract has distinct `session`, `token`, `metadata`, `error`, and
`done` events.

## 6. Mid-stream error handling

Once the first byte ships, the HTTP status is **already 200**.

- **Pre-stream failures** still return real HTTP status, because they run before the generator
  yields.
- **Mid-stream failures** must be caught inside the generator and emitted as a terminal
  **`event: error`** with the friendly `BUSY_MESSAGE`/generic text, then the stream closes
  cleanly. No internals leak; the UI renders it as an error bubble.

The friendly-message logic is reused, but delivery changes according to when the error occurs.
This keeps pre-stream API errors as normal HTTP responses while making post-start failures
visible to the browser.

The UI treats a terminal error as a friendly bubble and never exposes provider, SQL, tool, or
internal exception details.

The error event is followed by clean stream termination.
No retry or reconnect behavior is performed by the browser because a retry would repeat an
agent run and consume the serving quota.

The event stream uses browser-standard SSE framing while the fetch request provides the required
POST body.
This combines the server-to-client event semantics with the existing request validation contract.

## Sources

- LangChain and LangGraph streaming documentation, live-checked on 2026-07-13.
- FastAPI SSE documentation, live-checked on 2026-07-13.
- `docs/MVP_Technical_Design.md` section 9 owns the current streaming implementation.

## Live-checked facts

- `langchain 1.3.1` was installed in the project environment.
- `fastapi.sse.EventSourceResponse` and `ServerSentEvent` imported successfully.
- `sse-starlette` was not installed and was not required.
- The compiled graph had `model` and `tools` nodes with the final answer emitted by `model`.

The runtime filter is transport-agnostic.
SSE serialization happens after the answer-only event has left the runtime.
The browser consumes only public terminal and token events.

The protocol remains one-directional.
No browser message is accepted after the initial POST request.
The server emits only the established terminal and token events.
