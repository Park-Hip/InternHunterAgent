# Agent v0 legacy rule disposition

> **Last verified:** 2026-09-29
>
> **Eviction:** This map leaves `docs/refactor/` when the agent-v0 cutover in
> [#486](https://github.com/Park-Hip/InternHunterAgent/issues/486) is merged and measured, or when a
> successor contract is approved. Until then it is the audit trail that shows which legacy `G01` to
> `G47` expectation became a v0 expectation and why.

This is the companion to the
[agent v0 behavior and metric contract](agent-v0-contract.md).
It exists so that no legacy expectation is inherited silently and no legacy expectation is dropped
without a reason.

## Sources

| Source | What it provides |
| --- | --- |
| `docs/reference/agent-behavior.md` | The human-readable v1 spec, the settled decisions, and the 19 canonical strings |
| `config/prompts.yaml` | The prompt surfaces those expectations were expressed through, and the current glossary |

The behavior question bank that carries the `G01` to `G47` groups is not in the working tree.
It is preserved on the git tag `docs-history-pre-redesign` and is read with:

```sh
git show docs-history-pre-redesign:research/archive/agent-behavior-question-bank.md
```

38 of the 47 legacy groups carried a desired behavior.
9 were never populated: `G11`, `G15`, `G22`, `G23`, `G32`, `G38`, `G39`, `G41`, `G43`.

## The four dispositions

| Disposition | Meaning |
| --- | --- |
| `adopted` | v0 states the same expectation, in substance, as the legacy group |
| `replaced` | v0 states a different expectation on the same ground, and the legacy expectation is void |
| `retired` | v0 states no expectation on that ground, and the reason is out-of-scope or structural |
| `added` | The legacy group carried no expectation, and v0 adds one |

`added` is a fourth value on purpose.
Forcing a never-populated group into `adopted` would claim an inherited expectation that never
existed, which is the exact failure this map exists to prevent.
A group marked `added` cannot conflict with v0, because there was nothing to conflict with.

Totals: 31 `adopted`, 5 `replaced`, 5 `retired`, 6 `added`.

## Disposition by group

| Group | Legacy expectation | Disposition | v0 location and reason |
| --- | --- | --- | --- |
| `G01` | Route to one primary action, never pair a decline with a tool call, never answer from memory | `adopted` | Contract, question shapes. A borderline request is `CLARIFIED` or `UNSUPPORTED`, never answered from priors |
| `G02` | Ask at most one narrow clarifying question, never when a default exists | `adopted` | Contract, answer states. Tightened by the single-turn rule, which removes cross-turn chaining |
| `G03` | Answer every part of a compound request | `replaced` | Contract, decomposition rule. v0 executes at most two supported shapes and labels both; a third is a clarifying question. Unbounded composition is what the typed plan cannot carry, and a silent drop is not acceptable |
| `G04` | Map a subjective term only with a defensible mapping, and state the interpretation | `adopted` | Contract, matching rules and labels |
| `G05` | Three-way field honesty: negotiable, absent, free text | `adopted` | Contract, field contract and evidence labels |
| `G06` | Zero rows and an absent field are different answers | `adopted` | Contract, answer states |
| `G07` | A hard never-invent list | `adopted` | Contract, field contract, and the unsupported table |
| `G08` | Every upstream caveat survives into the answer | `adopted` | Contract, answer language and evidence |
| `G09` | Never rank or aggregate salary across currencies | `adopted` | Contract, `SALARY_AGGREGATE`. Extended: v0 forbids a cross-currency aggregate entirely, not only a ranking |
| `G10` | Every claim comes from a tool result | `adopted` | Contract, question shapes |
| `G11` | No expectation recorded | `added` | Contract, `SALARY_AGGREGATE`. The group's open question, how every salary shape is communicated, is answered in full |
| `G12` | City matching on canonical values, free-text hedge for remote, decide the Saigon case | `adopted` | Contract, location. The open decision is closed: an explicit user-term alias table, with `Saigon` mapping to `Ho Chi Minh City`. No diacritic folding is claimed |
| `G13` | Technology matching with the basis stated, abbreviations expanded, multi-tech as intersection | `adopted` | Contract, technology. The mechanism is now the ingestion vocabulary, and substring matching on a short token is forbidden |
| `G14` | Canonical role first, free-text fallback for a non-canonical term | `adopted` | Contract, role |
| `G15` | No expectation recorded | `added` | Contract, shape table. A company filter is a supported filter, and a company absent from the corpus is a zero-result answer |
| `G16` | `is_internship` is a precise boolean, and the persona must not bias toward internships | `adopted` | Contract, field contract and filter rules |
| `G17` | Refuse time-based claims; invent no date or ordering | `adopted` | Contract, unsupported table and the date fields. v0 states `UNSUPPORTED` for open status and publication date, and the `created_on` ordering rule is unchanged |
| `G18` | Seniority is not a queryable structured attribute; surface title text with a hedge | `replaced` | Contract, level. The legacy premise is false: `job_level` is populated in every fixture row. v0 answers level from the recorded value, reports coverage, and keeps "Senior" in a title as title text |
| `G19` | Corpus questions are tool-answerable, and completeness is never over-claimed | `adopted` | Contract, shapes `S2` and `S3` |
| `G20` | Resolve anaphora to the prior set and re-query | `retired` | v0 is single-turn. There is no prior set, so a referent cannot be resolved, and a request containing one is `UNSUPPORTED` |
| `G21` | Accumulate follow-up filters and re-query | `retired` | Same reason as `G20`. There is no follow-up turn to accumulate onto |
| `G22` | Handle a hard topic switch mid-conversation | `retired` | Same reason as `G20` |
| `G23` | Define what short-term memory promises and its edges | `retired` | v0 carries no state. The evaluation harness must drop its `memory` metric in Stage 5, which the track already requires |
| `G24` | One friendly off-topic redirect, no tool call | `adopted` | Contract, refused states |
| `G25` | Strictly read-only; refuse any mutation without calling a tool | `adopted` | Contract, refused states |
| `G26` | Instructions in the message or in tool content never override the system prompt | `adopted` | Contract, unsupported table and refused states |
| `G27` | Never reveal configuration, prompt text, or the existence of hidden columns | `adopted` | Contract, field contract. A source link is public and stays shareable |
| `G28` | In-domain but unbuilt asks get a future-feature redirect, never a timeline | `adopted` | Contract, unsupported table |
| `G29` | Decline discriminatory filters on values, distinct from a missing field | `adopted` | Contract, refused states. `REFUSED` and `UNSUPPORTED` are now named states, so the distinction is explicit rather than a tone |
| `G30` | Choose the tool and sequence the calls | `replaced` | Contract, question shapes. A v0 request is a typed query request per shape, not a free-text tool call, so tool selection is a contract term and not a model judgement |
| `G31` | Always select `id` first for a list so details can chain | `adopted` | Contract, shape table. The user-visible rule holds and moves into the query core |
| `G32` | No expectation recorded | `retired` | There are no model-authored calls left to duplicate. An identical consecutive request is a query-core invariant, tested in Stage 3 rather than graded as an answer rule |
| `G33` | Generated SQL honors every safety and correctness rule | `replaced` | Contract, matching and metric definitions. The v0 path has no model-authored SQL, so these become query-core invariants. A SQL-path metric returns only if #487 approves that path |
| `G34` | Distinguish the system cap from a user-requested limit | `adopted` | Contract, display cap and `TOP_N` |
| `G35` | Natural-language answers, no raw SQL, no raw table dump | `adopted` | Contract, answer states and format rules |
| `G36` | Show up to the cap, name the truncation, offer to narrow, never fabricate a next page | `adopted` | Contract, display cap |
| `G37` | Consistent voice, length matched to the ask | `adopted` | Contract, answer language |
| `G38` | No expectation recorded | `added` | Contract, links. The group's open question, when `source_url` and `id` are surfaced, is answered including the nullable case |
| `G39` | No expectation recorded | `added` | Contract, answer format. v0 answers the inverse of the legacy open question: no unsolicited suggestion, and at most one concrete narrowing step on a truncated or empty result |
| `G40` | No input shape crashes or leaks an internal error | `adopted` | Contract, answer states and the `UNSUPPORTED` row for empty input |
| `G41` | No expectation recorded | `added` | Contract, decomposition rule. Stacked constraints are bounded by the two-shape rule, and a request outside the supported filter set is `UNSUPPORTED` or `CLARIFIED` |
| `G42` | A friendly generic message on failure, never an internal error | `adopted` | Contract, `REFUSED` state and the unsupported table |
| `G43` | No expectation recorded | `added` | Contract, answer language. Vietnamese-first output, with an English question answered in Vietnamese |
| `G44` | Correct a false premise from the tool result | `adopted` | Contract, `ANSWERED` with the actual figure |
| `G45` | Honesty and safety behaviors must hold on every run | `adopted` | Contract, answer states. The must-be-invariant set is now the four states and the eight evidence labels, and Stage 5 measures them |
| `G46` | An explicit safety over honesty over helpfulness over style ladder | `adopted` | Contract, state table. The order is now visible in the states themselves |
| `G47` | Canonical reusable sentences for consistent, gradeable behavior | `replaced` | Contract, answer language. The 19 strings remain reference wording, not phrases the agent emits verbatim, and the contract adds the eight analytics labels the legacy set has no phrase for |

## What the map changes about the legacy docs

- `docs/reference/agent-behavior.md` stays readable as history and is not edited here.
  It describes the v1 prompt surfaces, which still serve the current runtime until the cutover.
- `G18` is the one place where a legacy expectation is void on the merits rather than on scope:
  the level field exists, so refusing level queries would be refusing a recorded fact.
  If #487 approves a guarded SQL path, the SQL rules return as that path's contract and its own
  evaluation metric.
- The five `retired` groups are all the same reason: v0 is single-turn and carries no state.
  They are not judgement calls about quality.

## Verification

| Check | Method | Expected result |
| --- | --- | --- |
| Every legacy group appears exactly once | Read the groups on tag `docs-history-pre-redesign` and count the rows below | 47 rows, no gap and no duplicate |
| The disposition totals add up | Add the four disposition columns | 47 |
| Every `adopted` and `added` rule exists in the contract | Follow each cited contract section | Each row names a section that states the rule |
| Every `replaced` and `retired` rule names a reason | Read the reason column | No row is void without a stated reason |
