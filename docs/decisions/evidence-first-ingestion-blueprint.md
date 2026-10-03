# Evidence-first ingestion blueprint

> **Status:** Approved design for [issue #455](https://github.com/Park-Hip/InternHunterAgent/issues/455).
> The minimum evidence contract is finalized by
> [#477](https://github.com/Park-Hip/InternHunterAgent/issues/477) and authorized by
> [ADR-0056](adr-0056-ingestion-gate.md).
>
> **Last verified:** 2026-09-28
>
> **Eviction:** This blueprint's proposed-record inventory, migration sequence, and acceptance-gate
> table leave when the evidence schema, shadow writer, and adapter slices implement them. The
> minimum executable contract below leaves with the same slices, once a `source_authorizations`
> record can answer the register's questions from data rather than from prose.

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
11. A declared cap is stored beside every observed count.
    An observed count equal to its cap is a saturated result, not a coverage claim.
12. A request body is stored as submitted, as its own record.
    It is never reconstructed from a provider echo, which cannot distinguish an omitted filter from
    an empty one.
13. Every availability transition names the collection run that produced it and that run's declared
    scope. A path that cannot name a run does not transition availability.

Rules 11 and 12 are requirements derived from the measured provider state in
[#470](https://github.com/Park-Hip/InternHunterAgent/issues/470) and are stated normatively in
[the minimum executable contract](#minimum-executable-evidence-contract).

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

## Minimum executable evidence contract

### Why a minimum exists

[ADR-0056](adr-0056-ingestion-gate.md) tracks five of the
[thirteen acceptance gates](#acceptance-gates-for-a-future-implementation) in the
[gate register](../refactor/ingestion-gate-register.md), because five are the only ones that can be
answered by a record rather than by an implementation.
This section is the contract those records must satisfy, at column level, so that a slice is written
against requirements instead of rediscovering them.

The requirements here are normative.
Where this section and the prose below both state something, this section wins.

### Scope of the minimum

| Proposed record | In the minimum? | Why |
| --- | --- | --- |
| `collection_plans` | Yes | G3 and G4 compare an observation against a declared scope, so the scope has to be a record. |
| `collection_runs` | Yes | Every gate's evidence is attributed to a run. |
| `raw_artifacts` | Yes | G4 is the retained artifact chain. |
| `raw_observations` | Yes | G3 and G5 both start from an observation. |
| `normalization_results` | Yes | G5 and the quarantine outcome live here. |
| Field-level provenance | Yes | G5 is required per populated field, not per result. |
| Request bodies | Yes, with the adapter | Without it there is no statement of what was actually asked for. |
| Provider execution traces | Yes, with the adapter | A run issues several requests, and one document per run cannot say what happened to each of them. It observes no listing, so it is not a `raw_artifact`. |
| `sources` | No | The source identifier is carried on the plan and the run in the minimum. |
| `source_authorizations` | No | The register answers G1 in prose until this record exists. Deferral D1. |
| `collection_run_scopes` | No | The declared scope is carried as digestable fields on the plan and the run in the minimum. Deferral D1. |
| `normalized_listings` | No | Deferred to the first cutover decision. Deferral D1. |
| `clean_jobs` projection lineage | No | The projection stays frozen under ADR-0053. Deferral D1. |

The deferred records are not abandoned.
Each is listed with its re-entry trigger in the
[deferral register](../refactor/ingestion-gate-register.md#deferral-register).

### Rules every record obeys

1. Every record is append-only.
   No `UPDATE`, no `DELETE`, and no in-place evidence rewrite.
2. Every record carries an immutable surrogate `id` and an explicit creation provenance: the plan
   version, run, artifact digest, or rule version that produced it.
3. Every timestamp is `timestamptz` in UTC, and is rounded only to the precision the plan declares.
   A rounded timestamp is never rounded up.
4. Every record that holds bytes or payload content holds that content's digest in the same row.
5. No record holds a credential, an API key, a cookie, or a person-identifying field.
6. `NULL` means not observed.
   It never means zero, empty string, false, or "not applicable". Those are value states, carried by
   the field-presence map and the provenance value state.
7. Every enum column has a closed vocabulary.
   A value outside the vocabulary is a write failure, not a new category.

### `collection_plans` - declared intent for one source, one version

| Column | Type | Required | Definition |
| --- | --- | --- | --- |
| `id` | `bigint` | yes | Immutable surrogate identifier, never reused. |
| `source_id` | `text` | yes | The declared source namespace. A provider identifier is not a source identifier. |
| `plan_version` | `text` | yes | Any change to declared scope, caps, requested fields, endpoints, or the completion rule creates a new version. A version is never edited. |
| `declared_scope` | `jsonb` | yes | Every query, feed partition, geographic or language filter, and page or cursor stop condition the plan intends to observe. |
| `declared_caps` | `jsonb` | yes | Every server-side or client-side cap the request carries, keyed by its parameter name. An absent key means the plan declares no such cap, which is a fact and not a zero. |
| `requested_fields` | `jsonb` | yes | Every field the plan asks for, with the field's meaning. A field the plan does not request is not available evidence even when the source returns it. |
| `declared_completion_rule` | `text` | yes | The terminal condition the adapter must record before a run may read `complete`. |
| `declared_endpoint_set` | `jsonb` | yes | Every endpoint the plan may address. A request outside this set aborts the run. |
| `retrieval_precision` | `text` | yes | The precision a run may round a retrieval timestamp to. |
| `authorization_revision` | `text` | yes | The source and gate register row this plan relies on. |
| `configuration_digest` | `text` | yes | Digest of the plan row itself, so a run can prove which plan version produced it. |
| `created_at` | `timestamptz` | yes | Creation time. |

A plan row never contains a response, an observed record, a credential, or a claim that a run
completed.
A plan is a declaration of intent, not evidence that the intent was met.

### `collection_runs` - one execution attempt against one plan version

| Column | Type | Required | Definition |
| --- | --- | --- | --- |
| `id` | `bigint` | yes | Immutable surrogate identifier. |
| `plan_id` | `bigint` | yes | The plan version this run executed. |
| `idempotency_key` | `text` | yes | Unique. Composition is normative in the next subsection. |
| `run_kind` | `text` | yes | `scheduled`, `manual`, or `replay`. |
| `started_at` | `timestamptz` | yes | When the run began. |
| `finished_at` | `timestamptz` | no | Null means the run is unfinished, and an unfinished run is never a success. |
| `outcome` | `text` | yes | `complete`, `incomplete`, `failed`, `authorization_blocked`, or `aborted`. |
| `coverage_result` | `text` | yes | `complete`, `partial`, or `unknown`. `complete` is permitted only when `outcome` is `complete`. |
| `declared_record_cap` | `integer` | no | The record cap the executed plan declared. Null means no cap was declared, which is a different fact from a cap of zero. |
| `observed_record_count` | `integer` | yes | What came back. Never a coverage, completeness, or inventory claim. |
| `declared_scope_digest` | `text` | yes | Digest of the scope actually executed, so a run cannot claim a scope it did not run. |
| `request_count` | `integer` | yes | Number of requests the run issued. |
| `failure_category` | `text` | no | Controlled code. Null only when `outcome` is `complete`. |
| `configuration_digest` | `text` | yes | Digest of the effective runtime configuration, not of the plan. |
| `replay_of_run_id` | `bigint` | no | Required when `run_kind` is `replay`. |
| `created_at` | `timestamptz` | yes | Creation time. |

A run row holds no payload bytes, listing keys, titles, companies, URLs, human-readable failure
text, or credential.
It keeps the same non-PII posture as the existing `ingestion_runs` summary, so a run record
can never become a data leak by widening the operational summary.

### Idempotency-key composition

This is the normative composition, and it replaces any looser reading of
[the section below](#observation-idempotency-and-replay).

1. When the source supplies a delivery identifier, that identifier is the deduplication key.
   It is stored as `delivery_id` on the observation and constrained unique within the source.
2. When the source supplies none, the run-local idempotency key is exactly the four-part tuple
   `(collection_run_id, source_listing_key, artifact_digest, retrieved_at)`,
   where `retrieved_at` is rounded to the plan's declared `retrieval_precision`.
3. Those four parts and no others compose the key.
   A later fifth part is a version change, and keys composed under the previous rule stay valid.
4. A repeated delivery with the same key is recorded as a duplicate-delivery outcome that references
   the existing observation.
   It creates no second listing identity, does not mutate the first artifact, and does not refresh
   lifecycle state.
5. A changed artifact digest for the same source listing key is a new observation, and it receives
   a new normalization result.

### `raw_artifacts` - one retained representation of one retrieval

| Column | Type | Required | Definition |
| --- | --- | --- | --- |
| `id` | `bigint` | yes | Immutable surrogate identifier. |
| `collection_run_id` | `bigint` | yes | The run that acquired the representation. |
| `content_digest` | `text` | yes | SHA-256 of the retained representation named by `representation_version`. |
| `representation_version` | `text` | yes | The rule that produced the retained representation: raw bytes, approved redaction, or approved field projection. |
| `media_type` | `text` | yes | The representation's media type. |
| `byte_length` | `bigint` | yes | Length of the retained representation. |
| `storage_locator` | `text` | yes | Where the representation is retained, or that it is stored in-row. |
| `acquired_at` | `timestamptz` | yes | Retrieval time, rounded only to the plan's declared precision. |
| `retention_disposition` | `text` | yes | `retained_full`, `retained_redacted`, `retained_derived`, or `discarded`. |
| `retention_until` | `timestamptz` | conditional | Required whenever `retention_disposition` begins with `retained`. A null value next to a retained disposition is a contract violation, not an open-ended permission. |
| `authorization_revision` | `text` | yes | The authorization that permitted keeping this representation. |
| `redaction_rules` | `jsonb` | conditional | Required when `retention_disposition` is `retained_redacted`. |
| `created_at` | `timestamptz` | yes | Creation time. |

**Retention representation.** A retained artifact states four things: its representation version,
its disposition, the end of its authorized retention period, and the authorization revision that
permitted it.
A digest with no retained representation is not evidence.

Provider availability is not a project retention right.
`retention_until` is the end of the project-side authorized period, which may never exceed either
the authorization's own stated period or the provider's stated window, whichever is shorter.
A provider's permissive window is never the value written to that column.

### `raw_observations` - one listing as seen in one artifact in one run

| Column | Type | Required | Definition |
| --- | --- | --- | --- |
| `id` | `bigint` | yes | Immutable surrogate identifier. |
| `collection_run_id` | `bigint` | yes | The run that produced the observation. |
| `raw_artifact_id` | `bigint` | yes | The artifact the observation was read from. |
| `source_id` | `text` | yes | The declared source namespace. |
| `source_listing_key` | `text` | yes | The key that names the listing within the source namespace. Unique only within the source. |
| `provider_listing_key` | `text` | no | The provider's own identifier, when the source supplies one distinct from the source listing key. Both are retained with their field meaning rather than one being chosen by assumption. |
| `delivery_id` | `text` | no | The source's delivery identifier, when supplied. Unique within the source. |
| `retrieved_at` | `timestamptz` | yes | When the source was asked, at the plan's declared precision. |
| `source_urls` | `jsonb` | yes | Every URL the observation carried, keyed by the field path that carried it. |
| `field_presence` | `jsonb` | yes | Maps every requested field path to exactly one of `present`, `source_empty`, or `source_missing`. |
| `idempotency_key` | `text` | yes | Unique. Composed normatively above. |
| `created_at` | `timestamptz` | yes | Creation time. |

`field_presence` never records a guessed, defaulted, or inferred value.
The latest observation does not erase an earlier one.

### `normalization_results` - one attempt to turn one observation into candidate values

| Column | Type | Required | Definition |
| --- | --- | --- | --- |
| `id` | `bigint` | yes | Immutable surrogate identifier. |
| `observation_id` | `bigint` | yes | The observation this attempt read. |
| `normalization_version` | `text` | yes | The deterministic normalizer, vocabulary, or reviewed mapping version. |
| `attempt_number` | `integer` | yes | Unique together with `observation_id` and `normalization_version`. |
| `outcome` | `text` | yes | `succeeded`, `quarantined`, `rejected`, or `superseded`. |
| `quarantine_reason_code` | `text` | conditional | Required when `outcome` is `quarantined`, and exactly one value from the closed vocabulary below. |
| `rule_version` | `text` | yes | The rule set that produced this attempt. |
| `output_digest` | `text` | conditional | Required when `outcome` is `succeeded`. |
| `provenance` | `jsonb` or related rows | yes | The seven provenance facts for every populated output field. |
| `warnings` | `jsonb` | yes | Structured warnings. Never free text containing field content. |
| `evaluator_metadata` | `jsonb` | no | Machine-readable evaluator output, no free text with field content. |
| `created_at` | `timestamptz` | yes | Creation time. |

**Closed quarantine reason vocabulary.** `identity_absent`, `listing_key_absent`,
`artifact_integrity_failed`, `declared_digest_mismatch`, `adapter_contract_violated`,
`shape_unparseable`, `display_field_invalid`, `unauthorized_field`.

`artifact_integrity_failed` is the retained representation no longer hashing to the digest stored
beside it.
`declared_digest_mismatch` is the captured payload not hashing to the digest the adapter declared when it
captured it.
Both retain the evidence and neither enters the projection, and they stay distinct codes because the
first points at a row and the second at a capture.

An internal error is a run `failure_category`, not a quarantine reason.
Quarantine is a decision about the evidence, and it retains the evidence.

A quarantine retains its reason and never invents a corrected value, never deletes the evidence, and
never silently drops the observation.
A later corrected normalizer creates a new result for the same observation under a new
`normalization_version`; the earlier result keeps its row and may be marked `superseded`.

### Field-level provenance

Every populated field carries the seven provenance facts tabulated in
[the field and provenance contract](#field-and-provenance-contract).
The storage requirement is one record per populated field, keyed by
`(normalization_result_id, output_field)`.

The facts are normative and the physical placement is not.
Both of these satisfy G5:

- preferred: a `field_provenance` table with a unique constraint on
  `(normalization_result_id, output_field)`, which makes "every populated field has a provenance
  record" a fact the database enforces.
- permitted: a `provenance` JSONB document on `normalization_results` holding the same seven facts
  under each output field key.

The table is preferred because a uniqueness constraint is checkable and a convention is not.
An output field that is populated without a provenance record is a write failure.

### Declared cap beside observed count

This is a requirement derived from the measured provider state in
[#470](https://github.com/Park-Hip/InternHunterAgent/issues/470), where the observed count
equalled the declared cap of ten and so said nothing about coverage.

1. The declared cap is stored on the plan and repeated on the run, so an observed count is never
   readable on its own.
2. A null `declared_record_cap` is rendered as "no cap declared", never as an unbounded result.
3. An observed count equal to its declared cap is a **saturated** result.
   It proves nothing about how many matching listings exist, and every report that shows it must say
   so.
4. No report, log, run summary, or agent-visible string states a coverage, completeness, or
   inventory claim derived from an observed count.

### Standalone request-body record

This is a requirement derived from the same observation, where every omitted filter came back in the
provider echo as an empty string, so the echo could not distinguish an omitted filter from one
submitted as empty and looked authoritative while destroying the distinction.

1. The request body is stored as the adapter submitted it, before the request is sent.
2. It is never reconstructed from a provider echo, a redirect, a retry log, or any other server
   return value.
3. It is stored as its own record, one row per request attempt, keyed by
   `(collection_run_id, request_ordinal, attempt_number)`.
4. An omitted parameter is absent from the stored body.
   It is never stored as an empty string, a null, or a default.
5. The stored body carries no credential.
   A credential is referenced by a named secret location, never by value.
6. A request whose body cannot be stored is not sent.

| Column | Type | Required | Definition |
| --- | --- | --- | --- |
| `id` | `bigint` | yes | Immutable surrogate identifier. |
| `collection_run_id` | `bigint` | yes | The run that issued the request. |
| `request_ordinal` | `integer` | yes | Position of the request within the run. |
| `attempt_number` | `integer` | yes | Retry attempt, counting from 1. |
| `adapter_id` | `text` | yes | The adapter that issued it. |
| `method` | `text` | yes | The HTTP method. |
| `endpoint` | `text` | yes | Must resolve to a value in the executed plan's `declared_endpoint_set`. A request to an undeclared endpoint aborts the run. |
| `body` | `jsonb` | yes | The body as submitted, with omitted parameters absent. |
| `body_digest` | `text` | yes | Digest of the submitted body. |
| `declared_caps` | `jsonb` | yes | The plan's declared caps, copied from the executed plan. |
| `requested_fields` | `jsonb` | yes | The plan's requested field map, copied from the executed plan. |
| `sent_at` | `timestamptz` | yes | When the request was sent. |
| `created_at` | `timestamptz` | yes | Creation time. |

The three columns added by [slice 2](https://github.com/Park-Hip/InternHunterAgent/issues/501) are
`endpoint_name`, `path_parameters`, and `query_parameters`.
Each exists because a real Bright Data run issues more than one request, which the table above was
written before anyone measured.

| Column | Type | Required | Definition |
| --- | --- | --- | --- |
| `endpoint_name` | `text` | yes | The key in the executed plan's `declared_endpoint_set` that `endpoint` was rendered from. |
| `path_parameters` | `jsonb` | yes | The values that render `endpoint` from that template. |
| `query_parameters` | `jsonb` | yes | The query string as submitted. The plan declares filters there as well as in the body. |

Storing `endpoint_name` together with `path_parameters` is what makes the endpoint rule checkable
by a reader rather than a property of the adapter that built the URL: the writer re-renders the
named template and refuses the run if the address does not match.
`query_parameters` exists because a filter the plan declares on the query string is part of what
was asked for, and a body column cannot hold it.

`declared_caps` and `requested_fields` restate the executed plan's declarations on every request
row, so a single row is self-describing.
What one particular request carried is in that row's own `body` and `query_parameters`; a follow-up
poll carries neither and its body is an empty object rather than an absent fact.

### Provider execution trace

The handoff, the progress envelopes, and the terminal delivery are the provider's account of
*running* a request, not a retained representation of a retrieval, so they do not belong in
`raw_artifacts` and they carry no `raw_observations` row.
They get their own record, one row per stored request, referenced by key.

| Column | Type | Required | Definition |
| --- | --- | --- | --- |
| `id` | `bigint` | yes | Immutable surrogate identifier. |
| `collection_run_id` | `bigint` | yes | The run the request belonged to. |
| `request_body_id` | `bigint` | yes | The request this answers. Exactly one execution per request. |
| `http_status` | `integer` | no | The status the provider returned. Absent when no response arrived. |
| `transport_error` | `text` | no | The failure that replaced a response. Absent when one arrived. |
| `response_digest` | `text` | yes | Digest of the response as read. |
| `observed_at` | `timestamptz` | yes | When the response was read, floored to the plan's retrieval precision. |
| `provider_facts` | `jsonb` | yes | The declared facts that one envelope carried. |
| `created_at` | `timestamptz` | yes | Creation time. |

`http_status` and `transport_error` are mutually exclusive and one of them is always present.
A transport failure produced no response at all, so recording a status for it would invent one,
and recording neither would make an attempt that failed indistinguishable from an attempt that
never happened.

`provider_facts` states only what the envelope carried.
A key the provider omitted is absent rather than null or zero, because a provider that omits a
count is asserting nothing about it and recording an absence as a claim of zero is the one thing
an omitted key must never become.
The two facts that are statements about this project's own reading of the envelope, rather than
about the envelope, are always stated so a reader can see they were checked: `terminal` against the
plan's declared states, and `schema_drift` against the same vocabulary.
A delay is recorded with where it came from, because a `retry-after` the provider sent and a delay
the plan guessed are the same number and not the same fact.

The two records are separate because the echo of a submitted request is not the submitted request.
A reader who wants to know what this project asked for reads `collection_request_bodies` and reads
no provider output at all.

The run-level facts that used to sit in a single execution document are not lost, and none of them
is stored twice: the observed count and the declared cap are columns on `collection_runs` and
saturation is derived from the two; the outcome and the failure category are columns on
`collection_runs`; the instant the run submitted its first request is that request's `sent_at`; the
snapshot identifier, the retry delay, and each wait belong to the response that produced them and
are stated on that response's row.

### Lifecycle attribution

The 7-day window stays.
Attribution is what changes.

1. Every availability transition names the `collection_run_id` that produced it and that run's
   `declared_scope_digest`.
2. A code path that cannot name a run does not transition availability.
   It fails instead.
3. The transition is attributable to a run and its declared scope, not to a wall-clock observation
   alone.
4. Attribution must not change which rows are active.
   If enforcing it would change which rows are active, that is a separate approved issue rather
   than a detail of the slice that enforces it.
5. Expiry scoping is per source.
   One source's window never ages out another source's rows.

Point 5 exists because `expire_stale_clean_jobs()` currently applies a time predicate with no source
and no coverage condition, so a single-source corpus hid the missing predicate that a second source
would expose.

### Which slice materializes which record

| Record | Slice 1, [#478](https://github.com/Park-Hip/InternHunterAgent/issues/478) | Slice 2, the provider adapter |
| --- | --- | --- |
| `collection_plans`, `collection_runs`, `raw_artifacts`, `raw_observations`, `normalization_results` | Added | Reused unchanged |
| Field-level provenance | Added | Reused unchanged |
| `collection_request_bodies` | Not added | Added |
| `collection_request_executions` | Not added | Added |
| `raw_jobs`, `clean_jobs` | Unchanged | Unchanged |

The request-body record lands with the adapter because it answers a provider-specific question: what
did this adapter actually ask for.
The VietnamWorks plan is fully described by its plan version, so the first slice has nothing to
record that the plan does not already carry.

The execution record lands with it for the same reason and because it cannot live anywhere else.
A run that issues several requests needs one row per request, and one document per run cannot
express that: a retry, a second discovery input, or a second submit would become a list entry inside
one representation rather than a record with its own `request_ordinal` and `attempt_number`.

### What the minimum does not change

- `raw_jobs` and `clean_jobs` keep the same columns, the same constraints, and the same
  agent-visible shape.
- The prompt surface, fixtures, evaluation corpus and thresholds, the HTTP and SSE contracts, and
  `/api/v1/ready` are unchanged.
- The `schedule:` trigger stays removed under ADR-0053.
- No semantic mapping is introduced.
  `technical_seniority` and `leadership_scope` stay first-class `unknown`, per the
  [#461](https://github.com/Park-Hip/InternHunterAgent/issues/461) decision.
- No cross-source identity or deduplication is introduced.

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

The idempotency-key composition, and the duplicate-delivery outcome, are normative in
[the minimum executable contract](#idempotency-key-composition).

Provider replay creates a new collection run with a replay reason and references retained artifacts.
It does not claim a new retrieval time or fresh source availability.
A replayed result may supersede a selected normalization result only under a versioned selection
rule and never deletes the prior result.

## Normalization and quarantine

Normalization is an append-only attempt against one raw observation.
Its outcomes are `succeeded`, `quarantined`, `rejected`, or `superseded`, with the column
definitions and the closed quarantine reason vocabulary normative in
[the minimum executable contract](#minimum-executable-evidence-contract).

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
Every transition is additionally attributed to a run and that run's declared scope, normatively in
[the lifecycle attribution contract](#lifecycle-attribution).
The current 7-day time-based `clean_jobs.is_active` predicate is retained and is the behavior
Slice 1 must preserve.

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

Five of these gates can be answered by a record and are therefore tracked as the five named gates in
the [ingestion gate register](../refactor/ingestion-gate-register.md).
The rest are answered by an implementation, a fixture, or a shadow run, and no register row can
stand in for them.
The last column states which, so that a reader does not look for a register row that will never
exist.

| Gate | Required evidence | How it is checked |
| --- | --- | --- |
| Authorization | A reviewed `source_authorizations` revision specifies acquisition, fields, retention, and revocation behavior. | Register **G1** |
| Provider evidence | The [Bright Data provider profile](../discovery/research/bright-data-linkedin-jobs-provider-profile.md) characterizes documented and observed provider boundaries. A separately authorized provider-specific evidence record must establish field quality, coverage, retention, lifecycle, and retry behavior before implementation. | Register **G2** for retention and spend, and G1 before the rest; the remaining provider facts need the adapter slice |
| Identity | Golden records prove that source listing keys stay stable within a source and never cause cross-source merging. | Register **G3** |
| Raw integrity | Every retained artifact has an authorized representation, digest, media type, retrieval time, and observation link. | Register **G4** |
| Field provenance | Every agent-visible candidate field traces to an observation, source field, transform, and rule version. | Register **G5** |
| Semantic honesty | Unsupported technical seniority and leadership scope are `unknown`, while source labels remain exact source facts. | Slice 1 fixture asserting `unknown`; the mapping itself is deferral D2 |
| Quarantine | Invalid identity, invalid shape, and missing publishable display fields produce retained controlled quarantine outcomes. | Slice 1 shadow run, checked against the closed reason vocabulary |
| Duplicate delivery | Repeating a delivery leaves one listing identity, preserves evidence, and produces no duplicate lifecycle transition. | Slice 1 contract fixture |
| Incomplete coverage | A failed or incomplete run cannot expire or deactivate a prior listing. | Slice 1 contract fixture |
| Replay | Reprocessing retained evidence names the replay run and never asserts a new observation or availability claim. | Slice 1 contract fixture |
| Rule correction | A corrected normalizer creates a new versioned result and a measurable delta report without mutating history. | Slice 1 contract fixture |
| Legacy rehearsal | The Neon-branch rehearsal preserves the baseline counts, legacy values, agent-reader query results, and frozen evaluation behavior. | Deferred, deferral D3 |
| Serving projection | The current `clean_jobs` schema, prompt surface, and API behavior remain unchanged until a separately approved coordinated switch. | Slice 1 acceptance, by re-measuring the `clean_jobs` aggregate baseline below |

## Remaining evidence and decisions

The
[gate register](../refactor/ingestion-gate-register.md) is the live record of which gates are
met for which source, and the
[deferral register](../refactor/ingestion-gate-register.md#deferral-register) is the live record of
what is deliberately not in this milestone and what pulls it back.

The [Bright Data provider profile](../discovery/research/bright-data-linkedin-jobs-provider-profile.md)
records the historical capped-spike evidence and the documentation-only provider boundary.
It does not establish provider selection, provider-specific mapping, collection authority,
field-quality measurement, cost, or production activation.
A future cross-source vacancy entity requires a separate decision with identity rules, false-merge
and false-split measurement, source authority, and rollback criteria.
A future agent-visible lifecycle or semantic field requires a coordinated schema, prompt, fixture,
evaluation, and API decision.
