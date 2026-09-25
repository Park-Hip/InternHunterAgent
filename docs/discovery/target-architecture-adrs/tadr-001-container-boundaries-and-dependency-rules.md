# TADR-001: container boundaries and dependency rules

> **Status:** Decided for the proposed target architecture.
>
> **Date:** 2026-09-25.
>
> **Decision scope:** Bounded single-agent MVP only.

## Context

The active MVP requires exactly one bounded, read-only model agent that chooses registered deterministic tools as needed.
The legacy system combines delivery, runtime construction, persistence, and tracing concerns in ways that cannot define the target structure.
The target needs stable seams without selecting an agent framework, delivery protocol, persistence implementation, or observability vendor.

## Decision

The target has six logical boundaries:

1. Delivery through an API adapter.
2. One-turn orchestration through a frequency-analysis application service.
3. Model-mediated tool selection through a bounded model-agent runtime.
4. Validation, deterministic analysis, and evidence retrieval through registered deterministic tools.
5. Fixed-corpus and retained-evidence reads through a read-only data port.
6. Optional telemetry through an observability adapter.

Dependencies point from delivery to application, application to agent runtime, agent runtime to registered tools, and tools to the corpus and evidence port.
Observability receives one-way domain telemetry events and cannot influence a functional result.
The composition root is the only place allowed to bind concrete adapters to these boundaries.

## Consequences

The API layer does not construct an agent, query a corpus, or import agent-framework types.
The application service does not import transport, persistence, provider, or tracing SDK types.
The agent runtime has no direct corpus, evidence, web, shell, or persistence capability.
Tools cannot invoke a model or return a transport response.
The data port has no dependency on request handling or agent behavior.

A framework, storage, provider, or tracing implementation can be replaced at its adapter boundary without changing the domain contracts.
A future implementation must make the dependency rules observable in its package structure and tests.

## Alternatives considered

A single service that owns request parsing, model construction, data reads, and response formatting was rejected.
It would make the single-agent contract depend on convention rather than on capabilities enforced by boundaries.

A fixed deterministic workflow with no model-mediated tool selection was rejected.
It would not satisfy the MVP requirement that one model agent decides whether and which registered tools to invoke.

A direct model-to-database or model-to-web integration was rejected.
It would allow factual authority and scope enforcement to escape deterministic, inspectable operations.

## Deferred decisions

The concrete API protocol, agent framework, tool library, corpus store, evidence store, tracing implementation, and deployment topology remain deferred.
They must be selected through a narrower decision that preserves these dependency rules.

## References

- [MVP specification](../mvp-spec.md)
- [Target architecture](../target-architecture.md)
- [Boundary-contract ledger](../boundary-contract-ledger.md)
- [Current-state architecture maps](../current-state-architecture-maps.md)
