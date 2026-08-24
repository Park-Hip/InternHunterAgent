# The judge runs on a provider that does not serve the agent

> **Status:** Active · **Decided:** 2026-07-03

## Context

Judging on the serving provider doubles pressure on its quota and lets a provider judge its own arm.

## Decision

Gemini judges; the serving side (DeepSeek since ADR-0045) is always a different provider.
The separation holds regardless of which provider serves.

## Consequences

Evaluation load stays off the serving account; no provider grades its own output.
