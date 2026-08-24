# Evaluation baselines freeze fixture data with the agent-visible contract

> **Status:** Active · **Decided:** 2026-07-03

## Context

Baseline comparisons are meaningless when the underlying data moves between runs.

## Decision

Baseline evaluation uses the frozen agent-visible schema and seeded fixture data together,
versioned with the scenarios, so prompt changes are measured independently of corpus churn.

## Consequences

Changing the fixture changes the baseline; honesty scenarios can assert exact counts and truncation
notices.
