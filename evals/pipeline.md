# Evaluation Pipeline

> **Last verified:** 2026-10-17.

> **Eviction:** This document leaves when the harness commands, metric contract, or result terms change.

> **Source:** `evals/__main__.py`, `evals/run.py`, `evals/metrics.py`, `evals/sql_check.py`, `evals/sql_gate.py`, `evals/milestone.py`

The rebuilt harness has one CLI and three ways to run it.
[`docs/how-to/evaluate.md`](../docs/how-to/evaluate.md) is the canonical how-to; this document is the reference for what the pipeline does under the hood.

## The three run modes

| Mode | Command | Needs | What it does |
|---|---|---|---|
| SQL guard gate | `python -m evals --gate` | Fixture database only | Runs the reviewed SQL statements through the guard and grades the guard verdict and the reviewed result. No model, judge, network, or credential |
| Capture + score | `python -m evals --dataset default` | Serving model (and judge for judge metrics) | Captures each scenario live and scores every declared metric |
| Offline capture scoring | `python -m evals --capture <replay>` | Fixture database when the scenario has reference SQL | Scores a retained replay and admits only deterministic metrics |

The gate's corpus is [`datasets/sql_guard.yaml`](datasets/sql_guard.yaml), read by
[`sql_gate.py`](sql_gate.py) rather than the scenario registry: its cases are reviewed SQL
statements and results, not capture scenarios.

## Capture-and-score pipeline

```text
fixture bind → dataset select → capture → score per metric → group by metric → report → exit code
```

The entry is `evals/__main__.py`, which drives [`run.py`](run.py).

1. **Fixture bind.** `run_dataset` calls `bind_fixture_environment()` before any `src` import, so a capture points at the frozen fixture rather than a serving database.
2. **Dataset select.** [`datasets.py`](datasets.py) resolves the `--dataset` name to a `DatasetSpec` and validates every scenario.
3. **Capture.** For a live run, each scenario's turns are captured once through the serving agent; an offline run reads the first capture per scenario from the retained replay instead.
4. **Score.** Each selected metric grades the captured turn. Judge metrics make a judge call here; deterministic metrics do not.
5. **Group.** [`report.py`](report.py) groups the flat metric rows by metric name, which is the shape the table renders and the JSON persists.
6. **Exit code.** [`__main__.py`](__main__.py) turns the grouped rows into a shell exit code.

## Metric contract

Metrics are declared in [`metrics.py`](metrics.py) and carry a kind.

| Metric | Kind | What it reads |
|---|---|---|
| `tool_correctness` | deterministic | Captured `tools_called` against the scenario's tool expectation |
| `sql_accuracy` | deterministic | Captured `sql_text` against `reference_sql` through [`sql_check.py`](sql_check.py) |
| `grounded` | judge | Captured `tool_output` as the retrieval context for the answer |
| `on_topic` | judge | Question and answer |
| `memory` | judge | Question, answer, and `conversation_history` |
| `rubric` | judge | Question, answer, and the scenario's own `rubric` |

Deterministic metrics are credential-free and are the gate.
Judge metrics need a judge credential, are continuous in `[0, 1]`, and are reported-only: no judge threshold is configured yet.

`sql_accuracy` and `memory` were kept off the governed v0 path by the Stage 4 decision (#487); that
path is retired (ADR-0060), and the v1 scenarios still declare both.

## Milestone runs

A milestone run is the committed record behind a reported number.
`--milestone <label>` writes `evals/runs/<date>-<label>/` with three files:
`manifest.yaml` (commit, prompt versions, models and temperatures, settings, dataset digest, snapshot manifest checksum), `captures.json` (question, answer, tool calls, generated SQL), and `scores.json` (the grouped scores).
The manifest digests the evidence files, and a re-score refuses a mismatch.

```text
capture or replay → score → group → write captures.json + scores.json + manifest.yaml
                                      ↓
                          --rescore: verify digest → score captures.json → compare scores.json
```

Only deterministic metrics are re-scored. Judge metrics need a model call and are reported as recorded-only.
`evals/baseline_sql.py` uses the same folder contract for the Layer 1 text-to-SQL run, with one generated SQL record per question.
Committed runs keep answers verbatim and drop tool output (ADR-0046, #757); the full snapshot stays private (#756).

The SQL guard gate declares its own metrics in [`sql_gate.py`](sql_gate.py):
`guard_correctness` (the validator verdict and the pinned rejection rule) and
`result_equivalence` (the reviewed result on the fixture).

## Deterministic scoring

### `tool_correctness`

Resolves the turn's expected and allowed tools, then fails on any unexpected call and requires every declared tool.
The resolution order is per-turn `turn_tool_expectations`, then scenario `tool_expectation`, then `expected_tools`.
A scenario with `tool_order` demands an exact tool-sequence match.

### `sql_accuracy`

Compares the generated SQL against the reference in [`sql_check.py`](sql_check.py), one of four modes:

| Mode | What it checks |
|---|---|
| `ids_only` | Generated row ids match the reference ids, optionally within a display cap |
| `aggregate_count` | A `COUNT(*) AS count` aggregate equals the reference |
| `zero_results` | Both the generated and reference query return nothing |
| `rows_equal` | Both queries return the same full rows, order-insensitively |

An id-less generated query can never pass on two empty results, and a SQL error is an infrastructure failure, not a bad answer.
`--capture` offline scoring is limited to `tool_correctness` and `sql_accuracy`.
The gate reuses `rows_equal` for group-shaped reviewed results.

## The SQL guard gate

The `--gate` flag routes to [`sql_gate.py`](sql_gate.py), which runs every reviewed statement in
[`datasets/sql_guard.yaml`](datasets/sql_guard.yaml) through the same pipeline the tool uses
(`validate_sql` → `resolve_bounds` → the fixture) and grades the guard verdict and the reviewed
result.
No capture, no serving model, no judge, no network.
It fails rather than skips: an unreachable fixture database is a failed gate that exits 2 and names
the command to start it.
`--gate` scores its own reviewed corpus, so it rejects a non-default `--dataset` with exit 2.

## Result terms

Every metric row carries `scenario_id`, `turn`, `metric`, and `score`.

| Term | Meaning |
|---|---|
| `score: 1.0` | The deterministic check passed |
| `score: 0.0` | The deterministic check failed |
| Judge score in `[0, 1]` | The judge returned a continuous score; reported, not gated |
| `score: null` | The metric could not be evaluated; the `reason` field names why |

Null scores are findings, never passes.
A metric that cannot be scored for a turn is reported as a null-score row with a `NOT_APPLICABLE` or `UNRUN` reason rather than dropped.
The table renders a scenario as `PASS` only when every scored metric is exactly `1.0`.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Every deterministic metric scored exactly `1.0` |
| `1` | A metric could not be evaluated, or a deterministic metric scored below `1.0` without `--allow-fail` |
| `2` | The SQL guard gate could not run (unreachable fixture), or `--gate` was given a non-default dataset |

A judge score never produces a below-threshold failure because no judge threshold is configured.
`--allow-fail` turns a below-threshold deterministic score into a printed finding for exploratory runs, but it never excuses an unevaluated metric.

## Commands quick reference

```sh
# Fixture
docker compose up -d postgres
uv run python -m evals.fixtures.loader

# SQL guard gate
uv run python -m evals --gate

# Live capture + full scoring (default dataset)
uv run python -m evals --dataset default --out evals/runs/local-report.json

# Narrow a live run
uv run python -m evals --ids HLP-LIST-1,SAF-INDIRECT-INJECTION-1
uv run python -m evals --only tool_correctness,sql_accuracy

# Offline deterministic scoring of a retained capture
uv run python -m evals --only tool_correctness,sql_accuracy \
  --capture evals/replays/t0025.9-committed.json \
  --ids SAF-DESTRUCTIVE-REFUSAL-1,HLP-CONTEXT-1

# Committed milestone run and its credential-free re-score
uv run python -m evals --dataset default --milestone agent-v1
uv run python -m evals --rescore evals/runs/2026-10-26-agent-v1

# Layer 1 milestone run, then score and re-score it on the snapshot
uv run python -m evals.baseline_sql generate --milestone baseline-v1
uv run python -m evals.baseline_sql score evals/runs/2026-10-26-baseline-v1 --database-url <snapshot URL>
uv run python -m evals --rescore evals/runs/2026-10-26-baseline-v1 --database-url <snapshot URL>
```
