# Characterization-evidence matrix

> **Last verified:** 2026-09-24 at commit `4d6f00e`.
>
> **Purpose:** This matrix identifies legacy behaviors that may need future characterization evidence after the MVP specification and compatibility posture are approved.
>
> **Decision status:** This is not a test plan authorization.
> No test is added or implied by [issue #427](https://github.com/Park-Hip/InternHunterAgent/issues/427).

## How to use this matrix

A row states why an observed behavior may matter and what evidence exists today.
`Existing automated evidence` means a named test surface exists in the repository.
It does not mean that the behavior has been observed in production or that it is an approved future contract.

A future issue should select only rows required by an approved MVP or confirmed compatibility obligation.
It must define the test environment, oracle, fixtures, and owner before adding characterization tests.

| ID | Behavior candidate | Source evidence | Existing automated evidence | Evidence confidence | Why future characterization may be needed | Preconditions before proposing a test |
| --- | --- | --- | --- | --- | --- | --- |
| C-427-01 | One-shot chat accepts a non-blank request and returns an answer with a server-managed session id. | `src/api/routes/query.py` (`query_agent`); `src/agents/service.py` (`generate_agent_response`); `src/api/schemas.py` | `tests/api/test_query.py`; `tests/api/test_conversation.py` | Source and automated legacy evidence | A retained HTTP client may depend on field names, session creation, or safe fallback behavior. | Approved MVP interaction and confirmed HTTP compatibility boundary. |
| C-427-02 | Blank one-shot and streaming queries return HTTP 400 before agent execution. | `src/api/routes/query.py` (`query_agent`); `src/api/routes/query.py` (`stream_query_agent`) | `tests/api/test_query.py`; `tests/api/test_stream.py` | Source and automated legacy evidence | Input validation can be visible to clients and prevents unnecessary model work. | Approved input contract and error-response policy. |
| C-427-03 | One-shot provider pressure maps to a safe HTTP 429, while unclassified failures map to a safe HTTP 500. | `src/api/routes/query.py`; `src/core/errors.py` | `tests/api/test_query.py` | Source and automated legacy evidence | Client retry behavior may distinguish status codes and messages. | Approved HTTP error and retry semantics. |
| C-427-04 | A stream begins with `session`, sends token and optional metadata events, and ends with `done`. | `src/agents/service.py` (`stream_agent_response`); `src/api/routes/query.py` (`stream_query_agent`) | `tests/api/test_stream.py` | Source and automated legacy evidence | Browser and external SSE clients can depend on event names and ordering. | Confirmed SSE consumer inventory and approved stream contract. |
| C-427-05 | A post-start stream failure is delivered as an in-band `error` event followed by `done`. | `src/agents/service.py` (`stream_agent_response`); `src/api/schemas.py` (`StreamErrorResponse`) | `tests/api/test_stream.py` | Source and automated legacy evidence | This differs from one-shot error delivery and is a likely compatibility edge. | Confirmed SSE compatibility requirement and approved retry policy. |
| C-427-06 | The stream emits heartbeats during a silent runtime period and cancels work when the client disconnects. | `src/api/routes/query.py` (`_with_heartbeats`); `src/api/routes/query.py` (`_DisconnectLoggingEventSourceResponse`) | `tests/api/test_stream.py`; `tests/api/test_stream_disconnect.py` | Source and automated legacy evidence | Proxy idle timeouts and resource cleanup are operational behavior, not merely presentation. | Approved serving topology and stream availability requirements. |
| C-427-07 | Streaming excludes non-model node output and chunks carrying tool-call metadata. | `src/agents/runtime/react_agent.py` (`AgentRuntime.astream`) | `tests/api/test_stream.py`; runtime stream tests under `tests/agents/` | Source plus partial automated evidence | The rule limits exposure of tool output, SQL, and agent internals if streaming remains public. | Approved runtime, framework version, and disclosure boundary. |
| C-427-08 | `query_clean_jobs` generates SQL, validates it, applies row bounds, queries the corpus, and returns safe tool text. | `src/agents/tools/query_clean_jobs.py`; `src/services/query/sql_validator.py`; `src/services/query/row_bound.py` | `tests/agents/tools/test_query_clean_jobs.py`; `tests/services/query/test_sql_validator.py`; `tests/services/query/test_row_bound.py` | Source and automated legacy evidence | A future data analysis path may need a different contract, but validated read behavior is a material safety baseline. | Approved data model, analysis requirements, and safety policy. |
| C-427-09 | A query tool can return safe handling for rejected SQL, missing columns, and database execution errors. | `src/agents/tools/query_clean_jobs.py` | Query-tool and query-service test surfaces | Source plus automated legacy evidence | Honest failure behavior may be an MVP requirement even if the query mechanism changes. | Approved user-facing honesty and error behavior. |
| C-427-10 | Conversation state is keyed by `session_id` and LangGraph checkpointer setup uses `DATABASE_URL`. | `src/agents/runtime/react_agent.py`; `src/core/checkpointer.py`; `src/api/app.py` (`lifespan`) | `tests/api/test_conversation.py`; checkpointer and runtime test surfaces | Source and automated legacy evidence | Session continuity and restart behavior are externally meaningful only if retained by the MVP. | Approved session, privacy, retention, and persistence requirements. |
| C-427-11 | `/health` is process-only, while `/ready` probes the database and reports a freshness value or fallback. | `src/api/routes/health.py`; `render.yaml` | Readiness and startup test surfaces under `tests/api/` | Source plus automated legacy evidence | Health semantics affect deployment automation and user-visible availability claims. | Approved operational readiness and freshness semantics. |
| C-427-12 | Settings load from environment and YAML, with startup validation for streaming and tracing configuration. | `src/core/config.py`; `config/settings.yaml` | `tests/core/test_config.py`; `tests/api/test_startup_config.py` | Source and automated legacy evidence | The future runtime needs a clear and minimal configuration boundary. | Approved deployment, provider, and persistence choices. |
| C-427-13 | The checked configuration selects DeepSeek for both serving and SQL generation, while the code retains Groq branches. | `config/settings.yaml`; `src/agents/runtime/provider.py` | `tests/agents/runtime/test_provider.py` | Source and automated legacy evidence | A provider switch affects quality, timing, failure behavior, privacy, and cost. | Approved capability metrics and provider-selection decision. |
| C-427-14 | Tracing is non-fatal and request or evaluation code can attach Langfuse context when initialized. | `src/agents/tracing/langfuse.py`; `src/agents/runtime/react_agent.py`; `evals/harness.py` | `tests/agents/test_langfuse_lifecycle.py`; `tests/agents/test_langfuse_tracing.py` | Source and automated legacy evidence | Observability may need a reliability and redaction contract rather than an implementation-specific assertion. | Approved observability, privacy, and incident-response requirements. |
| C-427-15 | The manual ingestion workflow can run the loader, and recovery automation may dispatch that workflow. | `.github/workflows/ingestion.yml`; `render.yaml`; `scripts/recover_ingestion_workflow.py` | `tests/test_ingestion_workflow_frozen.py`; `tests/scripts/test_recover_ingestion_workflow.py`; ingestion tests | Source and automated legacy evidence | This is an external write path with compliance and data-quality implications. | Provider-authorized data strategy and separately approved operations change. |
| C-427-16 | CI runs static checks, the test suite, fixture loading, replay, and migration validation. | `.github/workflows/ci.yml`; `pyproject.toml` | CI itself and named test surfaces | Source configuration evidence | Future gates must distinguish legacy regression signals from validated MVP outcomes. | Approved MVP acceptance criteria and evaluation strategy. |
| C-427-17 | Legacy evaluations construct the agent with fixtures, scenarios, replay artifacts, deterministic graders, and optional remote trace writeback. | `evals/harness.py`; `evals/driver.py`; `evals/replay.py`; `evals/scenarios_v1.yaml` | `tests/evals/` | Source and automated legacy evidence | Some harness seams may be reusable, but scenario meaning depends on the legacy corpus and agent behavior. | Approved MVP scenarios, corpus authority, and measurement rubric. |
| C-427-18 | Render declares a one-worker Docker web service and a separate recovery cron, while Compose and CI use local PostgreSQL topologies. | `render.yaml`; `docker/Dockerfile`; `docker-compose.yml`; `.github/workflows/ci.yml` | Startup and migration tests are indirect only | Declared deployment evidence | Production behavior can diverge from local and CI behavior in secrets, process count, network, and external services. | Verified service inventory plus approved release, rollback, and operations requirements. |

## Evidence gaps that cannot be filled by unit tests alone

The following require controlled environment or stakeholder evidence rather than only code-level characterization.

| Gap | Why unit tests are insufficient | Required evidence owner or source |
| --- | --- | --- |
| Live API and SSE consumers | Tests cannot reveal who depends on deployed endpoints. | Product and service owner, access logs, and client inventory. |
| Render service and cron state | Repository YAML does not prove the state of the Render dashboard. | Deployment owner and Render inspection. |
| Data-provider authority and source terms | Mocked ingestion tests do not establish permission to collect or retain data. | Data owner, provider authorization, and compliance review. |
| Provider availability, quality, latency, and cost | Fakes do not represent production models, quota, or pricing. | Approved measurement plan and controlled provider evaluation. |
| Langfuse ingestion, retention, and redaction | Local mocks do not prove hosted delivery or project policy. | Observability owner and controlled hosted-environment check. |
| Database contents, retention, and schema state | Fixture databases are not the deployed corpus. | Data owner and controlled database inventory. |

## Minimum content for a future characterization proposal

A future issue that chooses one or more rows must state the approved behavior being preserved or measured.
It must name the test environment, inputs, deterministic oracle or manual observation, and cleanup procedure.
It must identify any required credentials, data classification, and external writes.
It must keep unapproved legacy behavior out of scope rather than translating this entire matrix into tests.

## Scope boundary

The matrix records candidate evidence only.
It does not establish a public compatibility promise, a target architecture, an evaluation standard, or permission to touch external services.
