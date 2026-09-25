# Registered deterministic-tool contract

> **Status:** Proposed contract for [issue #435](https://github.com/Park-Hip/InternHunterAgent/issues/435).
>
> **Authority:** This contract refines the registered-tool boundary in [mvp-spec.md](mvp-spec.md), [target-architecture.md](target-architecture.md), and [boundary-contract-ledger.md](boundary-contract-ledger.md).
>
> **Scope:** It defines logical tool operations and domain-value schemas for the one-turn technology-frequency workflow.

## Purpose and boundary

The bounded model agent has only the operations registered in the composition root.
It has no direct corpus, evidence-store, provider, network, file-system, shell, database, SQL, or write capability.
A registered tool is read-only and deterministic for the same valid request, immutable corpus version, normalized-label set, counting rule, and retained evidence.

This document does not select concrete tool names, a schema library, an agent framework, an implementation language, a storage engine, a cache, or a public API serialization.
An implementation may expose the two logical operations below as separate registered tools or as one narrowly composed registered tool that preserves every listed validation and result obligation.
It must not expose a broader capability to make the composition convenient.

## Shared domain values

| Value | Required shape and meaning | Validation owner |
| --- | --- | --- |
| `question` | One non-empty user request that can express only the supported technology-frequency question. | Registered tool. |
| `corpus_version` | One explicit identifier for an available immutable permitted corpus version. | Registered tool. |
| `scope_filters` | A finite mapping of corpus-supplied filter names to values that the selected corpus version supports. | Registered tool. |
| `canonical_scope` | The accepted version and canonical supported filters, with no inferred, broadened, or omitted criteria. | Registered tool. |
| `request_correlation_id` | An opaque request-local value for correlation only. | Application service creates it, and tools must not use it in factual computation. |
| `stable_record_id` | An immutable corpus record identity used for de-duplication and evidence linkage. | Corpus and retained-evidence port. |
| `evidence_ref` | An immutable reference to retained source evidence associated with a stable record and normalized label. | Corpus and retained-evidence port. |

All inputs are values rather than transport, ORM, database-session, framework, prompt, or provider objects.
The tool must reject unknown fields unless a later approved schema version explicitly permits them.
The tool must reject absent, malformed, unsupported, or mutually inconsistent values before factual analysis begins.

## Logical operation: validate supported frequency request

This operation gives the model a bounded way to determine whether a request is representable by the MVP.
It does not infer a scope, choose a corpus version, retrieve records, or calculate a result.

### Input schema

| Field | Required | Rules |
| --- | --- | --- |
| `question` | Yes | Must express only the supported technology-frequency question. |
| `corpus_version` | Yes | Must name an available immutable permitted corpus version. |
| `scope_filters` | Yes | Must use only supported corpus-supplied filters and values. |
| `request_correlation_id` | Yes | Is opaque and cannot affect the validation outcome. |

### Deterministic result schema

| Field | Requirement |
| --- | --- |
| `outcome` | Is exactly `supported`, `unsupported_question_or_filter`, `invalid_arguments`, or `unavailable_corpus_version`. |
| `canonical_scope` | Is present only for `supported` and contains the accepted corpus version and filters. |
| `limitation` | Is a safe bounded explanation for every non-supported outcome. |
| `contract_version` | Identifies the version of this logical contract. |

For the same input and corpus-version registry state, this operation returns the same outcome and canonical scope.
A `supported` result is advisory to the agent, not authority to bypass analysis-time validation.
The frequency-analysis operation repeats every validation that protects factual results.

## Logical operation: analyze supported technology frequency

This operation is the sole factual authority for the MVP result.
It validates the request, selects qualifying immutable records, de-duplicates by stable record identity, uses only the reviewed fixed normalized-label set, applies the documented counting and percentage rule, and returns the evidence required for every reported fact.

### Input schema

| Field | Required | Rules |
| --- | --- | --- |
| `question` | Yes | Must remain within the supported technology-frequency question shape. |
| `corpus_version` | Yes | Must identify one available immutable permitted corpus version. |
| `scope_filters` | Yes | Must be a finite supported set of corpus-supplied filters. |
| `request_correlation_id` | Yes | Is opaque and cannot alter selection, counting, evidence, or outcomes. |

The operation must not accept free-form SQL, a query language, arbitrary record identifiers, an arbitrary URL or file path, a corpus location, a provider instruction, a write command, a model instruction, or a caller-supplied count or evidence reference.

### Successful result schema

A result with `outcome: supported_result` must contain every field below.

| Field | Requirement |
| --- | --- |
| `contract_version` | Identifies the version of this logical contract. |
| `corpus_version` | Identifies the immutable corpus version actually read. |
| `canonical_scope` | Contains only validated corpus-supplied filters. |
| `matching_record_count` | States the number of qualifying records after filter validation and stable-identity de-duplication. |
| `deduplication_rule` | Identifies the stable-record rule used to remove duplicates. |
| `normalized_label_set_version` | Identifies the reviewed fixed label set used for the analysis. |
| `counting_rule` | Defines what one count represents and the denominator for every percentage. |
| `ranked_results` | Contains labels, deterministic counts, percentages when applicable, and descending ordering with a documented deterministic tie rule. |
| `evidence` | Satisfies the [evidence-grounding contract](evidence-grounding-contract.md) for every reported label. |
| `exclusions_and_limitations` | States evidence exclusions, fixed-corpus scope, and that observed labels are not a market estimate. |

A valid zero-match response uses `outcome: zero_match` and contains the corpus version, canonical scope, matching-record count of zero, applicable counting and de-duplication rules, and limitations.
It must not create a substitute ranking, near match, recommendation, or broader search.

### Bounded non-success outcomes

| Outcome | Deterministic condition | Required result | Forbidden behavior |
| --- | --- | --- | --- |
| `unsupported_question_or_filter` | The question or a requested filter cannot be represented by the MVP. | Safe limitation and no factual result. | Inferring or broadening scope. |
| `invalid_arguments` | An input violates this contract's shape or domain rules. | Safe limitation and no corpus read for factual analysis. | Repairing the request with model inference or partial execution. |
| `unavailable_corpus_version` | The named version is absent, unreadable, or not an approved fixed input. | Safe availability limitation and no substituted result. | Falling back to another, live, or cached corpus without an approved cache contract. |
| `missing_evidence` | A selected record or label cannot meet the evidence contract for a requested fact. | Exclusion details, a bounded limitation, and no ranked factual result. | Recalculating a partial ranking, reporting the unsupported fact, or inventing a citation. |
| `internal_unavailability` | A required read-only dependency cannot complete. | Safe unavailable outcome without implementation details. | Provider speculation, raw exceptions, or stale data substitution. |

## Registration and mediation rules

The composition root supplies a closed registry of these conforming operations to the model-agent runtime.
The runtime rejects a call whose operation is absent from that registry or whose arguments fail the registered schema before the operation can read factual data.
The runtime does not manufacture a tool result, alter a factual result, or turn a failed call into a successful factual result.

A tool result carries only the safe domain values defined here and in the evidence contract.
It must not carry raw rows beyond approved evidence excerpts, SQL, database handles, provider responses, prompts, chain of thought, arbitrary tool output, or transport objects.

## Determinism and test-double seam

A production tool depends on one read-only corpus and retained-evidence port.
A contract test or agent-runtime test may replace that port with a fixture-backed deterministic double that supplies a named immutable corpus version, stable records, normalized labels, evidence references, and controlled unavailable or incomplete-evidence states.

The double must implement the same data-port obligations and produce the same result schema as production.
A mock that returns an unconstrained prose answer, bypasses validation, or omits evidence cannot establish conformity.
Tests must assert the exact structured result or exact bounded outcome for a named fixture version and input.

## Conformance checks

1. A model agent can invoke only operations registered in the closed registry.
2. Each operation rejects schema-invalid arguments and unknown fields before factual analysis.
3. The analysis operation repeats validation even after a successful validation-operation result.
4. Identical valid inputs over the same fixture corpus version return byte-for-byte equivalent canonical factual values, apart from request-local correlation or separately approved telemetry fields.
5. Every reported label has evidence that conforms to [evidence-grounding-contract.md](evidence-grounding-contract.md).
6. Unsupported, invalid, unavailable, missing-evidence, zero-match, and internal-unavailability cases produce their listed bounded outcome without fallback capability use.
