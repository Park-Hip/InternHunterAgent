# The judge runs on a provider that does not serve the agent

> **Status:** Active · **Decided:** 2026-07-03 · **Reaffirmed:** 2026-10-26 by [ADR-0066](adr-0066-evaluation-is-the-baseline-and-the-sql-guard-gate.md)

## Context

Judging on the serving provider doubles pressure on its quota and lets a provider judge its own arm.

## Decision

Gemini judges; the serving side (DeepSeek since ADR-0045) is always a different provider.
The separation holds regardless of which provider serves.

## Consequences

Evaluation load stays off the serving account; no provider grades its own output.

## What still holds after ADR-0066

No judge runs today: the DeepEval judge was deleted with the legacy harness.
The separation rule still holds if a judge returns, because reusing the serving provider would
fail for the same reasons it failed here.
