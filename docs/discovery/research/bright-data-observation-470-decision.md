# Decision note: #470 observation outcome and recommended next step

> **Date:** 2026-09-27
>
> **Input:** [bounded Bright Data observation](bright-data-bounded-observation-470.md) and the [Bright Data provider profile](bright-data-linkedin-jobs-provider-profile.md).
>
> **Decision:** open the provider-neutral evidence-schema and shadow-migration implementation proposal, and open one narrowly scoped provider-boundary follow-up alongside it.

## Recommendation

The observation completed and supports opening the provider-neutral evidence-schema and shadow-migration proposal.
It does not identify a provider-boundary gap that blocks that work, because every gap it did find is a state the provider-neutral schema is required to represent anyway.

The gaps block something narrower and later: provider-specific semantic mapping and any lifecycle or coverage rule.
Those must not be proposed yet.

## Why the schema proposal is unblocked

ADR-0055 and the blueprint already require the system to keep provider identity, source identity, declared scope, and per-field value states separate.
The observation produced concrete, retained examples of each, which is exactly the evidence a provider-neutral schema needs in order to be specified without guessing.

The observation also showed that the two hard controls a future adapter depends on, a server-side record cap and a server-side field selector, are real and documented.
An adapter design can therefore be specified against a bounded request rather than an open-ended one.

## Two schema requirements this observation creates directly

These are not new opinions. They are consequences of the observed provider state, and they should be requirements in the next proposal rather than discoveries during implementation.

1. **Store the declared cap beside the observed count.**
   The observed result count equalled the declared `limit_per_input` of 10, which makes the count uninformative about coverage.
   Any evidence record that stores an observed count without the declared cap beside it will be read as a coverage claim.
   The schema must carry declared scope and observed outcome as separate fields that cannot be conflated.

2. **Store the request body as its own record, never reconstruct it from the provider echo.**
   Every filter that was omitted came back in `discovery_input` as an empty string, so the echo cannot distinguish an omitted filter from one submitted as empty.
   The echoed filters round-tripped exactly, which makes the echo look authoritative while silently destroying the omitted-versus-empty distinction.
   A schema that stores acquisition context only in provider-echo form would lose the ability to state what was actually asked for.

## Why the provider-boundary follow-up is still needed

Open a single narrowly scoped follow-up covering the two findings below.
Both are provider-behaviour facts that no amount of provider-neutral design can substitute for, and neither can be resolved by a single request under the #470 bounds.

1. **The 202 handoff trigger is unknown.**
   The request handed off to a snapshot after 37.22 seconds, and the provider reported a collection duration of 36.326 seconds, both well inside the documented one-minute synchronous limit.
   A client cannot predict whether a request will return records inline or a snapshot reference.
   The follow-up should characterise the condition that produces the handoff, because it decides whether a future adapter needs synchronous-only handling, snapshot polling, or both.

2. **Record-level country provenance is absent.**
   `country_code` was null in all 10 records even though the submitted `country: VN` filter was echoed back exactly.
   No field in the record carries country evidence for these results.
   The follow-up should determine whether that is a LinkedIn Jobs extraction limitation, a provider normalization choice, or region-dependent behavior, and it should state plainly whether the project may use `job_location` as a country proxy at all.

## What is explicitly not recommended yet

- No provider selection. Bright Data remains a characterized candidate.
- No source selection. LinkedIn remains a claimed origin platform, supported only by the returned URL host.
- No coverage, completeness, or inventory claim. The cap was reached, so the observed count proves nothing about how many matching listings exist.
- No lifecycle or availability rule. No terminal-completeness signal was observed, so no listing can be expired, closed, or renewed on this evidence.
- No semantic mapping from `job_seniority_level` or `job_employment_type` to project seniority concepts. They are provider-delivered display labels with low cardinality in this sample.
- No stable-identity claim for `job_posting_id`. It was distinct across 10 records in one snapshot, which says nothing about stability across time.
- No production collection, webhook, scheduling, or adapter implementation.

## Follow-on evidence that remains necessary

A larger, separately approved reviewable corpus is required before any provider-specific semantic mapping or controlled production activation.
A single 10-record observation, even a clean one, cannot support semantic mapping.
The single-input success also leaves the error-report shape, partial-result behaviour, and retry safety entirely unmeasured.
