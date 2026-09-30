# Bright Data adapter fixtures

Nothing in this directory is provider output, and nothing in it is real.

The bounded observation behind these tests
(`docs/discovery/research/bright-data-bounded-observation-470.md`) deliberately retained
aggregate and field-presence evidence only: no row-level job data, no credential, and no
response payload.
So there are no recorded bytes to replay, and every provider response here is a
**reconstruction** constrained by facts that were recorded.

| File | What it is |
| --- | --- |
| `recorded_evidence.json` | The transcribed observation: the request of record, the observed provider states, the field-presence matrix, the terminal-completeness findings, and the digests. This is the evidence the fixtures are checked against. |
| `snapshot_records.json` | Ten records reconstructed to satisfy that matrix. Invented employers, titles, identifiers and locations. |

## What the reconstruction does and does not claim

It claims the shapes and value states the observation measured: `apply_link` and
`country_code` explicitly null in all ten records, `discovery_input` echoing the five
submitted filters exactly and the five omitted ones as empty strings, ISO 8601
`job_posted_date` values, relative `job_posted_time` values, three distinct
`job_seniority_level` values, one `job_employment_type`, `application_availability` true
everywhere, every `url` on the `www.linkedin.com` host, and ten distinct
`job_posting_id` values.

It does not reproduce the recorded digests, byte counts, or the exact string values, and
nothing here is evidence that any particular listing exists.
The tests assert the shape and the value states, never the contents.

## The one recorded fact deliberately left out

The 202 handoff body carried the keys `message`, `snapshot_id` and `status`, and the value
of `status` was not recorded.
It is therefore absent from the reconstructed handoff rather than invented, which also
proves the adapter never requires it: the handoff branch keys off the HTTP status code and
the snapshot identifier, nothing else.

## What is absent on purpose

No credential, no authorization header, and no provider account reference is present in any
file here.
The credential appears in `config/ingestion.yaml` as a named secret location and nowhere
else, which is the boundary the blueprint requires.
