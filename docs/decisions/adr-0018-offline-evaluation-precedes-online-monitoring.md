# Offline evaluation precedes online monitoring

> **Status:** Active · **Decided:** 2026-07-03 · **Reaffirmed:** 2026-10-26 by [ADR-0066](adr-0066-evaluation-is-the-baseline-and-the-sql-guard-gate.md)

## Context

Score writeback, alerts, and judge infrastructure add cost and complexity before a baseline exists
to compare against.

## Decision

Establish the offline baseline first; production-trace scoring, sampled goldens, judge matrices,
and chart metrics stay out of scope until that baseline exists.

## Consequences

Online monitoring remains explicitly deferred work behind measured evidence.

## What still holds after ADR-0066

The offline baseline is the only evaluation, and it is now the text-to-SQL baseline plus the SQL
guard gate.
Production-trace scoring, sampled goldens, and judge matrices remain out of scope.
