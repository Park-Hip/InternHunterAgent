# Authoring Scenarios

> **Last verified:** 2026-10-01.

> **Eviction:** This document leaves when the scenario grammar, metric contract, or authoring commands change.

> **Source:** `evals/datasets.py`, `evals/datasets/scenarios.yaml`, `evals/metrics.py`

Scenarios are declarative YAML, validated by [`datasets.py`](../datasets.py) when the harness loads them.
There is no separate registry loader: `DatasetSpec.scenarios()` is the single validator, and it rejects a scenario the harness would otherwise silently misread.

## Where scenarios live

| Dataset | File | Select with |
|---|---|---|
| v1 scenarios | [`../datasets/scenarios.yaml`](../datasets/scenarios.yaml) | `--dataset default` |
| v0 acceptance cases | [`../datasets/v0_acceptance.yaml`](../datasets/v0_acceptance.yaml) | `--dataset v0` |

A new version is a new dataset entry, never an edit to an existing registry.
The same id must be unique within its dataset.

## Enforced grammar

`DatasetSpec.scenarios()` rejects, in this order:

1. A registry that is not a YAML list of mappings.
2. A scenario without a string `id`, or a duplicate `id`.
3. A scenario with neither `input` nor `turns`.
4. A scenario without a string `expected`.
5. A `metrics` list that is empty, missing, or names an unknown metric.
6. A v0 case that declares `sql_accuracy` or `memory` (retired for the governed path by #487).
7. A scenario declaring `sql_accuracy` without `reference_sql`.
8. A scenario declaring `rubric` without a `rubric`.
9. A tool key the harness does not read, or a malformed tool expectation.

The loader reads only four tool keys: `expected_tools`, `tool_expectation`, `turn_tool_expectations`, and `tool_order`.
Any other key containing `tool` is an explicit error.

## Scenario fields

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | string | yes | Unique within its dataset |
| `input` | string | single-turn | The user question |
| `turns` | list of strings | conversational | The ordered turn questions |
| `expected` | string | yes | The reviewed expected behavior |
| `metrics` | list of metrics | yes | The metrics to score for this scenario |
| `expected_tools` | list of strings | for tool scenarios | Required tools when no finer declaration exists |
| `tool_expectation` | `{required, allowed}` | optional | Scenario-level tool contract |
| `turn_tool_expectations` | list of `{required, allowed}` | optional | Per-turn tool contract (conversational) |
| `tool_order` | bool | optional | Demand an exact tool-sequence match |
| `reference_sql` | string or list | if `sql_accuracy` | Reference SQL; a list is per-turn |
| `sql_mode` | `ids_only` / `aggregate_count` / `zero_results` | if `sql_accuracy` | Comparison mode |
| `expected_count` | int | for `aggregate_count` | The reviewed count |
| `display_limit` | int | for capped `ids_only` | Display cap to compare within |
| `rubric` | string | if `rubric` | The scenario's own judge rubric |
| `type` | `single` / `conversational` | conventional | Declared, not enforced by the loader |
| `name`, `requirements`, `decision`, `language`, `input_variants` | — | conventional | Annotation carried through the dataset |

The loader enforces the `required` column.
The read-but-not-enforced fields must still be correct: the harness keys on `type` for conversation handling and on `sql_mode` for SQL comparison even though the validator does not check every one of them.

## Metric contract

A metric only makes sense if the scenario declares the fields it reads.

| Metric | Requires |
|---|---|
| `tool_correctness` | `expected_tools`, `tool_expectation`, or `turn_tool_expectations` |
| `sql_accuracy` | `reference_sql`, plus `sql_mode` (and `expected_count` for `aggregate_count`) |
| `grounded` | Nothing extra; reads the captured tool output |
| `on_topic` | Nothing extra |
| `memory` | Multiple turns; reads `conversation_history` |
| `rubric` | `rubric` |

## Example

```yaml
- id: HLP-LIST-1
  name: List AI Engineer jobs
  type: single
  input: Liệt kê các việc làm AI Engineer.
  language: vi
  expected: List 5 rows with labelled original source links.
  expected_tools:
    - query_clean_jobs
  reference_sql: SELECT id, title, company, location, source_url FROM clean_jobs WHERE title ILIKE '%AI Engineer%' ORDER BY id
  metrics:
    - tool_correctness
    - sql_accuracy
    - grounded
    - on_topic
    - rubric
  rubric: 'Expected behavior: List 5 rows with labelled original source links; additional obligations: [{require_source_links: true, type: structural}]'
  sql_mode: ids_only
```

## Tool expectations

The harness resolves a turn's tools in this order:

1. `turn_tool_expectations` for the turn, when present.
2. `tool_expectation` for the scenario, when present.
3. `expected_tools` otherwise.

Each expectation declares `required` tools and optionally `allowed` tools; when `allowed` is omitted it equals `required`.
For a conversational scenario that changes its tool contract between turns, declare a `turn_tool_expectations` list with one entry per turn; its length must equal the turn count.

## Step-by-step runbooks

### Add a new scenario

1. Add the scenario to [`../datasets/scenarios.yaml`](../datasets/scenarios.yaml) with the fields above.
2. Validate the grammar by loading it: `uv run python -c "from evals.datasets import dataset; dataset('default').scenarios()"`.
3. Choose the metrics the scenario declares and add their required fields.
4. Re-run the offline suite: `uv run pytest tests/evals -q`.

### Edit an existing scenario

1. Edit the scenario in [`../datasets/scenarios.yaml`](../datasets/scenarios.yaml).
2. Re-run the grammar load and the offline suite.
3. If you changed the tools, SQL contract, or rubric, re-check the affected metric.

The disconnected v1 commands (`evals.driver`, `evals.score`, `evals.grader`, `freeze`, and `replay`) no longer exist.
Run everything through `python -m evals` as shown in [pipeline.md](../pipeline.md).