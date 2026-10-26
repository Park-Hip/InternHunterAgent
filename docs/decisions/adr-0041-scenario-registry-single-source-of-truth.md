# The scenario registry is the single source of truth for evaluation cases

> **Status:** Superseded by ADR-0066 · **Decided:** 2026-08-12

## Decision

`evals/scenarios_v1.yaml` owns the cases, their probe flags, reference SQL, and tool expectations.
Goldens are generated from it, ending probe-flag drift structurally.
The 29-scenario set is kept as authored: coverage is audited, not re-authored.

## Consequences

Every documented scenario id is a reference into the registry (enforced by the docs linter);
grading rules and expectations change there, not in prose.

## Superseded

[ADR-0066](adr-0066-evaluation-is-the-baseline-and-the-sql-guard-gate.md) deletes the scenario
registry and the docs check that read it.
The principle survives per dataset: `evals/datasets/sql_guard.yaml` owns the gate cases, and
`evals/datasets/baseline.yaml` owns the baseline questions.
