# Frozen replays retain evidence, not per-turn telemetry

> **Status:** Superseded by ADR-0066 · **Decided:** 2026-08-17

## Decision

A committed replay keeps source artifact name and run id, questions, answers, called tools,
generated SQL, and expected deterministic outcomes.
It excludes per-turn latency, token usage, finish reasons, tool output, and every trace identifier.
The freeze refuses captures carrying live trace identifiers or missing a prompt version.

## Consequences

Replays reproduce fixture-bound verdicts without broadening sanitization obligations; aggregate cost
and latency live in dated arm records.

## Superseded

[ADR-0066](adr-0066-evaluation-is-the-baseline-and-the-sql-guard-gate.md) deletes the replays and the
capture runner that wrote them.
The part that still applies is saved-run evidence: a milestone baseline run stores the generated SQL
and its prompt hashes so it can be re-scored without a model call.
