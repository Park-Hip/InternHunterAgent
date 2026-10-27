# `evals/` - Evaluation tooling

> **Last verified:** 2026-10-26.

> **Eviction:** This hub leaves when the evaluation layout, commands, or result terms change.

This directory holds the plain-Python evaluation tooling, with no model judge:

- The credential-free SQL guard gate, which grades reviewed SQL statements against the validator
  and the seeded fixture.
- Layer 1 of the text-to-SQL baseline, which generates one first-turn SQL statement per question
  and scores it offline against the frozen production snapshot.
- The capture contract and offline scorer for the agent baseline run, which is the headline B2 to
  B5 measurement.

The runner that drives the agent conversation lands in
[#759](https://github.com/Park-Hip/InternHunterAgent/issues/759).
Until it lands, no agent run is committed and the Layer 2 numbers in the behavior baseline remain
historical hand marks.

[`docs/how-to/evaluate.md`](../docs/how-to/evaluate.md) is the canonical step-by-step.
This hub is the navigation map and the module reference.
The legacy scenario harness, replays, calibration corpus, and DeepEval judge were deleted in
[ADR-0066](../docs/decisions/adr-0066-evaluation-is-the-baseline-and-the-sql-guard-gate.md);
git history is their archive.
[ADR-0067](../docs/decisions/adr-0067-agent-run-milestones-and-deterministic-answer-checks.md)
adds the agent-run milestone and supersedes item 6 of ADR-0066.

## Quick commands

```sh
# Start the fixture database and load the frozen 24-row dataset.
# The loader also provisions internhunter_eval_reader with column-level SELECT.
docker compose up -d postgres
uv run python -m evals.fixtures.loader

# Credential-free SQL guard gate (the CI gate).
uv run python -m evals

# Layer 1 text-to-SQL run (#708): one temperature-0 generation per question, then offline scoring.
# The snapshot is a local copy of production clean_jobs; see the module docstring.
uv run python -m evals.baseline_sql generate --milestone baseline-v1
uv run python -m evals.baseline_sql score evals/runs/2026-10-26-baseline-v1 --database-url <snapshot reader URL>
uv run python -m evals --rescore evals/runs/2026-10-26-baseline-v1 --database-url <snapshot reader URL>

# Agent baseline run (#760): the #759 runner writes the run, then these commands score it offline.
uv run python -m evals.baseline_agent score evals/runs/<date>-agent-v1 --database-url <snapshot reader URL>
uv run python -m evals.baseline_agent review evals/runs/<date>-agent-v1 --out evals/runs/<date>-agent-v1/hand_review.md
uv run python -m evals --rescore evals/runs/<date>-agent-v1 --database-url <snapshot reader URL>
```

`--out` writes the gate report elsewhere; the default is the gitignored
`evals/runs/sql-gate-latest.json`.<!-- lint-allow-link-path -->
`--ids` narrows the gate to named cases.
`--milestone <label>` on `baseline_sql generate` writes one Layer 1 run to
`evals/runs/<date>-<label>/` with a lineage manifest and the evidence needed to re-score it offline.
[`milestone.write_agent_run`](milestone.py) writes an agent run from the complete capture the #759
runner produces.
Only dated milestone directories are committed; other output under `evals/runs/` stays local and
gitignored.
`--rescore` verifies a committed run of either runner from its own evidence and makes no model call.

The fixture loader rebuilds and seeds with the owner DSN in `eval.fixture.database_url`, then
provisions `internhunter_eval_reader` with column-level `SELECT` on the 16 contract columns and
`SELECT` on `alembic_version`.
The gate binds `AGENT_DATABASE_URL` to that reader role, so a star query or a hidden-column read
fails as it does in production (#730).
Both baselines score against the snapshot, never the fixture: `score` takes the URL you pass and
verifies its manifest first.
The scoring path refuses an owner, a superuser, a table-level `SELECT`, a role that can read a hidden
column, or a role that cannot read a contract column.
The snapshot's reader role also needs `SELECT` on `alembic_version`, because the snapshot check reads
the migration revision.
Rebuilding the fixture re-applies the grants; see
[`docs/how-to/evaluate.md`](../docs/how-to/evaluate.md).

## Datasets

| Dataset | File | What it describes | How it runs |
|---|---|---|---|
| SQL guard | [`datasets/sql_guard.yaml`](datasets/sql_guard.yaml) | Reviewed, floor, accepted-risk, and injection SQL cases | [`python -m evals`](__main__.py) through [`sql_gate.py`](sql_gate.py) |
| Baseline | [`datasets/baseline.yaml`](datasets/baseline.yaml) | 36 MVP baseline questions (#708), 24 dev and 12 held-out, 45 turns, 32 first-turn reference SQLs and six later-turn ones | [`baseline_sql.py`](baseline_sql.py): Layer 1, `generate` once then `score` offline. [`baseline_agent.py`](baseline_agent.py): agent run, written by #759 then scored offline |

Each dataset file owns its own grammar and cases.
The baseline snapshot identity lives in [`datasets/baseline_manifest.yaml`](datasets/baseline_manifest.yaml)
and is verified by [`snapshot_manifest.py`](snapshot_manifest.py).

## Metrics

The gate declares two deterministic metrics in [`sql_gate.py`](sql_gate.py):

| Metric | Scores |
|---|---|
| `guard_correctness` | The `validate_sql` verdict against the reviewed one, and the rule that must reject a rejected case |
| `result_equivalence` | The rows the reviewed SQL returns on the fixture, against a reviewer-written reference |

Layer 1 reports `sql_accuracy` per split from [`sql_check.py`](sql_check.py) comparison modes.
It is a component diagnostic: first-turn SQL only, one temperature-0 generation per question.
It is not the headline B2.

An agent run reports four deterministic metrics per turn and repeat:

| Metric | Scores |
|---|---|
| `execution_accuracy` | B2: the exact result of the SQL behind the last `query_clean_jobs` call, through the reader role. A validator rejection, a missing call, a missing statement, or a tool error fails; a database error is unscored |
| `answer_faithfulness` | B3: cited links exist in the captured `source_urls`, count claims match `count_values` or `total_rows`, and a fallback answer does not claim rows |
| `result_communicated` | B4: an empty result, a cut-off list, a final page, and a continuation are said |
| `answer_language` | B5: the answer is Vietnamese |

A null score is not applicable and is excluded from the pass rate, never counted as a pass.
Tool calls, latency, and tokens are recorded beside the rows as instrumentation and never gate.
The generated `hand_review.md` covers invented postings, wording, concision, and filter retention for
a human; there is no model judge.

## Test-to-module mapping

Tests live in [`tests/evals/`](../tests/evals/).

| Test file | Production module | Behavior pinned |
|---|---|---|
| `test_env.py` | [`env.py`](env.py) | Fixture environment binding before any `src` import, owner versus reader DSN |
| `test_fixture_reader.py` | [`fixtures/loader.py`](fixtures/loader.py) | Reader-role provisioning, column grants after a rebuild, star denial, `rejected` mapping |
| `test_sql_check.py` | [`sql_check.py`](sql_check.py) | SQL comparison modes with query results stubbed |
| `test_sql_gate.py` | [`sql_gate.py`](sql_gate.py) + [`datasets/sql_guard.yaml`](datasets/sql_guard.yaml) | Dataset grammar, guard/result grading, gate refusals |
| `test_baseline_sql.py` | [`baseline_sql.py`](baseline_sql.py) + [`datasets/baseline.yaml`](datasets/baseline.yaml) | Baseline dataset grammar, reader role, validator rejection, repeats, offline scoring with execution stubbed |
| `test_baseline_agent.py` | [`baseline_agent.py`](baseline_agent.py) + [`datasets/baseline.yaml`](datasets/baseline.yaml) | Agent capture contract, execution accuracy, the six later turns, B3 to B5, instrumentation, hand review, agent re-scoring |
| `test_milestone.py` | [`milestone.py`](milestone.py) | Manifest lineage, evidence digests, dataset drift, both runners' re-score reproduction, gitignore boundary |

## The map

```
evals/
├── README.md                     This navigation hub
├── __main__.py                   CLI entry: python -m evals
├── sql_gate.py                   Credential-free SQL guard gate
├── reporting.py                  Shared result grouping and table rendering
├── milestone.py                  Committed run folders, lineage manifests, runner dispatch
├── sql_check.py                  Reader role, validator verdict, result comparison
├── baseline_sql.py               Layer 1 generation and offline scoring
├── baseline_agent.py             Agent capture contract, B2 to B5 scoring, hand review
├── baseline_config.py            Validated repeats and row cap from config/settings.yaml
├── snapshot_manifest.py          Frozen-snapshot identity and verification
├── manifest.py                   Compatibility re-export of snapshot_manifest
├── baseline_manifest.py          Compatibility re-export of snapshot_manifest
├── env.py                        Fixture owner/reader binding before any src import
├── _paths.py                     Shared path constants
│
├── datasets/
│   ├── sql_guard.yaml            The reviewed SQL guard corpus (20 cases)
│   ├── baseline.yaml             The 36 baseline questions
│   └── baseline_manifest.yaml    Committed identity of the frozen snapshot
│
├── manifest.yaml                 Duplicate snapshot manifest name
├── snapshot_manifest.yaml        Duplicate snapshot manifest name
│
├── runs/                         Dated baseline and agent runs - committed; other reports local
│
└── fixtures/
    ├── loader.py                 Fixture database build/reset and reader grants
    └── seed_eval_db.sql          The frozen 24-row fixture dataset
```
