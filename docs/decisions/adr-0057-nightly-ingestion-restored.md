# Nightly VietnamWorks ingestion is restored

> **Status:** Active · **Decided:** 2026-10-07

## Context

ADR-0053 shipped the demo as a frozen-data portfolio release and removed the scheduled
ingestion trigger, because scheduled runs then failed closed at the VietnamWorks robots gate.
Under ADR-0034 as amended on 2026-09-27, the API host's HTTP 404 robots response is a reviewed,
permitted absence, and the run proceeds.

## Decision

`.github/workflows/ingestion.yml` runs nightly at 02:00 UTC and keeps `workflow_dispatch`.
The path was proven in order: dispatch runs 36299600573 (2026-09-27) and 37318661030
(2026-10-05), then the first scheduled run 37436366175 (2026-10-06), all green.

If a scheduled run fails closed for any reason other than a row-level data rejection (config
load, schema drift, a robots policy that is no longer absent, the yield floor, or the job timeout),
the `schedule:` trigger is removed the same day and the failure is recorded.

## Consequences

ADR-0053 is superseded. The corpus is refreshed nightly, and `/api/v1/ready` reports the measured
date of the latest load.
Results still do not establish that a posting is currently open: lifecycle data stays hidden from
the agent under ADR-0021, and rows accumulate rather than being deleted.
The GitHub 60-day inactivity auto-disable applies to the schedule again, so the Render recovery
job (`scripts/recover_ingestion_workflow.py`) is in scope.