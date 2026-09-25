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
- **Evidence:** [Issue #423 eligibility review](https://github.com/Park-Hip/InternHunterAgent/issues/423#issuecomment-5797200204).

### D-011 - Bright Data technical pilot

- **Status:** Deferred
- **Historical record:** A capped Bright Data test demonstrated request/response viability only.
- **Current effect:** It does not select Bright Data, authorize collection, establish source rights, or affect the fixed-corpus MVP.
- **Revisit trigger:** A later source decision supplies applicable authority, retention, cost, field-quality, and reliability evidence.
- **Evidence:** [Issue #423 capped-test result](https://github.com/Park-Hip/InternHunterAgent/issues/423#issuecomment-5797556656).
