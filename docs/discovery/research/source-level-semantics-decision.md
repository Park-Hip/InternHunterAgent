# Decision memo: preserve source-level semantics before normalization

> **Last verified:** 2026-09-27
>
> **Eviction:** This memo leaves when an approved ingestion data contract adopts or rejects its
> recommended taxonomy posture using an authorized multi-source evidence corpus.

## Recommendation

Select a conservative first taxonomy posture for a future provider-neutral ingestion contract.
Call each normalized, source-specific record a **normalized listing**, not a canonical job.
Preserve a future `vacancy` or opportunity entity for a separately approved cross-source grouping
question.

This posture keeps three different concepts separate.

| Concept | First taxonomy posture | Initial population rule |
| --- | --- | --- |
| Source level | `source_level` is the source's exact label plus source, field name, locale when known, and vocabulary version when known. | Copy the source value without collapsing it into another dimension. |
| Technical seniority | `technical_seniority` may express `intern`, `entry`, `junior`, `mid`, `senior`, or `unknown`. | Set `unknown` unless a later versioned, measured rule has sufficient evidence for the specific source and language. |
| Leadership scope | `leadership_scope` may express `individual_contributor`, `team_lead`, `people_manager`, `executive`, or `unknown`. | Set `unknown` unless an explicit source field or later measured rule supports the value. |

`unknown` is a first-class truthful value, not an empty value to be backfilled from a platform
label, title wording, employer, salary, or model inference.
An implementation may retain versioned title matches as evidence, but a matched title word is not
by itself a semantic fact about technical seniority or people leadership.

This is a decision memo for [issue #461](https://github.com/Park-Hip/InternHunterAgent/issues/461).
It is a documentation recommendation only.
It does not change the frozen `clean_jobs` contract, fixtures, evaluation baselines, API schemas,
raw retention, data rows, source adapter, or deployed service.

## Why this posture is justified

The accompanying [evidence record](source-level-semantics-evidence.md) establishes all of the
following.

1. The historical VietnamWorks AI/Data sample has 112 records and five complete source-level
   labels, but it is one focused historical processed export rather than a current or multi-source
   corpus.
2. `Experienced (non-manager)` contains titles with junior, middle, senior, lead, and manager
   diagnostic words.
   A platform label therefore cannot completely determine technical seniority or leadership scope.
3. Only 26/112 titles have an English technical-level diagnostic word and only 12/112 have an
   English leadership diagnostic word.
   Most records would become fabricated certainty if title wording filled every missing semantic
   value.
4. The historical export does not retain employment type, publication or observation dates, or
   lifecycle fields.
   It cannot establish a complete listing contract from one source.
5. The authorized Bright Data test observed ten in-memory records with restricted core output
   fields, while provider documentation describes a broader LinkedIn schema.
   It supplies no retained Vietnam sample from which mapping coverage or conflict rates can be
   measured.

The recommended posture preserves the complete, observed source fact without promoting that fact
into one of two different meanings that the evidence does not establish.

## Candidate postures compared

| Posture | Measured coverage | Conflict and unknown behavior | Decision |
| --- | --- | --- | --- |
| Collapse each source label into one hierarchy such as intern, entry, experienced, manager, or director. | 112/112 VietnamWorks labels could be mechanically assigned. | The apparent coverage is misleading because 22/89 `Experienced (non-manager)` titles have a diagnostic level or leadership word and title evidence is absent for 68.8% of all records. It also assumes a future provider's labels mean the same thing. | Reject. |
| Derive technical seniority and leadership from title wording. | 23.2% technical-marker coverage and 10.7% leadership-marker coverage under a narrow English-only diagnostic rule. | 68.8% have no diagnostic marker. A word such as lead or manager does not alone prove people-management scope, and the rule has no Vietnamese-language validation. | Reject as a canonical mapping. Retain only as versioned candidate evidence if a future approved contract needs it. |
| Preserve source level and use explicit unknown semantic dimensions. | 100% source-level retention for the historical VietnamWorks export. | Unknowns remain visible instead of becoming inferred facts. A later source-specific rule can be measured and introduced additively. | Select. |

The selected posture is intentionally conservative.
It is a small semantic vocabulary with a broad unknown state, not a claim that the values have been
measured or that every future provider should populate them now.

## Naming and identity boundary

Use `normalized_listing` for the result of applying a versioned, source-specific normalization to
one source listing.
It is not a statement that two listings from different platforms describe the same vacancy.

A future `vacancy` or opportunity entity may group normalized listings only after a separately
approved identity, evidence, false-merge, and false-split decision.
This memo makes no cross-source deduplication recommendation and does not authorize one.

The later contract should preserve source-specific listing identity and immutable raw evidence.
It should also record the normalization version that produced each semantic value or `unknown`.
These are contract-design requirements for [issue #455](https://github.com/Park-Hip/InternHunterAgent/issues/455),
not instructions to modify the current schema.

## Minimum evidence to revisit a mapping

Do not promote a source-level, title-level, or provider field into a canonical semantic mapping
until an authorized provider path produces a retained, reviewable sample with its permitted raw
evidence and provenance.
The smallest acceptable next sample is:

1. At least 50 unique Vietnamese AI/Data normalized listings from one authorized provider run.
2. Title, source-level label, source or provider identifier, source and application URLs,
   description, job function, employment type, location, compensation representation, every
   source-originated date, and lifecycle or application-availability signal when the provider
   supplies them.
3. Collection-run and query context, retrieval timestamp, raw-response hash, source field names,
   and an allowed retained raw representation so a maintainer can trace any recommendation to its
   source text and label.
4. At least ten records for every non-empty source-level label represented in the review sample.
   If a label has fewer than ten available records, retain all of them and report that limitation.
5. A documented, language-aware title-signal rule that reports coverage, conflicts with each
   source-level label, and unknown rate without using the rule as a semantic truth oracle.

If the provider returns fewer than three distinct non-empty source-level labels, or cannot retain
the fields and provenance above, the evidence can characterize that provider's limitation but
cannot justify a provider-neutral mapping.

The sample must remain subject to the eligibility, authorization, budget, field, and retention
conditions recorded per source in the
[ingestion gate register](../../refactor/ingestion-gate-register.md), which supersedes the closed
[#423](https://github.com/Park-Hip/InternHunterAgent/issues/423) eligibility review as the live
gate.
This memo does not reopen those gates or authorize account activation, paid collection, credential
use, live ingestion, or production retention.

## Decision and rollback boundary

The selected taxonomy posture is an evidence-backed documentation decision, not an implementation
approval.
A future planned implementation must use an additive, compatibility-preserving migration and
preserve the current serving projection as required by issue #455.

If the later provider sample contradicts this memo, retain its evidence, revise or supersede this
memo, and leave the frozen corpus and current application contract unchanged.
No rollback is needed for this documentation-only outcome.
