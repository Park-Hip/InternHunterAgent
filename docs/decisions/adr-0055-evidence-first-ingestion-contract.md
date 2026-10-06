# Evidence-first ingestion preserves source evidence before serving projections

> **Status:** Superseded by [ADR-0058](adr-0058-single-source-mvp-ingestion.md) · **Decided:** 2026-09-27

## Context

The deployed data model accumulates one mutable `raw_jobs` row and one mutable `clean_jobs` row per
`(source, external_id)` pair.
The current ingestion run records summary counters, but it does not retain collection scope,
individual observations, raw artifact versions, field provenance, normalization versions, or
quarantine outcomes.
A subsequent provider integration or migration could otherwise overwrite source facts, expire
listings from an incomplete scope, or make a serving value impossible to trace.

The completed source-level semantics research for [issue #461](https://github.com/Park-Hip/InternHunterAgent/issues/461)
shows that a platform level is a source fact, not proof of technical seniority or leadership scope.
The portfolio remains a frozen historical corpus under
[ADR-0053](adr-0053-frozen-data-portfolio-release.md).
No provider has been selected or authorized for new collection.

## Decision

Adopt the provider-neutral evidence-first ingestion contract in
[evidence-first ingestion blueprint](evidence-first-ingestion-blueprint.md).
The future ingestion system records immutable source authority, collection, evidence, observation,
and normalization facts before it derives a serving projection.

A future source-specific listing is a `normalized_listing`.
It has a source-specific identity and is not a cross-source canonical job or vacancy.
Cross-source deduplication is prohibited by this decision.

The contract keeps these semantic dimensions separate:

- `source_level` preserves the exact available source label with field, locale, and vocabulary provenance.
- `technical_seniority` is one of `intern`, `entry`, `junior`, `mid`, `senior`, or `unknown`.
- `leadership_scope` is one of `individual_contributor`, `team_lead`, `people_manager`, `executive`, or `unknown`.

`unknown` is a first-class value and is not replaced with a null, title guess, employer inference,
or a mapping from a source level.
A title match may be retained as non-authoritative, versioned candidate evidence.
It cannot alone populate either semantic dimension.

Every future normalized value must name the raw observation, source field, normalization version,
and collection run that support it.
A failed or incomplete collection run cannot expire an earlier listing.
The existing `clean_jobs` table remains the agent-facing serving projection during a future additive
migration.

Existing `raw_jobs` and `clean_jobs` data is retained as a labelled legacy snapshot.
It is not reattributed as new evidence, a successful collection run, a source authorization, or a
freshness claim.

## Consequences

A future implementation must add schema only through approved additive Alembic revisions.
It must preserve the current `clean_jobs` API, prompts, fixtures, evaluations, and frozen-data
behavior until a separately approved serving-contract change updates them together.

A future source must have a recorded authorization and retention boundary before evidence is kept.
Provider capability, target-site visibility, robots.txt, terms availability, and a successful API
response do not by themselves establish reuse authority.
[ADR-0056](adr-0056-ingestion-gate.md) names the gate that requires that boundary, and the
[ingestion gate register](../refactor/ingestion-gate-register.md) records which gates are currently
met for which source.

The design does not authorize Bright Data activation, account use, credential use, provider
selection, collection, data migration, workflow scheduling, or production deployment.
The gate that must read met before provider-specific mapping or production activation is the
authorization gate in [ADR-0056](adr-0056-ingestion-gate.md), tracked per source in the
[ingestion gate register](../refactor/ingestion-gate-register.md).
The
[minimum executable evidence contract](evidence-first-ingestion-blueprint.md#minimum-executable-evidence-contract)
in the blueprint states that contract at column level.

The read-only legacy compatibility baseline measured on 2026-09-27 is part of the blueprint.
It establishes an inventory for later migration rehearsal, not a freshness claim or a replacement
for raw evidence.

## Alternatives rejected

Keeping only the mutable `raw_jobs` and `clean_jobs` rows was rejected because it loses evidence
versions and cannot distinguish a complete scoped observation from an incomplete fetch.

A provider-shaped schema was rejected because a future provider change would require another data
redesign and could blur the provider's identity with the source listing's identity.

A cross-source canonical-job table was rejected because no approved identity rule, false-merge
measurement, or false-split measurement exists.

Mapping source labels or title words directly to technical seniority or leadership scope was rejected
because the evidence in issue #461 does not support it.

## Rollback

This is a documentation-only decision.
If later evidence invalidates the contract, supersede this record and leave the frozen corpus,
current schema, workflows, and serving behavior unchanged.
Each implementation issue must have its own migration and publication rollback plan.
