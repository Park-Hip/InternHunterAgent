# Bounded Bright Data LinkedIn Jobs observation for #470

> **Observation window (UTC):** 2026-09-27T08:43:35Z to 2026-09-27T08:44:34Z
>
> **Result:** completed. One collection request was dispatched and reached a terminal provider state.
>
> **Retention:** aggregate and field-presence evidence only. No row-level job data, no credential, and no response payload is retained in this repository.
>
> **Governing design:** [ADR-0055](../../decisions/adr-0055-evidence-first-ingestion-contract.md) and the [evidence-first ingestion blueprint](../../decisions/evidence-first-ingestion-blueprint.md).

## Scope of what was executed

Exactly one collection request was sent.
No other collection request was sent, and none will be.
The snapshot produced by that single request was polled once and downloaded once, which is the documented handoff needed to reach this one request's terminal state.

| Bound from the issue | As executed |
| --- | --- |
| One `AI Engineer` query in Hanoi, Vietnam | One input: `keyword` `AI Engineer`, `location` `Hanoi`, `country` `VN` |
| Previously characterized discovery inputs | `time_range` `Past month`, `selective_search` `true` |
| Record omitted-versus-empty for every filter | Six documented filter keys were omitted entirely rather than sent empty. Both forms are listed below. |
| No pagination | No cursor, `next` link, result URL, company URL, or application URL was followed. |
| Hard maximum of 10 returned records | `limit_per_input: 10` in the request body, enforced server-side. Returned exactly 10. |
| No retries | Zero retries. The collection request was sent once. |
| Requested field set | The 13 fields enumerated in the issue, submitted through the documented `custom_output_fields` selector. |

## Pre-dispatch control confirmation

Both controls were confirmed in primary Bright Data documentation before any request was sent, and both were then confirmed to work by the observation itself.

### Ten-record result ceiling

The [Synchronous requests](https://docs.brightdata.com/api-reference/scrapers/synchronous-requests) OpenAPI schema for `POST /datasets/v3/scrape` defines `limit_per_input` on the request body object:

> Maximum number of records to return per input. Applies to discovery requests, whose result count is otherwise open-ended.

The same page states the parameter is a body field and is silently ignored as a query parameter on `/scrape`, so it was sent in the body.
The cap is therefore a provider-side bound and not a local truncation.

### Output field selector

The same schema defines `custom_output_fields`:

> List of output columns, separated by `|` (e.g., `url|about.updated_on`). Filters the response to include only the specified fields.

It was sent both as a query parameter and as a body field, because both placements are documented.
The observed snapshot returned zero fields outside the requested set.

### Spend ceiling

Web Scraper API is billed per successfully delivered record at the published pay-as-you-go rate of USD 1.50 per 1,000 records, with no charge for failed deliveries and no per-request fixed fee.
A server-capped response of at most 10 records is therefore bounded at USD 0.015 of usage for this request, which is roughly 1.5 percent of the USD 1 ceiling the issue requires.
The account-specific tariff was not independently inspected; the bound rests on the published per-record rate plus the server-side record cap.

## Request of record

| Element | Value |
| --- | --- |
| Method and path | `POST https://api.brightdata.com/datasets/v3/scrape` |
| `dataset_id` | `gd_lpfll7v5hcqtkxl6l` |
| `type` / `discover_by` | `discover_new` / `keyword` |
| `format` | `json` |
| `notify` | `false` |
| `include_errors` | `true` |
| `limit_per_input` | `10` |
| `custom_output_fields` | the 13 issue fields, pipe-separated, sent on the query string and in the body |
| Request digest (query plus canonical body, SHA-256) | `037c17c56e3ec8eea0eacd103e2cf18552676aabb2ac5c60bf1d07c2f97d8880` |
| Canonical body digest (SHA-256) | `90f4ec4be5d33056c4d6017c4ca460f3b311fbeb13a6125bba3aa6451df3b6f2` |

### Submitted versus omitted discovery inputs

Omitted keys were absent from the request body rather than sent as empty strings, so that omitted-versus-empty remained distinguishable on the request side.

| Documented input key | Submitted value |
| --- | --- |
| `keyword` | `AI Engineer` |
| `location` | `Hanoi` |
| `country` | `VN` |
| `time_range` | `Past month` |
| `selective_search` | `true` |
| `job_type` | omitted |
| `experience_level` | omitted |
| `remote` | omitted |
| `company` | omitted |
| `jobs_to_not_include` | omitted |
| `location_radius` | omitted |

## Observed provider state transitions

| Step | Observed |
| --- | --- |
| Submission | Accepted. Client-measured elapsed time to the response was 37.22 seconds. Zero retries were performed. |
| Immediate response | `HTTP 202 Accepted`, `content-type: application/json; charset=utf-8`, `content-length: 114`, `retry-after: 30`. |
| Handoff payload | `snapshot_id` `sd_mujknayt1rvg0aadjq` and the message "Snapshot is not ready yet, try again in 30s". The payload keys were `message`, `snapshot_id`, `status`. |
| Handoff body digest (SHA-256) | `e6a91c904c6917a40f7f5ca1476c18642358a90d781510d1bf5c75e5fd8736d8` |
| Progress poll | One poll of `GET /datasets/v3/progress/{snapshot_id}` returned `HTTP 200` with `status` `ready`. No `starting`, `running`, `failed`, or `canceled` state was observed. |
| Progress payload | Keys were `avg_duration_per_input`, `collection_duration`, `dataset_id`, `errors`, `records`, `snapshot_id`, `status`. `records` was the integer 10 and `errors` was the integer 0. |
| Provider timings | `collection_duration` 36326 ms and `avg_duration_per_input` 36326 ms for a single input. |
| Delivery | `GET /datasets/v3/snapshot/{snapshot_id}` with `format=json` returned `HTTP 200`, `content-type: application/json; charset=utf-8`, `content-length: 8703`. |
| Snapshot body digest (SHA-256) | `7531df8384cda8c4389c3993167cca728247ca81141d8aeae48254fa2530826e` |
| Result count | 10 records, equal to and not greater than the declared cap of 10. |
| Provider errors | None. The progress endpoint reported an `errors` count of 0. |
| Error association | Not observable. `include_errors` was requested, but no error occurred, so no error-report shape was exercised. |

### The 202 handoff did not match its documented trigger

The provider documentation states that a synchronous request returns `HTTP 202` when processing exceeds a one-minute limit.
In this observation the request returned `202` at 37.22 seconds client-measured, and the provider reported a collection duration of 36.326 seconds.
Collection therefore completed about 23 seconds before the documented one-minute limit, and the 202 body stated that the snapshot was "not ready yet" rather than that processing was still running.
The documented timeout is not a sufficient explanation for the handoff that was actually observed.
The real trigger for this handoff is unknown, and a future client must not predict a 200 by elapsed time.

## Field presence and value-state matrix

Ten records were returned and all 13 requested fields were inspected in every record.
No requested field was absent as a key, and no field was dropped by the selector.

| Requested field | Present | Explicit null | Empty string | Value state over 10 records |
| --- | --- | --- | --- | --- |
| `url` | 10 | 0 | 0 | non-empty string |
| `job_posting_id` | 10 | 0 | 0 | non-empty string |
| `job_title` | 10 | 0 | 0 | non-empty string |
| `company_name` | 10 | 0 | 0 | non-empty string |
| `job_location` | 10 | 0 | 0 | non-empty string |
| `job_posted_date` | 10 | 0 | 0 | non-empty string matching ISO 8601 with a `Z` suffix |
| `apply_link` | 10 | 10 | 0 | explicit null in every record |
| `country_code` | 10 | 10 | 0 | explicit null in every record |
| `discovery_input` | 10 | 0 | 0 | object with 10 members |
| `job_seniority_level` | 10 | 0 | 0 | non-empty string, 3 distinct values |
| `job_employment_type` | 10 | 0 | 0 | non-empty string, 1 distinct value |
| `application_availability` | 10 | 0 | 0 | boolean, `true` in all 10 records |
| `job_posted_time` | 10 | 0 | 0 | non-empty relative form, the "ago" pattern, in all 10 records |

| Additional measurement | Observed |
| --- | --- |
| Unrequested fields returned | none. The selector suppressed every field outside the 13 requested names. |
| `job_posting_id` distinctness | 10 present, 10 distinct within this single snapshot. |
| `url` host classification | All 10 values are on the `www.linkedin.com` host. |
| `job_location` non-null | 10 of 10. |
| `job_location` mentioning the requested city | 10 of 10. |

### The two previously unresolved field states

The prior capped spike in [#423](https://github.com/Park-Hip/InternHunterAgent/issues/423#issuecomment-5797556656) reported one record with no application link and a null `country_code`.
This observation resolves both to an exact value state and separates them from absence.

- `apply_link` is **present and explicitly null** in all 10 records.
  It is not an absent key and not an empty string.
  A null application link is therefore a provider-delivered assertion that no value exists for that field, which is stronger than a missing key and must still not be read as a closed or expired listing.
- `country_code` is **present and explicitly null** in all 10 records, even though `country: VN` was submitted and the provider echoed that value back exactly.
  The submitted country filter therefore did not populate the country field.
  `country_code` must never be back-filled from the request context, and it provides no country evidence for these records.
- `application_availability` was `true` in all 10 records while `apply_link` was null in all 10 records.
  A true application-availability signal therefore does not imply that an application link exists. This is a co-occurrence observed in 10 of 10 records, not a rule.

### `discovery_input` echo and the omitted-versus-empty boundary

`discovery_input` is provider-generated acquisition context rather than a source fact, and its behaviour differs from the documentation example.

| Measurement | Observed |
| --- | --- |
| Echo members present | 10 of the 11 documented input keys. `jobs_to_not_include` has no echo member. |
| Submitted filters echoed back exactly | All 5 of `keyword`, `location`, `country`, `time_range`, and `selective_search` matched the submitted value in all 10 records. |
| Omitted filters echoed | All 5 omitted filter keys were echoed in all 10 records as empty strings, never as null. |
| Omitted versus empty distinguishable from the echo | No. An omitted filter and a filter submitted as an empty string are indistinguishable in the response. |
| Documentation example for those members | null. The observed value is an empty string. |

This is the one place where the observation diverges from the documentation, and it is a provider-boundary finding rather than a defect in the request.
Acquisition context reconstructed from the echo cannot evidence which filters were actually applied versus which were defaulted, so the request body must be stored as its own record and the echo must never be treated as the authority on the submitted scope.

## Terminal-completeness signal

| Question | Answer |
| --- | --- |
| Cursor, page token, or next link in the response | none observed |
| Total or estimated count field in the response | none observed |
| Snapshot or dataset reference inside the records | none. Both exist only in the progress and handoff envelopes. |
| Distinguishable "scope complete" flag | none |
| Observable result count | 10, from the progress envelope |

The observed count equals the declared cap of 10.
Because the cap was reached, the count carries no information about whether more than 10 matching records existed.
Nothing in the observed state separates "the provider found exactly 10" from "the provider found more and stopped at the cap", so this observation cannot support any coverage or completeness claim.
The only reason the ambiguity is even visible is that the cap was declared and server-side, which is why the declared cap must be retained beside any observed count in the future evidence schema.

## Assessment against ADR-0055

| Rule | Assessment from this observation |
| --- | --- |
| Provider identity is not source identity | Satisfied. Bright Data is the acquisition provider. LinkedIn is the claimed origin platform, supported only by the `www.linkedin.com` host in all 10 `url` values, which is still a claim rather than verification. |
| Missing is distinct from source-empty, failed extraction, and unsupported | Satisfied only because the selector and cap were declared. The `apply_link` null, the `country_code` null, and the `discovery_input` empty-string echo are three distinct states and must stay distinct. |
| A successful HTTP response is not authorization, complete scope, or availability | Confirmed. HTTP 200 with 10 records and a provider error count of 0 still yields no coverage, authorization, or availability conclusion. |
| Only a completed declared scope may affect lifecycle | Not satisfiable for this provider today. No terminal-completeness signal exists, so no lifecycle transition may be derived. |
| Raw artifacts and observations are append-only and rebuildable | Partially. The digests recorded here allow later verification of a retained artifact, but the raw artifact itself was intentionally not retained. |
| Source listing and provider identifiers stay distinct | Satisfied. `job_posting_id` and `snapshot_id` are separately observed and must stay separate. |
| Normalization has field provenance and quarantine | Required. The documentation-example versus observed divergence in `discovery_input` is exactly a schema-drift condition to quarantine. |
| Runs, duplicate delivery, and replays are idempotent | Unchanged. No endpoint-specific idempotency key was observed. |

## Explicitly unmeasured and still unknown

- Stability of `job_posting_id` over time. Only one observation exists and no second query was permitted.
- Any error-report shape, error-to-input association, or partial-result behaviour. The single input succeeded.
- Behaviour on a failed, empty, or rate-limited request.
- Pagination, cursors, and any terminal-completeness rule.
- Schema compatibility and versioning policy.
- Whether `country_code` is ever populated for any region. Only a Vietnam-scoped query with a null result was observed.
- The account-specific tariff and any account-level spend control.
- Whether the 202 handoff repeats, and under what condition.

## Verification and manual check

- Terminal provider state, snapshot transition, result count, provider error count, and retry behaviour are recorded above.
- The field-presence matrix explicitly resolves the previously observed null `country_code` and absent `apply_link` cases.
- Every claim above traces to a recorded digest, the request context, a provider progress and download response, or a cited Bright Data page.
- Claims that were not measured are listed in the unknown section above rather than asserted.
- A maintainer can confirm the manual check by inspecting the matrix: one query, one collection request, no pagination, exactly ten records under a declared server-side cap of ten, zero retries, and no row-level data or secret in this file.
- `uv run python scripts/docs_lint.py` covers the documentation change.

## Credential and data hygiene

The observation ran against a live paid provider credential supplied for this purpose and held only in process memory.
It was never written to disk, never logged, and never appears in this repository, in the retained evidence, or in any issue or pull request.
A credential pasted into a chat transcript is exposed and must be rotated once this observation is accepted.
The key reported as exposed in the [#423](https://github.com/Park-Hip/InternHunterAgent/issues/423#issuecomment-5797431647) spike comment must still be revoked and must never be reused.

The retained working copies of the runner and the aggregate reports live outside this repository and contain only digests, counts, and value states.
They can be deleted once this record is accepted, and should be deleted if that is preferable.
Bright Data retains its own copy of the snapshot for the documented 30-day Scraper API window, and that provider-side copy is outside this project's control.
