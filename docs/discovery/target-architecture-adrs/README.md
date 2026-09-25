# Target-architecture decision records

> **Status:** Proposed discovery ADR set for [issue #434](https://github.com/Park-Hip/InternHunterAgent/issues/434).
>
> **Scope:** These records define the target architecture for the bounded single-agent MVP and identify decisions that future implementation proposals must make.

These discovery ADRs are intentionally separate from the historical records in `docs/decisions/`.
They do not amend legacy operational, provider, source, or deployment choices.
A future approved implementation or compatibility decision may supersede a discovery ADR with a durable project ADR when its scope requires that record.

| Record | Status | Decision |
| --- | --- | --- |
| [TADR-001](tadr-001-container-boundaries-and-dependency-rules.md) | Decided | The MVP uses delivery, application, bounded-agent, deterministic-tool, corpus-and-evidence, and observability boundaries with one-way dependencies. |
| [TADR-002](tadr-002-deterministic-facts-and-evidence-authority.md) | Decided | Registered deterministic tools, not the model agent, own validation, analysis, and evidence retrieval. |
| [TADR-003](tadr-003-defer-concrete-technology-and-legacy-compatibility-choices.md) | Deferred by decision | Concrete technologies and legacy compatibility posture remain unselected until a narrower proposal supplies the required evidence. |

## Decision gates before implementation

An implementation issue may use the target boundaries only after its proposal names the relevant decision gate below.
The issue must not silently select a deferred technology or compatibility posture by its implementation.

| Proposed work | Required prior or same-proposal decision |
| --- | --- |
| Public HTTP, SSE, browser, or health behavior | Compatibility posture, consumer evidence, public request and response contract, error semantics, and versioning or retirement plan. |
| Corpus schema, database, cache, or persistence adapter | Fixed-corpus physical model, retention and access policy, migration plan, and rollback path. |
| Agent framework, tool library, prompt, model, provider, or fallback | Measurable bounded-agent requirements, evaluation cases, privacy and reliability constraints, and a rollback path. |
| Tracing, logs, metrics, or hosted observability integration | Telemetry event contract, privacy and redaction policy, non-blocking failure behavior, retention posture, and operational owner. |
| Tests or evaluation harness | Approved MVP acceptance cases, deterministic fixtures or corpus evidence, oracle, environment, and cleanup policy. |
| Deployment, credentials, or operations | Service ownership, release and rollback plan, actual deployed-consumer inventory where relevant, and external-write safety review. |
| Corpus acquisition, refresh, ingestion, or source selection | Separate data-authority and operations proposal with provider permission, retention, provenance, and external-write controls. |

The target architecture does not itself authorize any row in this table.
