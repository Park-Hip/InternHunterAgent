# Collection from a source is authorized by a named gate with named evidence

> **Status:** Superseded by [ADR-0058](adr-0058-single-source-mvp-ingestion.md) · **Decided:** 2026-09-28

## Context

[ADR-0055](adr-0055-evidence-first-ingestion-contract.md) requires that a future source have
a recorded authorization and retention boundary before evidence is kept.
The [blueprint](evidence-first-ingestion-blueprint.md) lists thirteen acceptance gates, but no
live record states who authorizes collection from a given source, against which named gates, or
whether any of them is currently satisfied.

Until 2026-09-27 that record was
[issue #423](https://github.com/Park-Hip/InternHunterAgent/issues/423).
Its eligibility register concluded that no candidate source was eligible, and the issue is now
closed.
A closed issue therefore still functioned as the live collection-authorization boundary.
Its conclusion was also scoped to a multi-source comparison pilot rather than to the existing narrow
VietnamWorks path, so it never described the access authorization that
[ADR-0034](adr-0034-vietnamworks-robots-and-terms-gate.md) actually records.

The consequence is that no source's authorization state is currently readable, and the one source
with a real recorded access authorization is not represented as a gate at all.
Nothing else in the repository holds that state either.
The [component index](../refactor/component-index.md) parks ingestion,
[ADR-0053](adr-0053-frozen-data-portfolio-release.md) keeps the scheduled trigger removed, and the
blueprint records proposals rather than gate status.

## Decision

Collection from a source is authorized by **five named gates**, evaluated per source.
The gate definitions live in this record.
The current state of every gate lives in the
[ingestion gate register](../refactor/ingestion-gate-register.md), because a gate flips and this
record does not.

### The named owner

**The project maintainer** is the owner of the gate and its only approver.
The owner approves a gate status change, records the evidence that satisfies it, and revokes it.

No other role, agent, automation, or provider may mark a gate met.
No automated process writes the register.

### The five named gates

| Gate | Question it answers | Evidence that satisfies it |
| --- | --- | --- |
| **G1 Authorization** | Is this source permitted, for which fields, with which retention, and revocable by whom? | A reviewed authorization record naming acquisition method, permitted fields, retention rule, and revocation. |
| **G2 Retention and spend** | How long may project-held evidence exist, and what may the project spend? | A recorded retention representation and period, plus a spend ceiling. |
| **G3 Identity** | Does a source listing key stay stable within its source? | Golden records proving key stability within the source, and proving that no two source keys merge across sources. |
| **G4 Raw integrity** | Does every retained artifact have a representation, digest, media type, retrieval time, and observation link? | A retained artifact chain a maintainer can walk from an agent-visible value to a digest. |
| **G5 Field provenance** | Does every candidate agent-visible field trace to an observation, source field, transform, and rule version? | A provenance record per populated field. |

### The evidence rule

A gate is satisfied only by the named evidence recorded in the register row for that source and that
gate.
The register is the only live answer to whether collection from a source is permitted.

The following never satisfy a gate, alone or in combination:

- a successful HTTP response, or a run that completed without an error
- a robots.txt permission, or the absence of a robots.txt policy
- a public terms page, or public visibility of the data
- a provider account being active, paid, or able to serve a request
- an issue being open, closed, or resolved
- a count of returned records
- a plausible-looking value

A gate may read as **not met**.
The register ships with not-met rows, and a not-met row is the normal state of a new source rather
than a defect or pending paperwork.
Recording *not met* is what makes a gate checkable, because it is the state in which the evidence
requirement is stated rather than implied.

A document may not authorize or forbid collection by pointing at a closed issue.
A gate definition is never edited after this record.
A changed definition is a new superseding record.

### What the gates do not decide

The gates do not select a source, choose a provider, or reverse ADR-0053's frozen-data posture.
They do not authorize an account, a credential, a payment, a schedule, or a production deployment.

Meeting G1 through G5 authorizes evidence to be **kept**.
Publishing that evidence into `clean_jobs` is a separate cutover decision, and no gate in this
record grants it.
That cutover also requires a coordinated schema, prompt, fixture, evaluation, and API decision, plus
coverage evidence the current milestone does not produce.

### VietnamWorks

VietnamWorks automated access is authorized by
[ADR-0034](adr-0034-vietnamworks-robots-and-terms-gate.md), whose per-run fail-closed robots
preflight on the exact API host is retained.
It is not reopened by this record.
The ToS section 7 republishing question is a separate display concern and remains in
[#137](https://github.com/Park-Hip/InternHunterAgent/issues/137), unchanged.

### Supersession

This record supersedes
[issue #423](https://github.com/Park-Hip/InternHunterAgent/issues/423) as the provider-evidence and
collection-authorization gate.

Every live citation of #423 as a gate is superseded by this record: the Consequences section of
[ADR-0055](adr-0055-evidence-first-ingestion-contract.md), and decisions D-010, D-011, and D-012 in
[the discovery decision record](../discovery/decisions.md).

Citations of #423 that remain are citations of a dated historical measurement, labelled as such.
They are evidence about what was observed on a specific date, and they are never a current gate.

## Alternatives rejected

Keeping #423 as the gate was rejected because a closed issue cannot hold state, and a reader cannot
tell from it whether a gate is satisfied, pending, or abandoned.

Recording authorization per source inside ADR-0055 was rejected because ADR-0055 is immutable by the
`docs/decisions` contract, and a gate flips.

One combined approval per source was rejected because it cannot express that a source may be read
but not retained, or retained but not attributed.

A gate that an HTTP success, a robots permission, or a provider account could satisfy was rejected
because the bounded observation in [#470](https://github.com/Park-Hip/InternHunterAgent/issues/470)
showed an in-cap record count that proves nothing about coverage, and a provider echo that returns
an omitted filter as an empty string.

Choosing the owner as a rotating committee or the agent runtime was rejected because an
authorization gate with no single accountable holder is not revocable in a bounded time.

## Rollback

This is a documentation-only decision.
Reverting it leaves the blueprint, ADR-0055, the frozen corpus, the existing schema, the
workflows, and every serving behavior unchanged.

The register is the rollback-sensitive part.
If it is reverted after an evidence-schema or adapter slice has landed, retained evidence would
exist without the gate that authorized it, so the decision record and the register must land
together and before any such change.
Reverting them afterwards requires reverting the slice in the same change.
