# TADR-004: preserve legacy text delivery and operational baselines

> **Status:** Decided.
>
> **Date:** 2026-09-25.
>
> **Decision scope:** Legacy JSON, SSE, browser, liveness, readiness, and deployment-facing delivery surfaces for the bounded single-agent MVP.

## Context

The MVP is an agent that receives a plain-language question, chooses registered read-only tools, and returns a natural-language answer.
The first frequency-analysis question is intentionally a small, testable agent capability rather than a replacement public API design.

The checked source already exposes a minimal delivery contract.
`POST /api/v1/agent/chat` accepts `QueryRequest` with plain-text `query` and returns `QueryResponse` with plain-text `answer`.
`POST /api/v1/agent/chat/stream` accepts the same request and sends SSE `session`, `token`, optional `metadata` or `error`, and terminal `done` events.
The same FastAPI application serves the browser client from the root static mount.
`GET /api/v1/health` returns process liveness, and `GET /api/v1/ready` checks database reachability and returns snapshot-date provenance.
Render declares `/api/v1/health` as its web-service health check.

Source evidence does not identify live consumers, public promises, or the live Render state.
No authorized production traffic, browser, dashboard, or credential inspection was performed for this decision.
The absence of that evidence does not justify a speculative replacement contract when the existing minimal text delivery already supports the MVP.

## Decision

Preserve the existing `/api/v1` JSON and SSE delivery contracts as the MVP baseline.
The MVP continues to accept a plain-text question and return a natural-language text answer through either completed JSON or SSE token delivery.
The agent, its registered tools, the fixed corpus, and answer quality may evolve behind this delivery contract.

Preserve the same-origin browser delivery path as an existing client of those contracts.
This decision does not make the current browser presentation or chat workflow a separately expanded product requirement.

Preserve `/api/v1/health` as the platform liveness endpoint and retain it as the Render health-check path declared in source.
It means that the application process can respond and must not query the corpus, run an agent turn, or depend on model-provider availability.

Preserve `/api/v1/ready` as the current database-readiness and snapshot-provenance endpoint.
It must not be represented as proof that a model provider is available, that the agent can answer every question, that a corpus is current, or that a future fixed corpus has been approved.
The current `configured_fallback` provenance remains distinct from a measured snapshot date.

Do not introduce a new API version, alter delivery paths or payload shapes, remove SSE, remove the browser client, alter health or readiness behavior, or change Render configuration under this decision.
A future proposal may change a surface only when a confirmed product, consumer, or deployment requirement cannot fit this baseline.

## Consequences

Implementation work can focus on the agent's tool choices, tool safety, permitted corpus, and answer quality without an API redesign.
A caller can submit a natural-language question such as "What are the most popular programming languages for AI engineers?" through the current `query` field.
The agent may use only its registered tools to gather facts and return the answer as text through the existing response or SSE-token mechanism.

This decision preserves delivery compatibility, not the current agent runtime, tools, SQL-generation behavior, corpus, provider, session policy, tracing implementation, or deployment topology.
It does not authorize collection, ingestion, external writes, credential changes, or production configuration changes.

The known unknowns remain recorded rather than inferred.
They include live API and browser consumers, active Render state, production provider availability, and whether a future corpus should strengthen readiness semantics.
Because the baseline is preserved, those unknowns do not block the smallest agent implementation.
They become evidence requirements for a later change to a preserved surface.

## Alternatives considered

A specialized frequency-analysis API with required structured request and response fields was rejected.
It would prematurely turn one small test capability into the agent's permanent public contract and would not help the agent receive or answer plain-language questions.

Immediate replacement through a new API version was rejected.
The current versioned plain-text contract already meets the MVP delivery need, while consumer and deployment evidence is unknown.

Retiring JSON or SSE was rejected.
Both transports support the same agent interaction, and neither prevents the agent from choosing tools or returning a text answer.

Treating readiness as a full agent-capability or provider-availability probe was rejected.
A liveness or readiness probe must remain cheap and reliable, and external provider availability should not cause platform restart behavior.

## Revisit triggers

Revisit this decision only when one of the following is true:

- A required agent capability cannot be expressed through a plain-text question and text answer.
- Verified consumer evidence requires a migration, deprecation period, or different delivery behavior.
- A selected browser requirement cannot be met by the preserved client path.
- An approved corpus and tool implementation require a stronger definition of readiness.
- A separately approved deployment change requires a different liveness or readiness path.

## Verification and rollback

The decision is documentation-only.
A maintainer can trace a plain-language request through the existing JSON or SSE contract and confirm that no route, schema, browser, health, readiness, deployment, or external system changed.

Rollback is reverting the documentation-only change that records this decision.
A later decision that supersedes this baseline must state the affected surface, consumer or operational evidence, migration plan, and rollback path.

## References

- [Issue #436](https://github.com/Park-Hip/InternHunterAgent/issues/436)
- [MVP specification](../mvp-spec.md)
- [Target architecture](../target-architecture.md)
- [Current-state architecture maps](../current-state-architecture-maps.md)
- [Characterization-evidence matrix](../characterization-evidence-matrix.md)
- [Current-state debt register](../current-state-debt-register.md)
- [Legacy refactor baseline](../legacy-refactor-baseline.md)
- [TADR-003](tadr-003-defer-concrete-technology-and-legacy-compatibility-choices.md)
