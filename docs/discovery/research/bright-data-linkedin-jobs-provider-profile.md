# Bright Data LinkedIn Jobs Web Scraper API provider profile

> **Last verified:** 2026-09-27
>
> **Eviction:** This profile leaves when an authorized, retained provider observation or an approved adapter contract supersedes its documented-only claims.

## Decision memo

Bright Data is characterized only as a possible acquisition provider for LinkedIn job-listing observations.
It is not selected as a provider or source.
This profile makes no request, account, credential, payment, collection, retention, adapter, schema, or production change.

The documented endpoint family can return LinkedIn-shaped job fields and can expose an asynchronous snapshot state machine.
The prior capped spike establishes only one narrow keyword-discovery response path.
It does not establish Vietnamese coverage, complete pagination, result retention rights, stable identity over time, origin authority, source availability, field quality, or lifecycle semantics.

A future adapter must preserve Bright Data as the acquisition provider separately from LinkedIn as the claimed origin platform.
It must preserve missing, empty, invalid, partial, and failed states rather than converting them to a default, a false lifecycle event, or a source-independent meaning.
The provider-neutral blueprint already has records and rules for these requirements, but an adapter remains blocked on authorization, retention, field-quality, and lifecycle evidence.

## Evidence classes and sources

| Class | Evidence | What it supports | What it cannot support |
| --- | --- | --- | --- |
| Observed | [Capped failure](https://github.com/Park-Hip/InternHunterAgent/issues/423#issuecomment-5797431647) | An authorized historical request received HTTP 400 with `Customer is not active`. | General authentication, activation, retry, or error semantics. |
| Observed | [Capped success](https://github.com/Park-Hip/InternHunterAgent/issues/423#issuecomment-5797556656) | One non-paginated keyword query received HTTP 200 and ten records with a restricted field selection. | Retained row-level analysis, coverage, completeness, stable identifiers, or schema semantics. |
| Documented | [Discover LinkedIn Jobs by Keyword](https://docs.brightdata.com/api-reference/scrapers/social-media-apis/linkedin-jobs-discover-by-keyword) | The current request inputs, dataset and discovery parameters, response example, `notify`, and `include_errors` options. | A claim that an authorized project run will return the example fields or values. |
| Documented | [Collect LinkedIn Jobs by URL](https://docs.brightdata.com/api-reference/scrapers/social-media-apis/linkedin-jobs-collect-by-url) | A separate URL-input route uses the same LinkedIn Jobs dataset identifier and documents a 200 JSON response. | The keyword-discovery route's completion, coverage, or pagination behavior. |
| Documented | [Monitor Progress](https://docs.brightdata.com/api-reference/scrapers/management-apis/monitor-progress) | Snapshot statuses, a progress endpoint, and documented failed-state messages. | The precise response schema of every result, webhook, or HTTP failure. |
| Documented | [Synchronous requests](https://docs.brightdata.com/api-reference/scrapers/synchronous-requests) and [LinkedIn synchronous requests](https://docs.brightdata.com/datasets/scrapers/linkedin/send-first-request) | The one-minute synchronous timeout, conditional HTTP 202 snapshot handoff, dataset identifier, Bearer authentication, response formats, and error-report option. | An idempotency guarantee or a complete field-level error contract. |
| Documented | [LinkedIn asynchronous requests](https://docs.brightdata.com/datasets/scrapers/linkedin/async-requests) and [sync versus async](https://docs.brightdata.com/concepts/sync-vs-async) | The trigger, poll, download, delivery, retry, concurrency, and 30-day Scraper API snapshot availability behavior. | A project retention right, source authorization, or stable result schema. |
| Documented but different product | [Scraper Studio specifications](https://docs.brightdata.com/datasets/scraper-studio/specifications) | Scraper Studio says batch results persist for 16 days and real-time results for 7 days. | A retention period or retention right for the LinkedIn Jobs Web Scraper API. |

The provider documentation was read on 2026-09-27.
`Observed` means the historical issue comment states the fact.
`Documented` means a primary Bright Data page states or exemplifies it.
`Unknown` is an explicit evidence gap.

## Prior capped-spike facts

The authorized historical request was one `AI Engineer` keyword query in Hanoi, Vietnam.
It used a one-month time range, exact-keyword matching, no pagination, a ten-record cap, and a restricted output-field selection.
The account first returned HTTP 400 with `Customer is not active`.
A later request returned HTTP 200 and exactly ten records.

Only the following output fields were reported as observed: `url`, `job_posting_id`, `job_title`, `company_name`, `job_location`, `job_posted_date`, `apply_link`, `country_code`, and `discovery_input`.
The first inspected record had a source URL, no application link, and a null `country_code` despite the Vietnam query context.
No payload, record, or credential was retained.

Consequently, every field-level statement beyond that field list is documentation-only.
The observed null is a field value state, not evidence that the job was outside Vietnam, that country is unsupported, or that a normalizer may infer `VN` from the request.
The absent application link is a source-empty or unavailable field state, not evidence that the listing is closed or that no application destination exists.

## Request-to-result state map

| State | Evidence | Required future adapter outcome | Unsafe interpretation prohibited by the blueprint |
| --- | --- | --- | --- |
| Configuration and authorization | The endpoint requires a Bearer token, and the historical failure named an inactive customer. | Record provider configuration identity without storing credentials, authorization result, request digest, and controlled failure category. | Treating a valid token, HTTP success, or provider account as source authorization. |
| Submission | Keyword discovery documents `POST /datasets/v3/scrape`, `dataset_id`, `type=discover_new`, and `discover_by=keyword`. | Persist the collection-plan version, scope, requested fields, and provider request reference before interpreting results. | Calling an accepted request complete coverage. |
| Immediate response | Synchronous requests document HTTP 200 with records when completed within one minute, or HTTP 202 with a `snapshot_id` and `Retry-After` when processing continues. | Preserve the HTTP status, headers, body representation or digest, and whether records or a snapshot reference were actually received. | Assuming every accepted request is a completed observation. |
| Deferred completion or delivery | Progress documents `GET /datasets/v3/progress/{snapshot_id}` with `starting`, `running`, `ready`, `failed`, and `canceled`. | Poll or accept delivery only under a later approved operational policy, record every state transition, and attach a snapshot reference when supplied. | Treating request acceptance or `running` as a completed observation. |
| Successful result | The capped spike observed HTTP 200 and ten records. | Record a successful transport outcome separately from scope completion and per-record normalization outcomes. | Treating 200 or a non-empty array as provider authorization, source availability, or complete scope. |
| Empty result | Progress documents `No data found in discovery` and `Snapshot is empty` as failed-state messages. | Preserve the exact provider state and declared query scope, then mark coverage incomplete unless a later source-specific completion rule proves otherwise. | Expiring prior listings or equating empty discovery with no matching LinkedIn jobs. |
| Partial result | `include_errors=true` is documented to include a detailed error report, but its result shape is not specified. | Retain the error representation, successful-input and failed-input counters, and per-input relationship when available. | Dropping error-bearing inputs or presenting partial records as a complete run. |
| Schema variation | The documented example is a schema claim, and no version or compatibility policy is documented for this endpoint. | Validate the received artifact against a versioned adapter schema and quarantine unknown, missing-required, or type-changed shapes. | Silently discard new fields, coerce invalid types, or assume example fields are stable. |
| Provider validation failure | Progress lists `Input validation failed: DETAILS`, and the historical request received an activation-related 400. | Preserve status, provider message, input digest, and non-retriable classification unless provider documentation later states otherwise. | Retrying an unchanged invalid or blocked request indefinitely. |
| Authentication or account failure | Progress lists `Account is suspended` and `Account is new, please activate it in account settings`. | Classify as authorization-blocked or provider-account failure and stop automatic collection under the plan. | Retrying as a transient source outage or changing lifecycle state. |
| Limit, rate, timeout, and transport failure | Synchronous requests have a one-minute timeout that becomes a 202 handoff. The async guide reports a 5,000 active-job limit, and says 429 requires stopping new requests, honoring `Retry-After` when present, or bounded exponential backoff. | Record the unaltered response or local timeout, stop dispatch on 429, and mark the run failed or incomplete until a later policy supplies bounded retry rules. | Assuming a retry is free, idempotent, or safe for source lifecycle. |
| Retry or replay | The async guide says to retry individually failed URLs in a separate request, but no endpoint-specific idempotency key or replay contract is documented. | Use the blueprint's run and delivery idempotency keys, keep every attempted provider request distinct, and replay retained artifacts only as a replay. | Reissuing a request as though it were the same observation or refreshing retrieval time from a replay. |
| Pagination and termination | Discovery can cap results per input, but the keyword page documents no cursor, page token, next link, or terminal-completeness signal. | Store the declared limit and any observed termination evidence as scope facts. | Treating the first array, a fixed cap, or an empty page as full-inventory coverage. |
| Result retention | The Scraper API documentation says snapshots remain downloadable for 30 days after job completion. | Record the provider deletion deadline and require a separately authorized project retention representation and period before retaining artifacts. | Treating provider availability as a project retention right or importing Scraper Studio's different retention periods. |

## Field, identity, and provenance matrix

The following classifications describe the field names in the current documentation and the historical spike.
A field in a Bright Data response is provider-delivered evidence, not independently verified LinkedIn truth.
`Candidate origin-platform fact` means the name or example suggests LinkedIn provenance, but the documentation does not supply a contractual source-field definition.

| Field or concept | Status | Classification and required preservation |
| --- | --- | --- |
| `dataset_id` | Documented | Provider configuration identifier. Preserve it with the provider request and do not use it as a source or listing identity. |
| `snapshot_id`, progress `status`, `error_message`, webhook delivery reference | Documented | Provider execution and delivery facts. Preserve the exact value, transition time, and endpoint family. Their availability in a synchronous keyword response is unknown. |
| `job_posting_id` | Observed and documented | Candidate origin-platform listing identifier because the documentation example pairs it with a LinkedIn job URL. Preserve the field path and value as a source-listing-key candidate, while leaving stability, uniqueness, and formal source meaning unknown. |
| `company_id`, `title_id` | Documented only | Candidate origin-platform identifiers in the example. Preserve as distinct source fields, not as a verified company identity or a cross-source key. |
| `url`, `company_url`, `apply_link`, `job_poster.url` | `url` and `apply_link` observed; all documented | Candidate origin-platform URLs. Preserve each field name, original value, and absence separately. Do not equate a provider-returned URL with an accessible page, an employer origin, or an application outcome. |
| `job_title`, `company_name`, `job_location`, `job_summary`, `job_description_formatted`, `job_function`, `job_industries`, `job_employment_type`, `job_seniority_level` | The first three observed; all documented | Candidate origin-platform display or label fields. Preserve text, locale when supplied, field path, and value state. `job_seniority_level` remains an exact `source_level` candidate, not technical seniority or leadership scope. |
| `job_posted_date`, `job_posted_time` | `job_posted_date` observed; both documented | Candidate origin-platform date fields. Preserve the raw value and field name. The documentation does not define their event semantics, timezone policy, or whether either is authoritative enough for posted-date or lifecycle rules. |
| `country_code`, `discovery_input` | Both observed and documented | `country_code` is a candidate source field with observed nullability. `discovery_input` is provider-generated acquisition context that must retain its request-field path and must not fill a missing source value. |
| `application_availability`, `is_easy_apply` | Documented only | Candidate source visibility signals. Preserve raw boolean or missing state but do not map either to open, closed, or expired without a later source-specific lifecycle decision. |
| `job_num_applicants`, `job_poster`, `company_logo`, `base_salary`, `job_base_pay_range`, `salary_standards` | Documented only | Candidate source fields or provider representations. Preserve field-specific null, shape, and text states. Do not infer applicant data, compensation semantics, employer identity, or availability. |
| Keyword inputs: `location`, `keyword`, `country`, `time_range`, `job_type`, `experience_level`, `remote`, `company`, `selective_search`, `jobs_to_not_include`, and `location_radius` | Documented; the historical request used a subset | Provider acquisition facts. Preserve the exact submitted input, omitted-versus-empty state, API version, and declared scope. They are filters, not record facts. |
| `include_errors`, `notify`, `endpoint`, `format`, and custom output fields | Documented in the endpoint or linked asynchronous documentation | Provider request and delivery configuration. Preserve each setting because it affects error visibility, result form, and the evidence available to a future adapter. |

## Evidence classification by capability

| Capability | Classification | Basis and limitation |
| --- | --- | --- |
| Account activation can block a request. | Observed | One historical request returned 400 `Customer is not active`. The general failure taxonomy remains unmeasured. |
| A keyword discovery request can return ten restricted-field records. | Observed | One historical request returned HTTP 200 and ten records. It does not measure field completeness or coverage. |
| Keyword discovery accepts the documented filters. | Documented-only | The current endpoint lists the input properties and explains their intended filters. Their behavior was not retained for analysis. |
| A synchronous request returns an inline response when it completes within one minute. | Documented-only | The synchronous API documents HTTP 200 with a record array. It was not tested in this investigation. |
| A synchronous request hands off to asynchronous retrieval after its timeout. | Documented-only | The synchronous API documents HTTP 202, `snapshot_id`, and `Retry-After` after one minute. The keyword endpoint's snapshot wording is therefore conditional, even though its response example is an array. |
| Snapshot progress may be `starting`, `running`, `ready`, `failed`, or `canceled`. | Documented-only | The management endpoint states those values. Whether every LinkedIn keyword request enters that state machine is not observed. |
| A provider error report can accompany results. | Documented-only | `include_errors=true` says it includes a detailed report, but the report schema and input association are not published on this endpoint. |
| Pagination, terminal completeness, and idempotency semantics. | Unknown | No cursor, completion rule, or endpoint-specific idempotency key was found in the reviewed primary documentation. |
| Timeout, rate limiting, and bounded retry behavior. | Documented-only | The Scraper API documents its synchronous timeout and 429 handling, but this investigation did not observe either behavior for LinkedIn Jobs. |
| LinkedIn Jobs Web Scraper API result retention. | Documented-only | The Scraper API documents a 30-day snapshot download window. It does not confer project retention rights. |
| Schema compatibility, versioning, and deprecation notice. | Unknown | No endpoint-specific schema evolution policy was found. |

## ADR-0055 contract assessment

| ADR-0055 or blueprint rule | Assessment | Provider-specific requirement |
| --- | --- | --- |
| Provider identity is not source identity. | Accommodated. | Record Bright Data as acquisition provider and LinkedIn only as the claimed origin platform supported by field and URL evidence. |
| Missing is distinct from source-empty, failed extraction, and unsupported. | Accommodated, but field-state evidence is incomplete. | Preserve absent `apply_link`, null `country_code`, omitted fields from restrictive output selection, and error-bearing inputs as different states. |
| Successful HTTP response is not authorization, complete scope, or listing availability. | Directly required. | Preserve the 200 separately from account authorization, source rights, complete scope, and lifecycle conclusions. |
| Only a completed declared scope can affect lifecycle. | Not yet measurable. | Do not make availability transitions until pagination, termination, and source lifecycle signals are characterized. |
| Raw artifacts and observations are append-only and rebuildable. | Accommodated only after an authorization and retention decision. | Retain an allowed raw or redacted representation with digest, request context, provider references, and field-presence map. |
| Source listing and provider identifiers remain distinct. | Accommodated. | Keep `job_posting_id`, provider snapshot, dataset, and delivery identifiers separately pending stable-ID measurement. |
| Normalization has field provenance and quarantine. | Directly required. | Validate field shape and quarantine schema changes or missing publishable identity rather than normalizing silently. |
| Runs, duplicate delivery, and replays are idempotent. | Blueprint supplies the system rule, not provider evidence. | Generate project idempotency keys and record a later provider-specific retry policy because Bright Data idempotency is undocumented. |

The blueprint accommodates the documented provider boundary without change.
It does not supply the missing provider facts, source authorization, retention right, or lifecycle evidence.
No adapter implementation is authorized by this finding.

## Smallest follow-up evidence specification

A future issue may run this specification only after it separately records source authority, provider permission, account approval, allowed fields, cost limit, and artifact-retention rule.
This section does not authorize the request or retention.

| Element | Required bounded specification |
| --- | --- |
| Scope | One keyword-discovery request using the already characterized `AI Engineer` and Hanoi input, no pagination, with a hard limit of ten returned records. Do not follow result, company, or application URLs. |
| Requested field set | Request `url`, `job_posting_id`, `job_title`, `company_name`, `job_location`, `job_posted_date`, `apply_link`, `country_code`, `discovery_input`, `job_seniority_level`, `job_employment_type`, `application_availability`, `job_posted_time`, and provider error or snapshot fields when the endpoint exposes them. Record the exact custom-field request or its absence. |
| Retention representation | Retain only the separately authorized raw, redacted, or field-presence representation, its SHA-256 digest, request digest, retrieval timestamp, response status and headers, provider dataset and snapshot references, and deletion deadline. Do not retain credentials. |
| Required state evidence | Capture the submission response shape, any snapshot-progress transitions, terminal result, per-input error representation, and any timeout or delivery state without retrying automatically. |
| Success criteria | The evidence identifies the actual response path, provider references, result count, field-presence and null states, error association, and whether a terminal completeness signal exists. It must not make a coverage, stable-ID, source-authority, or lifecycle claim. |
| Failure criteria | Missing authority, absent retention rule, account activation failure, undocumented retry need, or inability to retain the approved evidence representation stops the run and records an authorization-blocked, failed, or incomplete outcome. |

A later semantic-mapping study needs a separately approved, larger reviewable corpus and remains governed by the source-level semantics decision.
