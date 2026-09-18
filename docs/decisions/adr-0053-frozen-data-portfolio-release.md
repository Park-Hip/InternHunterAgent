# Frozen-data portfolio release supersedes the self-refreshing MVP gate

> **Status:** Active · **Decided:** 2026-09-18

## Decision

The public demo ships as a frozen-data portfolio release, not as a claim that the original
self-refreshing v1.0 MVP is complete.
Scheduled ingestion is disabled (`.github/workflows/ingestion.yml` retains only
`workflow_dispatch`), the served corpus is a historical snapshot last measured `2026-08-27`, and the
UI and documentation state plainly that results do not establish current vacancies.

## Consequences

This narrower posture supersedes ADR-0038 for this release: an active schedule is no longer a gate
on tagging the portfolio release.
The HTTP API contract and database schema are unchanged - `/api/v1/ready` still returns the snapshot
date and provenance, and the existing corpus is retained.
Resuming scheduled ingestion requires a provider-authorized path approved, deployed, and proven by
one manual and one scheduled run; the workflow `schedule` trigger, the frozen-data notice, and the
affected documentation are then reverted together.