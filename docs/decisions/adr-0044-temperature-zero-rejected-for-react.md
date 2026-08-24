# Temperature 0 is rejected for the ReAct seam

> **Status:** Active · **Decided:** 2026-08-12

## Context

Greedy decoding degrades the tool-choice loop for this model family.

## Decision

The ReAct seam keeps tuned sampling values; SQL generation stays at 0.0 where determinism is wanted.
Sampling experiments change one variable at a time and require instrumented evidence.

## Consequences

Multi-variable sampling comparisons remain withdrawn; see the agent profiles in configuration.
