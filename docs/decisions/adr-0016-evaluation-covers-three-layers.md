# Evaluation covers outcome, trajectory, and component layers

> **Status:** Active · **Decided:** 2026-07-03

## Context

A single end-to-end score cannot distinguish task failure, unsafe reasoning, and component
regressions.

## Decision

The evaluation stack covers all three layers: outcome (task completion), trajectory (tool routing
and SQL generation), and component (deterministic internals).

## Consequences

Failures localize: a wrong answer with correct tool calls reads differently from a routing failure.
See [../how-to/evaluate.md](../how-to/evaluate.md).
