# Agent behavior baseline — Resumi

> **Eviction:** A behavior leaves when the maintainer drops it from the product scope, or a measured
> baseline run shows it is no longer needed.

This is the MVP baseline the agent is built and measured against, decided in
[#708](https://github.com/Park-Hip/InternHunterAgent/issues/708). It replaces the frozen behavior
spec of 2026-07-11, its glossary, and its scenario ladder, which remain in git history.

## Problem statement

Students and freshers in Vietnam looking for AI and Data jobs have to scroll through VietnamWorks
listings one by one. Resumi lets them ask in Vietnamese and get the matching postings, or a count of
them, from a nightly-refreshed copy of VietnamWorks data, each posting with a link to the original.
It includes internships when VietnamWorks lists them, which is rarely. It answers only from that
data, and says plainly when the data cannot answer.

## User needs, in priority order

1. **Find:** postings by role, skill or technology, location, level (Fresher/Entry level first), and
   internship when available.
2. **Inspect:** look closer at one or a few postings: requirements, tech stack, link.
3. **Count and overview:** for example "Có bao nhiêu việc làm AI ở TP.HCM trong tháng 6?".
4. **Narrow:** refine the last result in a follow-up ("chỉ ở Hà Nội thôi").

Salary is a minor need: the data often lacks it, so the agent reports what is stored and nothing
more. "AI jobs" means the `AI Engineer` role. A time window such as "in June" can only use the
record creation date, which is not the publication date.

Out of scope: CV writing, career advice, opinions about companies, and anything outside the postings.

## Expected behavior

Model behaviors, measured by the evaluation:

| ID | Behavior |
|---|---|
| B1 | Calls the tool for any posting question; never answers postings from memory. |
| B2 | Picks the right filters: the returned rows are the correct set. |
| B3 | The answer is faithful to the rows: no invented postings, numbers match, source links included. |
| B4 | Says so when nothing matched or the list is cut off. |
| B5 | Answers in Vietnamese, concisely. |
| B6 | A follow-up keeps the earlier filters. |

Code guarantees, held by unit tests whatever the model says:

- Read-only: least-privilege database role, read-only transaction, and the SQL validator.
- No secrets in the model's context.
- Row cap, statement timeout, and result byte budget.
- Facts come from code, not from the model: rows returned, total matched, and the SQL that ran,
  including any page offset
  ([ADR-0062](../decisions/adr-0062-tools-return-facts-the-prompt-owns-wording.md)).

The tools return facts and the system prompt owns all wording. The prompts are
`config/prompts.yaml` `system_prompt`, `schema_context`, and `sql_generation`, at `v1`.

## How it is measured

- **Data:** the frozen snapshot `internhunter_snapshot_20261018` of production `clean_jobs`
  (367 rows), because nightly ingestion changes the live data.
- **Questions:** [`evals/datasets/baseline.yaml`](../../evals/datasets/baseline.yaml), 36 questions
  written by a separate AI from the problem statement, split into dev (tune against it) and
  held-out (never tune against it). Every reference SQL was checked against the snapshot.
- **Layer 1, text-to-SQL:** `evals/baseline_sql.py` runs the generated and reference SQL on the
  snapshot and compares result sets. It scores B1, B2, and B6 for the first turn.
- **Layer 2, answer quality:** a small agent run over multi-turn and detail questions, with B3, B4,
  and B5 marked by hand. No model judge until hand review is too slow.
- **Pass bars:** B2 at least 85% on held-out; B3 and B4 at 100%.
- **Model credit:** run at milestones only, and save every run's output so re-scoring is free.

## Baseline results (2026-10-19, prompts v1)

| Layer | Result |
|---|---|
| Layer 1 | 31/32: dev 22/22, held-out 9/10. The one failure, 025, reads an ambiguous deadline question as a single posting. |
| Layer 2 | 12 cases, 21 turns (022, 024, 026 to 032, 007, 033, 035). B3, B4, B5, and B6 held in every turn: totals and partial lists stated, the empty result said plainly, no SQL, column name, or id shown, and every follow-up kept its filters. |

The held-out Layer 1 score is optimistic: rules 3 and 4 of `sql_generation` were written after
held-out failures 025 and 026.

## Rule for adding complexity

A new prompt rule or test must:

1. Fix a failure seen more than once, on a dev or held-out question.
2. Go at the lowest layer that works: data or column description, then tool facts, then a prompt
   rule as the last resort.
3. Be checked on paraphrases and the held-out set, not only the input that failed.
4. Record what it fixes, so it can be deleted once it stops mattering.
