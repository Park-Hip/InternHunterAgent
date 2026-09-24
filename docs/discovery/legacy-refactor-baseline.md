# Legacy-refactor baseline

> **Last verified:** 2026-09-24
>
> **Eviction:** This baseline leaves when an approved target architecture replaces the legacy implementation and its entrypoints are retired or superseded by a final architecture record.

## Purpose and scope

This is a read-only evidence record for [issue #424](https://github.com/Park-Hip/InternHunterAgent/issues/424).
It records the legacy system as found at commit `f20e688`, before any refactor decision.
It does not define the target MVP, select a migration strategy, or authorize runtime, deployment, data, dependency, schema, or framework changes.

The inventory in [legacy-inventory.md](legacy-inventory.md) distinguishes source-backed facts from legacy documentation claims and open questions.
The new MVP discovery records are intentionally out of scope for this legacy baseline.

## Working-tree preservation

<!-- lint-allow-link-path:begin -->
The original checkout at `D:/Data_Science_Project/InternHunterAgent` was inspected before this worktree was created.
It was on `main...origin/main` and contained the following pre-existing changes: `AGENTS.md`; `.playwright-cli/`; `RESEARCH_BRIEF_AI_AGENT_PRODUCTION_2025_2026.md`; `TEMP_AI_AGENT_LEARNING_ROADMAP.md`; `TEMP_DATA_COLLECTION_RESEARCH.md`; `TEMP_MVP_DISCOVERY_DECISIONS.md`; `docs/discovery/`; `nul`; and `research/phase3-missing-evidence.md`.
<!-- lint-allow-link-path:end -->
Those changes were neither modified, staged, copied, nor included in this worktree.

This documentation was created in the dedicated `issue-424-legacy-refactor-discovery` worktree, branched from `origin/main` at `f20e688`.

## Read-only baseline checks

| Check | Result | What it proves | What it does not prove |
| --- | --- | --- | --- |
| `git rev-parse HEAD` | Passed with `f20e688`. | The evidence has a reproducible legacy revision. | That the revision is deployed or behaviorally correct. |
| `git status --short --branch` in the discovery worktree | Passed with a clean worktree before this documentation was added. | The baseline was not blended with the original checkout's dirty work. | That the original dirty work is safe to discard or merge. |
| `uv tree` | Passed. | The resolved environment includes FastAPI, LangChain, Langfuse, SQLAlchemy, Psycopg, LangGraph Postgres checkpointing, Uvicorn, and the declared provider packages. | That every declared dependency is reached in production. |
| `uv run pytest --collect-only -q` | Passed with 964 collected and 52 `eval`-marked tests deselected by the default pytest configuration. | The default test suite can discover its recorded test surfaces at this revision. | That a test passes, that a deployed request works, or that a live provider, database, Langfuse project, Render service, or source is available. |
| Static route, entrypoint, configuration, workflow, and import inspection | Completed against `src/`, `config/`, `docker/`, `render.yaml`, `docker-compose.yml`, `.github/workflows/`, `tests/`, and `pyproject.toml`. | The entrypoint and dependency maps below are source-backed. | Runtime reachability of an environment-specific branch or correctness of stale documentation. |

The default pytest configuration deliberately deselects live API evaluation tests.
The collection result is therefore inventory evidence only, not behavioral coverage evidence.

## Entrypoint map

| Entrypoint | Invocation evidence | Current responsibility | External boundary | Compatibility posture |
| --- | --- | --- | --- | --- |
| Render web service | `render.yaml` selects `docker/Dockerfile`; the image starts `uvicorn src.api.app:app`. | Serves the FastAPI application on port 8000 and exposes `/api/v1/health` for platform health checks. | Render, environment secrets, PostgreSQL, selected model provider, and optional Langfuse. | Candidate public deployment boundary. Preserve only after the approved MVP defines availability and API compatibility needs. |
| Local Compose API | `docker-compose.yml` builds the same Dockerfile and maps port 8000. | Provides local API plus PostgreSQL development topology. | Docker and local PostgreSQL volume. | Developer-only topology. Keep as reference until the target development workflow is selected. |
| FastAPI application | `src/api/app.py` constructs module-level `app = create_app()`. | Assembles middleware, routes, static assets, startup checks, checkpointer, runtime, and tracing lifecycle. | FastAPI, static files, database schema, LangGraph checkpointer, Langfuse. | Preserve the application factory seam, not its current assembly choices. |
| One-shot request | `POST /api/v1/agent/chat` is registered in `src/api/routes/query.py`. | Validates `QueryRequest`, invokes the service, and serializes `QueryResponse`. | Caller-visible HTTP and JSON contract. | Public compatibility candidate. No preservation promise is made until the MVP specification is approved. |
| Streaming request | `POST /api/v1/agent/chat/stream` is registered in `src/api/routes/query.py`. | Validates input and sends typed Server-Sent Events. | Caller-visible HTTP and SSE event contract. | Public compatibility candidate. Confirm actual deployed clients before preserving or versioning it. |
| Liveness and readiness | `GET /api/v1/health` and `GET /api/v1/ready` are registered in `src/api/routes/health.py`. | Reports process liveness and database readiness with snapshot-date provenance. | Render health checks and PostgreSQL. | Operational compatibility candidate. Preserve only the required health semantics. |
| Browser UI | The root `StaticFiles` mount in `src/api/app.py` serves `src/api/static/`. | Same-origin HTML, JavaScript, CSS, and vendored browser libraries consume the public API. | Browser and public API. | User-visible compatibility candidate. Its current chat workflow is legacy evidence. |
| Manual ingestion | `.github/workflows/ingestion.yml` exposes `workflow_dispatch` and runs `python -m src.services.ingestion.loader`. | Fetches, normalizes, validates, and writes the legacy job corpus when manually authorized. | GitHub Actions, VietnamWorks, PostgreSQL, and Healthchecks.io. | Not an authorized product capability under current discovery status. Retain as evidence only. |
| Render recovery cron | `render.yaml` runs `scripts/recover_ingestion_workflow.py` daily. | Checks and may re-enable or dispatch the GitHub Actions ingestion workflow. | Render Cron, GitHub Actions API, and Healthchecks.io. | Operational legacy behavior. Reassess with the data-collection decision, not during this refactor discovery. |
| Migration CLI | `alembic.ini` and `alembic/` define the migration chain; the README and CI call Alembic. | Evolves database schema outside request handling. | PostgreSQL. | Schema-management boundary. Preserve the migration invariant if a database remains in the target. |
| Evaluation and maintenance CLIs | `evals/` modules and scripts such as `register_langfuse_prompts.py` are invoked by CI or maintainers. | Evaluate legacy behavior and synchronize operational assets. | Optional providers, Langfuse, fixture database, and filesystem. | Offline-only evidence. Reuse individual seams only after MVP evaluation requirements are set. |

## Public contract and settings surfaces

The source currently defines these observable HTTP surfaces.
This list is an inventory, not an assertion that the legacy public API must remain compatible.

| Surface | Source-backed shape | Error or availability behavior |
| --- | --- | --- |
| `POST /api/v1/agent/chat` | `QueryRequest {query, user_id?, session_id?}` to `QueryResponse {answer, session_id?, trace_id?, trace_url?}`. | Blank input maps to 400; provider pressure maps to a safe 429; unclassified failure maps to a safe 500. |
| `POST /api/v1/agent/chat/stream` | A `QueryRequest` starts an SSE stream with `session`, zero or more `token`, optional `metadata`, optional `error`, and terminal `done` events. | Blank input maps to 400 before streaming; post-start failures are in-band safe error events. |
| `GET /api/v1/health` | Returns process liveness. | Does not probe dependencies. |
| `GET /api/v1/ready` | Returns status and snapshot-date provenance after a database probe. | Returns 503 when the readiness database probe fails. |
| `/`, static paths, `/docs`, `/redoc`, and `/openapi.json` | The static mount serves the browser client; documentation and OpenAPI exposure are controlled by `api.docs_enabled`. | Root mounting order is significant because it follows the API routers. |

`src/core/config.py` loads `.env` and YAML files from `config/`.
Required runtime variables are `DATABASE_URL` and `AGENT_DATABASE_URL`.
Optional provider, tracing, operational, and evaluation variables include `DEEPSEEK_API_KEY`, `GROQ_API_KEY`, `GOOGLE_API_KEY`, `OPENROUTER_API_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_BASE_URL`, and `HEALTHCHECKS_URL`.
`render.yaml` declares the web-service secrets and the recovery-cron secrets separately.

## Dependency and deployment evidence

`pyproject.toml` directly declares FastAPI, Uvicorn, SQLAlchemy, Psycopg, Alembic, LangChain, LangGraph Postgres checkpointing, Langfuse, DeepSeek and Groq LangChain integrations, ingestion parsing libraries, HTTPX, and SlowAPI.
It also declares Google and OpenAI LangChain integrations, but static inspection did not find a corresponding production import in `src/`.
Declared dependencies are not proof of production use.

The legacy deployment topology has a Render Docker web service in Singapore on the free plan, a Render recovery cron, GitHub Actions CI, a manually dispatched GitHub Actions ingestion workflow, PostgreSQL locally and apparently externally, a selected model provider, optional Langfuse Cloud, and Healthchecks.io for ingestion/recovery signaling.
The checked source does not independently prove the existence, configuration, reachability, or current health of any hosted service.

## Known gaps and contradictions to resolve later

| Item | Evidence | Why it matters | Required follow-up |
| --- | --- | --- | --- |
| MVP and data authority are unresolved. | Current discovery status prohibits production collection and implementation. | The legacy app assumes a job-posting corpus and a conversational ReAct workflow. | Approve the MVP and data-collection strategy before selecting a target runtime or data path. |
| Legacy architecture prose is not current-state proof. | `docs/architecture.md` describes a broad prior system and frozen-data posture. | It can conflict with source, deployment, and the future MVP. | Use source and controlled runtime observations to characterize only required behavior. |
| Public-client compatibility is unknown. | Routes and browser assets exist in source, but no deployed-client inventory was collected. | Preserving an unused API or UI shape can constrain the replacement unnecessarily. | Identify live consumers and contractual obligations before choosing a strangler or clean-rebuild approach. |
| Deployment configuration has overlapping operational paths. | Render web, Render recovery cron, GitHub Actions CI, and manual ingestion workflow are all present. | Retirement or replacement can unintentionally leave an active external process. | Confirm active Render services, workflow state, secrets, and owners before operational changes. |
| Some declared dependencies may be stale. | Google and OpenAI integrations are declared without a production import found by the static scan. | Removing or retaining packages without reachability evidence is unsafe. | Use runtime/import and deployment evidence before dependency retirement. |
| Test collection is not a behavior baseline. | Collection passed with live `eval` tests deselected. | A green collection cannot establish external behavior, grounding quality, or deployment health. | Add characterization tests only for approved MVP behavior or confirmed compatibility contracts. |

## Exit criterion

Step 0 is complete when maintainers can name every production and request entrypoint above, can find its source evidence, and can use [legacy-inventory.md](legacy-inventory.md) to see the component's dependencies, test evidence, risks, and provisional disposition.
No disposition authorizes implementation until the MVP specification and later architecture decisions are approved.
