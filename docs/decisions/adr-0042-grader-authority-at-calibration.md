# Grader authority passes from human to grader at calibration

> **Status:** Superseded by ADR-0066 · **Decided:** 2026-08-12

## Decision

During calibration the human label wins and assertions are amended.
After calibration the grader wins and each disagreement becomes a new labeled case.
Where a structural check and the judge disagree, the structural check wins.
Holdout assertions are authored without reference to recorded answers - they prove contracts, never
empirical calibration.

## Consequences

Post-calibration grader disagreements feed the registry instead of being hand-waved; known phrasing
noise has its own tracking issues.

## Superseded

[ADR-0066](adr-0066-evaluation-is-the-baseline-and-the-sql-guard-gate.md) deletes the calibration
corpus and the judge, so there is no handoff to administer.
Reviewed reference SQL and result sets are the authority the baseline scores against.
