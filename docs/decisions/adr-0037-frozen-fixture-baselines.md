# Evaluation baselines freeze fixture data with the agent-visible contract

> **Status:** Active · **Decided:** 2026-07-03 · **Reaffirmed:** 2026-10-26 by [ADR-0066](adr-0066-evaluation-is-the-baseline-and-the-sql-guard-gate.md)

## Context

Baseline comparisons are meaningless when the underlying data moves between runs.

## Decision

Baseline evaluation uses the frozen agent-visible schema and seeded fixture data together,
versioned with the scenarios, so prompt changes are measured independently of corpus churn.

## Consequences

Changing the fixture changes the baseline; honesty scenarios can assert exact counts and truncation
notices.

## What still holds after ADR-0066

The seeded 24-row fixture and the frozen production snapshot still fix the data a measurement reads.
The scenario registry they were once versioned with is deleted, so the baseline dataset and its
snapshot manifest carry that role now.
