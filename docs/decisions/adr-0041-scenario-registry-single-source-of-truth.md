# The scenario registry is the single source of truth for evaluation cases

> **Status:** Active · **Decided:** 2026-08-12

## Decision

`evals/scenarios_v1.yaml` owns the cases, their probe flags, reference SQL, and tool expectations.
Goldens are generated from it, ending probe-flag drift structurally.
The 29-scenario set is kept as authored: coverage is audited, not re-authored.

## Consequences

Every documented scenario id is a reference into the registry (enforced by the docs linter);
grading rules and expectations change there, not in prose.
