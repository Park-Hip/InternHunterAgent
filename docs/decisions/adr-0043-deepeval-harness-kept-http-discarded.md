# Keep the DeepEval harness, discard its HTTP transport

> **Status:** Superseded by ADR-0066 · **Decided:** 2026-08-12

## Decision

DeepEval's instrumentation (LangChain callback and trace manager) stays; its archived HTTP runner
does not - the driver runs the agent in-process.

## Consequences

The three seams are observable through runtime-config injection; no orchestration pattern is
imported from the HTTP runner.

## Superseded

[ADR-0066](adr-0066-evaluation-is-the-baseline-and-the-sql-guard-gate.md) deletes DeepEval with the
rest of the legacy harness. The observation it bought is no longer used, and both the dependency
and its instrumentation are gone.
