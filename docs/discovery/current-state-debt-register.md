# Current-state boundary violation and debt register

> **Last verified:** 2026-09-24 at commit `4d6f00e`.
>
> **Purpose:** This register records source-backed risks and contradictions found for [issue #427](https://github.com/Park-Hip/InternHunterAgent/issues/427).
>
> **Decision status:** A debt item is not authorization to refactor, delete, reconfigure, or preserve a legacy component.

## Classification

`Verified` means the cited source directly demonstrates the condition.
`Declared` means repository configuration declares a relationship without proving it is active.
`Unknown` means the evidence needed to assess the condition was not collected.

Priority is about potential impact on a future decision, not implementation order.
Every remediation remains blocked until the MVP and its compatibility posture are approved.

| ID | Area | Confidence | Material risk or boundary violation | Source evidence | Why it matters | Decision or evidence that unblocks a follow-up |
| --- | --- | --- | --- | --- | --- | --- |
| D-427-01 | Persistence | Verified | `AGENT_DATABASE_URL` is required and has an engine proxy, but the serving checkpointer derives its connection string from `DATABASE_URL`. | `src/core/config.py` (`Settings`); `src/core/db.py`; `src/core/checkpointer.py` (`_checkpointer_dsn`) | Operators can reasonably infer separate agent persistence while the current serving path uses the main database URL. | Approve the persistence and conversation-state contract, then characterize the deployed connection topology before changing settings or schema. |
| D-427-02 | API composition | Verified | The FastAPI composition root imports the runtime factory, `AgentRuntime`, the Langfuse lifecycle adapter, and the checkpointer. | `src/api/app.py` | Application assembly is concentrated in an API module, so a transport change can affect agent construction, database setup, and tracing lifecycle. | Approve target composition boundaries and compatibility needs. |
| D-427-03 | Tracing separation | Verified | The application service imports `StreamLatency` from the tracing layer to coordinate stream completion. | `src/agents/service.py`; `src/agents/tracing/langfuse.py` | The service layer has a direct tracing type dependency, which makes tracing less locally replaceable than the legacy architecture prose describes. | Define the target observability contract and stream lifecycle ownership. |
| D-427-04 | Configuration | Verified | `Settings` requires `DATABASE_URL` and `AGENT_DATABASE_URL` for every invocation, while the ingestion workflow supplies a dummy `AGENT_DATABASE_URL`. | `src/core/config.py` (`Settings`); `.github/workflows/ingestion.yml` | An offline ingestion command inherits serving configuration requirements even though its documented path does not need agent persistence. | Approve command-specific configuration boundaries and characterize every CLI's required settings. |
| D-427-05 | Data authority | Declared | The repository retains a manual ingestion workflow and a Render recovery cron that can dispatch it, while the workflow comments state that collection is frozen pending an authorized recovery. | `.github/workflows/ingestion.yml`; `render.yaml`; `scripts/recover_ingestion_workflow.py` | An operational path can have external write effects, but no evidence establishes its current dashboard state, authorization, or owner. | Obtain provider authorization, service ownership, and a separately approved data and operations proposal. |
| D-427-06 | Public compatibility | Unknown | JSON routes, an SSE route, and a browser client exist, but no deployed-consumer inventory was collected. | `src/api/routes/query.py`; `src/api/static/app.js`; `docs/discovery/legacy-refactor-baseline.md` | Treating all legacy shapes as permanent could overconstrain the MVP, while removing a live shape could break users. | Identify live clients, public promises, and acceptable versioning or retirement behavior. |
| D-427-07 | Stream contract | Verified | The stream commits a `200` response after its initial `session` event, so provider and runtime failures are later represented as in-band `error` events. | `src/api/routes/query.py` (`stream_query_agent`); `src/agents/service.py` (`stream_agent_response`) | Streaming error semantics differ from the one-shot HTTP error semantics and need explicit compatibility treatment if retained. | Approve the stream contract and characterize real clients' handling of event ordering and in-band errors. |
| D-427-08 | Stream filtering | Verified | Runtime streaming passes only non-empty string chunks from `langgraph_node == "model"` and excludes chunks carrying tool-call fragments. | `src/agents/runtime/react_agent.py` (`AgentRuntime.astream`) | The safety claim depends on a framework node name and chunk shape that could change with an agent-library upgrade. | Pin or test the intended framework behavior after an approved runtime decision. |
| D-427-09 | Data freshness | Verified | Readiness reports a configured snapshot date when the corpus is empty or its freshness query fails. | `src/api/routes/health.py` (`get_data_snapshot_date`); `config/settings.yaml` | A ready response can retain a plausible historical date while the freshness query or expected schema is unavailable. | Approve operational readiness semantics and decide whether freshness is a compatibility promise. |
| D-427-10 | Model coupling | Verified | `query_clean_jobs` builds the SQL-generation model directly, while the runtime factory builds the outer agent model. | `src/agents/tools/query_clean_jobs.py` (`generate_sql`); `src/agents/runtime/factory.py` | Provider configuration and availability influence both tool execution and agent behavior through two construction sites. | Define target model and tool contracts, then measure quality, latency, cost, privacy, and provider failure behavior. |
| D-427-11 | Tracing reachability | Unknown | Langfuse initialization is optional and failure is non-fatal, but no hosted project or trace was inspected. | `src/agents/tracing/langfuse.py`; `render.yaml` | Source instrumentation cannot establish trace completeness, retention, redaction, or the visibility of production failures. | Establish the approved observability and privacy requirements, then perform a controlled environment check. |
| D-427-12 | Evaluation relevance | Verified | The evaluation harness and replay artifacts exercise legacy agent and frozen fixture paths, and the committed replay currently fails `HON-CURRENCY-1` after its fixture is loaded. | `evals/harness.py`; `evals/replay.py`; `evals/scenarios_v1.yaml`; [issue #428](https://github.com/Park-Hip/InternHunterAgent/issues/428) | Historical evidence does not automatically define or validate the future MVP, and the currently failing replay is not a reliable gate. | Resolve #428, then approve observable MVP outcomes and select a traceable evaluation corpus and acceptance criteria. |
| D-427-13 | Deployment equivalence | Declared | Docker Compose, the Render web declaration, CI PostgreSQL services, and external provider configuration represent different topologies. | `docker-compose.yml`; `docker/Dockerfile`; `render.yaml`; `.github/workflows/ci.yml` | A local or CI result may not characterize the hosted service's secrets, database, networking, worker count, or background cron state. | Collect a deployment inventory and approve release and rollback requirements before operations changes. |
| D-427-14 | Documentation authority | Verified | `docs/architecture.md` contains broad claims about legacy behavior and future-facing architecture, while the current maps find unchecked external state and source-level couplings. | `docs/architecture.md`; [current-state-architecture-maps.md](current-state-architecture-maps.md) | Readers can mistake legacy design prose for verified production evidence or a current architectural decision. | Assign authoritative documents after the MVP and target architecture decisions are approved. |

## Cross-check with the Phase 0 inventory

The Phase 0 inventory records the API composition root, service, runtime, tools, tracing adapter, configuration, persistence, ingestion, evaluation, deployment files, and external services.
Each item above maps to one or more of those components.
No new runtime component is introduced by this register.

| Debt item range | Phase 0 component or surface |
| --- | --- |
| D-427-01, D-427-09 | `src/core/db.py`, `src/core/checkpointer.py`, `src/api/routes/health.py`, PostgreSQL |
| D-427-02, D-427-06, D-427-07 | `src/api/app.py`, `src/api/routes/query.py`, schemas, static client |
| D-427-03, D-427-11 | `src/agents/service.py`, `src/agents/tracing/`, Langfuse |
| D-427-04 | `src/core/config.py`, `config/settings.yaml`, ingestion workflow |
| D-427-05 | ingestion service, workflow, recovery script, Render cron |
| D-427-08, D-427-10 | runtime, provider, prompts, query tool |
| D-427-12 | `evals/` and evaluation assets |
| D-427-13 | Docker, Render, CI, PostgreSQL, providers |
| D-427-14 | legacy architecture documentation and every inventoried surface |

## Blocked questions

The following questions remain intentionally unanswered.
They should not be inferred from source declarations.

- Which HTTP, SSE, and browser behaviors have live consumers or contractual commitments?
- Is the Render web service or recovery cron currently enabled, healthy, and owned by an active maintainer?
- Which database URLs, schemas, and data-retention commitments are in use outside local and CI configurations?
- Does any model provider and Langfuse project receive production traffic with the declared settings?
- Which legacy evaluation scenarios express the approved MVP rather than historical corpus behavior?
- Is any collection or recovery operation presently authorized by the data provider and project owner?

## Scope boundary

This register records risks for later decisions.
It does not rank a replacement architecture, authorize characterization tests, or change runtime behavior.
