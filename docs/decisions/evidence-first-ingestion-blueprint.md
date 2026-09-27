# Evidence-first ingestion blueprint

> **Status:** Approved design for [issue #455](https://github.com/Park-Hip/InternHunterAgent/issues/455).
>
> **Last verified:** 2026-09-27
>
> **Eviction:** This blueprint leaves when approved implementation records replace every proposed
> entity, migration phase, and acceptance gate with an executable contract.

## Purpose and boundary

This blueprint defines the future provider-neutral data contract before a provider integration or
legacy-data migration.
It is documentation only.
It does not authorize collection, provider selection, source authorization, account activation,
credential use, retention of new job data, schema migration, workflow changes, or production use.

The design applies the conservative semantic boundary in
[source-level semantics decision](../discovery/research/source-level-semantics-decision.md).
A `normalized_listing` represents one source-specific listing.
It is not a canonical job, vacancy, or cross-source grouping.

The existing `clean_jobs` table remains the single-table agent-facing serving projection during a
future migration.
The frozen portfolio posture in [ADR-0053](adr-0053-frozen-data-portfolio-release.md) remains
unchanged.

## Contract rules

1. Evidence and observations are append-only facts.
2. A derived record names the evidence, collection run, and version that produced it.
3. A source-specific listing identity is unique only within its declared source.
4. A missing source field is distinct from an observed empty value, a failed extraction, and an
   unsupported field.
5. A successful HTTP response is not proof of authorized collection, complete scope, or listing
   availability.
6. Only a completed run whose declared coverage is complete may cause a lifecycle transition.
7. A serving projection is rebuildable from retained evidence and approved normalization results.
8. Legacy rows remain labelled legacy facts and are never reclassified as new source evidence.
9. Cross-source deduplication is out of scope and prohibited.
10. A future implementation must make every state transition idempotent.

## Proposed records

The names below are future schema concepts, not authorization to create tables in this issue.
All identifiers are immutable surrogate identifiers unless a column is explicitly an immutable
business key.

| Record | Immutable business key or identity | Required facts | Prohibited interpretation |
| --- | --- | --- | --- |
| `sources` | A stable source identifier. | Source display name, source listing namespace, operator or provider relationship, and creation provenance. | A provider identifier is not automatically the source of a listing. |
| `source_authorizations` | Authorization revision and effective interval. | Applicable source, allowed acquisition method, permitted fields, retention rule, evidence reference, reviewer, and revocation state. | Robots, public visibility, or a provider response is not authorization. |
| `collection_plans` | Versioned plan identifier. | Authorized source, declared query or feed scope, expected coverage, pagination and completion rule, requested fields, and version. | A plan does not assert that its run completed. |
| `collection_runs` | Immutable run identifier and idempotency key. | Plan version, start and finish time, execution result, coverage result, request and response counters, failure category, and configuration digest. | A successful process exit does not imply complete coverage. |
| `collection_run_scopes` | Run plus scope-part identity. | Declared scope partition, expected cursor or page boundary, observed boundary, completion state, and omission reason. | An unobserved partition is not evidence that listings disappeared. |
| `raw_artifacts` | Content digest plus retention representation version. | Byte or approved redacted representation, digest, media type, acquisition timestamp, retention disposition, and authorization revision. | A digest alone is not raw evidence if no authorized representation remains. |
| `raw_observations` | Observation identifier with delivery idempotency key when supplied. | Source listing key, artifact reference, collection run and scope references, retrieval time, source URLs, and source-field presence map. | The latest observation does not erase an earlier observation. |
| `normalization_results` | Observation plus normalization version and attempt number. | Outcome, output digest, rule version, field-level provenance, warnings, quarantine reason, and evaluator metadata. | A successful normalization is not a truth claim beyond its cited source fields. |
| `normalized_listings` | Source identifier plus source listing key. | Stable source identity and links to the selected successful normalization result and latest eligible observation. | Equal titles, employers, or URLs from different sources are not one listing. |
| `clean_jobs` projection | Existing `(source, external_id)` compatibility key. | Current agent-visible legacy shape and source-to-projection lineage. | The projection is not the evidence system of record. |

A source listing key is the source or provider identifier that names a listing within the declared
source namespace.
When a provider returns a provider identifier and a source identifier, both are retained with their
field meaning rather than choosing one by assumption.

## Field and provenance contract

Every populated future field has a field-level provenance record with these facts:

| Provenance fact | Requirement |
| --- | --- |
| Output field | Names the normalized or projection field. |
| Source field | Names the original field path and locale when known. |
| Observation | Links to the exact raw observation and artifact digest. |
| Rule version | Names the deterministic normalizer, vocabulary, or reviewed mapping version. |
| Transform | States copy, parse, normalize, derive, or unavailable. |
| Value state | Distinguishes present, source-empty, source-missing, invalid, unavailable, and unknown. |
| Review status | States automatic, reviewed, quarantined, or superseded. |

The following mapping is the minimum future compatibility map.
It does not claim that every source can supply every field.

| Current field or concept | Future source fact | Normalization rule | Null or unknown rule | Projection rule |
| --- | --- | --- | --- | --- |
| `source` | `source_id` and source namespace. | Copy the declared source identity. | Missing source identity quarantines the observation. | Preserve the legacy source value only for a declared compatible source. |
| `external_id` | Source listing key and provider listing key when distinct. | Copy without cross-source reconciliation. | Missing stable listing key quarantines the observation. | Preserve only the compatible source listing key. |
| `source_url` | Source URL with field meaning. | Copy and retain the original field path. | Missing is source-missing, not an invalid URL claim. | Copy when the legacy projection supports it. |
| `title` and `company` | Source display text. | Preserve text plus locale and source field path. | Empty required display text quarantines a future publishable listing. | Copy only after successful normalization. |
| `description` | Source description and permitted representation. | Preserve or transform with a versioned text rule. | Missing is source-missing. | Populate only from an authorized retained representation. |
| `role`, `tech_stack`, and `location` | Source facts and candidate normalized values. | Use reviewed versioned rules with field provenance. | Unsupported or low-quality output is unavailable or quarantined. | Do not overwrite legacy values without a separate projection rule. |
| `job_level` | Exact `source_level` label. | Copy verbatim with source, field, locale, and vocabulary provenance. | Missing remains source-missing. | Do not reinterpret the legacy field as seniority. |
| Technical seniority | `technical_seniority`. | Populate only from an explicit source field or a later measured, approved rule. | Use first-class `unknown` otherwise. | It is not added to the frozen projection in this issue. |
| Leadership scope | `leadership_scope`. | Populate only from an explicit source field or a later measured, approved rule. | Use first-class `unknown` otherwise. | It is not added to the frozen projection in this issue. |
| Title diagnostic | Candidate evidence only. | Retain match text, language, rule version, and coverage result. | No match and a match both leave semantic dimensions unchanged unless a later rule is approved. | Never expose it as a semantic fact. |
| `created_on`, `posted_date`, and `listing_expires_on` | Source dates with declared source meaning. | Parse only with a source-specific declared meaning. | Missing or ambiguous dates remain unavailable. | Continue ADR-0010 and ADR-0011 honesty rules. |
| Salary fields | Source compensation representation. | Retain amount, currency, period, visibility, and source sentinel handling separately. | Missing, hidden, negotiable, and unbounded are distinct states. | Populate only through a reviewed source-specific projection rule. |
| `is_internship` | Legacy projection boolean only. | Do not derive it from title or `source_level` for future semantic classification. | The future semantic state is `technical_seniority = unknown` when unsupported. | Preserve existing legacy values without reclassification. |

The existing boolean `is_internship` cannot express `unknown`.
A future serving-contract change must define safe agent-visible semantics before it interprets that
legacy boolean for newly collected evidence.
Until then, it cannot be used as evidence for technical seniority.

## Observation, idempotency, and replay

A source delivery identifier is the primary deduplication key when the source supplies one.
Otherwise, a run-local idempotency key consists of the collection-run identifier, source listing key,
artifact digest, and source retrieval timestamp precision declared by the plan.

A repeated delivery with the same idempotency key is recorded as a duplicate delivery outcome that
references the existing observation.
It does not create a second normalized listing, mutate the first artifact, or refresh lifecycle
state by itself.
A changed artifact digest for the same source listing key is a new observation and receives a new
normalization result.

Provider replay creates a new collection run with a replay reason and references retained artifacts.
It does not claim a new retrieval time or fresh source availability.
A replayed result may supersede a selected normalization result only under a versioned selection
rule and never deletes the prior result.

## Normalization and quarantine

Normalization is an append-only attempt against one raw observation.
Its outcomes are `succeeded`, `quarantined`, `rejected`, or `superseded`.
A result is quarantined when required identity is absent, the artifact fails integrity validation,
the source field shape violates the declared adapter contract, or a publishable required display
field is invalid.

A quarantine record retains the controlled reason code, rule version, and supporting observation.
It does not invent a corrected value or silently drop the evidence.
A later corrected normalizer creates a new result for the same observation with a new version.

A normalization-rule correction must be replayed against a fixed artifact set.
The acceptance report must state the input artifact count, selected result count, changed field
count, quarantine count, and every changed rule version.

## Collection coverage and lifecycle

A collection plan declares the source scope that it is capable of observing.
The plan must explicitly state each query, feed partition, geographic or language filter, page or
cursor stop condition, and completion criterion.

A collection run is `complete` only when every declared scope partition completed and the source
adapter recorded its terminal condition.
A run is `incomplete`, `failed`, or `authorization_blocked` for every other outcome.

Only a complete run may update an availability state, and only for listings inside its declared
coverage scope.
A complete observation may mark a listing `observed_open` when the source explicitly supplies that
signal.
An explicit source expiry or unavailable signal may set an appropriate source-backed closed state.
Absence from a successful scope is not itself an expiry fact unless a later source-specific plan
proves that its scope is an authoritative full inventory and an approved lifecycle policy permits
that transition.

An incomplete, failed, duplicate, replay, or authorization-blocked run cannot expire, deactivate,
or otherwise reduce the availability of any prior listing.
The current time-based `clean_jobs.is_active` behavior remains a legacy projection behavior until a
separate approved implementation changes it.

## Legacy compatibility baseline

The following baseline was measured against the deployed Neon database in one explicit
read-only transaction at `2026-09-27T06:35:25+00:00`.
The transaction set `READ ONLY`, used a ten-second statement timeout, queried aggregate metadata
only, and was rolled back.
No raw payload, job title, company, URL, identifier, or personal data was exported.

The database identified itself as `neondb` on PostgreSQL server version `170011`.
The `public` schema contained `alembic_version`, `checkpoint_blobs`, `checkpoint_migrations`,
`checkpoint_writes`, `checkpoints`, `clean_jobs`, `ingestion_runs`, and `raw_jobs`.
The observed `clean_jobs`, `raw_jobs`, and `ingestion_runs` columns match the current Alembic and
ORM inventory.

| Existing table | Observed column inventory | Compatibility meaning |
| --- | --- | --- |
| `alembic_version` | `version_num` | Migration revision bookkeeping. |
| `checkpoint_blobs`, `checkpoint_migrations`, `checkpoint_writes`, `checkpoints` | LangGraph checkpoint implementation tables. | Not part of the ingestion or serving projection contract. |
| `raw_jobs` | `id`, `source`, `external_id`, `source_url`, `raw_payload`, `content_hash`, `fetched_at` | Mutable legacy raw landing row per source-specific identity. |
| `clean_jobs` | `id`, `source`, `external_id`, `source_url`, `title`, `company`, `role`, `description`, `tech_stack`, `job_level`, `location`, `posted_date`, `listing_expires_on`, `created_on`, `is_internship`, `salary_min`, `salary_max`, `salary_currency`, `is_salary_negotiable`, `is_active`, `first_seen_at`, `last_seen_at` | Existing single-table serving projection. |
| `ingestion_runs` | `id`, `source`, `started_at`, `finished_at`, `outcome`, `failure_phase`, `failure_code`, `fetched`, `raw_upserted`, `raw_new`, `raw_changed`, `raw_unchanged`, `clean_loaded`, `skipped`, `expired_count`, `pages_failed` | Append-only legacy operational summary. |

| Aggregate | Observed value |
| --- | ---: |
| `clean_jobs` rows | 308 |
| `raw_jobs` rows | 308 |
| `ingestion_runs` rows | 4 |
| `clean_jobs` source namespaces | 1, `vietnamworks` |
| Active legacy `clean_jobs` rows | 105 |
| Earliest `clean_jobs.first_seen_at` | 2026-07-01T09:02:19.147386+00:00 |
| Latest `clean_jobs.last_seen_at` | 2026-09-27T06:17:19.949477+00:00 |
| Earliest `raw_jobs.fetched_at` | 2026-07-01T09:02:19.147386+00:00 |
| Latest `raw_jobs.fetched_at` | 2026-09-27T06:17:04.979306+00:00 |

`raw_jobs` had no null raw payload or source URL values.
`clean_jobs` had no null source URL, description, job level, location, listing-expiry, or created-on
values.
All 308 legacy `posted_date` values were null.
Sixteen `tech_stack` values were null.
Salary minimum, maximum, and currency were null for 236, 238, and 236 rows respectively.

The following aggregate queries express compatibility expectations for the existing serving table:

| Existing agent-query concept | Expected aggregate result |
| --- | ---: |
| All visible `clean_jobs` rows | 308 |
| `role = 'Data Engineer'` | 29 |
| `is_internship = true` | 2 |
| Rows with `listing_expires_on` | 308 |
| `is_salary_negotiable = true` | 236 |

These aggregate checks used the supplied database-owner connection in read-only mode.
They validate existing data shape and expected query results, but they do not verify the separate
least-privilege `AGENT_DATABASE_URL` role or its grants.
A future migration rehearsal must repeat the checks through that agent-reader connection.

The snapshot is a compatibility baseline only.
It is not evidence that the 308 records are current vacancies, that their source authorization is
current, or that their raw rows satisfy the future artifact and observation contract.

## Future migration sequence

Each numbered phase requires a separately approved implementation issue.
No phase is authorized by this blueprint.

1. **Characterize and freeze the baseline.**
   Capture the aggregate baseline, migration head, representative agent-reader results, fixture
   checksum, and prompt/evaluation contract before changing a database.
2. **Expand the evidence schema.**
   Add the proposed append-only records through an Alembic migration without altering or dropping
   `raw_jobs`, `clean_jobs`, their constraints, or agent-visible fields.
3. **Write evidence in shadow mode.**
   Run a provider-neutral dry-run path that writes no production data until authorization,
   retention, and source gates are satisfied.
   Exercise duplicate delivery, incomplete coverage, and replay behavior with synthetic or
   authorized fixtures.
4. **Produce versioned normalization results.**
   Generate and quarantine results without changing the `clean_jobs` projection.
   Compare every selected field with golden records and retain the comparison report.
5. **Rehearse additive legacy migration.**
   Use a Neon branch or equivalent isolated database to label existing rows as legacy snapshot
   records without inventing unavailable collection, source authorization, or raw-artifact facts.
   Confirm the aggregate baseline and agent-reader results remain unchanged.
6. **Run a shadow projection.**
   Build a candidate `clean_jobs` projection from selected normalization results alongside the
   legacy projection.
   Measure row identity, field deltas, null or unknown rates, quarantine rates, and lifecycle
   eligibility before any cutover.
7. **Approve controlled publication.**
   Change writers or serving only after the source-specific authority, provider evidence, semantic
   mapping, migration rehearsal, and evaluation gates all pass.
8. **Contract later.**
   Consider any legacy table change or serving-contract exposure only in a later approved issue
   after rollback evidence and an evaluation recalibration are available.

Every phase preserves a rollback boundary because prior evidence, prior normalization results, and
the existing projection remain available.
No destructive migration, in-place evidence rewrite, or legacy-row reclassification is permitted.

## Acceptance gates for a future implementation

| Gate | Required evidence |
| --- | --- |
| Authorization | A reviewed `source_authorizations` revision specifies acquisition, fields, retention, and revocation behavior. |
| Provider evidence | The [Bright Data provider profile](../discovery/research/bright-data-linkedin-jobs-provider-profile.md) characterizes documented and observed provider boundaries. A separately authorized provider-specific evidence record must establish field quality, coverage, retention, lifecycle, and retry behavior before implementation. |
| Identity | Golden records prove that source listing keys stay stable within a source and never cause cross-source merging. |
| Raw integrity | Every retained artifact has an authorized representation, digest, media type, retrieval time, and observation link. |
| Field provenance | Every agent-visible candidate field traces to an observation, source field, transform, and rule version. |
| Semantic honesty | Unsupported technical seniority and leadership scope are `unknown`, while source labels remain exact source facts. |
| Quarantine | Invalid identity, invalid shape, and missing publishable display fields produce retained controlled quarantine outcomes. |
| Duplicate delivery | Repeating a delivery leaves one listing identity, preserves evidence, and produces no duplicate lifecycle transition. |
| Incomplete coverage | A failed or incomplete run cannot expire or deactivate a prior listing. |
| Replay | Reprocessing retained evidence names the replay run and never asserts a new observation or availability claim. |
| Rule correction | A corrected normalizer creates a new versioned result and a measurable delta report without mutating history. |
| Legacy rehearsal | The Neon-branch rehearsal preserves the baseline counts, legacy values, agent-reader query results, and frozen evaluation behavior. |
| Serving projection | The current `clean_jobs` schema, prompt surface, and API behavior remain unchanged until a separately approved coordinated switch. |

## Remaining evidence and decisions

The [Bright Data provider profile](../discovery/research/bright-data-linkedin-jobs-provider-profile.md)
records the historical capped-spike evidence and the documentation-only provider boundary.
It does not establish provider selection, provider-specific mapping, collection authority,
field-quality measurement, cost, or production activation.
A future cross-source vacancy entity requires a separate decision with identity rules, false-merge
and false-split measurement, source authority, and rollback criteria.
A future agent-visible lifecycle or semantic field requires a coordinated schema, prompt, fixture,
evaluation, and API decision.
