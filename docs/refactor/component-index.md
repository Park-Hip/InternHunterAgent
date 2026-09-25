# Refactor component index

> **Last verified:** 2026-09-25
>
> **Eviction:** A row leaves this index when its component is retired or its refactor reaches the
> documented target state. Detailed historical evidence remains in `docs/discovery/`.

Start here to see what remains in the current application and which boundary is active next.
This is a navigation index, not a second legacy inventory: source remains the current truth, and the
linked historical records contain dependencies, tests, and risks.

## Current next action

**Do only this next:** create and approve one focused proposal to replace the application's concrete
tracing dependency. It must define observation ownership and characterize successful, failed,
timeout, and cancelled streaming behavior before changing any tracing code.

Serving composition completed in [#443](https://github.com/Park-Hip/InternHunterAgent/pull/443).
After the tracing slice merges, update this index and the [active backlog](active-backlog.md), then
take the next listed boundary. Do not begin the configuration or model-policy work first.

## Component status

| Component group | Current paths | Current responsibility | Status and next action | Evidence |
| --- | --- | --- | --- | --- |
| Serving composition | `src/serving/composition.py`, `src/api/app.py` | Concrete composition owns settings, schema guard, checkpointer, runtime, and Langfuse lifecycle; API app factory accepts an injected lifespan. | **Completed:** [#443](https://github.com/Park-Hip/InternHunterAgent/pull/443) externalized assembly. Keep `app.state.runtime` as a temporary compatibility seam. | [Target map](target-layer-dependency-map.md#current-gaps-that-motivate-the-map) |
| API transport and browser delivery | `src/api/routes/`, `src/api/schemas.py`, `src/api/static/` | Translates HTTP and SSE; exposes health/readiness; serves the browser client. | **Retain:** delivery behavior was preserved by #443. Reassess dependencies only in a later approved slice. | [Legacy inventory](../discovery/legacy-inventory.md#runtime-and-public-delivery) |
| Application service | `src/agents/service.py` | Owns request orchestration, session and fallback policy, and one-shot/stream response flow. | **No active slice:** retain behavior. Its direct tracing dependency is queued next. | [Debt register D-427-03](../discovery/current-state-debt-register.md) |
| Tracing adapter | `src/agents/tracing/` | Implements Langfuse lifecycle, request observations, prompt lineage, and stream latency. | **Active candidate (1):** define a tracing event/observation port so application service does not import Langfuse types. | [Active backlog](active-backlog.md) |
| Agent runtime | `src/agents/runtime/` | Builds and executes the conversational workflow, provider branches, prompts, and checkpointed runtime behavior. | **Retain:** no framework or prompt change is active. Revisit only after its ports and model policy are explicit. | [Legacy inventory](../discovery/legacy-inventory.md#runtime-and-public-delivery) |
| Tool adapters | `src/agents/tools/` | Translates model tool calls into query/detail operations. | **Retain:** no active slice. Revisit after tool and model contracts are selected. | [Architecture map](../discovery/current-state-architecture-maps.md#serving-and-request-flow) |
| Deterministic query services | `src/services/query/` | Validates, queries, transforms, and formats legacy job facts. | **Retain:** no data/schema change is active. Revisit only with an approved data or domain contract. | [Legacy inventory](../discovery/legacy-inventory.md#core-data-and-offline-processing) |
| Persistence and checkpointing | `src/core/db.py`, `src/core/checkpointer.py`, `alembic/` | Provides database sessions, LangGraph checkpoint persistence, and schema evolution. | **Retain:** #443 moved lifecycle ownership without changing persistence behavior or schema. | [Debt register D-427-01](../discovery/current-state-debt-register.md) |
| Configuration | `src/core/config.py`, `config/` | Loads process, YAML, provider, serving, tracing, and command settings. | **Queued (3):** separate command-specific configuration from serving configuration. | [Active backlog](active-backlog.md) |
| Model construction | `src/agents/runtime/factory.py`, `src/agents/tools/query_clean_jobs.py` | Constructs the serving and SQL-generation models in separate paths. | **Queued (4):** define model/tool contracts, then measure options before changing providers or prompts. | [Active backlog](active-backlog.md) |
| Offline ingestion and migrations | `src/services/ingestion/`, `.github/workflows/ingestion.yml`, `alembic/` | Legacy source collection, normalization, loading, and database migration paths. | **Parked:** no collection, activation, or data-policy work belongs in the current refactor. | [Legacy baseline](../discovery/legacy-refactor-baseline.md#known-gaps-and-contradictions-to-resolve-later) |
| Evaluation, operations, and delivery | `evals/`, `scripts/`, `docker/`, `render.yaml`, `.github/workflows/` | Legacy evaluation, operational automation, container delivery, and CI paths. | **Parked:** retain as evidence until a later approved slice establishes a compatibility or operational need. | [Architecture map](../discovery/current-state-architecture-maps.md#tracing-and-evaluation-flow) |

## Reading rule

For an active component, read this index, its linked issue, and the relevant row in the target map.
Open a historical discovery record only when the issue needs evidence about current behavior,
dependencies, or tests. Do not read the historical collection from beginning to end.
