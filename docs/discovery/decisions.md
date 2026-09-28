# InternHunterAgent material decisions

> **Status:** Active MVP decisions for [issue #426](https://github.com/Park-Hip/InternHunterAgent/issues/426).
>
> **System of record:** [mvp-spec.md](mvp-spec.md) defines the supported release workflow.

`Decided` means the choice guides the active MVP.
`Deferred` means the record is retained as context but must not block or expand this release.

## Active MVP decisions

### D-005 - One technology-frequency workflow

- **Status:** Decided
- **Choice:** The first release supports one one-turn question: which reviewed normalized technologies occur most frequently in a selected AI-job scope within a fixed corpus version.
- **Why:** One bounded agent using deterministic tools demonstrates evidence-backed agent behavior without conflating it with comparisons, trends, or advice.
- **Boundary:** The release does not support career-level comparisons, trends, semantic skill grouping, or general career advice.
- **Evidence:** [MVP specification](mvp-spec.md).

### D-006 - Fixed-corpus scope and identity integrity

- **Status:** Decided
- **Choice:** Each answer identifies a fixed corpus version, selected supported filters, matching-record count, and stable-record de-duplication rule.
- **Why:** Scope and record identity must remain inspectable so frequencies are not silently inflated or generalized beyond the corpus.
- **Boundary:** No live collection, implicit corpus refresh, or unsupported filter inference is allowed.
- **Evidence:** [MVP specification](mvp-spec.md#corpus-and-truth-boundary).

### D-007 - Retain normalized-label evidence without semantic grouping

- **Status:** Decided
- **Choice:** Results use a reviewed fixed normalized-technology label set and retain the original source evidence supporting every reported label.
- **Why:** The labels make deterministic counting possible while the evidence preserves an auditable connection to the corpus.
- **Boundary:** A label is not a semantic skill category or model-invented grouping, and the MVP does not use embeddings, similarity search, or automatic LLM classification.
- **Evidence:** [MVP specification](mvp-spec.md#corpus-and-truth-boundary).

### D-008 - Deterministic, evidence-backed answers

- **Status:** Decided
- **Choice:** Registered deterministic tools calculate results and retrieve evidence; the agent returns the scope, corpus version, calculation, labels, source evidence, and relevant limitations from those results.
- **Why:** Natural-language presentation must not hide the calculation or create claims beyond retained evidence.
- **Boundary:** Missing evidence, no matching records, and unsupported questions produce a bounded explanation rather than an invented conclusion.
- **Evidence:** [MVP specification](mvp-spec.md#one-turn-workflow).

### D-009 - Bounded single-agent orchestration

- **Status:** Decided
- **Choice:** The MVP is exactly one bounded, read-only model agent. For each request, it decides whether and which registered deterministic tools to invoke, supplies schema-valid arguments, and grounds its final factual claims only in deterministic tool outputs and retained evidence.
- **Why:** The MVP must demonstrate model-mediated tool use rather than a fully deterministic fixed workflow, while preserving deterministic calculations and evidence as the factual authority.
- **Boundary:** The agent cannot invoke unregistered tools, access or mutate data outside the fixed corpus, invent tool outputs, broaden a requested scope, or make factual claims absent from tool outputs and retained evidence. Tool implementation, framework and ReAct-loop pattern, model provider, fallback, and any future multi-agent topology are deferred.
- **Evidence:** [MVP specification](mvp-spec.md#bounded-single-agent-contract).

## Deferred source-research history

### D-010 - Data-collection strategy

- **Status:** Deferred
- **Historical record:** No source model, authority policy, provider or scraper posture, date or lifecycle policy, or initial-cohort threshold was selected.
- **Current effect:** Source selection and collection are not MVP blockers because the active workflow uses a fixed permitted corpus.
- **Revisit trigger:** A later release needs a new or refreshed corpus and has a separately approved source-authority, retention, and provenance decision.
- **Live gate:** The [ingestion gate register](../refactor/ingestion-gate-register.md), not this record, states whether any source may currently be collected from.
- **Historical evidence:** The eligibility review recorded in [issue #423](https://github.com/Park-Hip/InternHunterAgent/issues/423#issuecomment-5797200204) is a dated measurement. It is cited for what it found, and it is not a current gate.

### D-011 - Bright Data technical pilot

- **Status:** Deferred
- **Historical record:** A capped Bright Data test demonstrated one restricted-field request/response path only.
- **Current effect:** The [provider profile](research/bright-data-linkedin-jobs-provider-profile.md) documents that path, its account-activation failure, documented state boundaries, and unknowns. It does not select Bright Data, authorize collection, establish source rights, or affect the fixed-corpus MVP.
- **Revisit trigger:** A later source decision supplies applicable authority, endpoint-specific retention, cost, field-quality, coverage, lifecycle, and reliability evidence.
- **Live gate:** The Bright Data rows of the [ingestion gate register](../refactor/ingestion-gate-register.md) are the current authorization state. All five read not met.
- **Historical evidence:** The [Bright Data provider profile](research/bright-data-linkedin-jobs-provider-profile.md) and the capped-test result in [issue #423](https://github.com/Park-Hip/InternHunterAgent/issues/423#issuecomment-5797556656) are dated measurements. They characterize what was observed, and they are not a current gate.

### D-012 - Evidence-first ingestion contract

- **Status:** Decided, design only
- **Choice:** Future ingestion preserves immutable source authority, collection, artifact, observation, and normalization evidence before deriving a backward-compatible serving projection.
- **Semantic boundary:** A source-specific result is a normalized listing, `source_level` remains a source fact, and unsupported technical seniority and leadership scope are `unknown`.
- **Current effect:** The approved [ADR-0055](../decisions/adr-0055-evidence-first-ingestion-contract.md) and [blueprint](../decisions/evidence-first-ingestion-blueprint.md) define a future contract without authorizing collection, provider selection, data migration, or a runtime change. The blueprint's [minimum executable evidence contract](../decisions/evidence-first-ingestion-blueprint.md#minimum-executable-evidence-contract) states that contract at column level, and [ADR-0056](../decisions/adr-0056-ingestion-gate.md) names the gate it is held behind.
- **Remaining gate:** The [ingestion gate register](../refactor/ingestion-gate-register.md) records, per source, whether authorization, retention and spend, identity, raw integrity, and field provenance are met. A gate that is not met there is not met for mapping or production activation.
- **Evidence:** [Issue #461 semantic decision](research/source-level-semantics-decision.md), [issue #455 blueprint](https://github.com/Park-Hip/InternHunterAgent/issues/455), and the read-only legacy compatibility baseline in the blueprint.
