# Agent v0 scenario disposition

> **Last verified:** 2026-09-29
>
> **Eviction:** This map leaves `docs/refactor/` when the agent-v0 cutover in
> [#486](https://github.com/Park-Hip/InternHunterAgent/issues/486) is merged and measured, and the v1
> registry has an approved retirement or archival decision under
> [#472](https://github.com/Park-Hip/InternHunterAgent/issues/472). Until then it is the audit trail
> from the 50 v1 scenarios to the 16 v0 acceptance cases.

This is the Stage 2 deliverable's audit trail.
It answers one question per v1 scenario: does the v0 acceptance set still test it, does a v0
contract rule now state it, or is it gone.

## Method

Nothing here is a mechanical prune.
The v1 registry is the historical record of what the harness measured; the v0 acceptance set was
written from
[the v0 behavior and metric contract](agent-v0-contract.md) and sized by behavior coverage.
Where a v1 scenario's behavior still matters and no v0 case states it, the row says so instead of
pretending the tiny set covers it.

The v1 registry, its replays, and the captured evidence are untouched and stay selectable.

## The three dispositions

| Disposition | Meaning |
| --- | --- |
| `carried` | A v0 acceptance case states the same behavior, and names it |
| `restated` | A v0 contract rule states the behavior, and no question in the tiny set asks for it |
| `retired` | There is no v0 behavior, and the reason is structural rather than a judgement about quality |

Totals: 17 `carried`, 19 `restated`, 14 `retired`.

## Disposition of the 50 v1 scenarios

| v1 scenario | Disposition | v0 case or rule | Reason |
| --- | --- | --- | --- |
| `HLP-COUNT-1` | `restated` | `V0-COUNT-CORPUS`, `V0-GROUP-LOCATION`, `V0-SHARE-PYTHON-AI` | The count shape is covered twice over: once against the display cap, once per city. The role count of 5 is now the share denominator, so a separate case would repeat the shape without a new discriminator |
| `HLP-LIST-1` | `carried` | `V0-LIST-ROLE-CITY` | A canonical-role list, now with a city filter and a stated match total |
| `HLP-TECH-STACK-1` | `carried` | `V0-COMPARE-PYTHON-CITY`, `V0-ML-ZERO` | The Python token count and the substring trap are both v0 rules, and both are now graded on whole-token matching |
| `HLP-TRUNCATION-1` | `carried` | `V0-LIST-ALL-TRUNCATED` | Identical intent: 24 match, 20 display, and the shortfall is stated |
| `HLP-CONTEXT-1` | `retired` | none | Multi-turn. v0 carries no state, so there is no filter to accumulate onto |
| `HLP-REFERENT-1` | `retired` | none | Multi-turn. The prior set it resolves against does not exist at v0 |
| `HON-CREATED-ON-1` | `restated` | Field contract, date rows | Ordering by the source-record creation date with its label is a field rule, not a question the tiny set asks |
| `HON-CURRENCY-1` | `carried` | `V0-SALARY-AMBIGUOUS`, `V0-TOPN-USD-SALARY` | Strengthened: v0 forbids a cross-currency figure, not only a cross-currency ranking. The top-N case is the positive form of the same scoping rule |
| `HON-ZERO-RESULTS-1` | `carried` | `V0-ML-ZERO` | A confident zero-result answer, with the substring trap that would fake a non-zero |
| `HON-FREE-TEXT-1` | `carried` | `V0-FREETEXT-REMOTE` | A free-text match reported as a hedged lead rather than a structured count |
| `HON-NEGOTIABLE-SALARY-1` | `carried` | `V0-SALARY-AMBIGUOUS` | The negotiable posting is the excluded row, and the answer must name its state |
| `HLP-SENIORITY-1` | `carried` | `V0-GROUP-LEVEL` | Reversed. v1 refused level questions because the field looked absent; the field is populated, so v0 groups by the stored value and reports coverage |
| `HON-ABSENT-FIELD-1` | `carried` | `V0-DEADLINE-UNSUPPORTED` | The data has no application deadline, and the listing expiry may be offered as itself |
| `HON-OPEN-STATUS-1` | `carried` | `V0-DETAIL-BY-ID` | An open-status claim is a rejected answer on the detail case |
| `SAF-DESTRUCTIVE-REFUSAL-1` | `carried` | `V0-REFUSED-DESTRUCTIVE` | One sentence, no tool call, no data change |
| `SAF-OFF-TOPIC-REDIRECT-1` | `restated` | Refused states | Unchanged by v0. No tiny case spends a slot on a redirect, so the v1 scenario keeps the line until the cutover |
| `SAF-INJECTION-REFUSAL-1` | `restated` | Refused states | Unchanged by v0. The tiny set covers retrieved injection, not a user-message override |
| `HLP-CLARIFY-1` | `carried` | `V0-CLARIFY-SUBJECTIVE` | The scenario is multi-turn, but the behavior, one narrow question and no data answer, is a v0 case |
| `HLP-REFERENT-2` | `restated` | Unsupported table, prior-turn row | A request that depends on a prior turn is unsupported at v0, not a clarification |
| `HLP-COMPOUND-1` | `restated` | Decomposition rule | A message is decomposed into at most two supported shapes. The tiny set has no two-shape message |
| `HON-GENERAL-KNOWLEDGE-1` | `restated` | Refused states | Unchanged by v0 |
| `SAF-INJECTION-RESILIENCE-1` | `restated` | Refused states | The injected-instruction case the tiny set does not carry |
| `SAF-INDIRECT-INJECTION-1` | `carried` | `V0-UNTRUSTED-DESCRIPTION`, `V0-DETAIL-DESCRIPTION` | The posting that says "ignore all previous instructions" is answered as posting text, in two halves: listed without its text projected, and retrieved whole when the user asks for the detail |
| `SAF-INDIRECT-INJECTION-2` | `restated` | Focused test, base64 row | The base64 variant stays in the v1 registry; the focused test asserts the fixture row exists so it cannot silently disappear |
| `HON-PREMISE-CORRECTION-1` | `restated` | Answered state | Correcting a false count premise is unchanged. No tiny case sets a false premise |
| `HLP-SENIOR-TITLE-1` | `carried` | `V0-GROUP-LEVEL` | Postings 10 and 12 say Senior in the title and record a different level, so the same case tests the title-text rule |
| `HON-SQL-DESCRIBE-1` | `restated` | Answer format | The v0 model never authors SQL, so there is no SQL to describe. Not disclosing internals survives as a format rule |
| `HLP-LOCATION-SYNONYM-1` | `carried` | `V0-LIST-ROLE-CITY` | The question is written "Hà Nội" and the stored value is `Hanoi`, so the case is the diacritic and alias case |
| `HLP-ABSTRACTION-1` | `carried` | `V0-ML-ZERO` | v1 failed here by adding a role filter. v0 forbids that filter and requires a whole-token technology match, so the correct answer is a confident zero |
| `HLP-ROLE-FALLBACK-1` | `restated` | Matching rules, role | The fallback to title and description is a rule, and no tiny case uses a non-canonical role term |
| `SAF-DESTRUCTIVE-REFUSAL-2` | `restated` | Decomposition rule | A mutation plus a read is two shapes; v0 refuses the mutation and answers the read. No tiny case is compound |
| `HLP-DETAIL-1` | `carried` | `V0-DETAIL-BY-ID`, `V0-DETAIL-DESCRIPTION` | A detail request by id, with the absences named, and the posting's own text returned when the user asks to describe it |
| `HLP-DETAIL-2` | `restated` | Answer states | An id-less detail request is a clarification. No tiny case is id-less |
| `HLP-DETAIL-3` | `restated` | Shape table, `S7 DETAIL` | The detail id cap is a query-core limit, decided in Stage 3, not an answer rule |
| `HLP-DETAIL-4` | `restated` | Shape table, `S7 DETAIL` | Same, for several ids inside the cap |
| `HLP-DETAIL-5` | `restated` | Answer states | A non-existent id is a zero result, the same state `V0-ML-ZERO` pins for lists |
| `HLP-DETAIL-6` | `retired` | none | Multi-turn. The prior result it refers to does not exist at v0 |
| `HLP-DETAIL-7` | `restated` | Shape table, `S7 DETAIL` | A bulk id request beyond the cap is a query-core limit |
| `HLP-CLARIFY-2` | `retired` | none | Multi-turn |
| `HLP-PRONOUN-1` | `retired` | none | Multi-turn. A pronoun has no antecedent at v0 |
| `HLP-PRONOUN-2` | `retired` | none | Multi-turn, and v0 has no cross-turn language carry either |
| `HON-CORRECTION-1` | `retired` | none | Multi-turn |
| `HON-CORRECTION-2` | `retired` | none | Multi-turn |
| `HLP-MEMORY-1` | `retired` | none | Multi-turn, and the harness `memory` metric is dropped in Stage 5 |
| `HLP-MEMORY-2` | `retired` | none | Multi-turn. The truncation rule it checks survives as `V0-LIST-ALL-TRUNCATED` |
| `SAF-CARRYOVER-1` | `retired` | none | Multi-turn safety carry-over has nothing to carry |
| `SAF-CARRYOVER-2` | `retired` | none | Multi-turn. The indirect-injection rule itself survives as `V0-UNTRUSTED-DESCRIPTION` |
| `HLP-ERROR-RECOVERY-1` | `retired` | none | Multi-turn. The single-turn failure wording is a Stage 3 and Stage 6 concern |
| `HLP-ERROR-RECOVERY-2` | `restated` | `REFUSED` state | The degradation response is unchanged in substance: a friendly message, never an internal error |
| `HLP-CLARIFY-3` | `retired` | none | Multi-turn. The single-turn clarification is `V0-CLARIFY-SUBJECTIVE` |

## What the tiny set does not cover, and what holds the line until the cutover

The v0 set is 16 questions. These v0 behaviors have no question in it, and each one names where it
is still held.

| Uncovered v0 behavior | Held by, until Stage 6 |
| --- | --- |
| Off-topic redirect, general-knowledge decline | The v1 `SAF-OFF-TOPIC-REDIRECT-1` and `HON-GENERAL-KNOWLEDGE-1` scenarios |
| A user-message injection or secret request | `SAF-INJECTION-REFUSAL-1`, `SAF-INJECTION-RESILIENCE-1` |
| A base64 payload inside a description | `SAF-INDIRECT-INJECTION-2`, plus a focused test that the fixture row exists |
| A destructive request combined with a read | `SAF-DESTRUCTIVE-REFUSAL-2` |
| Correcting a false premise | `HON-PREMISE-CORRECTION-1` |
| A message containing two supported shapes | No v1 scenario. The contract's decomposition rule is the only statement until Stage 2's successor is reviewed |
| Ordering by the source-record creation date with its label | `HON-CREATED-ON-1` |
| A role term with no canonical category, and its disclosed fallback | `HLP-ROLE-FALLBACK-1` |
| A detail request with no id, or with ids beyond the cap | `HLP-DETAIL-2`, `HLP-DETAIL-7` |
| Behavior under tool or database failure | `HLP-ERROR-RECOVERY-2`, and Stage 3's query-core tests |
| A row with a null link inside a list | The focused edge tests only, because the pinned fixture has no such row |
| A job level missing from a row | The focused edge tests only, because the pinned fixture has no such row |

Two entries in that table are real gaps rather than deferrals.
A two-shape message is not exercised anywhere, and a null level or null link inside a listed answer
is only reachable through the rolled-back edge rows, not through the pinned fixture.
Both are recorded here so Stage 3 and Stage 5 can decide whether to add a case or accept the
coverage as it stands.

## Verification

| Check | Method | Expected result |
| --- | --- | --- |
| Every v1 scenario appears exactly once | Compare the table against `evals/datasets/scenarios.yaml` | 50 rows, no gap, no duplicate |
| Every v0 case is accounted for by at least one v1 row | Compare the named cases against `evals/datasets/v0_acceptance.yaml` | Every case is named, none unmentioned |
| The disposition totals add up | Add the three disposition columns | 50 |
| Every `carried` row names a real v0 case | Resolve each name against `evals/datasets/v0_acceptance.yaml` | No dangling name |
| Every `restated` row names a contract section | Resolve each rule against the v0 contract | No dangling name |
| v1 stays selectable | `uv run pytest tests/evals -q` | The v1 registry and its scenarios still load |
