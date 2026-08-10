# Tech Stack

> **Last verified:** 2026-08-10 against `pyproject.toml`, `config/settings.yaml`, and
> `render.yaml`. This document is the **single owner** of "what is this built with" — versions,
> runtime choices, and hosted services. Other docs link here rather than restating.
> `scripts/docs_lint.py --check stack` fails the build if the dependency list below drifts from
> `pyproject.toml`, so this file cannot go stale silently.

## At a glance

| Layer | Choice | Version | Where configured |
|---|---|---|---|
| Language | Python | 3.12 | `.python-version`, `pyproject.toml` |
| Package manager | uv | lockfile `uv.lock` | `pyproject.toml` |
| API | FastAPI + uvicorn | ≥0.136.3 / ≥0.48.0 | `src/api/app.py` |
| Agent | LangChain ReAct | ≥1.3.1 | `src/agents/`, `config/prompts.yaml` |
| LLM (serving) | Groq — `qwen/qwen3.6-27b` | — | `config/settings.yaml` → `agent` |
| Database | PostgreSQL | 17 (Neon) | `DATABASE_URL` |
| ORM / driver | SQLAlchemy + psycopg | ≥2.0 / ≥3.2 | `src/services/query/` |
| Migrations | Alembic | ≥1.14 | `alembic/`, `alembic.ini` |
| Tracing | Langfuse Cloud | ≥4.6.1 | `src/agents/tracing/` |
| Evaluation | DeepEval, Gemini judge | ≥4.0.7 | `evals/`, `config/settings.yaml` → `eval` |
| Hosting | Render (Docker) | Free tier | `render.yaml`, `docker/Dockerfile` |

<!-- deps:begin -->

## Runtime & API

| Package | Role |
|---|---|
| `fastapi` | HTTP layer. Routes stay agnostic of how the agent is built (`CLAUDE.md` §2). |
| `uvicorn` | ASGI server. `WEB_CONCURRENCY=1` in production — the free tier has one worker. |
| `pydantic-settings` | Typed config loading from `config/settings.yaml` + environment. |
| `slowapi` | Per-IP rate limiting, default `15/minute`; applied to chat, not to health. |

## Agent

| Package | Role |
|---|---|
| `langchain` | ReAct agent runtime and tool binding. |
| `langchain-groq` | Serving provider. Two profiles: `react` and `sql_generation`. |
| `langchain-google-genai` | Gemini, used **only** as the eval judge — never on the serving path. |
| `langgraph-checkpoint-postgres` | Short-term conversation memory, `session_id → thread_id`. |

Two model profiles are deliberately separate — the outer ReAct loop reasons, while SQL
generation is pinned to `temperature: 0.0` and `reasoning_effort: none` for determinism.

## Data

| Package | Role |
|---|---|
| `sqlalchemy` | Query construction and session management, 2.0 style. |
| `psycopg` | PostgreSQL driver (`[binary,pool]` extras — no local build, built-in pooling). |
| `alembic` | Schema migrations. Production head: `b7e2f4a91c3d`. |

The agent reads one table, `clean_jobs`, through a read-only path with a single-table
allowlist. The frozen v1 column contract lives in [`Schema_Contract.md`](Schema_Contract.md).

## Observability

| Package | Role |
|---|---|
| `langfuse` | Trace capture and eval score writeback. Confined to the tracing layer. |
| `structlog` | Structured application logging. |

## Ingestion

| Package | Role |
|---|---|
| `cloudscraper` | Fetches VietnamWorks listings past bot protection. |
| `httpx` | HTTP client for the JSON API path. |
| `beautifulsoup4` | HTML parsing for detail pages. |
| `lxml` | Parser backend for BeautifulSoup. |

## Quality (dev group)

| Package | Role |
|---|---|
| `pytest` | Test runner. `eval`-marked tests are deselected by default. |
| `pytest-asyncio` | Async test support. |
| `pytest-mock` | Mocking helpers. |
| `mypy` | Type checking over `src/`, with the pydantic plugin. |
| `ruff` | Lint and format. `scripts/` is excluded — throwaway spikes live there. |
| `deepeval` | Evaluation harness for the golden-dataset and three-seam metric runs. |

<!-- deps:end -->

## Hosted services

| Service | Tier | Region | Notes |
|---|---|---|---|
| **Render** | Free, Docker | Singapore | Deploys from `main`, pinned by `render.yaml`. Health check `/api/v1/health`. |
| **Neon** | Free, PostgreSQL 17 | — | Serverless Postgres. Idle-pool behaviour matters on the free tier. |
| **Langfuse Cloud** | Hobby | JP | Chosen over self-hosting (decided 2026-07-12). |
| **GitHub Actions** | Free | — | CI merge gate, plus the ingestion cron (currently parked). |

Running cost is **$0/month** against a self-imposed $10 ceiling. Secrets are Render
environment variables; nothing credential-bearing is committed.

## Deliberately not used

Recorded so these choices are not re-litigated:

- **CORS** — the demo UI is served same-origin from FastAPI, so `api.cors.allowed_origins`
  stays `[]`. Adding a cross-origin front end is the only reason to revisit.
- **Self-hosted Langfuse** — `infra/langfuse/` has no Compose service; Cloud Hobby won on
  operational cost.
- **A JavaScript framework** — the demo UI is vanilla HTML/CSS/JS consuming SSE via
  `fetch()` + `ReadableStream`. No build step, nothing to keep patched.
- **Celery / Redis / a task queue** — ingestion runs as a scheduled GitHub Action, not a
  long-lived worker.
- **`EventSource`** — it is GET-only; the chat endpoint is POST, hence the `fetch()` reader.
