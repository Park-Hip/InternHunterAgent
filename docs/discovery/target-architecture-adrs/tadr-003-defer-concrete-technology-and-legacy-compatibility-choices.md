# TADR-003: defer concrete technology and legacy compatibility choices

> **Status:** Deferred by decision.
>
> **Date:** 2026-09-25.
>
> **Decision scope:** Implementation technologies and legacy compatibility for the bounded single-agent MVP.

## Context

The MVP decides the supported workflow and its behavioral boundaries, but it explicitly defers framework, agent-loop, prompt, provider, fallback, tracing, memory, and future multi-agent choices.
Current-state discovery also establishes that legacy JSON routes, SSE behavior, browser behavior, deployment state, corpus contents, external providers, and public consumers are not verified compatibility commitments.
Selecting a concrete technology or preserving a legacy shape in target documentation would create an irreversible or unsupported implementation constraint.

## Decision

The target architecture defines ports and dependency rules without selecting their concrete implementations.
The target makes no promise to preserve, version, retire, or replace legacy JSON routes, SSE events, browser behavior, health endpoints, schema, database, deployment, source-collection path, or operational automation.

A future issue must make one concrete decision only when it has the evidence and scope needed for that decision.
It must record the chosen contract, affected consumers where known, evaluation or operational criteria, rollback path, and any required compatibility or migration plan.
[TADR-004](tadr-004-preserve-legacy-text-delivery-and-operational-baselines.md) is the approved compatibility decision for the existing minimal delivery baseline.

## Consequences

The target can guide package boundaries and capability constraints without choosing LangChain, a ReAct loop, a model provider, a tool library, a database, a cache, Langfuse, another observability service, or a hosting platform.
An implementation issue cannot cite this target as authorization to adopt one of those technologies.
It must instead propose the smallest technology decision that fulfills a confirmed MVP requirement.

The legacy code and documentation remain evidence, not a template for unrelated replacement design.
TADR-004 preserves the existing minimal text-delivery baseline without claiming that unknown consumers prove a broader or permanent compatibility obligation.
A missing consumer inventory blocks a later claim to alter, retire, or expand a public behavior without an explicit owner decision.
A missing data-authority decision blocks corpus acquisition, refresh, ingestion, and source-provider work.

## Alternatives considered

Selecting the current LangChain, DeepSeek, PostgreSQL, Langfuse, Render, JSON, and SSE implementation as the target was rejected.
Current-state source relationships do not establish that those choices are live, suitable for the new MVP, or contractually required.

Declaring a clean replacement API and immediate legacy retirement was rejected.
No evidence identifies deployed consumers or acceptable migration behavior.

Deferring all architecture work until every technology decision is made was rejected.
The MVP needs stable responsibility and capability boundaries before later implementation proposals can be evaluated safely.

## Revisit triggers

Revisit this ADR when a bounded implementation proposal needs one of the following:

- A change to the public delivery baseline, with confirmed consumers where available or an explicit owner decision.
- A persistent corpus and evidence adapter with retention, migration, and rollback requirements.
- A model-agent runtime with measurable capability, reliability, privacy, and evaluation requirements.
- An observability adapter with privacy, redaction, retention, and non-blocking failure requirements.
- Deployment or data-operations work with verified ownership and external-write authority.

## References

- [MVP specification](../mvp-spec.md)
- [Current-state debt register](../current-state-debt-register.md)
- [Characterization-evidence matrix](../characterization-evidence-matrix.md)
- [Target-architecture ADR index](README.md)
