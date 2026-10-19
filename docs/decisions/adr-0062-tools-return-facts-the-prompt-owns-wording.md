# Tools return facts; the prompt owns wording

> **Status:** Active · **Decided:** 2026-10-19

## Context

The two read-only tools returned finished Vietnamese sentences with a caveat block appended.
`query_clean_jobs` rendered "Tìm thấy N kết quả..." and attached `MANDATORY CAVEATS` lines
detected by `src/services/query/obligations.py` from the SQL and the result table.
The `behavior_glossary` and `behavior_glossary_anchors` blocks in `config/prompts.yaml` were the
machine source of truth for those phrasings, and `evaluation_anchors` held the tokens the
evaluation rules matched, so three artifacts had to agree before one hedge could be said.
A sentence owned by the tool cannot be shaped to the question, and it displaced the prompt's
voice: a listing over the cap read "hiển thị một phần" even when the reader had asked for the
newest five, and a count query's card read "1 kết quả" while the answer said 11 (#677, #702).
The free-text contract also forced the system prompt to relay caveats rather than own them.

## Decision

Both tools return typed JSON facts and no prose, and the system prompt owns every user-facing
word.

- `query_clean_jobs(request)` returns `QueryResult`: `sql` (the statement that ran, after
  bounds), `columns`, `rows`, `row_count`, and `total_rows` (the whole match set, without the
  LIMIT). `get_job_details(ids)` returns `JobDetailsResult`: `jobs` in request order, `not_found`,
  and `not_fetched`. FastMCP publishes an `outputSchema` for both, and the adapter keeps the
  structured content as the tool message artifact.
- The SQL is passed to the model, as `sql`, because it is the fact that explains how a match was
  made. It is internal: the prompt forbids showing or quoting it.
- Failures raise `ToolFailure(kind, detail)` with the closed kind set `rejected`,
  `unknown_column`, `timeout`, `too_large`, and `unavailable`. The MCP wrapper raises
  `ToolError("<kind>: <detail>")`; the model reads the detail in a `status="error"` tool message,
  and the observation middleware reports `status="error"` with `error=None`, so the card keeps
  server-owned Vietnamese copy (ADR-0061). `unavailable` never carries the driver message.
  A failure publishes no result facts.
- `system_prompt` v14 adds one `# Reading tool results` section that states what to do with
  `sql`, `total_rows`, `row_count`, `rows`, `not_found`, and `not_fetched`, and how to describe a
  `description ILIKE` match. The MANDATORY CAVEATS relay is deleted.
- The cross-currency salary rule lives in `sql_generation` v15: every salary aggregate groups by
  `salary_currency`. It is a SQL rule, not code, and the #708 baseline measures it.
- `behavior_glossary`, `behavior_glossary_anchors`, `evaluation_anchors`, the obligations module
  and its config, and `load_behavior_glossary` are deleted.

This is also the compatibility decision the tool names deferred (#465): names stay, the argument
`question` becomes `request`, and the result format changes from text to typed JSON. The
Streamable HTTP endpoint is internal and development-only, so no external client breaks.

## Consequences

The false-success risk that the obligation detector graded moves to the SQL rule plus the
measured baseline, which partly supersedes the gate note in ADR-0060: the SQL guard gate now
grades `guard_correctness` and `result_equivalence` only, and R05, R06, and A02 pin the SQL that
exercises the cross-currency risk instead of asserting a caveat.
Wording can now be adapted to the question, which is what makes truncation, zero results, and a
missing field sayable in the reader's terms, and it removes the three-way agreement between
glossary, anchors, and obligations.
The cost is that no code path guarantees a hedge: the prompt rules and the evaluation layers are
the only place a missing hedge shows up, so a prompt edit is a behavior change with evaluation
consequences.
Prompt versions bump with the YAML (`system` v14, `sql_generation` v15, `schema_context`
unchanged at v12), and Langfuse labels follow
[manage-langfuse-prompts](../how-to/manage-langfuse-prompts.md).
Checkpointed threads can hold old text tool messages after rollout, or JSON ones after a
rollback; both are ordinary history to the model and neither breaks a turn.

## Rollback

Revert the change: no migration and no stored state are involved, and the previous prompt
versions return with the YAML.
