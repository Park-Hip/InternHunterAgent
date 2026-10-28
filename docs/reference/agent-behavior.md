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
- An offset page has a total order or is refused: the outermost ORDER BY must include `id`, the
  unique key, before any OFFSET runs
  ([ADR-0064](../decisions/adr-0064-offset-pages-require-a-total-order.md)).

The tools return facts and the system prompt owns all wording. The prompts are
`config/prompts.yaml` `system_prompt`, `schema_context`, and `sql_generation`; traces identify each
by the first 12 hex of the SHA-256 of its text.

## How it is measured

- **Data:** the frozen snapshot `internhunter_snapshot_20261018` of production `clean_jobs`
  (367 rows), because nightly ingestion changes the live data.
- **Questions:** the baseline case files under [`evals/datasets/`](../../evals/datasets/), 76 cases and 94 turns, written by a separate AI from the problem statement.
  The 36 #708 questions are all dev now, because the 12 that were once held-out were used while tuning `sql_generation`.
  Six dev paraphrases measure wording sensitivity.
  Thirty fresh held-out questions were written after the dev set was frozen and are never read while a change is tuned.
  Four safety cases cover destructive, injection, and secret-exfiltration requests, plus an injection carried by posting text.
  The #708 reference SQL was checked against the snapshot.
  The fresh held-out statements follow the same reviewed shapes; every one executes on the fixture, and scoring executes it against the snapshot.
  [`evals/baseline_dataset.py`](../../evals/baseline_dataset.py) validates every case, including the quoted `answerable` enum.
- **Layer 1, text-to-SQL:** `evals/baseline_sql.py` runs the generated and reference SQL on the
  snapshot and compares result sets. It scores `sql_accuracy` for the first turn only, as a component
  diagnostic. It is not the headline B2, because it never sees the validator verdict or the answer.
- **Agent run, headline:** `evals/baseline_agent.py` scores `execution_accuracy` (B2) on the SQL behind the last `query_clean_jobs` call of each turn that has a reference, through the reader role.
  It also scores deterministic answer checks: `answer_faithfulness` (B3), `result_communicated` (B4), and `answer_language` (B5).
  `safety_refusal` scores the cases with an `expect` block: the refusal is present and no forbidden value leaks.
  The later-turn reference SQLs are scored; B6 and the behaviors code cannot settle are on a hand-review sheet.
  No model judge is used.
- **Runner:** [`evals/agent_runner.py`](../../evals/agent_runner.py) drives the conversations through
  `stream_agent_response`, added in [#759](https://github.com/Park-Hip/InternHunterAgent/issues/759).
  No agent run is committed yet, so no agent metric is reported.
- **Pass bars:** B2 at least 85% on held-out; B3 and B4 at 100%; every safety case passes.
- **Model credit:** run at milestones only, and commit each Layer 1 or agent run under
  [`evals/runs/`](../../evals/runs/) with the evidence re-scoring reads, so a re-score is free
  ([milestone runs](../how-to/evaluate.md#milestone-runs)).

## Baseline results (2026-10-19, prompts v1)

| Layer | Result | Evidence |
|---|---|---|
| Layer 1 | 31/32: dev 22/22, held-out 9/10. The one failure, 025, reads an ambiguous deadline question as a single posting. | [committed run](../../evals/runs/2026-10-19-baseline-v1/manifest.yaml) |
| Layer 2, historical | 12 cases, 21 turns (022, 024, 026 to 032, 007, 033, 035). B3, B4, B5, and B6 held in every turn: totals and partial lists stated, the empty result said plainly, no SQL, column name, or id shown, and every follow-up kept its filters. | hand-marked before the committed-run contract existed, no committed run |

The Layer 1 run is committed with the generated SQL, the recorded score per question, and the lineage manifest that names the commit, the prompts, the model, and the digests of the case files.
Re-score it from its own evidence without a model call:

```
uv run python -m evals --rescore evals/runs/2026-10-19-baseline-v1 \
  --database-url "$BASELINE_DATABASE_URL"
```

The `dev 22/22, held-out 9/10` breakdown is historical.
Those 12 held-out cases are dev now, so a re-score reproduces the same 32 score rows but reports them all as dev.
The 31/32 total is the reproducible result.

The Layer 2 marks were made by hand before the committed-run contract existed, and the run files are not recoverable.
The agent-run contract and scorer were added in
[#760](https://github.com/Park-Hip/InternHunterAgent/issues/760), and the runner landed in
[#759](https://github.com/Park-Hip/InternHunterAgent/issues/759), but no agent run is committed.
Those numbers stay historical until one is, and no B2 headline, B3, B4, or B5 number is reported from
this baseline yet.

The held-out Layer 1 score is optimistic: rules 3 and 4 of `sql_generation` were written after
held-out failures 025 and 026.
Those 12 cases are dev now, and the fresh held-out set has no committed run, so no held-out number
is reported for it yet.

## Rule for adding complexity

A new prompt rule or test must:

1. Fix a failure seen more than once, on a dev or held-out question.
2. Go at the lowest layer that works: data or column description, then tool facts, then a prompt
   rule as the last resort.
3. Be checked on the dev paraphrases first, then on the fresh held-out set at the next milestone, not only on the input that failed.
   A held-out run is committed before its failures are read, so a fix is not made against the question that measures it.
4. Record what it fixes, so it can be deleted once it stops mattering.
