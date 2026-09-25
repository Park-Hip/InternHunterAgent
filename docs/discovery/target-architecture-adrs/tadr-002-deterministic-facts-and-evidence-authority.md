# TADR-002: deterministic facts and evidence authority

> **Status:** Decided for the proposed target architecture.
>
> **Date:** 2026-09-25.
>
> **Decision scope:** Factual-result and evidence responsibilities for the bounded single-agent MVP.

## Context

The MVP answers one technology-frequency question over a fixed, permitted, versioned corpus.
Its answer must identify the selected scope, corpus version, matching-record count, de-duplication rule, labels, calculation, retained evidence, and relevant limitations.
A model can interpret a request and present a response, but it cannot reliably establish factual correctness, scope, evidence completeness, or reproducible calculations through prompt instruction alone.

## Decision

Registered deterministic tools exclusively own supported-question and argument validation, corpus-version and filter checks, record filtering and de-duplication, normalized-label lookup, counting, percentage calculation, and retained-evidence retrieval.
The model agent may choose whether to call one of these tools and supply schema-valid arguments.
The model agent may present tool results in natural language, but it may make factual claims only from deterministic fact bundles and retained evidence returned by those tools.

The tool-result contract must retain corpus version, supported scope, record count, de-duplication rule, normalized labels, counting and percentage rule, ranked results, evidence references, and exclusions or limitations.
Missing required evidence excludes a fact from a result.
It does not permit the model to fill the gap.

## Consequences

For identical valid inputs and corpus version, deterministic tools return the same factual result.
Unsupported filters, invalid arguments, unavailable corpus versions, missing evidence, and zero-match results remain bounded outcomes.
They never authorize inferred scope, semantic grouping, live lookup, data mutation, or an invented recommendation.

The model-agent runtime must not receive a database session, arbitrary query capability, unrestricted corpus payload, or direct evidence-store client.
The API adapter and application service must not calculate or transform factual results.
The deterministic tool boundary becomes the primary test and evaluation seam for reproducibility and evidence completeness.

## Alternatives considered

Prompt-only instructions that tell the model to calculate carefully and cite sources were rejected.
They cannot ensure reproducible results or prevent unsupported factual claims.

A model-generated SQL tool with a validator was rejected for this MVP target.
The MVP needs fixed normalized-label analysis and evidence-bound counting rather than arbitrary query construction.

Putting calculation and evidence retrieval in the application service was rejected.
It would make factual authority bypass the registered tool surface that constrains the model's available actions.

## Deferred decisions

Tool names, input schemas, output serialization, implementation language, storage implementation, and caching policy remain deferred.
A future implementation may use one narrowly composed tool or several narrow tools only if it preserves every deterministic responsibility and required fact-bundle field.

## References

- [MVP specification](../mvp-spec.md)
- [Boundary-contract ledger](../boundary-contract-ledger.md)
- [TADR-001](tadr-001-container-boundaries-and-dependency-rules.md)
