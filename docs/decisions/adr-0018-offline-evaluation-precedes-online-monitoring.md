# Offline evaluation precedes online monitoring

> **Status:** Active · **Decided:** 2026-07-03

## Context

Score writeback, alerts, and judge infrastructure add cost and complexity before a baseline exists
to compare against.

## Decision

Establish the offline baseline first; production-trace scoring, sampled goldens, judge matrices,
and chart metrics stay out of scope until that baseline exists.

## Consequences

Online monitoring remains explicitly deferred work behind measured evidence.
