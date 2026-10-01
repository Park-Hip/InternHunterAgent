# Evaluation Pipeline

> **Last verified:** 2026-10-01.

> **Eviction:** This document leaves when the harness commands, metric contract, or result terms change.

> **Source:** `evals/__main__.py`, `evals/run.py`, `evals/metrics.py`, `evals/sql_check.py`, `evals/v0_gate.py`

The rebuilt harness has one CLI and two ways to run it.
[`docs/how-to/evaluate.md`](../docs/how-to/evaluate.md) is the canonical how-to; this document is the reference for what the pipeline does under the hood.

## The two run modes

| Mode | Command | Needs | What it does |
|---|---|---|---|
| v0 gate | `python -m evals --deterministic --dataset v0` | Fixture database only | Calls the query core directly and grades the 19 governed cases with no model, judge, or network |
| Capture + score | `python -m evals --dataset default` | Serving model (and judge for judge metrics) | Captures each scenario live and scores every declared metric |

A third form, `--capture`, scores a retained replay offline and admits only deterministic metrics.

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
| `plan_correctness` | deterministic | The v0 core's applied plan against the case's reviewed filters |
| `result_equivalence` | deterministic | The v0 result against the case's golden |

Deterministic metrics are credential-free and are the gate.
Judge metrics need a judge credential, are continuous in `[0, 1]`, and are reported-only: no judge threshold is configured yet.

## Deterministic scoring

### `tool_correctness`

Resolves the turn's expected and allowed tools, then fails on any unexpected call and requires every declared tool.
The resolution order is per-turn `turn_tool_expectations`, then scenario `tool_expectation`, then `expected_tools`.
A scenario with `tool_order` demands an exact tool-sequence match.

### `sql_accuracy`

Compares the generated SQL against the reference in [`sql_check.py`](sql_check.py), one of three modes:

| Mode | What it checks |
|---|---|
| `ids_only` | Generated row ids match the reference ids |
| `aggregate_count` | A `COUNT(*) AS count` aggregate equals the reference |
| `zero_results` | Both the generated and reference query return nothing |

An id-less generated query can never pass on two empty results, and a SQL error is an infrastructure failure, not a bad answer.
`--capture` offline scoring is limited to `tool_correctness` and `sql_accuracy`.

## The v0 gate

The `--deterministic` flag routes to [`v0_gate.py`](v0_gate.py), which calls the governed query core directly against the fixture.
No capture, no serving model, no judge, no network.
It grades two deterministic metrics over every case, and fails rather than skips: an unreachable fixture database is a failed gate that exits 2 and names the command to start it.

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
| `2` | The v0 gate could not run (unreachable fixture), or `--deterministic` was given a non-v0 dataset |

A judge score never produces a below-threshold failure because no judge threshold is configured.
`--allow-fail` turns a below-threshold deterministic score into a printed finding for exploratory runs, but it never excuses an unevaluated metric.

## Commands quick reference

```sh
# Fixture
docker compose up -d postgres
uv run python -m evals.fixtures.loader

# v0 gate
uv run python -m evals --deterministic --dataset v0

# Live capture + full scoring (default dataset)
uv run python -m evals --dataset default --out evals/runs/local-report.json

# Narrow a live run
uv run python -m evals --ids HLP-LIST-1,SAF-INDIRECT-INJECTION-1
uv run python -m evals --only tool_correctness,sql_accuracy

# Offline deterministic scoring of a retained capture
uv run python -m evals --only tool_correctness,sql_accuracy \
  --capture evals/replays/t0025.9-committed.json \
  --ids SAF-DESTRUCTIVE-REFUSAL-1,HLP-CONTEXT-1
```