# Milestone 2 Coding Plan: ReAct Agent Runtime

> For milestone 2 of [react-fastapi-langchain-mvp-roadmap.md](./react-fastapi-langchain-mvp-roadmap.md)

## Goal

Finish milestone 2 by turning the current request flow into a real `ReAct`-style agent runtime that:

- lives outside the FastAPI route layer
- uses `LangChain`
- uses `ChatGroq` as the single model provider
- has one simple tool: `get_current_time`
- keeps the architecture small and teachable
- avoids design choices that will hurt future `P95` latency

This document is guidance, not implementation code. It tells you what to build, where it should go, and why.

---

## 1. What milestone 2 should mean in this repo

Milestone 2 is complete when all of these are true:

- the route no longer fakes the response
- the service layer calls a real runtime object
- the runtime constructs and invokes a ReAct agent
- the agent has exactly one tool: `get_current_time`
- prompts and provider settings are easy to inspect and change
- the app still feels small and understandable

This is the right scope because it gives you a true vertical slice of agent behavior without dragging in SQL, Langfuse wiring, or a large tool surface too early.

---

## 2. Architecture choice you should make

### Recommended architecture

Use this shape:

`FastAPI route -> API schema -> agent service -> runtime wrapper -> LangChain ReAct agent -> ChatGroq + tools`

### Why this is the right choice

This is the smallest architecture that keeps responsibilities clean:

- `api/` owns HTTP only
- `agents/service.py` owns orchestration for one request
- `agents/runtime/` owns LangChain, prompts, and model behavior
- `agents/tools/` owns tool functions only
- `config/` owns YAML-backed settings and prompts

This fits the repo guidance in `AGENTS.md` and protects you from the most common beginner mistake: letting the FastAPI route become the agent runtime.

### What not to do

Do not:

- construct the LangChain agent directly inside `src/api/routes/query.py`
- let tools live in the route file
- pass raw FastAPI request models deep into the runtime
- create a large abstraction layer for multiple providers before you need it
- add tracing into the runtime control flow yet

---

## 3. ReAct choice: what you should use and why

### Recommendation

For this milestone, use LangChain’s `create_react_agent` pattern with `AgentExecutor`.

### Why

You explicitly want a ReAct agent, and this is the clearest way to learn the mental model:

- prompt contains tool instructions
- agent reasons about whether it needs a tool
- tool runs
- final answer returns through one runtime boundary

### Tradeoff

Classic ReAct is not the lowest-latency style. It often takes more tokens and may require multiple reasoning/tool steps.

That is acceptable for milestone 2 because:

- you only have one simple tool
- the goal is learning and boundary design
- the system is still small enough to refactor later

### Important P95 note

If your long-term priority is tight `P95`, a classic ReAct loop will probably not be your final production form.

A likely future path is:

1. keep ReAct for learning and MVP behavior
2. cap iterations aggressively
3. later replace simple tools with deterministic fast paths or model-native tool calling where appropriate

For now, use ReAct because it teaches the right boundaries.

---

## 4. Async and latency: what matters and what does not

### What async helps

`async` helps server concurrency. It allows your FastAPI app to keep handling other work while waiting on the model or tool I/O.

### What async does not help

`async` does not magically make a single LLM request faster.

If one request spends 900 ms inside the model, `async` does not reduce that model time. It improves throughput and headroom, not raw model latency.

### What actually matters for P95 here

For this milestone, your biggest `P95` wins will come from:

- not rebuilding the agent on every request
- not doing extra model calls
- keeping tool descriptions short
- keeping the prompt short and stable
- capping agent iterations
- using one fast model configuration
- avoiding unnecessary streaming complexity

### Streaming recommendation

Do **not** make this first JSON API streaming yet.

Why:

- streaming helps perceived latency more than backend `P95`
- it complicates the API contract
- it adds one more moving part while you are still stabilizing runtime boundaries

For milestone 2, use `ainvoke`, not `astream`.

---

## 5. File map: what to create and what to change

## Create

- `src/agents/models.py`
  Internal agent input/output models or DTOs
- `src/agents/tools/current_time.py`
  One simple tool: `get_current_time`
- `src/agents/prompts.py`
  Small helper to load and validate the ReAct prompt from YAML
- `tests/agents/tools/test_current_time.py`
  Unit tests for the tool
- `tests/agents/runtime/test_react_agent.py`
  Runtime-level tests with model calls mocked
- `tests/api/test_query.py`
  API test that proves the route uses the real service/runtime path

## Modify

- `src/agents/runtime/provider.py`
  Build `ChatGroq` correctly and validate config
- `src/agents/runtime/factory.py`
  Construct the ReAct agent and attach tools
- `src/agents/runtime/react_agent.py`
  Wrap async invocation cleanly
- `src/agents/service.py`
  Become the application entrypoint for agent execution
- `src/api/routes/query.py`
  Call the service and return structured output
- `src/core/config.py`
  Make prompt/settings access predictable enough for this milestone
- `config/settings.yaml`
  Add or confirm provider/runtime knobs
- `config/prompts.yaml`
  Store the ReAct system prompt/template
- `pyproject.toml`
  Ensure required LangChain/Groq dependencies are present

## Optional cleanup

- `src/agents/tracing/`
  Leave this alone for now unless it blocks imports
- `__pycache__/`
  Ensure it is ignored, not committed

---

## 6. The implementation plan, step by step

## Step 1: Freeze the target runtime contract

Before changing files, decide on the minimal runtime contract:

- service input: `query`, `session_id`, `user_id`
- service output: `answer`, optional `session_id`, optional future trace fields
- runtime input: user query string
- runtime output: final answer string

### Why

You need a stable seam between FastAPI and the runtime. If you skip this and let route/request models flow everywhere, every later change becomes harder.

### What to do

- keep API Pydantic schemas in `src/api/schemas.py`
- create small internal models in `src/agents/models.py`, or at minimum define clear primitive arguments for the service

### Recommendation

Use small internal models. It is a good habit and still lightweight.

---

## Step 2: Create the one simple tool

Create `src/agents/tools/current_time.py`.

### What it should do

- define exactly one tool called `get_current_time`
- return a human-readable current time string
- support a simple timezone parameter only if you really want it

### Recommendation

Start with the smallest useful version:

- no external API calls
- default to `UTC`
- simple output string

### Why

This tool should teach the runtime pattern, not distract you with edge cases.

### Good design tip

Keep tool docstrings short and precise. In ReAct, tool descriptions become part of the prompt budget. That affects cost and latency.

---

## Step 3: Move prompt ownership out of the runtime code

Right now `config/prompts.yaml` is effectively empty.

You should make prompt loading explicit by adding `src/agents/prompts.py`.

### What `src/agents/prompts.py` should own

- loading the ReAct prompt text from `settings.prompts_yaml`
- validating that the needed prompt key exists
- returning the prompt template in a form the runtime can use

### Why

This keeps your runtime code focused on execution, not file parsing.

### Prompt design guidance

Keep the ReAct prompt:

- short
- tool-aware
- explicit about when to use `get_current_time`
- explicit about when not to use the tool

### P95 tip

Prompt length directly affects latency. Do not write a giant “super assistant” prompt here. A shorter, sharper prompt is usually both faster and more reliable for this stage.

---

## Step 4: Fix and simplify the provider layer

Your current `src/agents/runtime/provider.py` is close, but it should become a clean model builder only.

### What this file should own

- read provider name from settings
- validate only supported providers
- build one `ChatGroq` instance

### What this file should not own

- prompts
- tools
- runtime invocation
- request/session data

### Recommended `ChatGroq` settings for milestone 2

- `model`
- `temperature`
- `max_tokens`
- `timeout`
- `max_retries`
- `streaming`

### Recommendation

Keep:

- `temperature` low
- `streaming: false`
- `max_retries` low
- `timeout` explicit

### Why

These settings protect consistency and latency.

### P95 tip

Avoid large `max_tokens` defaults unless you need them. Overly generous token budgets can hurt both tail latency and cost.

---

## Step 5: Build the ReAct agent in one place

Use `src/agents/runtime/factory.py` as the construction point for:

- model
- prompt
- tools
- `create_react_agent`
- `AgentExecutor`

### Why this file should exist

This is your composition root for the runtime. It lets you see the entire agent assembly in one place.

### What to put here

- instantiate the provider
- get the model
- load the prompt
- import `get_current_time`
- build the ReAct agent
- wrap it with `AgentExecutor`

### Recommended runtime guardrails

Set:

- low `max_iterations`
- parsing error handling
- non-verbose mode by default

### Why

For one simple tool, you do not want the agent to bounce through many loops. That is bad for `P95`, cost, and debugging clarity.

### Strong recommendation

Cap `max_iterations` at `2` or `3`.

That is one of the most important latency controls in this milestone.

---

## Step 6: Turn `react_agent.py` into a real async runtime wrapper

Your current `src/agents/runtime/react_agent.py` should become a thin wrapper around the agent executor.

### What it should own

- receiving runtime input
- calling `await executor.ainvoke(...)`
- extracting the final answer safely
- returning a clean runtime result

### What it should not own

- provider construction logic
- tool definitions
- HTTP response shaping

### Why

This file should be the runtime boundary, not a second composition root.

### Async guidance

Use async invocation all the way through:

- route stays async
- service stays async
- runtime stays async
- model invocation uses `ainvoke`

### P95 tip

Avoid creating the executor inside every request. Construct it once and reuse it.

That is one of the simplest and highest-value optimizations you can make.

---

## Step 7: Make `service.py` the application entrypoint

`src/agents/service.py` should stop being a stub and become the single place the route calls.

### What it should do

- accept `query`, `session_id`, `user_id`
- call the runtime
- return a clean application result

### Why

The service layer is where later additions belong:

- request IDs
- tracing metadata
- guardrails
- SQL tools
- retries and fallback behavior

You want that seam in place now.

### Recommendation

Keep this file small. One public function is enough for milestone 2.

---

## Step 8: Keep the route thin

Update `src/api/routes/query.py` so it:

- validates HTTP input
- calls the service
- maps service output into `QueryResponse`
- handles exceptions consistently

### Why

This keeps `api/` as a transport boundary only, which matches `AGENTS.md`.

### Important design rule

The route should not know:

- what model you use
- what tools exist
- how ReAct works
- how prompts are loaded

If the route knows those things, the boundary is already leaking.

---

## Step 9: Add the prompt and config data

Update `config/prompts.yaml`.

### What to add

Add a dedicated prompt section for the milestone 2 ReAct agent.

It should describe:

- who the assistant is
- when to use `get_current_time`
- that it should answer directly when no tool is needed
- that it should keep answers concise

Update `config/settings.yaml` only with settings this milestone truly needs.

### Why

YAML-backed prompts are already part of the intended project design, so now is the right time to start using them for real.

### P95 tip

Treat prompt size like a budget. The more tokens you burn in your system prompt and tool descriptions, the worse your tail latency gets.

---

## Step 10: Test the three important layers

Do not jump straight to manual testing only.

Add three focused test levels:

### Tool test

In `tests/agents/tools/test_current_time.py`:

- verify the tool returns a non-empty string
- verify bad input handling if you support a timezone argument

### Runtime test

In `tests/agents/runtime/test_react_agent.py`:

- mock the executor or model
- verify the runtime calls async invocation correctly
- verify it extracts the answer correctly

### API test

In `tests/api/test_query.py`:

- hit the query endpoint
- verify the route returns a valid `QueryResponse`
- verify the service/runtime path is exercised through mocking

### Why

This gives you confidence in boundaries, not just in one happy manual request.

---

## 7. Recommended architecture details

## DTOs or not?

### Recommendation

Use small internal models in `src/agents/models.py`.

### Why

This is the sweet spot:

- better boundary than passing FastAPI models around
- much lighter than full enterprise layering
- easier to extend when trace IDs and tool artifacts arrive later

### What they should represent

- runtime input
- runtime result

Keep them tiny.

## Singleton runtime or per-request runtime?

### Recommendation

Reuse a single runtime object, or at least a single model/executor instance, instead of building it for every request.

### Why

Per-request construction adds avoidable overhead and hurts `P95`.

### Smallest safe approach

Create the runtime once at module load or through a simple dependency helper.

## Classic ReAct vs simpler tool-calling

### Recommendation

For this milestone, use classic ReAct because that is what you want to learn.

### But know this tradeoff

If your long-term priority is strict `P95`, you may later prefer:

- direct fast paths for deterministic tools
- model-native tool calling
- very small custom routing logic for simple decisions

That is a future optimization, not a milestone 2 blocker.

---

## 8. P95 guidance you should internalize now

These are the choices that matter most for future tail latency:

### Keep the runtime warm

Do not rebuild:

- prompts
- tools
- model clients
- agent executors

on every request unless you have a very specific reason.

### Cap the loop

ReAct can drift into multiple thought/action steps. Put a hard ceiling on iterations early.

### Keep tools cheap

Your first tool should be local and deterministic.

That is exactly why `get_current_time` is a good learning tool.

### Keep prompts short

Long prompts quietly destroy `P95`.

### Keep the answer short

Shorter completions generally improve latency. Set expectations in the prompt.

### Avoid streaming for now

Streaming is not your first optimization target for backend `P95`.

### Measure later, guess less

Once milestone 2 is done, record:

- total request time
- model time
- tool time
- number of agent iterations

That will tell you where the real latency lives.

---

## 9. Suggested order of work

Follow this order:

1. Clean up provider construction
2. Create `get_current_time`
3. Add prompt loading
4. Build the ReAct factory
5. Build the async runtime wrapper
6. Replace the stub service with real runtime invocation
7. Keep the route thin
8. Add focused tests
9. Run manual API verification

This order is important because it isolates failures:

- provider failures stay in the provider layer
- prompt failures stay in the prompt layer
- tool failures stay in the tool layer
- route failures stay in the API layer

---

## 10. Definition of done for your version of milestone 2

You can mark milestone 2 done when:

- `POST /api/v1/agent/query` uses the real runtime path
- the runtime invokes a LangChain ReAct agent
- the agent can call `get_current_time`
- prompts come from `config/prompts.yaml`
- Groq settings come from `config/settings.yaml`
- there is at least one tool test, one runtime test, and one API test
- the runtime is async
- the runtime is not rebuilt on every request
- the design still feels small and understandable

---

## 11. Final recommendation from a senior-engineering perspective

If I were guiding a junior engineer on this repo, I would say:

- keep the architecture small
- use a real ReAct loop now because it teaches the right boundary design
- only add one deterministic tool
- avoid streaming for now
- optimize `P95` first by reducing work, not by adding clever concurrency

The best next step is not to add more features. It is to make one request path real, clean, and measurable.
