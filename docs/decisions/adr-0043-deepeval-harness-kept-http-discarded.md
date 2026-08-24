# Keep the DeepEval harness, discard its HTTP transport

> **Status:** Active · **Decided:** 2026-08-12

## Decision

DeepEval's instrumentation (LangChain callback and trace manager) stays; its archived HTTP runner
does not - the driver runs the agent in-process.

## Consequences

The three seams are observable through runtime-config injection; no orchestration pattern is
imported from the HTTP runner.
