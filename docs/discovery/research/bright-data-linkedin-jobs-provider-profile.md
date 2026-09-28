# Bright Data LinkedIn Jobs Web Scraper API provider profile

> **Last verified:** 2026-09-27
>
> **Eviction:** This profile leaves when an approved adapter contract supersedes its documented-only claims. The authorized, retained observation named below has converted several capabilities from documented-only to observed, which is progress toward eviction but is not itself an adapter contract.

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

One authorized bounded observation has since run against this profile and is recorded in the [bounded observation evidence](bright-data-bounded-observation-470.md).
It converted the requested field set, the output field selector, the per-input record cap, the snapshot handoff, and the progress envelope from documented claims into observed facts.
It also produced three findings that a future adapter must carry rather than resolve.
The handoff did not occur at its documented trigger, the observed count reached the declared cap and therefore carries no coverage information, and the provider echo of acquisition context cannot distinguish an omitted filter from an empty one.
The [decision note](bright-data-observation-470-decision.md) recommends opening the provider-neutral evidence-schema and shadow-migration proposal on that basis and records what must still be measured first.

The live authorization gate for this provider is the Bright Data rows of the
[ingestion gate register](../../refactor/ingestion-gate-register.md), where all five named gates
read not met.
The issue #423 citations in this profile are dated capped-spike measurements.
They are not a current gate.

## Evidence classes and sources

| Class | Evidence | What it supports | What it cannot support |
| --- | --- | --- | --- |
| Observed | [Capped failure](https://github.com/Park-Hip/InternHunterAgent/issues/423#issuecomment-5797431647) | An authorized historical request received HTTP 400 with `Customer is not active`. | General authentication, activation, retry, or error semantics. |
| Observed | [Capped success](https://github.com/Park-Hip/InternHunterAgent/issues/423#issuecomment-5797556656) | One non-paginated keyword query received HTTP 200 and ten records with a restricted field selection. | Retained row-level analysis, coverage, completeness, stable identifiers, or schema semantics. |
| Observed | [Bounded observation](bright-data-bounded-observation-470.md) | One non-paginated keyword query reached `ready` through the snapshot path, returned exactly ten records under a declared server-side cap, and honored the field selector with zero unrequested fields. | Coverage, completeness, stable identity over time, error-report shape, retry safety, or any lifecycle conclusion. |
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

## Bounded observation facts

The bounded observation in [its evidence record](bright-data-bounded-observation-470.md) supplied the following measured facts.

The single `AI Engineer` keyword query for Hanoi, Vietnam, past month, with selective search, returned a `202` handoff carrying a `snapshot_id` and a `retry-after` of 30 seconds.
Progress reported `ready` on the first poll and the snapshot downloaded with ten records and a provider error count of zero.
The provider-reported collection duration was 36.326 seconds, and the client measured 37.22 seconds to the `202`, so the handoff occurred well inside the documented one-minute synchronous limit and is not explained by that documented trigger.

The two hard controls held.
A body-level `limit_per_input` of 10 produced exactly ten records, and the documented `custom_output_fields` selector produced a snapshot containing no field outside the requested set.
This matters because it makes the record count a declared cap rather than a local truncation, which is what allowed the completeness ambiguity below to be detected at all.

All thirteen requested fields were present in all ten records, so no field was lost to the selector.
Two of them are present and explicitly null in every record rather than absent: `apply_link` and `country_code`.
`application_availability` was `true` in every record while `apply_link` was null in every record, so a true availability signal does not imply an existing application link.

The `country_code` null is now measured rather than incidental.
`country: VN` was submitted and was echoed back exactly, and `country_code` was still null in all ten records, so no field in the record carries country evidence for these results.

`discovery_input` behaved differently from its documentation example.
All ten of its members were present and the five submitted filters round-tripped with exact value matches, but the five omitted filters were echoed as empty strings rather than null.
The echo therefore cannot distinguish an omitted filter from a filter submitted as empty, and the documented example's null values were not reproduced.
The documented input key `jobs_to_not_include` has no echo member at all.

Every `url` value was on the `www.linkedin.com` host, which supports LinkedIn as the claimed origin platform and nothing more.
`job_posting_id` was present and distinct in all ten records, which says nothing about stability across time because only one observation exists.
`job_posted_date` was ISO 8601 with a `Z` suffix in every record while `job_posted_time` was a relative "ago" string in every record, so the two temporal fields use different representations with no documented reconciliation.

The observed count of ten equals the declared cap, and no cursor, page token, next link, total-count field, or completion flag was returned.
Nothing in the observed state separates "the provider found exactly ten" from "the provider found more and stopped at the cap".

## Request-to-result state map

| State | Evidence | Required future adapter outcome | Unsafe interpretation prohibited by the blueprint |
| --- | --- | --- | --- |
| Configuration and authorization | The endpoint requires a Bearer token, and the historical failure named an inactive customer. | Record provider configuration identity without storing credentials, authorization result, request digest, and controlled failure category. | Treating a valid token, HTTP success, or provider account as source authorization. |
| Submission | Keyword discovery documents `POST /datasets/v3/scrape`, `dataset_id`, `type=discover_new`, and `discover_by=keyword`. | Persist the collection-plan version, scope, requested fields, and provider request reference before interpreting results. | Calling an accepted request complete coverage. |
| Immediate response | Synchronous requests document HTTP 200 with records when completed within one minute, or HTTP 202 with a `snapshot_id` and `Retry-After` when processing continues. The bounded observation observed the 202 branch at 37.22 seconds with a provider collection duration of 36.326 seconds, which is below the documented limit. | Preserve the HTTP status, headers, body representation or digest, and whether records or a snapshot reference were actually received. Branch on the status code rather than predicting an inline result from elapsed time. | Assuming every accepted request is a completed observation. |
| Deferred completion or delivery | Progress documents `GET /datasets/v3/progress/{snapshot_id}` with `starting`, `running`, `ready`, `failed`, and `canceled`. Observed `ready` on the first poll, carrying integer `records` and `errors` counts plus `collection_duration`, `avg_duration_per_input`, and `dataset_id`. | Poll or accept delivery only under a later approved operational policy, record every state transition, and attach a snapshot reference when supplied. | Treating request acceptance or `running` as a completed observation. |
| Successful result | The capped spike observed HTTP 200 and ten records. The bounded observation observed the same ten records through a 202 handoff and a `ready` snapshot instead, with a provider error count of zero. | Record a successful transport outcome separately from scope completion and per-record normalization outcomes. | Treating 200 or a non-empty array as provider authorization, source availability, or complete scope. |
| Empty result | Progress documents `No data found in discovery` and `Snapshot is empty` as failed-state messages. | Preserve the exact provider state and declared query scope, then mark coverage incomplete unless a later source-specific completion rule proves otherwise. | Expiring prior listings or equating empty discovery with no matching LinkedIn jobs. |
| Partial result | `include_errors=true` is documented to include a detailed error report, but its result shape is not specified. | Retain the error representation, successful-input and failed-input counters, and per-input relationship when available. | Dropping error-bearing inputs or presenting partial records as a complete run. |
| Schema variation | The documented example is a schema claim, and no version or compatibility policy is documented for this endpoint. | Validate the received artifact against a versioned adapter schema and quarantine unknown, missing-required, or type-changed shapes. | Silently discard new fields, coerce invalid types, or assume example fields are stable. |
| Provider validation failure | Progress lists `Input validation failed: DETAILS`, and the historical request received an activation-related 400. | Preserve status, provider message, input digest, and non-retriable classification unless provider documentation later states otherwise. | Retrying an unchanged invalid or blocked request indefinitely. |
| Authentication or account failure | Progress lists `Account is suspended` and `Account is new, please activate it in account settings`. | Classify as authorization-blocked or provider-account failure and stop automatic collection under the plan. | Retrying as a transient source outage or changing lifecycle state. |
| Limit, rate, timeout, and transport failure | Synchronous requests have a one-minute timeout that becomes a 202 handoff. The async guide reports a 5,000 active-job limit, and says 429 requires stopping new requests, honoring `Retry-After` when present, or bounded exponential backoff. | Record the unaltered response or local timeout, stop dispatch on 429, and mark the run failed or incomplete until a later policy supplies bounded retry rules. | Assuming a retry is free, idempotent, or safe for source lifecycle. |
| Retry or replay | The async guide says to retry individually failed URLs in a separate request, but no endpoint-specific idempotency key or replay contract is documented. | Use the blueprint's run and delivery idempotency keys, keep every attempted provider request distinct, and replay retained artifacts only as a replay. | Reissuing a request as though it were the same observation or refreshing retrieval time from a replay. |
| Pagination and termination | Discovery can cap results per input, and the synchronous requests page documents a body-level `limit_per_input` that was observed to work. The keyword page documents no cursor, page token, next link, or terminal-completeness signal, and the bounded observation returned none. | Store the declared limit and any observed termination evidence as scope facts, and keep the declared cap beside the observed count so the two cannot be conflated. | Treating the first array, a fixed cap, or an empty page as full-inventory coverage. |
| Result retention | The Scraper API documentation says snapshots remain downloadable for 30 days after job completion. | Record the provider deletion deadline and require a separately authorized project retention representation and period before retaining artifacts. | Treating provider availability as a project retention right or importing Scraper Studio's different retention periods. |

## Field, identity, and provenance matrix

The following classifications describe the field names in the current documentation and the historical spike.
A field in a Bright Data response is provider-delivered evidence, not independently verified LinkedIn truth.
`Candidate origin-platform fact` means the name or example suggests LinkedIn provenance, but the documentation does not supply a contractual source-field definition.

| Field or concept | Status | Classification and required preservation |
| --- | --- | --- |
| `dataset_id` | Documented | Provider configuration identifier. Preserve it with the provider request and do not use it as a source or listing identity. |
| `snapshot_id`, progress `status`, `error_message`, webhook delivery reference | Observed and documented | Provider execution and delivery facts. Observed to appear only in the 202 handoff body and the progress envelope, never inside the result records, and the progress envelope also carried integer `records` and `errors` counts plus `collection_duration`, `avg_duration_per_input`, and `dataset_id`. No `error_message` or webhook reference was observed. Preserve the exact value, transition time, and endpoint family. |
| `job_posting_id` | Observed and documented | Candidate origin-platform listing identifier because the documentation example pairs it with a LinkedIn job URL. Observed present and distinct in all ten records of one snapshot. Preserve the field path and value as a source-listing-key candidate, while leaving stability, uniqueness, and formal source meaning unknown. |
| `company_id`, `title_id` | Documented only | Candidate origin-platform identifiers in the example. Preserve as distinct source fields, not as a verified company identity or a cross-source key. |
| `url`, `company_url`, `apply_link`, `job_poster.url` | `url` and `apply_link` observed; all documented | Candidate origin-platform URLs. Every observed `url` was on the `www.linkedin.com` host, and every observed `apply_link` was present and explicitly null rather than absent, so that null is a provider assertion of no value and still not a closed or expired listing. Preserve each field name, original value, absence, and null separately. Do not equate a provider-returned URL with an accessible page, an employer origin, or an application outcome. |
| `job_title`, `company_name`, `job_location`, `job_summary`, `job_description_formatted`, `job_function`, `job_industries`, `job_employment_type`, `job_seniority_level` | The first three observed; all documented | Candidate origin-platform display or label fields. Preserve text, locale when supplied, field path, and value state. `job_seniority_level` remains an exact `source_level` candidate, not technical seniority or leadership scope. |
| `job_posted_date`, `job_posted_time` | Both observed; both documented | Candidate origin-platform date fields. Observed as ISO 8601 with a `Z` suffix and as a relative "ago" string respectively, in the same records, with no documented reconciliation between the two forms. Preserve the raw value and field name. The documentation does not define their event semantics, timezone policy, or whether either is authoritative enough for posted-date or lifecycle rules. |
| `country_code`, `discovery_input` | Both observed and documented | `country_code` is a candidate source field, observed present and explicitly null in all ten records even though `country: VN` was submitted and echoed back exactly, so it provided no country evidence and must never be back-filled from request context. `discovery_input` is provider-generated acquisition context that must retain its request-field path and must not fill a missing source value. Observed to echo all five omitted filters as empty strings, so it cannot evidence which filters were applied and the request body must be stored separately as its own record. |
| `application_availability`, `is_easy_apply` | `application_availability` observed; both documented | Candidate source visibility signals. Observed as boolean `true` in all ten records while `apply_link` was null in all ten records, so a true value does not imply an existing application link. Preserve raw boolean or missing state but do not map either to open, closed, or expired without a later source-specific lifecycle decision. |
| `job_num_applicants`, `job_poster`, `company_logo`, `base_salary`, `job_base_pay_range`, `salary_standards` | Documented only | Candidate source fields or provider representations. Preserve field-specific null, shape, and text states. Do not infer applicant data, compensation semantics, employer identity, or availability. |
| Keyword inputs: `location`, `keyword`, `country`, `time_range`, `job_type`, `experience_level`, `remote`, `company`, `selective_search`, `jobs_to_not_include`, and `location_radius` | Observed as a filter echo; all documented | Provider acquisition facts. Five keys were submitted and observed to echo back with exact value matches, while `jobs_to_not_include` produced no echo member at all. Preserve the exact submitted input, omitted-versus-empty state, API version, and declared scope as a record separate from the echo. They are filters, not record facts. |
| `include_errors`, `notify`, `endpoint`, `format`, and custom output fields | `custom_output_fields` observed; the rest documented in the endpoint or linked asynchronous documentation | Provider request and delivery configuration. Preserve each setting because it affects error visibility, result form, and the evidence available to a future adapter. The `custom_output_fields` selector was observed to suppress every unrequested field, and a body-level `limit_per_input` was observed to cap the result count, so both belong in the declared-scope record rather than only in the request. |

## Evidence classification by capability

| Capability | Classification | Basis and limitation |
| --- | --- | --- |
| Account activation can block a request. | Observed | One historical request returned 400 `Customer is not active`. The general failure taxonomy remains unmeasured. |
| A keyword discovery request can return ten restricted-field records. | Observed | One historical request returned HTTP 200 and ten records, and the bounded observation returned ten records through the snapshot path with zero unrequested fields. Neither measures coverage. |
| Keyword discovery accepts the documented filters. | Observed as an echo | All five submitted filters were echoed back with exact value matches, but the echo renders omitted filters as empty strings, so acceptance of a filter was not independently confirmed and the echo cannot prove which filters were applied. |
| A synchronous request returns an inline response when it completes within one minute. | Disproven as a guarantee | The bounded observation returned a 202 handoff after 37.22 seconds, with a provider collection duration of 36.326 seconds, so an inline 200 cannot be assumed and elapsed time does not predict the response shape. |
| A synchronous request hands off to asynchronous retrieval after its timeout. | Observed, but the trigger is unknown | The bounded observation received HTTP 202 with `snapshot_id` and `Retry-After: 30` and a "Snapshot is not ready yet" message, well inside the documented one-minute limit. The documented timeout is therefore not the only handoff condition, and the real condition remains uncharacterized. |
| Snapshot progress may be `starting`, `running`, `ready`, `failed`, or `canceled`. | Partially observed | Only `ready` was observed, on the first poll, with integer `records` and `errors` counts. The other states remain documented-only, and whether every LinkedIn keyword request enters that state machine is still not observed. |
| A provider error report can accompany results. | Documented-only | `include_errors=true` was submitted on the bounded observation, but the single input succeeded and the progress envelope reported an `errors` count of zero, so the report schema and input association remain unpublished and unobserved. |
| Pagination, terminal completeness, and idempotency semantics. | Unknown | No cursor, completion rule, or endpoint-specific idempotency key was found in the reviewed primary documentation, and the bounded observation returned none. The observed count equalled the declared cap, so the response cannot distinguish an exhausted scope from a truncated one. |
| Timeout, rate limiting, and bounded retry behavior. | Partially observed | The bounded observation measured a handoff below the documented timeout, which is timeout-related but not the documented behavior. Rate limiting and 429 handling remain unobserved for LinkedIn Jobs. |
| LinkedIn Jobs Web Scraper API result retention. | Documented-only | The Scraper API documents a 30-day snapshot download window. It does not confer project retention rights. |
| Schema compatibility, versioning, and deprecation notice. | Unknown, with one observed drift | No endpoint-specific schema evolution policy was found. The bounded observation did see `discovery_input` echo omitted filters as empty strings where the documentation example shows null, which is a live example of documentation and behavior diverging. |

## ADR-0055 contract assessment

| ADR-0055 or blueprint rule | Assessment | Provider-specific requirement |
| --- | --- | --- |
| Provider identity is not source identity. | Accommodated. | Record Bright Data as acquisition provider and LinkedIn only as the claimed origin platform supported by field and URL evidence. |
| Missing is distinct from source-empty, failed extraction, and unsupported. | Accommodated, and now backed by measured states. | Preserve the explicit null `apply_link`, the explicit null `country_code`, the empty-string echo of omitted filters in `discovery_input`, fields suppressed by the output selector, and error-bearing inputs as four different states. The observed null `apply_link` is not an absent key, and the empty-string echo is not a null. |
| Successful HTTP response is not authorization, complete scope, or listing availability. | Directly required, and demonstrated. | The observation produced HTTP 200 with ten records and a provider error count of zero, and still yielded no coverage, authorization, or availability conclusion. Preserve the 200 separately from account authorization, source rights, complete scope, and lifecycle conclusions. |
| Only a completed declared scope can affect lifecycle. | Not yet measurable, and now known to be blocked. | The observed count equalled the declared cap and no terminal-completeness signal exists, so no completion claim is even representable. Do not make availability transitions until pagination, termination, and source lifecycle signals are characterized. |
| Raw artifacts and observations are append-only and rebuildable. | Accommodated, and exercised. | The observation retained a field-presence map, the request digest, provider references, and response digests without retaining row-level data. Retain an allowed raw or redacted representation with digest, request context, provider references, and field-presence map. |
| Source listing and provider identifiers remain distinct. | Accommodated. | Keep `job_posting_id`, provider snapshot, dataset, and delivery identifiers separately pending stable-ID measurement. |
| Normalization has field provenance and quarantine. | Directly required, with a live example. | The `discovery_input` echo diverged from its documentation example, which is a quarantine condition. Validate field shape and quarantine schema changes or missing publishable identity rather than normalizing silently. |
| Runs, duplicate delivery, and replays are idempotent. | Blueprint supplies the system rule, not provider evidence. | Generate project idempotency keys and record a later provider-specific retry policy because Bright Data idempotency is undocumented. |

The blueprint accommodates the documented provider boundary without change.
It does not supply the missing provider facts, source authorization, retention right, or lifecycle evidence.
The bounded observation supplied the request-path, state-machine, and field-state facts that the blueprint already anticipated, and it did not require a change to that blueprint.
No adapter implementation is authorized by this finding.

## Completed follow-up evidence specification

The specification below was run once as [#470](https://github.com/Park-Hip/InternHunterAgent/issues/470) and is retained here as the record of what was specified and measured.
The outcome is in [its evidence record](bright-data-bounded-observation-470.md) and the recommendation is in the [decision note](bright-data-observation-470-decision.md).

| Element | As specified, and as executed |
| --- | --- |
| Scope | One keyword-discovery request using the already characterized `AI Engineer` and Hanoi input, no pagination, with a hard limit of ten returned records. Executed as one request, one progress poll, and one download, with no URL followed. |
| Requested field set | The thirteen enumerated fields, submitted through the documented `custom_output_fields` selector. All thirteen were present in all ten records and the selector suppressed every unrequested field. |
| Retention representation | A field-presence and value-state map, the request digest, provider references, response digests, and safe headers. No raw payload, no row-level data, and no credential was retained. |
| Required state evidence | Captured as a 202 handoff, a `ready` progress transition with integer `records` and `errors` counts, and a 200 download. No per-input error representation was exercised because no error occurred. |
| Success criteria | Met. The response path, provider references, result count, field-presence and null states, and the absence of any terminal completeness signal were all identified, with no coverage, stable-ID, source-authority, or lifecycle claim made. |
| Failure criteria | Not triggered. The account was active, the request succeeded, and the approved evidence representation was retained. |

Three follow-up gaps remain open and are named in the decision note.
The handoff trigger is uncharacterized, record-level country provenance is absent, and the error-report shape is still unobserved.

A later semantic-mapping study needs a separately approved, larger reviewable corpus and remains governed by the source-level semantics decision.
A single ten-record observation, even a clean one, cannot support semantic mapping.
