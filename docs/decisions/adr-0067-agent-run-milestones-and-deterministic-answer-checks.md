# Agent-run milestones score the SQL the agent ran, with deterministic answer checks

> **Status:** Active, provisional until the runner in [#759](https://github.com/Park-Hip/InternHunterAgent/issues/759) lands · **Decided:** 2026-10-26
>
> **Supersedes:** item 6 of [ADR-0066](adr-0066-evaluation-is-the-baseline-and-the-sql-guard-gate.md), the clause that ruled out an agent-run milestone

## Context

Layer 1 scores the SQL generated for the first turn of each baseline question.
It never sees the agent's tool calls, the validator verdict, or the answer the user reads.
It also ran through any database role, so a star or hidden-column read could pass where production refuses it.
B3 to B5 were hand-marked once, over 12 cases and 21 turns, with no committed evidence.
[#760](https://github.com/Park-Hip/InternHunterAgent/issues/760) changes both: the headline B2 is the SQL the agent actually ran, and the answer checks become deterministic.

The runner that drives a real baseline conversation through the application service is
[#759](https://github.com/Park-Hip/InternHunterAgent/issues/759), and it is still open.
This record fixes the evidence contract and the offline scorer before that runner exists, so the runner
cannot define its own metric or its own evidence shape.

## Decision

1. **Two runners share one dataset.** `baseline_sql` remains the Layer 1 text-to-SQL diagnostic.
   `agent` is the headline agent-run runner.
   Both write committed milestone directories under `evals/runs/`, and neither needs a model to re-score.
2. **The agent run is a milestone run.** Its `captures.json` holds one conversation record per question
   and repeat, with every turn's question, answer, `answer_source`, latency, tokens, and tool calls.
   A tool call holds the SQL, validator verdict, result shape, counts, page offset, truncation flag,
   and source links.
   Full result rows are never captured, so the private snapshot stays out of the repository.
3. **B2 is execution accuracy of the agent's query.** `execution_accuracy` scores the last
   `query_clean_jobs` call in a turn.
   The `generated_sql` is the exact-match basis because the tool's own row cap and offset are not the
   model's SQL; a capture that holds only `executed_sql` uses it, and a truncated executed statement
   loses the tool's cap with the basis recorded.
   The statement is compared with its reference through the non-owner reader role.
   A validator rejection is a failure and is never executed.
   A turn with no query call, no SQL, or a tool error fails; a database error is unscored, not a bad
   answer.
4. **The six later-turn reference SQLs are scored.** Questions 027 to 032 carry a reference for turn
   two, and the agent run scores those turns like the first.
   Questions 033 to 036 have no reference SQL, and follow-up turns 022, 024, and 026 have none either,
   so execution accuracy does not apply to them; their answers are still checked.
5. **B3 to B5 have deterministic checks.** `answer_faithfulness` requires every cited link to appear
   among the captured `source_urls` and every count claim to appear among `count_values` or
   `total_rows`, and refuses a fallback answer that claims rows.
   `result_communicated` requires an empty result, a cut-off list, a final page, and a continuation to
   be stated.
   `answer_language` requires Vietnamese.
   A turn where a check does not apply is recorded with a null score and reported as not applicable,
   never counted as a pass.
6. **The hand-review sheet covers what code cannot check.** `hand_review.md` lists invented postings,
   nuanced wording, concision, and follow-up filter retention for a human.
   No model judge is introduced.
7. **Instrumentation is reported, never gated.** Tool calls, latency, and tokens are stored per turn
   in `scores.json` and printed by the scorer, but they do not change a metric.
8. **Repeats stay visible.** Layer 1 runs one temperature-0 generation per question.
   The agent run repeats every conversation `eval.baseline.agent_repeats` times and reports per-repeat
   rows, so variance is not averaged away.
   A run records its repeat count and `agent.query.max_rows`, and re-scoring uses those recorded
   values rather than the current configuration.
9. **Scoring is offline and verified.** Scoring verifies the manifest digests, the dataset digest, the
   snapshot identity, and the reader role before it computes a row.
   `python -m evals --rescore` recomputes every deterministic row and refuses a mismatch; it calls no
   model.
10. **This is provisional.** The runner is #759.
    Until it lands and a real run is committed, no agent metric is reported, and the historical Layer
    2 hand marks stay historical.

## What still holds from earlier records

- **ADR-0016 (three layers).** The agent run measures outcome and trajectory; the gate and unit tests
  keep measuring the component boundary.
- **ADR-0017 (judge provider separate from serving).** No judge runs. If one returns, it still must not
  share the serving provider.
- **ADR-0018 (offline before online).** The agent run is another offline baseline, not online trace
  scoring.
- **ADR-0037 (frozen fixture baselines).** The frozen snapshot and fixture still fix the data a
  measurement reads.
- **ADR-0062 (tools return facts).** The capture reads the facts the tools already return; the scorer
  never parses prose to reconstruct a result set.
- **ADR-0063 (least-privilege boundary).** Both runners score through the reader role.
- **ADR-0066 (evaluation instrument).** The baseline and the guard gate remain the evaluation.
  Only the no-agent-run clause is superseded.

## Consequences

- `evals/baseline_agent.py` owns the capture contract, the four metrics, the hand-review sheet, and the
  scoring CLI.
  `evals/milestone.py` writes an agent run, refuses a changed dataset, verifies repeats, and dispatches
  re-scoring by runner.
- `config/settings.yaml` gains `eval.baseline.layer1_repeats: 1` and
  `eval.baseline.agent_repeats: 3`.
  The settings are recorded in each run's lineage.
- The private snapshot needs a non-owner reader role with column-level `SELECT` on the 16 contract
  columns and `SELECT` on `alembic_version`.
  Without the revision read, the snapshot check cannot verify the manifest and refuses to score.
- The committed `evals/runs/2026-10-19-baseline-v1/` remains Layer 1 evidence.
  It is not an agent run and does not support a B3 to B5 claim.
- The Layer 2 result in [`agent-behavior.md`](../reference/agent-behavior.md) remains a historical hand
  mark until a real agent run is committed.

## Verification

| Check | Method | Expected result |
| --- | --- | --- |
| The capture contract refuses leaked rows | `uv run pytest tests/evals/test_baseline_agent.py -k "capture or full"` | Green |
| The six later-turn references are scored | `uv run pytest tests/evals/test_baseline_agent.py -k "six_later_turns"` | Green |
| The scorer is offline and repeat-aware | `uv run pytest tests/evals/test_baseline_agent.py` | Green, no model call |
| A committed agent run re-scores | `uv run python -m evals --rescore <agent run> --database-url <reader URL>` | Every deterministic row reproduces |
| Layer 1 still re-scores | `uv run python -m evals --rescore evals/runs/2026-10-19-baseline-v1 --database-url <reader URL>` | The recorded pass counts reproduce |
| Docs resolve | `uv run python scripts/docs_lint.py` | Exit 0 |

## Rollback

Revert this change.
The scorer and the capture contract are plain Python, the settings have no runtime side effect, and no
stored data or external contract is involved.
An uncommitted agent run directory is local evidence and can be deleted with the revert.
