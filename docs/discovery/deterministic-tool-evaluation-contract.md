# Deterministic-tool evaluation contract

> **Status:** Proposed contract for [issue #435](https://github.com/Park-Hip/InternHunterAgent/issues/435).
>
> **Authority:** This contract makes the MVP evaluation requirements in [mvp-spec.md](mvp-spec.md) executable against the proposed tool and evidence contracts.
>
> **Scope:** It specifies deterministic evaluation inputs and oracles for the bounded agent and registered deterministic tools.

## Purpose and exclusions

Evaluation must establish that the one model agent is capability-bounded and that every factual result is deterministic and evidence-grounded.
It must distinguish model-mediated tool selection from factual authority.
The model may decide whether to invoke a registered tool, but deterministic oracles judge the tool calls, structured outputs, evidence graph, and bounded outcomes.

This contract does not select an evaluation framework, a model provider, a prompt, a judge model, a tracing service, a public API test, a production corpus, a benchmark threshold, or a release gate.
It does not authorize live provider calls, corpus refresh, external writes, or reuse of legacy evaluation scenarios whose meaning is outside the fixed-corpus MVP.

## Evaluation fixture contract

Every deterministic evaluation case supplies the following controlled values:

| Fixture element | Requirement |
| --- | --- |
| `case_id` | Is a stable identifier local to the future evaluation registry. |
| `contract_version` | Identifies the tool and evidence contract version being evaluated. |
| `corpus_fixture_version` | Names an immutable, permitted fixture corpus version. |
| `normalized_label_set_version` | Names the reviewed fixed label set used by the fixture. |
| `user_request` | Contains one supported or deliberately unsupported question and scope input. |
| `registered_operations` | Lists the closed operation registry visible to the agent. |
| `expected_tool_trace` | States the permitted operations, argument schema expectations, and whether factual analysis may occur. |
| `expected_outcome` | States one exact outcome category from the registered deterministic-tool contract. |
| `expected_fact_bundle` | States exact canonical factual values when the expected outcome is a supported result or zero match. |
| `expected_evidence` | States the evidence graph or exclusion state required for each potentially reportable label. |

Fixture data must be self-contained and immutable for the case.
It must not need a live corpus, a web request, a provider response, a clock-dependent value, or hidden mutable state to establish an oracle.

## Evaluation layers and deterministic oracles

| Layer | Subject under evaluation | Deterministic oracle | Must not be used as the oracle |
| --- | --- | --- | --- |
| Tool schema and domain validation | Each registered operation. | Exact accept or bounded rejection for declared input fields and values. | Model self-report or prompt text. |
| Deterministic analysis | Frequency analysis over a named fixture version. | Exact canonical scope, stable-record selection, de-duplication, labels, counts, percentages, ordering, and limitations. | Natural-language plausibility or a judge model. |
| Evidence grounding | Evidence returned for each reportable label. | Complete fixture evidence graph with exact version, record, label, and retained-reference relationships. | A URL-only check or generated citation. |
| Registry confinement | Agent runtime and composition root. | Observed tool trace contains only closed-registry operations with schema-valid arguments. | The agent's statement that it followed policy. |
| Final-answer grounding | Model-agent response composition. | Every factual claim maps to a deterministic fact-bundle value or evidence item, and all required limitations are present. | A general helpfulness score. |
| Bounded failure handling | Agent and registered tools. | Exact non-success outcome and proof that no factual fallback capability was invoked. | A response that merely sounds cautious. |

A quality or style assessment may be added later, but it cannot override a failed deterministic oracle.
A model-based judge may be used only for a separately approved non-authoritative presentation assessment.

## Required case families

| Case family | Controlled condition | Required deterministic oracle |
| --- | --- | --- |
| Supported analysis | Valid supported question, available fixture version, supported filters, and complete evidence. | The agent uses only registered operations, and the exact expected fact bundle and evidence graph are returned and faithfully presented. |
| Unsupported question | The request asks for a workflow outside technology frequency. | The outcome is `unsupported_question_or_filter`, and no factual analysis or fallback occurs. |
| Unsupported filter | The request contains a filter absent from the fixture corpus contract. | The outcome is `unsupported_question_or_filter`, and scope is not broadened or inferred. |
| Invalid arguments | A model-supplied call omits, malforms, or adds a prohibited field. | The call is rejected as `invalid_arguments` before factual analysis and cannot be repaired implicitly. |
| Unavailable corpus version | The request names a fixture version that is absent or unreadable. | The outcome is `unavailable_corpus_version`, and no substitute version, cache, or live source is used. |
| Missing evidence | A qualifying record or label lacks a required retained source or label link. | The outcome is `missing_evidence` with exclusion details and no ranked factual result, and the answer does not cite or claim the unsupported fact. |
| Inconsistent evidence | A fixture evidence item conflicts with its version, record identity, label, or count. | The inconsistent support is not reportable, and the required safe outcome or recalculated result is returned. |
| Zero match | Valid filters select no qualifying evidence. | The outcome is `zero_match` with zero matching records and no invented near match, advice, or broader search. |
| Unregistered capability attempt | The model attempts a non-registered operation or a prohibited input such as SQL, a URL, or a write command. | The runtime blocks the attempt, no data operation occurs, and the public result remains bounded. |
| Internal unavailability | The deterministic fixture port fails a required read-only operation. | The outcome is `internal_unavailability` without raw exception disclosure or stale-result substitution. |

## Agent trace assertions

The evaluation harness captures a minimal structured trace sufficient to determine capability use without retaining chain of thought or raw provider content.
For each attempted operation, the trace records the registry operation identity, schema-validation result, safe canonical arguments or an argument fingerprint, outcome category, and whether a factual data read was authorized.

The trace must permit the following assertions:

1. The agent receives only the closed registry defined by the case.
2. Every attempted call names a registered operation and passes schema validation before any factual read.
3. A non-success outcome does not cause an unregistered call, live lookup, corpus mutation, or substituted factual result.
4. A supported result's answer is linked to the exact fact-bundle and evidence identifiers returned for the case.
5. Telemetry capture can be disabled without changing the deterministic outcome or tool trace semantics.

The trace must not expose hidden prompts, chain of thought, raw provider content, database handles, credentials, unrestricted raw rows, or internal exception text.

## Final-answer oracle

The final-answer check operates over an approved safe claim representation derived from the answer and the expected fact bundle.
It verifies that the answer contains all mandatory result disclosures and no additional factual propositions.

| Required disclosure for a supported result | Oracle source |
| --- | --- |
| Corpus version and selected scope | Expected canonical scope. |
| Matching-record count and de-duplication rule | Expected fact bundle. |
| Normalized labels, counts, percentages, ordering, and counting rule | Expected fact bundle. |
| Retained evidence for every reported label | Expected evidence graph. |
| Fixed-corpus and observed-label limitations | Expected fact bundle limitations. |

For bounded outcomes, the oracle requires the correct outcome and safe limitation while forbidding a factual ranking, invented citation, inferred scope, recommendation, or market-wide assertion.
A failure to ground one factual claim is an evaluation failure even if the rest of the answer is helpful or fluent.

## Test-double and isolation rules

The agent runtime is evaluated against the fixture-backed data-port double described in [registered-deterministic-tool-contract.md](registered-deterministic-tool-contract.md) and [evidence-grounding-contract.md](evidence-grounding-contract.md).
The double provides deterministic records, labels, evidence states, and controlled failures.
It records authorized reads so the harness can prove that validation failures did not access factual data.

The harness may replace the model with a scripted tool-calling double for deterministic runtime and registry tests.
A separately approved integration evaluation may use a real model, but it must run over the same closed registry and fixture oracle and must not weaken any deterministic assertion.

## Minimum acceptance evidence

A future implementation issue must provide automated evidence for every required case family that its changed boundary can affect.
At minimum, the full MVP path must demonstrate one supported analysis, one unsupported request, one invalid call, one unavailable version, one incomplete-evidence case, one zero-match case, and one unregistered-capability attempt.

The manual check is to inspect a supported fixture response and its trace.
The expected result is that a maintainer can reproduce every factual value and evidence reference from the fixture version and see that the agent had no direct data access or unregistered capability.
