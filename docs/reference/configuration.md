# Configuration and stack

> **Eviction:** A parameter or dependency entry leaves when the code that reads it is retired.

This document owns the settings contract, required environment, technology choices, and the
dependency list.
Operational procedures live in [how-to/operate.md](../how-to/operate.md); architecture explanation in
[architecture.md](../architecture.md).

## Stores and environment

## 5. Data and configuration

### Stores and environment

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
The database URL and the Langfuse keys, where tracing degrades gracefully if the Langfuse keys are
absent.
Provider keys are optional at boot and validated by the branch that needs them, so a checkout runs
with only the selected provider's key.

**Tunable parameters** live in `config/settings.yaml`, read through `src/core/config.py`:
`agent.react.*` for the outer model, `agent.sql_generation.*` for the nested SQL-generation model,
`agent.memory.*` for the memory window, `agent.query.*` for the retrieval bounds, `api.*` for the
hardening controls, and `ingestion.*` for the pipeline.
Per project convention, parameters are configured here rather than hard-coded.


## Technology stack

## 10. Technology stack

This section is the single owner of "what is this built with": versions, runtime choices, and hosted
services.
Other documents link here rather than restating.
`python scripts/docs_lint.py --check stack` fails the build if the dependency list below drifts from
`pyproject.toml`, so it cannot go stale silently.
`pyproject.toml` remains authoritative for exact versions.

### 1 At a glance

| Layer | Choice | Version | Where configured |
|---|---|---|---|
| Language | Python | 3.12 | `.python-version`, `pyproject.toml` |
| Package manager | uv | lockfile `uv.lock` | `pyproject.toml` |
| API | FastAPI and uvicorn | >=0.136.3 / >=0.48.0 | `src/api/app.py` |
| Agent | LangChain ReAct | >=1.3.1 | `src/agents/`, `config/prompts.yaml` |
| Model, serving | DeepSeek | - | `config/settings.yaml`, `agent` |
| Model, second arm | Groq, selectable | - | `config/settings.yaml`, `agent` |
| Database | PostgreSQL | 17 on Neon | `DATABASE_URL` |
| ORM and driver | SQLAlchemy and psycopg | >=2.0 / >=3.2 | `src/services/query/` |
| Migrations | Alembic | >=1.14 | `alembic/`, `alembic.ini` |
| Tracing | Langfuse Cloud | >=4.6.1 | `src/agents/tracing/` |
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

| Package | Role |
|---|---|
| `langchain` | ReAct agent runtime and tool binding. |
| `langchain-deepseek` | Serving provider, and the default for both profiles since D-045. Thinking is disabled so temperature applies. |
| `langchain-groq` | Second selectable serving provider, and the judge's alternate branch. Reached only when a profile names it. |
| `langchain-google-genai` | Gemini, used only as the evaluation judge, never on the serving path. |
| `langgraph-checkpoint-postgres` | Short-term conversation memory, session id to thread id. |

**Data**

| Package | Role |
|---|---|
| `sqlalchemy` | Query construction and session management, 2.0 style. |
| `psycopg` | PostgreSQL driver, with binary and pool extras: no local build, built-in pooling. |
| `alembic` | Schema migrations. |

**Observability**

| Package | Role |
|---|---|
| `langfuse` | Trace capture and evaluation score writeback. Confined to the tracing layer. |
| `structlog` | Structured application logging. |

**Ingestion**

| Package | Role |
|---|---|
| `cloudscraper` | Fetches VietnamWorks listings past bot protection. |
| `httpx` | HTTP client for the JSON API path. |
| `beautifulsoup4` | HTML parsing for detail pages. |
| `lxml` | Parser backend for BeautifulSoup. |

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

On Windows, invoke live DeepEval checks with `PYTHONUTF8=1` and the eval marker.
The fixture count tests skip when the evaluation database is unavailable, and the trace extractor
expects the nested SQL-generation span to be a sibling of its tool span.

### 3 Hosted services

| Service | Chosen offering | Why |
|---|---|---|
| Render | Free Docker web service | Managed container hosting without an additional platform. |
| Neon | Free PostgreSQL 17 | Managed serverless Postgres. |
| Langfuse Cloud | Hobby, Japan | Selected over self-hosting on operational-cost grounds. |
| GitHub Actions | Free | CI and the ingestion workflow. |

For the current cost position, topology, environment variables, deploy procedures, and cron
operation, see [how-to/operate.md](../how-to/operate.md).

### 4 Provider quotas and cost

The serving agent is metered and the judge is on a free tier, which keeps evaluation work off the
serving provider's account (D-017).

DeepSeek has no free tier and publishes no per-minute or per-day token limit, only account
concurrency.
A full 29-scenario evaluation run measured about four cents at list rates, spending roughly 3.7K
tokens per turn across 77 turns.
Serving traffic on the demo is the same per-turn shape.
For the measured derivation see [T0027.3 DeepSeek arm](../../evals/t0027_deepseek_arm.md); for the
judge-side rate-limit caveats see
the evaluation strategy record on git tag docs-history-pre-redesign, sections 4a and 4b.

The Groq arm remains selectable on its free tier, at 8000 tokens per minute and 200K per day.
That ceiling is what the driver's turn-pacing setting exists for: restore it whenever a profile
moves back to Groq.

### 5 Deliberately not used

Recorded so these choices are not re-litigated.

- **CORS.** The demo UI is served same-origin from FastAPI, so the allowed-origins list stays empty.
  Adding a cross-origin front end is the only reason to revisit.
- **Self-hosted Langfuse.** Langfuse Cloud Hobby won on operational cost.
- **A JavaScript framework.** The demo UI is vanilla HTML, CSS, and JavaScript consuming SSE via
  `fetch()` and `ReadableStream`. No build step, nothing to keep patched.
- **Celery, Redis, or a task queue.** Ingestion runs as a scheduled GitHub Action, not a long-lived
  worker.
- **The browser `EventSource` API.** It is GET-only; the chat endpoint is a POST, hence the
  `fetch()` reader.
- **RAG, embeddings, and fine tuning.** Future phases, not MVP scope.
- **A hardcoded technology allowlist.** Source tags are noisy; an external, refreshable vocabulary
  retains coverage without a model call.

