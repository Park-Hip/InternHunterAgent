# Configuration and stack

> **Eviction:** A parameter or dependency entry leaves when the code that reads it is retired.

This document owns the settings contract, required environment, technology choices, and the
dependency list.
Operational procedures live in [how-to/operate.md](../how-to/operate.md); architecture explanation in
[architecture.md](../architecture.md).

## 5. Data and configuration

The agent reads the normalized `clean_jobs` table through a single-table allowlist.
Its frozen agent-visible columns are owned by [schema reference](schema.md).

Source creation dates are preserved, posting dates are never invented, and listing expiry comes from
the truthful source expiry field.
The lifecycle column exists in the data layer but is not exposed to the agent until behavior
evidence supports an honest presentation.

Alembic owns schema changes.
The application database owns domain data and persisted checkpoint state, while Langfuse Cloud owns
traces and project metadata.
Those stores have separate owners, lifecycles, and schemas, and no overlap.

**Required environment.**
The database URL and the agent-read database URL are required at boot.
The Langfuse keys are optional and enable tracing plus native prompt trace links when present.
Without them, the service serves its reviewed release-pinned prompt text unlinked and disables tracing.
The provider key for every deployment a served profile selects is required at boot: the serving lifespan refuses to start when it is unset or empty, naming the variable.
Declared but unselected deployments stay optional, so a checkout runs with only the selected provider's key.

The agent-facing SQL-read path uses `AGENT_DATABASE_URL`, a dedicated least-privilege credential
backed by a separate PostgreSQL role with `SELECT` only on `clean_jobs`. The writer paths
(ingestion, Alembic, LangGraph checkpoint persistence) continue using `DATABASE_URL`.
`AGENT_DATABASE_URL` is required at boot; absence fails closed and must never silently fall back
to `DATABASE_URL`.

**Tunable parameters** live in `config/settings.yaml`, read through `src/core/config.py`.
`agent.providers.*` is the trusted serving-deployment allowlist; each entry is a lowercase provider-qualified LiteLLM model and an API-key environment-variable name only.
The provider is derived from the model prefix, so no separate `provider` key exists to disagree with it.
`agent.react.*` and `agent.sql_generation.*` select a deployment and configure portable generation settings plus explicit validated provider options.
`agent.<profile>.max_attempts` counts attempts, not retries: `2` means the request is made twice when the first attempt fails.
A request timeout, a connection failure, a rate limit, and LiteLLM's generic API error are retried, with waits that start at 4 seconds and cap at 10; provider 5xx and 4xx responses are not retried, because a retry cannot fix a 4xx and provider pressure is already reported to the client as a retryable `provider_busy` error.
The worst case per call is `timeout x max_attempts` plus those waits: 64 seconds at the shipped 30-second timeout and two attempts, 98 seconds at three, against the 120-second `agent.stream_turn_timeout_seconds` turn deadline.
`agent.prompts.*` configures the Langfuse deployment label that links traces to registered prompt versions, its SDK cache lifetime, and the two bounds that keep Langfuse off the request path: boot resolves each surface once with a fetch bounded by `fetch_timeout_seconds` and never retried, and a background task refreshes the links every `refresh_interval_seconds` (see the [Langfuse prompt management guide](../how-to/manage-langfuse-prompts.md); #698).
`agent.stream_turn_timeout_seconds` is the end-to-end serving deadline for one agent turn: both the streamed `/api/v1/agent/chat/stream` and the non-streaming `/api/v1/agent/chat` stop at it and report the expiry as a retryable `provider_busy`.
It is required, and a missing, non-integer, boolean, or non-positive value refuses boot (ADR-0048, amended by #656) instead of falling back.
`database.connect_timeout_seconds` bounds every connection attempt (TCP, TLS, and authentication) so an unreachable database refuses boot within the bound; the configured value overrides any `connect_timeout` in a DSN.
`agent.memory.max_turns` bounds the model's window, counted in complete turns, and `agent.memory.retention_days` bounds storage: the serving process deletes every thread whose newest checkpoint is older than that age, once at boot and then daily.
`agent.query.*` controls retrieval bounds, and `api.*` owns hardening controls including the positive finite `stream_heartbeat_seconds` SSE comment cadence (validated during settings load and application startup).
`ingestion.*` configures the pipeline.
Per project convention, parameters are configured here rather than hard-coded.

### MCP tool endpoint

The two read-only job-query tools (`query_clean_jobs` and `get_job_details`) are exposed as a
discoverable Model Context Protocol (MCP) surface through `langchain.mcp.MCPAdapter`, served in
process from the same FastMCP server the agent uses (`src/agents/mcp/job_server.py`).

- **URL and transport:** a Streamable HTTP endpoint mounts at `/mcp` when enabled; clients use POST.
- **Tools and schemas:** `query_clean_jobs(request: string) -> QueryResult` and `get_job_details(ids: array[integer], at least one) -> JobDetailsResult`.
  Both publish an `outputSchema`, and `request` replaces the earlier `question` name ([ADR-0062](../decisions/adr-0062-tools-return-facts-the-prompt-owns-wording.md)).
- **Access policy:** internal and development-only (issue #465 access decision, option A).
  It is not an Internet-facing supported integration.
- **Enablement:** disabled by default. Set `MCP_ENABLED=1` to mount `/mcp` for local manual tests only.
  The public Render deployment never sets it.
  No authentication, rate limiting, or audit controls are added for this endpoint.
- **Local manual test:** run `MCP_ENABLED=1 uv run uvicorn src.serving.composition:app --reload` and point an MCP inspector at `http://localhost:8000/mcp`.
  `tools/list` returns exactly the two tools above, and `/`, `/api/v1/health`, and `/api/v1/agent/chat` keep working.

### Serving deployment migration

The prior `agent.provider` and per-profile `provider` plus `model` fields are replaced by named `agent.providers` deployments.
Each deployment is a lowercase provider-qualified LiteLLM model plus an `api_key_env` name, and each profile selects it through `deployment`.
The provider is derived from the model prefix, so the earlier per-deployment `provider` key is now refused rather than kept in sync.
The bundled deployment references `DEEPSEEK_API_KEY`; the optional eval-judge Groq branch still reads `GROQ_API_KEY` from `.env`.
Do not place an API key value in YAML, documentation, a Langfuse tag, or a log message.

```yaml
agent:
  providers:
    approved_deployment:
      model: deepseek/deepseek-flash
      api_key_env: DEEPSEEK_API_KEY
  react:
    deployment: approved_deployment
    provider_options:
      thinking: disabled
```

DeepSeek accepts only the explicit `thinking` option in the serving contract.
All other provider options, unqualified models, missing sections, and unknown deployments refuse settings load, and an unavailable selected credential refuses boot before model construction.
To roll back, revert the deployment contract and LiteLLM runtime together with the dependency change, then restore the native adapter configuration while retaining the existing environment variables through the rollback window.


## 10. Technology stack

This section is the single owner of "what is this built with": versions, runtime choices, and hosted
services.
Other documents link here rather than restating.
`python scripts/docs_lint.py --check stack` fails the build if the dependency list below drifts from
`pyproject.toml`, so it cannot go stale silently.
`pyproject.toml` remains authoritative for declared compatible ranges, and `uv.lock` records the exact tested resolutions.

### 1 At a glance

| Layer | Choice | Version | Where configured |
|---|---|---|---|
| Language | Python | 3.12 | `.python-version`, `pyproject.toml` |
| Package manager | uv | lockfile `uv.lock` | `pyproject.toml` |
| API | FastAPI and uvicorn | >=0.136.3 / >=0.48.0 | `src/api/app.py` |
| Agent | LangChain ReAct | >=1.4.2 | `src/agents/`, `config/settings.yaml`, `config/prompts.yaml` |
| Model, serving | LiteLLM with a configured DeepSeek deployment | - | `config/settings.yaml`, `agent` |
| Database | PostgreSQL | 17 on Neon | `DATABASE_URL` |
| ORM and driver | SQLAlchemy and psycopg | >=2.0 / >=3.2 | `src/services/query/` |
| Migrations | Alembic | >=1.14 | `alembic/`, `alembic.ini` |
| Tracing | Langfuse Cloud | >=4.15.6,<5.0.0 | `src/agents/tracing/` |
| Evaluation | DeepEval with a Gemini judge | >=4.0.7 | `evals/`, `config/settings.yaml` |
| Hosting | Render Docker web service | Free tier | `render.yaml`, `docker/Dockerfile` |

### 2 Dependencies

<!-- deps:begin -->

**Runtime and API**

| Package | Role |
|---|---|
| `fastapi` | HTTP layer. Routes stay agnostic of how the agent is built. |
| `uvicorn` | ASGI server. Production runs a single worker; the free tier has one. |
| `pydantic-settings` | Typed config loading from `config/settings.yaml` and the environment. |
| `slowapi` | Per-IP rate limiting, applied to chat and not to health. |

**Agent**

| Package | Compatible range | Role |
|---|---|---|
| `langchain` | `>=1.4.2,<1.5.0` with the `mcp` extra | ReAct agent runtime and tool binding. The `mcp` extra pulls in FastMCP and provides `langchain.mcp.MCPAdapter`, which discovers the read-only job-query tools in process (see `src/agents/mcp/`). |
| `langchain-litellm` | `>=0.8.0,<0.9.0` | In-process provider-neutral serving adapter. It brings LiteLLM for provider-qualified models and serves the configured deployment allowlist. |
| `langchain-groq` | `>=1.1.2,<1.2.0` | Evaluation judge's Groq alternate branch. It is not on the serving path. |
| `langchain-openai` | `>=1.5.0,<1.6.0` | Evaluation-judge fallback via OpenRouter's OpenAI-compatible endpoint, never on the serving path. |
| `langchain-google-genai` | `>=4.3.5,<4.4.0` | Evaluation judge (`gemma-4-31b-it`) via Google AI Studio, never on the serving path. Restored after the OpenRouter detour; the retired arm was Gemini 2.5 Flash. |
| `langgraph-checkpoint-postgres` | `>=3.1.0,<3.2.0` | Short-term conversation memory, session id to thread id. |

**Data**

| Package | Role |
|---|---|
| `sqlalchemy` | Query construction and session management, 2.0 style. |
| `psycopg` | PostgreSQL driver, with binary and pool extras: no local build, built-in pooling. |
| `pglast` | PostgreSQL's own parser (`libpg_query`) for validating and bounding agent SQL against the real grammar. |
| `alembic` | Schema migrations. |

**Observability**

| Package | Role |
|---|---|
| `langfuse` | Trace capture and evaluation score writeback. Confined to the tracing layer. |
| `structlog` | Structured application logging. |

**Ingestion**

| Package | Role |
|---|---|
| `httpx` | HTTP client for the JSON API path. |

**Scraping spikes** (throwaway scripts, excluded from lint)

| Package | Role |
|---|---|
| `cloudscraper` | Cloudflare bypass in the `scripts/scrape_*_spike.py` throwaway spikes only; no `src/` module imports it. |
| `beautifulsoup4` | HTML parsing in the `scripts/scrape_*_spike.py` throwaway spikes only; no `src/` module imports it. |
| `lxml` | Parser backend for BeautifulSoup in the `scripts/scrape_*_spike.py` throwaway spikes only; no `src/` module imports it. |

**Quality, dev group**

| Package | Role |
|---|---|
| `pytest` | Test runner. Eval-marked tests are deselected by default. |
| `pytest-asyncio` | Async test support. |
| `pytest-mock` | Mocking helpers. |
| `mypy` | Type checking over `src/`, with the pydantic plugin. |
| `ruff` | Lint and format. `scripts/` is excluded; throwaway spikes live there. |
| `deepeval` | Evaluation harness for the scenario and three-seam metric runs. |

<!-- deps:end -->

### 3 Agent-critical dependency upgrades

Do not widen an agent-critical dependency range until its target minor line has passed the runtime and evaluation checks.
First update the range in `pyproject.toml`, regenerate the lockfile with `uv lock`, and confirm the resolved package version is inside the declared range.
Run `uv run pytest tests/agents/runtime/test_factory.py tests/agents/runtime/test_provider.py tests/agents/runtime/test_react_agent.py` and `uv run pytest tests/evals`.
Then run the full verification gate: `uv run pytest`, `uv run ruff check .`, `uv run mypy`, and `uv run python scripts/docs_lint.py`.
Record the resolved versions and check results in the pull request before merging the widened range.

On Windows, invoke live DeepEval checks with `PYTHONUTF8=1` and the eval marker.
The fixture count tests skip when the evaluation database is unavailable, and the trace extractor
expects the nested SQL-generation span to be a child of its tool span, falling back to the
pre-MCP hierarchy where that span is a sibling sharing the tool span's parent.

### 4 Hosted services

| Service | Chosen offering | Why |
|---|---|---|
| Render | Free Docker web service | Managed container hosting without an additional platform. |
| Neon | Free PostgreSQL 17 | Managed serverless Postgres. |
| Langfuse Cloud | Hobby, Japan | Selected over self-hosting on operational-cost grounds. |
| GitHub Actions | Free | CI and the ingestion workflow. |

For the current cost position, topology, environment variables, deploy procedures, and cron
operation, see [how-to/operate.md](../how-to/operate.md).

### 5 Provider quotas and cost

The serving agent is metered and the judge is on a free tier, which keeps evaluation work off the
serving provider's account ([ADR-0017](../decisions/adr-0017-judge-provider-separate-from-serving.md)).

DeepSeek has no free tier and publishes no per-minute or per-day token limit, only account
concurrency.
A full 29-scenario evaluation run measured about four cents at list rates, spending roughly 3.7K
tokens per turn across 77 turns.
Serving traffic on the demo is the same per-turn shape.
For the measured derivation see [T0027.3 DeepSeek arm](../../evals/archive/t0027_deepseek_arm.md); for the
judge-side rate-limit caveats see
the evaluation strategy record on git tag docs-history-pre-redesign, sections 4a and 4b.

### 6 Deliberately not used

Recorded so these choices are not re-litigated.

- **CORS.** The demo UI is served same-origin from FastAPI, so the allowed-origins list stays empty.
  Adding a cross-origin front end is the only reason to revisit.
- **Self-hosted Langfuse.** Langfuse Cloud Hobby won on operational cost.
- **A JavaScript framework.** The demo UI is vanilla HTML, CSS, and JavaScript consuming SSE via
  `fetch()` and `ReadableStream`. No build step, nothing to keep patched.
- **Celery, Redis, or a task queue.** Ingestion runs as a GitHub Actions workflow (nightly by the
  workflow's `schedule:` trigger and on manual `workflow_dispatch`), not a long-lived worker.
- **The browser `EventSource` API.** It is GET-only; the chat endpoint is a POST, hence the
  `fetch()` reader.
- **RAG, embeddings, and fine tuning.** Future phases, not MVP scope.
- **A hardcoded technology allowlist.** Source tags are noisy; an external, refreshable vocabulary
  retains coverage without a model call.

