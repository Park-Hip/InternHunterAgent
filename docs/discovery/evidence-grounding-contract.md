# Evidence-grounding contract

> **Status:** Proposed contract for [issue #435](https://github.com/Park-Hip/InternHunterAgent/issues/435).
>
> **Authority:** This contract refines the corpus truth boundary in [mvp-spec.md](mvp-spec.md) and the deterministic fact-bundle contract in [boundary-contract-ledger.md](boundary-contract-ledger.md).
>
> **Scope:** It defines the minimum inspectable evidence required for factual labels in one technology-frequency result.

## Purpose and authority

The model agent may present evidence but never establishes, repairs, normalizes, groups, calculates, or cites a factual result itself.
Only registered deterministic tools can turn retained corpus evidence into a reportable label result.
A source URL alone, an unlinked citation, a model-generated explanation, or a post-hoc web lookup is not evidence under this contract.

This document does not authorize corpus acquisition, retention-policy changes, live lookup, a source provider, a database schema, storage format, evidence extractor, public response shape, or a provenance technology.
The immutable corpus version and reviewed normalized-label set remain preconditions supplied through separately approved work.

## Required evidence graph

Every reportable occurrence of a normalized technology label must have this complete deterministic chain:

1. One `corpus_version` identifies the fixed permitted input.
2. One `stable_record_id` identifies the selected, de-duplicated corpus record.
3. One retained source-evidence item identifies the original material retained for that record.
4. One retained technology-evidence item links the reviewed `normalized_label` to a bounded source excerpt or location within that retained material.
5. One frequency result includes that record-label support in its evidence set or records its exclusion.

A normalized label represents an explicit technology name in retained evidence.
It must not represent a semantic category, inferred capability, synonym expansion, embedding match, or model judgment.
The same retained support may contribute to the count only under the documented counting and de-duplication rule.

## Evidence item schema

The deterministic tool returns safe evidence items rather than raw corpus or persistence objects.

| Field | Requirement |
| --- | --- |
| `corpus_version` | Equals the version used by the frequency result. |
| `stable_record_id` | Identifies one selected corpus record after the documented de-duplication rule. |
| `normalized_label` | Is one member of the reviewed fixed normalized-label set used by the result. |
| `source_evidence_ref` | Is a stable retained-source reference resolvable within the selected corpus version. |
| `technology_evidence_ref` | Is a stable retained reference that links the normalized label to the record's source material. |
| `excerpt_or_locator` | Is a bounded safe excerpt or retained-material locator sufficient for a reviewer to inspect the explicit technology mention. |
| `evidence_status` | Is exactly `complete` for reportable support or an explicit non-reportable status defined below. |

An evidence item must not expose credentials, unrestricted raw records, internal storage paths, unapproved personal data, provider output, or model reasoning.
A later delivery contract may choose how to serialize safe evidence items, but it must preserve enough information to inspect every reported label.

## Result-level evidence schema

For each item in `ranked_results`, the deterministic fact bundle must include an evidence collection with all of the following:

| Field | Requirement |
| --- | --- |
| `normalized_label` | Equals the reported label. |
| `supporting_record_ids` | Lists the stable identities that deterministically support the label's reported count. |
| `evidence_items` | Contains a complete evidence item for every required record-label support under the counting rule. |
| `support_count` | Equals the count derived from the supporting records under the documented counting rule. |
| `evidence_completeness` | Is `complete` only when every required support has complete retained evidence. |

The tool must validate that each evidence item belongs to the same corpus version, selected scope, record, and normalized-label set as the result.
The tool must validate that `support_count`, the result count, and the evidence collection agree under the stated counting rule.

## Completeness and exclusion rules

| Evidence status | Meaning | Tool behavior | Model-agent behavior |
| --- | --- | --- | --- |
| `complete` | The record-label chain is retained, stable, and internally consistent. | May contribute it to a reportable result. | May state only the fact and evidence supplied by the tool. |
| `missing_source_evidence` | The record lacks retained original-source evidence. | Excludes the affected support and records the limitation. | Must not report the unsupported fact. |
| `missing_label_link` | The record has source material but no retained link from the label to an explicit mention. | Excludes the affected support and records the limitation. | Must not infer a label or cite the source generically. |
| `inconsistent_evidence` | Version, stable identity, label, or count linkage conflicts with the requested analysis. | Treats the support as unavailable and records a safe limitation. | Must not reconcile the conflict by judgment. |
| `unavailable_evidence` | The required retained evidence cannot be read. | Returns a bounded missing-evidence or internal-unavailability outcome. | Must not substitute another source or stale evidence. |

Missing evidence never permits a partial claim that silently retains an unsupported count.
For this MVP, any qualifying record or label with incomplete required evidence produces the `missing_evidence` outcome and no ranked factual result.
The tool records the excluded support and safe limitation, but it does not recalculate a partial ranking from the remaining records.
This conservative rule protects the inspectable denominator and is invariant for the same corpus version and request.

## Grounding rules for the final answer

The model-agent runtime may transform a deterministic fact bundle into readable natural language.
It may not add a factual technology, count, percentage, corpus characteristic, source interpretation, scope condition, or limitation that is absent from the bundle and evidence items.
It must identify the corpus version, selected scope, matching-record count, counting and de-duplication rules, reported labels, evidence, and relevant limitations.

The final answer must state that it reports observed labels in the fixed corpus rather than a current-market or market-wide estimate.
A no-match or missing-evidence outcome must remain explicit and must not be replaced with advice, a recommendation, semantic grouping, or an ungrounded alternative.

## Evidence-port and test-double seam

The corpus and retained-evidence port is read-only and returns immutable fixture or production values that can establish the evidence graph.
A contract double supplies named corpus versions, stable records, complete evidence chains, and deliberately incomplete or inconsistent cases.
It does not return generated prose or declare evidence complete without the linked source and technology references.

Tests must be able to inspect the evidence graph for each reported label without a live network call or provider invocation.
They must prove that removing or corrupting a required evidence link yields the required exclusion or bounded outcome and never a citation invented by the model.

## Conformance checks

1. Every reportable label result has complete evidence items for every required support under the counting rule.
2. Every evidence item resolves to the result's corpus version, stable record, normalized label, and retained source material.
3. A missing source item, label link, or inconsistent link cannot remain in a reportable count.
4. The final answer contains no factual claim that is absent from the deterministic fact bundle and its evidence items.
5. Evidence inspection and fixture-based testing need no live lookup, model judgment, or access to an unregistered capability.
