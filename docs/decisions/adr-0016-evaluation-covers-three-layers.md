# Evaluation covers outcome, trajectory, and component layers

> **Status:** Active · **Decided:** 2026-07-03 · **Reaffirmed:** 2026-10-26 by [ADR-0066](adr-0066-evaluation-is-the-baseline-and-the-sql-guard-gate.md)

## Context

A single end-to-end score cannot distinguish task failure, unsafe reasoning, and component
regressions.

## Decision

The evaluation stack covers all three layers: outcome (task completion), trajectory (tool routing
and SQL generation), and component (deterministic internals).

## Consequences

Failures localize: a wrong answer with correct tool calls reads differently from a routing failure.
See [../how-to/evaluate.md](../how-to/evaluate.md).

## What still holds after ADR-0066

Two of the three layers keep an offline measurement.
The baseline scores the outcome layer on generated SQL, while the SQL guard gate pins the validator
and executor boundary and unit tests hold the component contracts.
Tool routing has no offline measurement after the harness deletion; measuring it again is a new
decision with its own evidence.
