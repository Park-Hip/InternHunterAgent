# `evals/` - Evaluation tooling

> **Last verified:** 2026-10-26.

> **Eviction:** This hub leaves when the evaluation layout, commands, or result terms change.

This directory holds two plain-Python checks of agent behavior, with no model judge:

- The credential-free SQL guard gate, which grades reviewed SQL statements against the validator
  and the seeded fixture.
- The text-to-SQL baseline, which generates SQL once and scores it offline against the frozen
  production snapshot.

[`docs/how-to/evaluate.md`](../docs/how-to/evaluate.md) is the canonical step-by-step.
This hub is the navigation map and the module reference.
The legacy scenario harness, replays, calibration corpus, and DeepEval judge were deleted in
[ADR-0066](../docs/decisions/adr-0066-evaluation-is-the-baseline-and-the-sql-guard-gate.md);
git history is their archive.

## Quick commands

```sh
# Start the fixture database and load the frozen 24-row dataset.
# The loader also provisions internhunter_eval_reader with column-level SELECT.
docker compose up -d postgres
uv run python -m evals.fixtures.loader

# Credential-free SQL guard gate (the CI gate).
uv run python -m evals

# Baseline text-to-SQL run (#708): one model call per question, then offline scoring.
# The snapshot is a local copy of production clean_jobs; see the module docstring.
uv run python -m evals.baseline_sql generate --milestone baseline-v1
uv run python -m evals.baseline_sql score evals/runs/2026-10-26-baseline-v1 --database-url <snapshot URL>
uv run python -m evals --rescore evals/runs/2026-10-26-baseline-v1 --database-url <snapshot URL>
```

`--out` writes the gate report elsewhere; the default is the gitignored
`evals/runs/sql-gate-latest.json`.<!-- lint-allow-link-path -->
`--ids` narrows the gate to named cases.
`--milestone <label>` on `generate` writes `evals/runs/<date>-<label>/` with a lineage manifest and
the evidence needed to re-score it offline.
Only dated milestone directories are committed; other output under `evals/runs/` stays local and
gitignored.
`--rescore` verifies a committed baseline run from its own evidence and makes no model call.

The fixture loader rebuilds and seeds with the owner DSN in `eval.fixture.database_url`, then
provisions `internhunter_eval_reader` with column-level `SELECT` on the 16 contract columns.
The gate binds `AGENT_DATABASE_URL` to that reader role, so a star query or a hidden-column read
fails as it does in production (#730).
The baseline never reads the fixture: `score` takes the snapshot URL you pass and verifies its
manifest first.
Rebuilding the fixture re-applies the grants; see
[`docs/how-to/evaluate.md`](../docs/how-to/evaluate.md).

## Datasets

| Dataset | File | What it describes | How it runs |
|---|---|---|---|
| SQL guard | [`datasets/sql_guard.yaml`](datasets/sql_guard.yaml) | Reviewed, floor, accepted-risk, and injection SQL cases | [`python -m evals`](__main__.py) through [`sql_gate.py`](sql_gate.py) |
| Baseline | [`datasets/baseline.yaml`](datasets/baseline.yaml) | 36 MVP baseline questions (#708), 24 dev and 12 held-out, with reference SQL for a production snapshot | [`baseline_sql.py`](baseline_sql.py): `generate` once, then `score` offline |

Each dataset file owns its own grammar and cases.
The baseline snapshot identity lives in [`datasets/baseline_manifest.yaml`](datasets/baseline_manifest.yaml)
and is verified by [`snapshot_manifest.py`](snapshot_manifest.py).

## Metrics

The gate declares two deterministic metrics in [`sql_gate.py`](sql_gate.py):

| Metric | Scores |
|---|---|
| `guard_correctness` | The `validate_sql` verdict against the reviewed one, and the rule that must reject a rejected case |
| `result_equivalence` | The rows the reviewed SQL returns on the fixture, against a reviewer-written reference |

The baseline reports pass counts per split from [`sql_check.py`](sql_check.py) comparison modes;
it is a diagnostic run, not a pass/fail gate.

## Test-to-module mapping

Tests live in [`tests/evals/`](../tests/evals/).

| Test file | Production module | Behavior pinned |
|---|---|---|
| `test_env.py` | [`env.py`](env.py) | Fixture environment binding before any `src` import, owner versus reader DSN |
| `test_fixture_reader.py` | [`fixtures/loader.py`](fixtures/loader.py) | Reader-role provisioning, column grants after a rebuild, star denial, `rejected` mapping |
| `test_sql_check.py` | [`sql_check.py`](sql_check.py) | SQL comparison modes with query results stubbed |
| `test_sql_gate.py` | [`sql_gate.py`](sql_gate.py) + [`datasets/sql_guard.yaml`](datasets/sql_guard.yaml) | Dataset grammar, guard/result grading, gate refusals |
| `test_baseline_sql.py` | [`baseline_sql.py`](baseline_sql.py) + [`datasets/baseline.yaml`](datasets/baseline.yaml) | Baseline dataset grammar, offline scoring with execution stubbed |
| `test_milestone.py` | [`milestone.py`](milestone.py) | Manifest lineage, evidence digests, baseline re-score reproduction, gitignore boundary |

## The map

```
evals/
├── README.md                     This navigation hub
├── __main__.py                   CLI entry: python -m evals
├── sql_gate.py                   Credential-free SQL guard gate
├── reporting.py                  Shared result grouping and table rendering
├── milestone.py                  Committed run folders, lineage manifests, re-scoring
├── sql_check.py                  Generated-SQL vs reference-result comparison
├── baseline_sql.py               Baseline generation and offline scoring
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
├── runs/                         Dated baseline milestone runs - committed; other reports local
│
└── fixtures/
    ├── loader.py                 Fixture database build/reset and reader grants
    └── seed_eval_db.sql          The frozen 24-row fixture dataset
```
