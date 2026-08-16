# Tech Stack

> **Last verified:** 2026-08-15 against `pyproject.toml`, `config/settings.yaml`, and
> `render.yaml`. This document is the **single owner** of "what is this built with" — versions,
> runtime choices, and hosted services. Other docs link here rather than restating.
> `scripts/docs_lint.py --check stack` fails the build if the dependency list below drifts from
> `pyproject.toml`, so this file cannot go stale silently.

> **Eviction:** A stack entry leaves when its dependency, service, or runtime is removed from the
> deployed system and its configuration is deleted.

The [vendored technology vocabulary sources](../data/vendor/README.md) record the inputs to the
technology-vocabulary builder.

## At a glance

| Layer | Choice | Version | Where configured |
|---|---|---|---|
| Language | Python | 3.12 | `.python-version`, `pyproject.toml` |
| Package manager | uv | lockfile `uv.lock` | `pyproject.toml` |
| API | FastAPI + uvicorn | ≥0.136.3 / ≥0.48.0 | `src/api/app.py` |
| Agent | LangChain ReAct | ≥1.3.1 | `src/agents/`, `config/prompts.yaml` |
| LLM (serving) | DeepSeek — `deepseek-v4-flash` | — | `config/settings.yaml` → `agent` |
| LLM (second arm) | Groq — `qwen/qwen3.6-27b` | — | `config/settings.yaml` → `agent`, selectable |
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
| `langchain-groq` | Second selectable serving provider, and the eval judge's alternate branch. Reached only when `agent.provider` or a profile names `groq`. |
| `langchain-deepseek` | Serving provider, and the default for both profiles since D-045. Thinking is disabled so `temperature` applies. |
| `langchain-google-genai` | Gemini, used **only** as the eval judge — never on the serving path. |
| `langgraph-checkpoint-postgres` | Short-term conversation memory, `session_id → thread_id`. |

Two model profiles are deliberately separate — the outer ReAct loop reasons, while SQL
generation is pinned to `temperature: 0.0` and `reasoning_effort: none` for determinism.
`load_sql_generation_prompt()` intentionally returns text because SQL-generation prompt and schema
context are combined before the model call.
Conversation memory limits only the messages sent on each turn; persisted thread history is not
pruned in this MVP.

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

On Windows, invoke live DeepEval checks with `PYTHONUTF8=1` and `-m eval`.
The fixture count tests skip when the eval database is unavailable, and the current trace extractor
expects the nested SQL-generation span to be a sibling of its tool span.

<!-- deps:end -->

## Hosted services

| Service | Chosen offering | Why |
|---|---|---|
| Render | Free Docker web service | Managed container hosting without an additional platform. |
| Neon | Free PostgreSQL 17 | Managed serverless Postgres. |
| Langfuse Cloud | Hobby, JP | Selected over self-hosting on operational-cost grounds. |
| GitHub Actions | Free | CI and the ingestion workflow. |

For the current cost position, topology, environment variables, deploy procedures, and cron
operation, see [Operations.md](Operations.md).

## Provider quotas and cost

The serving agent is metered and the DeepEval judge is on Gemini's free tier, which keeps
evaluation work off the serving provider's account (D-017).

DeepSeek has no free tier and publishes no TPM or TPD limit, only account concurrency.
A full 29-scenario evaluation run measured **$0.043** at `deepseek-v4-flash` list rates on
2026-08-14, spending ~3.7K tokens per turn across 77 turns.
Serving traffic on the demo is the same per-turn shape.
For the measured derivation, see [T0027.3 DeepSeek arm](../evals/t0027_deepseek_arm.md); for the
judge-side rate-limit caveats, see
[`research/evaluation-strategy.md`](../research/evaluation-strategy.md), sections 4a and 4b.

The Groq arm remains selectable on its free tier, at 8000 TPM and 200K TPD.
That ceiling is what `eval.driver.turn_pacing_seconds` exists for: restore it to 75 whenever a
profile moves back to `groq`.

## Deliberately not used

Recorded so these choices are not re-litigated:

- **CORS** — the demo UI is served same-origin from FastAPI, so `api.cors.allowed_origins`
  stays `[]`. Adding a cross-origin front end is the only reason to revisit.
- **Self-hosted Langfuse** - deliberately not used; Langfuse Cloud Hobby won on operational cost.
- **A JavaScript framework** — the demo UI is vanilla HTML/CSS/JS consuming SSE via
  `fetch()` + `ReadableStream`. No build step, nothing to keep patched.
- **Celery / Redis / a task queue** — ingestion runs as a scheduled GitHub Action, not a
  long-lived worker.
- **`EventSource`** — it is GET-only; the chat endpoint is POST, hence the `fetch()` reader.
