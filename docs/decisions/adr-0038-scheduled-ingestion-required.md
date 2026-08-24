# Scheduled ingestion is a required MVP capability, not an optional refresh

> **Status:** Active · **Decided:** 2026-08-12

## Decision

A hand-loaded static corpus does not satisfy the MVP: the nightly VietnamWorks schedule must be
active and observed before the v1.0.0 tag is cut.
Every activation gate is release-blocking, including the terms posture that gates rearming the
schedule.

## Consequences

The currently paused schedule (manual workflow dispatch only) leaves the demo below specification;
activation follows the cron activation runbook and is tracked through GitHub Issues.
