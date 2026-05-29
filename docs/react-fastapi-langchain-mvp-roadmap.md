# ReAct Agent MVP Roadmap with LangChain, FastAPI, and Self-Hosted Langfuse

## Goal

Build a runnable MVP backend for an agent project using:

- `FastAPI` for the API layer
- `LangChain` for the agent runtime
- `ReAct` as the agent pattern
- `Langfuse` self-hosted with Docker Compose for tracing

This MVP is intentionally narrow.

The first goal is **not** tool use, memory, retrieval, or multi-agent orchestration.
The first goal is to prove one clean request flow:

`request -> FastAPI -> agent service -> LangChain ReAct execution -> traced response`

## Recommended MVP Scope

### In Scope

- One FastAPI service
- One runnable request endpoint
- One basic ReAct-style agent flow
- One model provider integration
- Self-hosted Langfuse for tracing
- Basic config, logging, and error handling
- One happy-path integration test

### Out of Scope for Now

- External tools
- SQL execution
- Database-backed memory
- Retrieval / RAG
- Multi-agent routing
- Auth and user management
- Frontend UI
- Background jobs

Keeping these out of scope is important. If the first slice tries to prove everything at once, debugging becomes expensive and unclear.

## Big Picture Architecture

The first version should be a thin vertical slice with clear boundaries:

`FastAPI route -> request schema -> application service -> agent runtime -> model call -> response schema`

Recommended responsibilities:

- `API layer`
  Accept request, validate input, return structured response.
- `Application service`
  Own request lifecycle, generate request ID, invoke runtime, map errors.
- `Agent runtime`
  Build the ReAct agent, prepare prompt, execute LangChain flow.
- `Tracing layer`
  Attach Langfuse callback handler and request metadata.
- `Core layer`
  Settings, logging, IDs, shared exceptions.

The API should not know how the agent is built internally. This keeps the project easy to extend later.

## Suggested Project Layout

Suggested direction for the codebase:

```text
src/
  api/
    app.py
    routes/
    dependencies.py
  agents/
    service.py
    prompts.py
    runtime/
      factory.py
      react_agent.py
      tracing.py
      provider.py
  core/
    config.py
    logger.py
    ids.py
    errors.py
  schemas/
    chat.py
  config/
    settings.yaml
docs/
  react-fastapi-langchain-mvp-roadmap.md
docker-compose.yml
tests/
```

This keeps the first slice small while leaving room for future tools and richer orchestration.

## What You Should Do First

Build the MVP in this order:

1. Establish the backend entrypoint.
2. Make the FastAPI app boot locally.
3. Add a health endpoint.
4. Define the request and response schemas.
5. Add an application service that accepts a message and returns an answer.
6. Wire a minimal LangChain ReAct flow behind that service.
7. Stand up self-hosted Langfuse with Docker Compose.
8. Attach tracing to the LangChain execution path.
9. Add one happy-path integration test.
10. Add failure handling for invalid input and provider errors.

The most important idea is sequencing:

- First prove the app runs.
- Then prove the agent runs.
- Then prove traces appear.
- Only then expand scope.

## Milestone Roadmap

## Milestone 0: Foundation

Objective: create a stable local development base.

Deliverables:

- `pyproject.toml` updated with the minimum runtime dependencies
- Config loading for app environment and secrets
- Logging setup
- FastAPI app bootstrap
- `GET /health` endpoint
- Local run instructions in docs

Suggested dependency set for the MVP:

- `fastapi`
- `uvicorn`
- `langchain`
- `langchain-openai` or your chosen provider package
- `langfuse`
- `pydantic`
- `structlog`
- `pytest`
- `httpx`

Success criteria:

- App starts with one local command
- Health endpoint responds successfully

## Milestone 1: Runnable Request Flow

Objective: prove one end-to-end request path without tools.

Recommended endpoint:

- `POST /api/v1/agent/chat`

Suggested request schema:

```json
{
  "message": "Summarize how you can help me",
  "session_id": "optional-session-id",
  "user_id": "optional-user-id"
}
```

Suggested response schema:

```json
{
  "request_id": "generated-request-id",
  "session_id": "optional-session-id",
  "answer": "agent response",
  "trace_id": "optional-trace-id",
  "trace_url": "optional-trace-url"
}
```

Implementation guidance:

- Keep the route thin.
- Put orchestration into an application service.
- Keep the first runtime simple and deterministic.
- Use one model provider only.
- Do not introduce tools yet, even placeholder ones.

Success criteria:

- A POST request returns a valid structured response
- The request path works repeatedly in local development

## Milestone 2: ReAct Agent Runtime

Objective: add a ReAct-style agent structure behind the request flow.

Even without tools, this step is useful because it establishes the agent runtime shape you will build on later.

What to implement:

- Agent factory function
- Prompt template for system and user messages
- ReAct-oriented execution wrapper
- Provider abstraction only as far as needed for one model

Important note:

If true tool calling is not in scope yet, keep the runtime "ReAct-shaped" rather than over-engineering around future tool execution. The point is to preserve the mental model and code boundaries without adding unnecessary moving parts.

Success criteria:

- The agent execution lives outside the route layer
- Prompting and provider configuration are easy to inspect and change

## Milestone 3: Self-Hosted Langfuse

Objective: make tracing part of the MVP baseline.

Use Docker Compose to run Langfuse locally or in a low-scale environment. Based on current Langfuse documentation, a self-hosted stack typically includes:

- Langfuse web
- Langfuse worker
- Postgres
- ClickHouse
- Redis or Valkey
- Object storage or compatible blob storage

Important operational note:

Langfuse documents that core infrastructure components should run in `UTC` to avoid incorrect query behavior.

Recommended outputs for this milestone:

- `docker-compose.yml` for the local observability stack
- `.env.example` entries for Langfuse host and API keys
- Basic startup instructions in docs

Success criteria:

- Langfuse UI is reachable locally
- API keys can be created and used by the app

## Milestone 4: Tracing Integration

Objective: capture every agent request in Langfuse.

Use the Langfuse LangChain integration via callback handlers for the LangChain execution path. Wrap this with a small local tracing helper so the rest of the app does not depend directly on callback wiring details.

Recommended trace metadata:

- `request_id`
- `session_id`
- `user_id`
- route name
- environment
- model name

Recommended behavior:

- Tracing failures should not crash the request path in local development.
- The application should log tracing issues clearly.
- If possible, return trace metadata in the API response for easier debugging.

Success criteria:

- Each successful request creates a visible trace
- The trace is easy to map back to an API request

## Milestone 5: Hardening

Objective: make the MVP predictable and developer-friendly.

Add:

- Structured error handling
- Timeouts
- Invalid configuration detection
- Consistent error response shape
- Basic request logging
- One integration test for success
- One integration test for failure

Suggested failure cases:

- Missing model credentials
- Invalid request body
- Model provider timeout or exception
- Langfuse unavailable

Success criteria:

- Local failures are understandable
- The app degrades cleanly when tracing fails

## Milestone 6: First Real SQL Tool

Objective: add one safe production tool over `clean_jobs` so the agent can answer real job-data questions while keeping the public API response simple.

What to implement:

- one SQL tool exposed through the agent runtime
- schema/context builder for `clean_jobs`
- SQL generation prompt for the tool path
- strict read-only SQL validation
- validated execution against the database
- table shaping for internal tool/debug use
- refusal path for unsafe or unsupported SQL

Behavior rule:

- if the user asks about jobs, counts, salaries, locations, titles, companies, filters, or trends that depend on `clean_jobs`, the agent must use the SQL tool

Success criteria:

- the agent can answer one real `clean_jobs` question end-to-end
- unsafe SQL is rejected before execution
- the public response includes a natural-language answer
- tool output remains structured internally for tracing and future UX expansion
- the SQL path is traceable in Langfuse
- at least one success-path and one refusal/failure-path test exist

Important note:

This milestone should come before memory. A useful InternHunter MVP is defined first by trustworthy job-data answers, then by conversational refinement.

Response note:

For the first shipped MVP, prefer an answer-only public API response. Keep table-shaped results internal to the SQL tool and tracing path so the product can ship faster without committing to early output-format complexity.

## Milestone 7: Native Short-Term Memory

Objective: add lightweight multi-turn memory using LangChain/LangGraph's native checkpointer-based thread memory.

What to implement:

- native short-term memory through a shared checkpointer
- `InMemorySaver` for MVP
- `session_id` mapped to `thread_id`
- memory automatically read and updated by the runtime on each invocation

Constraints:

- memory is session-scoped only
- memory is in-process only for MVP
- memory resets on app restart
- no long-term or cross-session recall
- no custom manual transcript store in the service layer

Success criteria:

- follow-up questions work inside the same `session_id`
- separate sessions stay isolated
- the app still works when `session_id` is missing
- memory implementation remains invisible to the route layer

Memory note:

Use native checkpointer-based short-term memory before building any custom memory layer. If context growth later hurts latency or model quality, the next optimization should be message trimming, not long-term memory.

## First Implementation Plan

If you want the shortest path to a working MVP, use this order:

1. Create `src/api/app.py` and boot FastAPI.
2. Add `GET /health`.
3. Define `ChatRequest` and `ChatResponse` Pydantic models.
4. Create `AgentService` that returns a hardcoded answer first.
5. Replace the hardcoded answer with a LangChain model call.
6. Refactor that model call into a ReAct-style runtime module.
7. Add Docker Compose for Langfuse.
8. Add Langfuse environment settings and callback wiring.
9. Return `trace_id` or `trace_url` when available.
10. Add smoke and integration tests.

This order matters because it lets you isolate failures quickly:

- If step 3 fails, it is an API issue.
- If step 5 fails, it is a model/provider issue.
- If step 8 fails, it is a tracing issue.

## Guardrails

To keep the MVP healthy, follow these rules:

- Do not add real tools before the request flow and tracing are stable.
- Do not add memory before the base API contract is settled.
- Do not add multiple providers before one provider works well.
- Do not let FastAPI routes own LangChain logic directly.
- Do not let tracing concerns leak across the whole codebase.

## MVP Definition of Done

The MVP is complete when all of the following are true:

- FastAPI boots locally
- `GET /health` works
- `POST /api/v1/agent/chat` returns a valid structured response
- The request path uses a LangChain-based ReAct-style runtime
- Self-hosted Langfuse runs through Docker Compose
- Requests appear in Langfuse as traces
- One happy-path integration test passes
- One failure-path test passes

## What Comes After This MVP

Once this is stable, the next logical expansions are:

1. Add prompt versioning
2. Add evaluation and feedback capture
3. Add auth and rate limiting
4. Add deployment environments
5. Add additional production tools only when product value is clear
6. Consider persistent or long-term memory only after session memory proves necessary

At that point, the existing request flow and tracing setup will give you a reliable base instead of forcing a rewrite.

## Shippable MVP

The MVP should be considered shippable when all of the following are true:

- FastAPI boots locally and through Docker
- `GET /health` works
- the ReAct-style runtime is stable
- Langfuse tracing works for the request path
- hardening is complete enough that config and runtime failures are understandable
- one safe SQL tool over `clean_jobs` works end-to-end
- the agent returns a trustworthy natural-language answer grounded in SQL tool results
- short-term memory works through native checkpointer-based thread memory
- follow-up questions work within the same `session_id`

The MVP does not require:

- long-term memory
- persistent memory storage
- RAG
- multiple production tools
- multi-agent routing
- autonomous workflows

Product test for the shipped MVP:

Can a user ask about jobs, refine the question naturally, and get a trustworthy result with visible evidence?

## Notes For This Repo

Given the current repository state, this roadmap is the safest direction:

- The codebase appears early-stage
- Existing docs are minimal
- Dependencies are still very light
- Agent-related structure already exists, but the MVP should avoid overcommitting to unfinished tool flows

That makes a thin runnable request slice the right first target.

## References

- Langfuse self-hosting overview: https://langfuse.com/self-hosting
- Langfuse LangChain tracing docs: https://langfuse.com/docs/integrations/langchain
