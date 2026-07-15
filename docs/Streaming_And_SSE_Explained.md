# Streaming & SSE in InternHunterAgent — A Beginner's Walkthrough

This doc explains how the streaming chat endpoint works, from the browser all
the way down to the LLM. It assumes you've never used Server-Sent Events (SSE)
before, so it starts with the concept and then walks the actual code.

---

## 1. Why streaming at all?

The normal (non-streaming) endpoint `POST /api/v1/agent/chat` works like this:

1. You send a query.
2. The server calls the agent, waits for the **entire** answer to be produced.
3. It sends back one JSON blob.

If the answer takes 8 seconds to generate, the user stares at a spinner for 8
seconds and then the whole thing appears at once.

The streaming endpoint `POST /api/v1/agent/chat/stream` instead sends the answer
**as it is being generated**, token by token — the same "typing" effect you see
in ChatGPT. The user sees words appear almost immediately.

Same agent, same LLM. The only difference is *how the answer is delivered*.

---

## 2. What is SSE (Server-Sent Events)?

SSE is a simple, one-directional streaming protocol built on top of a plain HTTP
response. Instead of the server closing the connection after sending one body, it
**keeps the connection open** and pushes a series of small text messages over
time.

Key facts for a newcomer:

- **One direction only:** server → client. (For two-way, you'd use WebSockets.
  We don't need that — the client sends one query, then just listens.)
- **It's just text over HTTP.** No special library required on the server; you
  literally write specially-formatted text lines to the response body.
- **The `Content-Type` is `text/event-stream`.** That header is what tells the
  browser "this is a stream, keep reading."

### The wire format

Each event on the wire looks like this (note the **blank line** that terminates
each event):

```
event: token
data: {"text": "Hello "}

event: token
data: {"text": "world"}

event: done
data: {}

```

The rules:
- `event: <name>` — an optional label so the client can tell event kinds apart.
- `data: <payload>` — the actual content. We put JSON here.
- A blank line (`\n\n`) marks the **end** of one event.

That's the entire protocol. When you understand those three lines, you
understand SSE.

---

## 3. The event contract in this project

The stream always emits events in a fixed order. This is documented right in the
schema file so everyone agrees on it:

> `src/api/schemas.py`
> ```python
> # Streaming chat emits SSE events in this order: session {session_id}, token
> # {text} zero or more times, metadata {trace_id, trace_url}, then done {}.
> # On mid-run failure, error {message} replaces further token/metadata events
> # before done.
> ```

So a healthy stream looks like:

| Order | `event:` | `data:` payload | Meaning |
|-------|----------|-----------------|---------|
| 1 | `session` | `{"session_id": "..."}` | Here's the conversation id (so the client can continue the thread later). Sent **first**, before any LLM work. |
| 2..N | `token` | `{"text": "..."}` | A chunk of the answer. Zero or more of these. |
| N+1 | `metadata` | `{"trace_id": ..., "trace_url": ...}` | Langfuse trace info, known only *after* the run finishes. |
| Last | `done` | `{}` | The stream is complete; client can stop listening. |

And an unhealthy stream (something blew up mid-answer):

| `event:` | `data:` payload | Meaning |
|----------|-----------------|---------|
| `session` | `{"session_id": "..."}` | (still sent first) |
| `token` | `{"text": "..."}` | maybe a few partial tokens made it out |
| `error` | `{"message": "..."}` | a **safe** error message (never the raw exception) |
| `done` | `{}` | stream still closes cleanly |

The important design idea: **errors are delivered *inside* the stream, not as an
HTTP error code.** Once we've started streaming (status `200` already sent), we
can't change the status code. So a failure becomes an `error` event followed by a
normal `done`. The only thing that returns a real HTTP error is a bad request
*before* the stream starts (see the blank-query check below).

---

## 4. The four layers

The code keeps strict separation between layers (a hard rule in this project). A
token's journey crosses all four:

```
   ┌────────────────────────────────────────────────────────────────┐
   │  Browser / client                                               │
   │     └─ opens POST /api/v1/agent/chat/stream, reads the stream   │
   └───────────────▲────────────────────────────────────────────────┘
                   │  SSE text: "event: token\ndata: {...}\n\n"
   ┌───────────────┴────────────────────────────────────────────────┐
   │  1. API layer      src/api/routes/query.py                      │
   │     - validates the request                                     │
   │     - formats each dict into SSE wire text                      │
   │     - wraps it in EventSourceResponse                           │
   └───────────────▲────────────────────────────────────────────────┘
                   │  dicts: {"type": "token", "text": "..."}
   ┌───────────────┴────────────────────────────────────────────────┐
   │  2. Application service   src/agents/service.py                 │
   │     - adds session + done events                                │
   │     - reorders metadata to the end                              │
   │     - converts exceptions into safe error events                │
   └───────────────▲────────────────────────────────────────────────┘
                   │  dicts: {"type": "token"/"metadata", ...}
   ┌───────────────┴────────────────────────────────────────────────┐
   │  3. Agent runtime   src/agents/runtime/react_agent.py           │
   │     - drives LangGraph's astream(stream_mode="messages")        │
   │     - filters to just the model's text tokens                   │
   │     - emits a trailing metadata event (Langfuse trace)          │
   └───────────────▲────────────────────────────────────────────────┘
                   │  raw LangChain (chunk, metadata) pairs
   ┌───────────────┴────────────────────────────────────────────────┐
   │  4. LLM / LangGraph agent (the actual model)                    │
   └────────────────────────────────────────────────────────────────┘
```

Each layer only knows about the one directly below it. The API layer has no idea
there's an LLM; the runtime has no idea it's being served over SSE. That's the
"strict layer isolation" rule paying off — you could swap SSE for WebSockets by
changing only layer 1.

Notice each layer speaks in **plain Python dicts** (`{"type": "token", ...}`)
until the very last moment. Only the API layer turns those dicts into SSE text.
That's deliberate: the business logic stays testable and protocol-agnostic.

---

## 5. Walking the code, layer by layer

### Layer 3 — Agent runtime: where tokens are born

`src/agents/runtime/react_agent.py`, method `astream`:

```python
async for chunk, metadata in self.agent.astream(
    messages,
    config=config or None,
    stream_mode="messages",
):
    if metadata.get("langgraph_node") != "model":
        continue
    content = getattr(chunk, "content", None)
    tool_call_chunks = getattr(chunk, "tool_call_chunks", None)
    if not isinstance(content, str) or not content or tool_call_chunks:
        continue
    yield {"type": "token", "text": content}
```

What's happening:

- `self.agent` is a **LangGraph** ReAct agent. Calling `.astream(...,
  stream_mode="messages")` gives you an async stream of `(chunk, metadata)`
  pairs as the graph runs.
- A ReAct agent has multiple internal steps ("nodes"): it may call **tools**,
  think, then produce the final answer via the **model** node. We only want the
  words of the answer, so:
  - `metadata.get("langgraph_node") != "model"` → skip anything that isn't the
    model speaking (e.g. tool output).
  - `not content` → skip empty chunks.
  - `tool_call_chunks` → skip chunks that are the model *deciding to call a
    tool* (that's JSON machinery, not answer text).
- Whatever survives the filter is a genuine slice of the answer, emitted as
  `{"type": "token", "text": content}`.

After the loop finishes (the model is done talking), it fetches the Langfuse
**trace id / url** and emits one final event:

```python
yield {
    "type": "metadata",
    "trace_id": trace_id,
    "trace_url": trace_url,
}
```

The trace info only exists *after* the run, which is why metadata comes last from
this layer.

> Tracing stays localized here — the runtime owns the Langfuse handler, and no
> other layer touches it. That's the "tracing boundaries" rule.

### Layer 2 — Application service: shaping the event stream

`src/agents/service.py`, function `stream_agent_response`:

```python
async def stream_agent_response(query, runtime, session_id=None, user_id=None):
    session_id = session_id or str(uuid.uuid4())
    yield {"type": "session", "session_id": session_id}          # (a)

    saw_token = False
    metadata_event = {"type": "metadata", "trace_id": None, "trace_url": None}

    try:
        async for event in runtime.astream(...):                 # (b)
            if event["type"] == "metadata":
                metadata_event = event                           # (c) hold it back
                continue
            if event["type"] == "token":
                saw_token = True
            yield event

        if not saw_token:
            yield {"type": "token", "text": FALLBACK_ANSWER}     # (d)

        yield metadata_event                                     # (e) emit last
    except Exception as exc:
        classify_provider_busy_error(exc)
        yield {"type": "error", "message": BUSY_MESSAGE}         # (f) safe error
    yield {"type": "done"}                                       # (g) always
```

This layer does four jobs the runtime shouldn't care about:

- **(a)** Generate/echo the `session_id` and emit it **first**, so the client
  gets it immediately (before any slow LLM work).
- **(c)+(e)** The runtime emits metadata as soon as the model stops, but the
  contract says metadata must come **after** all tokens and just before `done`.
  So the service *captures* the metadata event, keeps streaming tokens, and only
  re-emits metadata at the end.
- **(d)** If the model produced **no** tokens at all (e.g. it refused or
  returned empty), the client would get an empty answer. The service substitutes
  a `FALLBACK_ANSWER` token so there's always something to show.
- **(f)** If anything throws mid-stream, it is **not** re-raised. Instead a
  single, generic `error` event with `BUSY_MESSAGE` is emitted. The raw
  exception (which could leak internal details — see the test that asserts
  `"database password leaked"` never appears in the body) is swallowed.
- **(g)** `done` is emitted **no matter what** — success or failure — so the
  client always knows the stream ended cleanly.

`classify_provider_busy_error(exc)` is called for its side effect of
logging/classifying, but the message sent to the user is always the neutral
`BUSY_MESSAGE`.

### Layer 1 — API route: turning dicts into SSE text

`src/api/routes/query.py`, function `stream_query_agent`:

```python
async def stream_query_agent(payload: QueryRequest, request: Request):
    if not payload.query or not payload.query.strip():
        raise HTTPException(status_code=400, detail="Query must not be empty.")   # (1)

    async def _event_source():
        async for event in stream_agent_response(                                 # (2)
            query=payload.query,
            session_id=payload.session_id,
            user_id=payload.user_id,
            runtime=request.app.state.runtime,
        ):
            event_type = event["type"]
            data = {key: value for key, value in event.items() if key != "type"}  # (3)
            yield _server_sent_event(event=event_type, data=data)                 # (4)

    return EventSourceResponse(                                                    # (5)
        _event_source(),
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

- **(1)** The **only** thing that returns a real HTTP error. A blank query is
  rejected *before* we start streaming, so we can still use a `400`. (Once the
  stream starts, it's too late — that's why every other failure becomes an
  in-band `error` event.)
- **(2)** It calls the service's async generator and loops over the dict events.
- **(3)** It splits each dict into the event name (`type`) and the rest (the
  data payload). E.g. `{"type": "token", "text": "hi"}` becomes name `"token"`
  and data `{"text": "hi"}`.
- **(4)+`_server_sent_event`** formats it into the SSE wire text:

  ```python
  def _server_sent_event(*, event, data):
      payload = ServerSentEvent(event=event, data=data)
      encoded_data = json.dumps(payload.data)
      return f"event: {payload.event}\ndata: {encoded_data}\n\n"
  ```

  This is where the `event: token\ndata: {...}\n\n` text from Section 2 is
  actually produced. The trailing `\n\n` is the mandatory blank-line terminator.
- **(5)** `EventSourceResponse` (from FastAPI) sets `Content-Type:
  text/event-stream` and streams each yielded string to the client as it's
  produced. The two headers matter for real deployments:
  - `Cache-Control: no-cache` — don't let a proxy/browser cache the stream.
  - `X-Accel-Buffering: no` — tells nginx **not** to buffer the response.
    Without it, nginx would collect tokens and release them in one lump,
    defeating the whole point of streaming.

### The wiring

At the top of the router, both routes are registered — note only the
non-streaming one declares a `response_model`, because the stream isn't a single
JSON object:

```python
router.post("/agent/chat", response_model=QueryResponse)(endpoint)
router.post("/agent/chat/stream")(stream_endpoint)
```

If rate limiting is configured, the same limiter decorator is applied to both.

---

## 6. Following one token end-to-end

Putting it together, here's the life of the word `"roles."` in the answer
"There are 3 roles.":

1. **LLM** generates the token; LangGraph surfaces it via `astream`.
2. **Runtime** (`react_agent.py`) sees it's from the `model` node with real text,
   yields `{"type": "token", "text": "roles."}`.
3. **Service** (`service.py`) sets `saw_token = True` and passes it straight
   through.
4. **Route** (`query.py`) reshapes it to name `"token"` + data `{"text":
   "roles."}`, then formats:
   ```
   event: token
   data: {"text": "roles."}

   ```
5. **`EventSourceResponse`** flushes that text down the open HTTP connection.
6. **Browser** receives the event, appends `"roles."` to what's on screen.

Multiply by every token and you get the live "typing" effect.

---

## 7. How the tests pin this down

`tests/api/test_stream.py` uses a **fake** `astream` (an async generator) so the
tests never touch a real LLM. They assert the exact contract:

- **`test_stream_route_returns_session_tokens_metadata_and_done`** — the happy
  path: verifies the event *order* is exactly
  `["session", "token", "token", "metadata", "done"]`, that the headers are set,
  and that `metadata` was moved to the end even though the runtime emitted it.
- **`test_stream_route_returns_fallback_before_metadata_when_no_tokens`** — when
  the runtime yields no tokens, the stream still contains one `token` event
  carrying `FALLBACK_ANSWER`.
- **`test_stream_route_returns_in_band_error_and_done_for_mid_run_failure`** —
  when the runtime raises mid-stream, the response is still `200`, the raw
  exception text (`"database password leaked"`) is **not** in the body, and the
  events end with `error` then `done`.
- **`test_stream_route_rejects_blank_query_before_stream_starts`** — a blank
  query returns a real `400` and the runtime is **never called**.

Reading these four tests is the fastest way to internalize the contract, because
each one encodes one rule from Section 3.

---

## 8. Quick mental model to remember

- **SSE = keep the HTTP response open and write `event:` / `data:` / blank-line
  text over time.**
- **Dicts everywhere, SSE text only at the very edge (the route).**
- **`session` first, `token`s in the middle, `metadata` then `done` last.**
- **Errors after streaming starts are events, not HTTP codes; `done` always
  fires.**
- **Each layer only talks to the one below it.**

---

## 9. Try it yourself

With the server running, you can watch the raw stream from a terminal. `curl -N`
disables curl's own buffering so you see events arrive live:

```bash
curl -N -X POST http://localhost:8000/api/v1/agent/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "list 3 data engineer jobs", "session_id": "demo-1"}'
```

You should see `event: session` appear immediately, then `event: token` lines
trickle in, then `event: metadata`, then `event: done`.

Run the tests for the contract:

```bash
python -m pytest tests/api/test_stream.py -v
```
```
