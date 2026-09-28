# Ingestion gate register

> **Last verified:** 2026-09-28
>
> **Eviction:** A row leaves this register when its source is retired. A deferral leaves when its
> re-entry trigger fires. The whole register leaves when a `source_authorizations` record in the
> evidence schema can answer these questions from data rather than from prose, which is scoped to
> [#478](https://github.com/Park-Hip/InternHunterAgent/issues/478).

This is the live record of which source may be collected from.
The gate *definitions* live in
[ADR-0056](../decisions/adr-0056-ingestion-gate.md) and never change.
This file changes; that one does not.

## The three questions, answered

| Question | Answer |
| --- | --- |
| Who authorizes collection from a given source? | The project maintainer, who is the named gate owner and the only approver of a row change. |
| Against which named gates? | G1 Authorization, G2 Retention and spend, G3 Identity, G4 Raw integrity, G5 Field provenance, as defined in [ADR-0056](../decisions/adr-0056-ingestion-gate.md). |
| Which are currently unmet? | Nine of the ten rows below. Only VietnamWorks G1 is met, and only for automated access. **No source other than VietnamWorks may be collected from today, and no Bright Data collection is authorized at all.** |

## How to read a row

| Status | Meaning |
| --- | --- |
| **Met** | The evidence named in the "Evidence held" cell exists, is recorded, and the owner approved it. |
| **Not met** | That evidence does not exist. This is the normal state of a new source, not a defect. |

Every **Not met** row states why, in its own words.
A row with no reason is an incomplete row and is treated as **Not met**.

An HTTP success, a robots permission, public visibility, an active provider account, an issue
state, or a count of returned records never moves a row.
See the evidence rule in
[ADR-0056](../decisions/adr-0056-ingestion-gate.md#the-evidence-rule).

## Gate state

Rows are one per source per gate, so adding a source is a new row set rather than a rewrite of this
file.

| Source | Gate | Status | Evidence required | Evidence held | As of |
| --- | --- | --- | --- | --- | --- |
| `vietnamworks` | G1 Authorization | **Met** | A reviewed authorization record naming acquisition, fields, retention, and revocation. | [ADR-0034](../decisions/adr-0034-vietnamworks-robots-and-terms-gate.md), human review ratified 2026-08-13 and amended 2026-09-27, for automated access only, with the per-run fail-closed robots preflight on the exact API host retained. The ToS section 7 republishing question is a separate display concern and stays in [#137](https://github.com/Park-Hip/InternHunterAgent/issues/137). | 2026-09-28 |
| `vietnamworks` | G2 Retention and spend | **Not met** | A recorded retention representation and period, plus a spend ceiling. | Nothing. The retained corpus has no recorded retention period, no retention representation, and no project spend ceiling. How long `raw_jobs` evidence may be kept is currently unrecorded even though the rows are kept indefinitely. | 2026-09-28 |
| `vietnamworks` | G3 Identity | **Not met** | Golden records proving a source listing key stays stable within the source, and that no two source keys merge. | Nothing. No golden identity record exists. The `(source, external_id)` unique constraint is a schema guard, not evidence of stability. | 2026-09-28 |
| `vietnamworks` | G4 Raw integrity | **Not met** | A retained artifact chain a maintainer can walk from an agent-visible value to a digest. | Nothing. `raw_jobs` stores `raw_payload` and `content_hash`, but no media type, no retention disposition, no authorization revision, and no observation link, so no artifact chain exists to walk. | 2026-09-28 |
| `vietnamworks` | G5 Field provenance | **Not met** | A provenance record per populated field. | Nothing. No provenance record exists for any field of any listing. | 2026-09-28 |
| Bright Data / LinkedIn | G1 Authorization | **Not met** | A reviewed authorization record naming acquisition, fields, retention, and revocation. | Nothing. The eligibility register in [#423](https://github.com/Park-Hip/InternHunterAgent/issues/423) excluded this candidate pending compliance review, and no candidate is currently eligible. A required maintainer action is also outstanding, recorded in the Bright Data G2 row; until that action is closed this row cannot read met. | 2026-09-28 |
| Bright Data / LinkedIn | G2 Retention and spend | **Not met** | A recorded retention representation and period, plus a spend ceiling. | Nothing. No retention rule, no retention period, and no spend ceiling are recorded. **Required maintainer action, open:** revoke the Bright Data API key reported as exposed in the [#423](https://github.com/Park-Hip/InternHunterAgent/issues/423) spike comment, rotate it, and confirm the exposed key serves no valid request. The exposed key must never be reused. | 2026-09-28 |
| Bright Data / LinkedIn | G3 Identity | **Not met** | Golden records proving a source listing key stays stable within the source, and that no two source keys merge. | Nothing. The #470 observation saw `job_posting_id` distinct across ten records in one snapshot, which says nothing about stability across time. | 2026-09-28 |
| Bright Data / LinkedIn | G4 Raw integrity | **Not met** | A retained artifact chain a maintainer can walk from an agent-visible value to a digest. | Nothing. The #470 handoff body exists as a measurement with a digest, but it is not a retained artifact under any authorization, and no artifact record exists. | 2026-09-28 |
| Bright Data / LinkedIn | G5 Field provenance | **Not met** | A provenance record per populated field. | Nothing. The #470 observation recorded that `country_code` was null in all ten records despite an echoed `country: VN` filter, so record-level country provenance is absent. No provenance record exists. | 2026-09-28 |

### Reading of the current state

Nine of ten rows are **Not met**, and that is the accurate state rather than a documentation debt.
`vietnamworks` G1 being met is what keeps the existing narrow manual ingestion path authorized under
[ADR-0034](../decisions/adr-0034-vietnamworks-robots-and-terms-gate.md).
It does not authorize a second source, a provider, or a schedule.

That row needs its basis stated precisely, because it is the only met row and the evidence rule
forbids a robots permission from satisfying G1.
It is met on ADR-0034's **recorded human terms and robots review**, ratified 2026-08-13 and amended
2026-09-27, which is a reviewed authorization record and therefore exactly what G1 requires.
It is not met on the robots permission itself, and not on the per-run preflight: the preflight is how
the review is enforced on each attempt, and enforcement is not authority.

The Bright Data G1 row is why
[#478](https://github.com/Park-Hip/InternHunterAgent/issues/478) and its Slice 2 successor may be
implemented, reviewed, and merged while no Bright Data collection is authorized.
The adapter is built; the run is not taken.
An adapter that has never been authorized to run is testable, and a register row that reads met on
the strength of a working adapter is exactly what the evidence rule forbids.

## Required maintainer actions

| Action | Owner | Blocks | Status |
| --- | --- | --- | --- |
| Revoke and rotate the Bright Data API key reported as exposed in the [#423](https://github.com/Park-Hip/InternHunterAgent/issues/423) spike comment, and confirm the exposed key serves no valid request. | Gate owner | Bright Data G1 | Open |

## What this register does not do

- It does not authorize a schedule. The `schedule:` trigger stays removed under
  [ADR-0053](../decisions/adr-0053-frozen-data-portfolio-release.md).
- It does not authorize publishing evidence into `clean_jobs`. That is a separate cutover decision.
- It does not select a source or a provider. Bright Data remains a characterized candidate, and
  LinkedIn remains a claimed origin platform supported only by the returned URL host.
- It does not change when a slice lands. A slice records evidence; only the owner moves a row.
- It does not replace the per-run VietnamWorks robots preflight, which remains the operational
  access check on every attempt.

## Deferral register

Work that is deliberately outside the current milestone, with the condition that pulls it back.
A deferral is only honest if the trigger is written down.

| ID | Deferred | Re-entry trigger |
| --- | --- | --- |
| D1 | Remaining blueprint records: `sources`, `source_authorizations`, `collection_run_scopes`, `normalized_listings`, and projection lineage. | The first cutover decision. |
| D2 | Semantic mapping for `technical_seniority` and `leadership_scope`. Both stay first-class `unknown`. | An authorized corpus of at least 50 records, per the [#461](https://github.com/Park-Hip/InternHunterAgent/issues/461) decision. |
| D3 | Neon-branch rehearsal and legacy-row labelling. | The first write path beyond shadow. |
| D4 | Shadow projection, delta report, and controlled publication. | A clean shadow run, then its own approved cutover issue. |
| D5 | Cron re-activation and the ADR-0053 reversal. | One manual and one scheduled run on a provider-authorized path, then the [cron activation runbook](../how-to/cron-activation-runbook.md). |
| D6 | Repeat of the compatibility queries through the least-privilege `AGENT_DATABASE_URL` role. The 2026-09-27 baseline used the database-owner connection. | The D3 rehearsal. |
| D7 | Legacy debt sweep: `max_jobs` re-measure, truncation signal, `expired_count` counter, and `data_snapshot_date` drift. | The next VietnamWorks configuration change. The `expired_count` item folds into the lifecycle-attribution slice. |
| D8 | Housekeeping: the uncommitted `docs/refactor/` refresh, stray root files, and a local `main` behind `origin/main`. | A separate housekeeping pull request. |

## How a row changes

1. A slice or a measurement produces the evidence named in the "Evidence required" cell.
2. The evidence is recorded somewhere a reviewer can walk to: a decision record, a migration, a
   retained artifact, a fixture, or a measurement document.
3. The gate owner moves the row and updates its date.
4. Nothing else in the repository is edited to reflect the change.

A row is never moved on the strength of a description.
The evidence cell is a pointer, not a summary.
