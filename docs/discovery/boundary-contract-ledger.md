# Boundary-contract ledger for the bounded single-agent MVP

> **Status:** Proposed architecture contract ledger for [issue #434](https://github.com/Park-Hip/InternHunterAgent/issues/434).
>
> **Authority:** This ledger implements the boundary intent in [mvp-spec.md](mvp-spec.md) and the container rules in [target-architecture.md](target-architecture.md).
>
> **Scope:** The entries are technology-neutral contracts for the one-turn technology-frequency workflow, not public API or database schemas.

## Contract rules

Every boundary must carry only the minimum information needed by the receiver to perform its owned responsibility.
An upstream caller must not precompute a downstream result in order to bypass validation.
A downstream receiver must validate the semantic obligations it owns even when an earlier layer has validated syntax.

The names below are conceptual contract names.
They are not authorization to introduce a public type, HTTP field, database table, framework class, or implementation package with the same name.

## Request and result boundaries

| Boundary | Sender responsibility | Receiver responsibility | Required information | Prohibited information |
| --- | --- | --- | --- | --- |
| Caller to API adapter | Submit one question and any declared scope inputs. | Parse the delivery format and apply only transport-level validation. | User question, requested corpus version when exposed, and requested supported filters. | Internal tool arguments, corpus records, agent state, prompts, SQL, model settings, and trace SDK objects. |
| API adapter to application service | Translate a valid transport request into a transport-neutral application request. | Correlate the request and invoke exactly one bounded analysis use case. | Question, requested scope, request identity, and delivery-neutral metadata. | HTTP request or response objects, SSE writers, framework exceptions, or raw headers unless a separately approved policy requires a normalized value. |
| Application service to model-agent runtime | Request a bounded one-turn frequency analysis. | Interpret the request only within the MVP contract and choose whether to invoke registered tools. | Question, supported scope inputs, request correlation, and a tool registry constrained by the composition root. | Transport objects, persistence clients, direct corpus handles, arbitrary capabilities, long-term memory, or a provider SDK client. |
| Model-agent runtime to registered tool | Supply one schema-valid request for a registered deterministic operation. | Reject invalid arguments and perform only the registered read-only operation. | Validated argument fields defined by the tool schema and a request correlation value. | Raw user authority, arbitrary code, free-form SQL, arbitrary URLs, arbitrary file paths, write instructions, provider instructions, or framework objects. |
| Registered tool to corpus and evidence port | Request specific approved facts from one fixed corpus version. | Return only retained data that satisfies the tool's deterministic criteria. | Corpus version, validated corpus-supplied filters, stable record identities, and approved evidence keys. | Natural-language scope inference, model judgment, unbounded queries, mutable commands, or source-acquisition instructions. |
| Corpus and evidence port to registered tool | Return selected immutable records and retained evidence. | Apply deterministic analysis, evidence completeness checks, and limitation rules. | Stable record identifiers, filter fields, reviewed normalized labels, evidence links, corpus version, and any data-availability status. | Unapproved corpus versions, live-source results, hidden mutable state, or an inferred semantic category. |
| Registered tool to model-agent runtime | Return a deterministic fact bundle or bounded failure result. | Compose an answer without adding factual claims outside the bundle. | The fact-bundle fields listed below, safe error status when applicable, and deterministic limitations. | SQL, ORM objects, connection details, unrestricted raw rows, model instructions, or a factual conclusion without supporting result data. |
| Model-agent runtime to application service | Return a grounded final answer or a bounded unsupported or unavailable outcome. | Map the application outcome to the selected delivery contract. | Answer text, factual-bundle references required for inspection, and outcome category. | Chain of thought, hidden tool calls, provider responses, raw evidence payloads beyond the approved result contract, or transport-specific objects. |
| Application service to API adapter | Return a delivery-neutral result. | Serialize the selected response shape and map transport errors. | Outcome category, answer content, inspectable result metadata when the later delivery contract selects it, and safe public error data. | Agent framework objects, tool internals, database errors, provider errors, or tracing SDK objects. |

## Deterministic fact-bundle contract

Every successful frequency-analysis result must preserve the information below until it can be inspected by the caller or an approved evaluation path.
The final presentation may use natural language, but it must not remove a required limitation or replace a deterministic fact with a model-created claim.

| Field | Owner | Requirement |
| --- | --- | --- |
| Corpus version | Deterministic tools. | Identify the immutable corpus version used for the result. |
| Supported scope | Deterministic tools. | State only corpus-supplied filters that passed validation. |
| Matching-record count | Deterministic tools. | State the number of records after supported filtering and before label presentation. |
| Stable-record de-duplication rule | Deterministic tools. | Identify how duplicate records are removed by stable identity. |
| Normalized-label set | Deterministic tools. | Use only the reviewed fixed labels present in retained evidence. |
| Counting and percentage rule | Deterministic tools. | State the denominator and calculation used for each ranking or percentage. |
| Ranked deterministic results | Deterministic tools. | Carry labels, counts, percentages when applicable, and an explicit no-match result when no evidence qualifies. |
| Retained source evidence | Deterministic tools. | Link every reported label to retained evidence and stable record identity. |
| Exclusions and limitations | Deterministic tools. | State missing-evidence exclusions, unsupported filters, fixed-corpus scope, and the limit that observed labels are not a market estimate. |
| Natural-language answer | Model-agent runtime. | Present only the deterministic results, evidence, and limitations supplied in the fact bundle. |

A successful answer without retained evidence for a reported factual label is invalid.
A result with missing required evidence is an exclusion or unavailable-evidence outcome, not a partially invented answer.

## Validation and policy ownership

| Concern | Owner | Required behavior | Must not be delegated to |
| --- | --- | --- | --- |
| Transport syntax | API adapter. | Reject malformed delivery input before application invocation. | The model agent, corpus port, or observability adapter. |
| Supported-question shape | Registered deterministic tools. | Accept only the MVP frequency question and reject scope expansion. | The model agent or prompt. |
| Tool arguments | Registered deterministic tools. | Check every model-supplied argument against the tool's schema and domain rules. | The application service alone or a model self-check. |
| Corpus version and filter validity | Registered deterministic tools. | Accept only an available fixed version and corpus-supplied filters. | The model agent or a caller assertion. |
| Filtering, de-duplication, labels, counts, and percentages | Registered deterministic tools. | Produce reproducible results for the same valid inputs and corpus version. | Model reasoning, prompt text, or presentation code. |
| Evidence completeness | Registered deterministic tools. | Exclude unsupported facts and communicate the resulting limitation. | The model agent or observability adapter. |
| Response grounding | Model-agent runtime. | Use only deterministic fact bundles and retained evidence to make factual claims. | The API adapter, caller, or a tracing service. |
| Public error translation | Application service and API adapter. | Return a bounded safe outcome without exposing implementation details. | Provider exception text, database exceptions, or raw tool payloads. |
| Telemetry | Observability adapter. | Record optional lifecycle events without changing a functional outcome. | The factual calculation path or public response contract. |

## Outcome contract

The application service must distinguish the following outcomes before a delivery adapter assigns transport status codes, response fields, or stream events.

| Outcome | Deterministic basis | Required user-facing behavior | Forbidden fallback |
| --- | --- | --- | --- |
| Supported result | Valid scope, available corpus version, complete retained evidence, and deterministic calculation. | Present version, scope, result, evidence, and relevant limitations. | Market-wide, current-market, or semantic claims beyond the result. |
| Unsupported question or filter | The request cannot be represented by the supported question and corpus-supplied filters. | Explain that the request is unsupported and identify the bounded limit when useful. | Inferred filters, broadened scope, advice, or a guessed alternative analysis. |
| Invalid tool arguments | A model-supplied request fails the registered tool schema or domain validation. | Return a safe bounded failure and prevent factual analysis. | Repairing arguments through unvalidated model inference or executing a partial request. |
| Unavailable corpus version | The requested version does not exist or cannot be read as an approved fixed input. | State that the version is unavailable. | Using a newer, older, live, or otherwise substituted corpus. |
| Missing evidence | A record or label lacks the retained evidence required for the answer. | Exclude the unsupported fact and explain the affected limitation. | Reporting the fact without evidence or inventing an evidence reference. |
| Zero match | Valid filters select no qualifying evidence. | State that no matching evidence exists for the selected version and scope. | Recommendations, broader searches, or invented near matches. |
| Internal unavailability | A required deterministic dependency cannot complete its read-only operation. | Return a safe unavailable outcome and retain diagnostics only in approved internal telemetry. | Provider speculation, a stale cached result without an approved cache contract, or implementation detail disclosure. |

## Capability-denial ledger

The table below makes every forbidden capability explicit so its owner is inspectable.

| Forbidden capability | Denying boundary | Enforcement owner |
| --- | --- | --- |
| Direct agent-to-corpus or agent-to-evidence access | Model-agent runtime to tool boundary. | Tool registry and composition root. |
| Arbitrary SQL, shell, file, URL, or network execution | Model-agent runtime to tool boundary. | Registered tool schemas and runtime registration. |
| Model-created validation, counting, percentages, or evidence | Tool to model-agent result boundary. | Deterministic tools. |
| Corpus mutation, ingestion, refresh, or source selection during a request | Request path to data and operations boundary. | Corpus adapter, composition root, and deployment policy selected later. |
| Live-provider or web lookup as factual fallback | Agent runtime and tool boundaries. | Runtime registration and deterministic tool implementations. |
| Unsupported filter broadening or semantic grouping | Supported-question and scope-validation boundary. | Deterministic validation tool. |
| Long-term or cross-turn memory | Application service to model-agent runtime boundary. | Runtime contract and composition root. |
| Tracing, logging, or metrics influence on a factual answer | Telemetry boundary. | Observability adapter interface. |
| Leakage of prompts, chain of thought, raw rows, provider errors, or internal tool payloads | Model-agent and application-result boundaries. | Runtime output contract and application error translation. |

## Contract acceptance checks

A future implementation issue must make each affected boundary executable through tests or controlled checks.
The following checks are the minimum architecture acceptance evidence.

1. A supported request can be traced from delivery input to one grounded response without a direct agent-to-corpus dependency.
2. The same valid corpus version, filters, and counting rule produce the same deterministic fact bundle.
3. An unsupported question, invalid tool arguments, missing evidence, unavailable version, and zero-match result remain bounded and never invoke a live or unregistered fallback.
4. A response exposes no raw SQL, persistence handle, framework object, prompt, chain of thought, provider exception, or unapproved raw record payload.
5. Disabling observability leaves validation, calculations, evidence selection, and the delivery result unchanged.
6. A dependency-graph review shows no forbidden arrow in [target-architecture.md](target-architecture.md).
