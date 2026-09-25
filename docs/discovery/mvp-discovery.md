# MVP discovery rationale

> **Status:** Discovery rationale for [issue #426](https://github.com/Park-Hip/InternHunterAgent/issues/426).
>
> **System of record:** [mvp-spec.md](mvp-spec.md) is the active MVP contract.

## Why the MVP is narrower

The earlier discovery draft correctly identified Vietnamese university students and early-career candidates as the intended users and required answers to stay grounded in evidence.
It also combined current-requirement analysis, career-level comparison, source-strategy selection, and open implementation choices into one first release.
That made a permitted data source, provider decision, taxonomy, and architecture prerequisites for demonstrating the first agent capability.

The approved MVP keeps the user and evidence boundary while reducing the release to one bounded, single-agent, one-turn analysis.
The agent decides whether and which registered read-only deterministic tools to invoke, uses schema-valid arguments, and grounds its final answer only in their outputs and retained evidence.
Those tools measure the frequency of reviewed normalized technology labels in a selected AI-job scope within a fixed, permitted, versioned corpus.
This makes the input, calculation, output, and evidence inspectable without claiming live coverage or selecting a collection strategy.

## Evidence and retained research context

Source-authority work found that systematic collection is not authorized without explicit reuse authority and retention terms.
The eligibility review in [issue #423](https://github.com/Park-Hip/InternHunterAgent/issues/423) therefore authorized no candidate for collection.
Its [gate decision](https://github.com/Park-Hip/InternHunterAgent/issues/423#issuecomment-5797200204) retains the vendor, authority, field, cost, and retention analysis for later source research.
The capped Bright Data technical tests in [issue #423](https://github.com/Park-Hip/InternHunterAgent/issues/423#issuecomment-5797556656) establish request/response viability only, not data-source approval or a release dependency.

A fixed permitted corpus removes that unresolved source decision from the first portfolio slice without weakening the truth boundary.
The MVP must identify the corpus version and may only make claims supported by its retained source evidence and fixed normalized labels.
The static corpus is an input to the future implementation, not authorization to acquire or refresh records.

## Deferred decisions

The MVP does not need a semantic taxonomy, embeddings, automatic LLM classification, or an answer to what broad skill group a technology belongs to.
It does not need live collection, provider or agent-framework selection, an agent-loop or ReAct implementation pattern, model fallback, memory, multi-turn conversation, or a future multi-agent topology.
It also does not promise trends, career-level comparisons, or general career advice.

The MVP being a bounded single agent is decided.
The implementation pattern for that agent loop and any future multi-agent topology remain separate because each changes the data, behavior, or evaluation surface beyond the one technology-frequency workflow.
They need their own evidence and approval before implementation.

## Review criterion

A reviewer should be able to read [mvp-spec.md](mvp-spec.md) alone and identify the user, supported question, bounded single-agent contract, deterministic-tool boundary, fixed-corpus boundary, required answer content, exclusions, and definition of done.
The specification is intentionally independent of legacy runtime and source-research details.
