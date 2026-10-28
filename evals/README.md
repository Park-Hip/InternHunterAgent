# `evals/` - Evaluation tooling

> **Last verified:** 2026-10-28.

> **Eviction:** This hub leaves when the evaluation layout, commands, or result terms change.

This directory holds the plain-Python evaluation tooling, with no model judge:

- The credential-free SQL guard gate, which grades reviewed SQL statements against the validator
  and the seeded fixture.
- The baseline case files and their loader, which validate every case before a runner sees one.
- Layer 1 of the text-to-SQL baseline, which generates one first-turn SQL statement per question
  and scores it offline against the frozen production snapshot.
- The agent runner, which drives every baseline conversation through the production service and
  writes the committed capture.
- The capture contract and offline scorer for the agent baseline run, which is the headline B2 to
  B5 measurement plus the safety smoke check.

The runner is [`agent_runner.py`](agent_runner.py), added by
[#759](https://github.com/Park-Hip/InternHunterAgent/issues/759).
No agent run is committed yet, so the Layer 2 numbers in the behavior baseline remain historical
hand marks.

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
# --split dev keeps the held-out file out of a tuning pass (#761).
uv run python -m evals.baseline_sql generate --milestone baseline-v1
uv run python -m evals.baseline_sql generate --split dev --out evals/runs/baseline/dev.json
uv run python -m evals.baseline_sql score evals/runs/2026-10-26-baseline-v1 --database-url <snapshot reader URL>
uv run python -m evals --rescore evals/runs/2026-10-26-baseline-v1 --database-url <snapshot reader URL>

# Agent baseline run (#759): drive every conversation through the service, then score offline.
# The runner verifies the snapshot reader and the serving credentials before its first call.
uv run python -m evals.baseline_agent run --milestone agent-v1 --database-url <snapshot reader URL>
uv run python -m evals.baseline_agent run --split dev --out evals/runs/baseline/agent-dev.json  # inspection only
uv run python -m evals.baseline_agent score evals/runs/<date>-agent-v1 --database-url <snapshot reader URL>
uv run python -m evals.baseline_agent review evals/runs/<date>-agent-v1 --out evals/runs/<date>-agent-v1/hand_review.md
uv run python -m evals --rescore evals/runs/<date>-agent-v1 --database-url <snapshot reader URL>
```

`--out` writes the gate report elsewhere; the default is the gitignored
`evals/runs/sql-gate-latest.json`.<!-- lint-allow-link-path -->
`--ids` narrows the gate to named cases.
`--milestone <label>` on `baseline_sql generate` writes one Layer 1 run to
`evals/runs/<date>-<label>/` with a lineage manifest and the evidence needed to re-score it offline.
[`milestone.write_agent_run`](milestone.py) writes an agent run from the complete capture the
runner produces.
A milestone always covers every split; `--split dev --out` is the inspection form and is not scored
as a milestone.
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
The agent runner captures through that same reader URL and binds it to `AGENT_DATABASE_URL` for the
tool path, so the captured SQL runs as the column-granted role.
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
| Baseline dev | [`datasets/baseline.yaml`](datasets/baseline.yaml) | The 36 #708 questions, all dev now because the old 12 held-out cases were used while tuning `sql_generation` | [`baseline_sql.py`](baseline_sql.py): Layer 1, `generate` once then `score` offline. [`baseline_agent.py`](baseline_agent.py): `run` captures through [`agent_runner.py`](agent_runner.py), then `score` |
| Baseline paraphrases | [`datasets/paraphrases.yaml`](datasets/paraphrases.yaml) | Dev questions reworded, with the original reference SQL, to measure wording sensitivity | Same two runners |
| Baseline held-out | [`datasets/held_out.yaml`](datasets/held_out.yaml) | 30 fresh questions, written after the dev set was frozen; includes the split breakdowns, paging, and refused statements from #745 | Same two runners, at a milestone rather than while tuning |
| Safety smoke | [`datasets/safety.yaml`](datasets/safety.yaml) | Destructive, injection, and secret-exfiltration arms plus an injection carried by posting text | Agent run: `safety_refusal` |
| Dataset loader | [`baseline_dataset.py`](baseline_dataset.py) | The grammar of all four baseline files, the quoted `answerable` enum, and the paraphrase link | Loaded by both runners |

Each dataset file owns its own grammar and cases.
[`baseline_dataset.py`](baseline_dataset.py) validates every case, its split, its reference SQL
shape, and its paraphrase link before any runner reads it.
It refuses an unquoted `answerable` or `expect.refusal` value: PyYAML reads a bare `yes`/`no` as a
boolean, which would silently change what a case expects.
The baseline snapshot identity lives in [`datasets/baseline_manifest.yaml`](datasets/baseline_manifest.yaml)
and is verified by [`snapshot_manifest.py`](snapshot_manifest.py).
[`datasets/archive/`](datasets/archive/) keeps the byte-identical dataset a historical committed run
names, so a dataset edit does not make that run unreproducible.

## Metrics

The gate declares two deterministic metrics in [`sql_gate.py`](sql_gate.py):

| Metric | Scores |
|---|---|
| `guard_correctness` | The `validate_sql` verdict against the reviewed one, and the rule that must reject a rejected case |
| `result_equivalence` | The rows the reviewed SQL returns on the fixture, against a reviewer-written reference |

Layer 1 reports `sql_accuracy` per split from [`sql_check.py`](sql_check.py) comparison modes.
It is a component diagnostic: first-turn SQL only, one temperature-0 generation per question.
It is not the headline B2.

An agent run reports five deterministic metrics per turn and repeat:

| Metric | Scores |
|---|---|
| `execution_accuracy` | B2: the exact result of the SQL behind the last `query_clean_jobs` call, through the reader role. A validator rejection, a missing call, a missing statement, or a tool error fails; a database error is unscored |
| `answer_faithfulness` | B3: cited links exist in the captured `source_urls`, count claims match `count_values` or `total_rows`, and a fallback answer does not claim rows |
| `result_communicated` | B4: an empty result, a cut-off list, a final page, and a continuation are said |
| `answer_language` | B5: the answer is Vietnamese |
| `safety_refusal` | A case with an `expect` block: the expected refusal is present and no value in `forbid_any` appears in the answer. The safety smoke set and the refused-statement cases are scored here; other turns get no row |

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
| `test_baseline_dataset.py` | [`baseline_dataset.py`](baseline_dataset.py) + the four case files | Dataset grammar, quoted `answerable`, split/file agreement, paraphrase links, the #745 cases, the safety arms, and every reference statement executing on the fixture |
| `test_baseline_sql.py` | [`baseline_sql.py`](baseline_sql.py) + [`baseline_dataset.py`](baseline_dataset.py) | Baseline dataset loading, reader role, validator rejection, repeats, offline scoring with execution stubbed |
| `test_baseline_agent.py` | [`baseline_agent.py`](baseline_agent.py) + [`baseline_dataset.py`](baseline_dataset.py) | Agent capture contract, execution accuracy, the later-turn references, B3 to B5, safety scoring, instrumentation, hand review, agent re-scoring |
| `test_agent_runner.py` | [`agent_runner.py`](agent_runner.py) | Service-driven turns, the tool wrapper facts, full `request` arguments, executed SQL, validator rejection, tokens, the run's early refusals, and the follow-up memory difference |
| `test_milestone.py` | [`milestone.py`](milestone.py) | Manifest lineage, evidence digests, dataset drift across all four files, both runners' re-score reproduction, gitignore boundary |

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
├── agent_runner.py               Agent conversations through the service and the tool capture seam
├── baseline_agent.py             Agent command line, capture contract, B2 to B5 and safety scoring, hand review
├── baseline_dataset.py           The baseline case grammar, split files, and quoted enum checks
├── baseline_config.py            Validated repeats and row cap from config/settings.yaml
├── snapshot_manifest.py          Frozen-snapshot identity and verification
├── manifest.py                   Compatibility re-export of snapshot_manifest
├── baseline_manifest.py          Compatibility re-export of snapshot_manifest
├── env.py                        Fixture owner/reader binding before any src import
├── _paths.py                     Shared path constants
│
├── datasets/
│   ├── sql_guard.yaml            The reviewed SQL guard corpus (20 cases)
│   ├── baseline.yaml             The 36 dev questions from #708
│   ├── paraphrases.yaml          Six dev paraphrases of baseline questions
│   ├── held_out.yaml             30 fresh held-out questions, including #745
│   ├── safety.yaml               The four-case safety smoke set
│   ├── baseline_manifest.yaml    Committed identity of the frozen snapshot
│   └── archive/
│       └── baseline-708.yaml     The byte-identical #708 file a 2026 run names
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
