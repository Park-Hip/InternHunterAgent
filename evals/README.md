# `evals/` - The Evaluation Instrument

> **Last verified:** 2026-10-01.

> **Eviction:** This hub leaves when the evaluation layout, commands, metric contract, or result terms change.

This directory measures the agent against the frozen fixture and the behavior contract.
The rebuilt harness (#476) has one CLI, `python -m evals`, and two declarative datasets.
[`docs/how-to/evaluate.md`](../docs/how-to/evaluate.md) is the canonical step-by-step for running it.
This hub is the navigation map and the full command and module reference.

## Role routing

| Role | Start here | Then read |
|---|---|---|
| **Operator** | [`docs/how-to/evaluate.md`](../docs/how-to/evaluate.md) | [pipeline.md](pipeline.md) |
| **Contributor** | [authoring/index.md](authoring/index.md) | [pipeline.md](pipeline.md) |
| **Maintainer** | [`docs/how-to/evaluate.md`](../docs/how-to/evaluate.md) | [`archive/`](archive/) for historical baselines and calibration evidence |

## Quick commands

```sh
# Start the fixture database and load the frozen dataset
docker compose up -d postgres
uv run python -m evals.fixtures.loader

# Credential-free v0 acceptance gate (the CI gate)
uv run python -m evals --deterministic --dataset v0

# Live capture + scoring of the v1 scenarios (needs the serving-model credential)
uv run python -m evals --dataset default --out evals/runs/local-report.json

# Offline scoring of a retained capture (no model call)
uv run python -m evals --only tool_correctness,sql_accuracy \
  --capture evals/replays/t0025.9-committed.json \
  --ids SAF-DESTRUCTIVE-REFUSAL-1,HLP-CONTEXT-1
```

Use `--out` to write the JSON report elsewhere.
The default output lands in the gitignored `evals/runs/` directory.

## Datasets

| Dataset | File | What it describes | How it runs |
|---|---|---|---|
| `default` | [`datasets/scenarios.yaml`](datasets/scenarios.yaml) | 50 v1 scenarios (34 single-turn, 16 conversational) | A live capture against the serving agent, or a retained capture |
| `v0` | [`datasets/v0_acceptance.yaml`](datasets/v0_acceptance.yaml) | 19 governed v0 acceptance cases (16 with a request, 3 absent-capability cases with no request) | The credential-free gate, which calls the query core directly |

The registry and its validation live in [`datasets.py`](datasets.py).
The two datasets never mix: a new version is a new entry, never an edit to an existing registry.

## Metrics

Metrics are declared in [`metrics.py`](metrics.py) and selected per scenario by its `metrics` list.

| Metric | Kind | Credential-free | Scores |
|---|---|---|---|
| `tool_correctness` | deterministic | yes | Required tools were called, with no unexpected tools |
| `sql_accuracy` | deterministic | yes | Generated SQL returns the reference result on the fixture |
| `grounded` | judge | no | Answer is supported by the retrieved tool output |
| `on_topic` | judge | no | Answer responds to the question and its constraints |
| `memory` | judge | no | Answer uses the previous conversation turns and their constraints |
| `rubric` | judge | no | Answer satisfies the scenario's own rubric |
| `plan_correctness` | deterministic | yes | The v0 core applied the reviewed filters |
| `result_equivalence` | deterministic | yes | The v0 result matches the reviewed golden |

The v0 dataset may not declare `sql_accuracy` or `memory`: those two are retired for the governed path and remain only for the v1 replays (#487).

## Test-to-module mapping

Tests live in [`tests/evals/`](../tests/evals/).

| Test file | Production module | Behavior pinned |
|---|---|---|
| `test_datasets.py` | [`datasets.py`](datasets.py) | Registry selection and scenario-grammar validation |
| `test_env.py` | [`env.py`](env.py) | Fixture environment binding before any `src` import |
| `test_judge.py` | [`judge.py`](judge.py) | Config-to-model wiring, provider arm selection |
| `test_metrics.py` | [`metrics.py`](metrics.py) | Metric construction, tool expectations, field adaptation |
| `test_report.py` | [`report.py`](report.py) | Result grouping and table rendering |
| `test_run.py` | [`run.py`](run.py) | Capture and scoring with the database boundary stubbed |
| `test_sql_check.py` | [`sql_check.py`](sql_check.py) | SQL comparison modes with query results stubbed |
| `test_v0_acceptance.py` | [`datasets/v0_acceptance.yaml`](datasets/v0_acceptance.yaml) | Dataset structure and goldens recomputed against the fixture |
| `test_v0_gate.py` | [`v0_gate.py`](v0_gate.py) | Gate refusals: wrong plan, wrong golden, missing label, unavailable database |
| `test_holdout_judge.py` | [`judge.py`](judge.py) + [`calibration_v8.yaml`](calibration_v8.yaml) | Opt-in judge-versus-human check over the retained v8 holdout |

## The map

```
evals/
├── README.md                     This navigation hub
├── __main__.py                   CLI entry: python -m evals
├── datasets.py                   Dataset registry and scenario-grammar validation
├── run.py                        Capture and scoring pipeline
├── metrics.py                    Declared metrics and their required capture fields
├── judge.py                      Shared DeepEval judge (provider arms)
├── sql_check.py                  Generated-SQL vs reference-result comparison
├── report.py                     Result grouping and table rendering
├── v0_gate.py                    Credential-free v0 acceptance gate
├── env.py                        Fixture database binding before any src import
├── _paths.py                     Shared path constants
│
├── datasets/
│   ├── scenarios.yaml            The v1 scenario registry (50 scenarios)
│   └── v0_acceptance.yaml        The governed v0 acceptance dataset (19 cases)
│
├── fixtures/
│   ├── loader.py                 Fixture database build/reset
│   └── seed_eval_db.sql          The frozen 24-row fixture dataset
│
├── authoring/                    How to author and edit scenarios
│   └── index.md                  Grammar, metric contract, step-by-step runbooks
│
├── calibration_v7.yaml           Immutable human-labelled corpus (retained evidence)
├── calibration_v8.yaml           Immutable independent holdout (retained evidence)
│
├── pipeline.md                   Pipeline, metric contract, and commands reference
│
├── runs/                         Raw reports - local, gitignored
├── replays/                      Committed sanitized replays - retained evidence
│
└── archive/                      Historical v1 records (readable history, not fixtures)
    ├── replays/                  Archived replays
    ├── deterministic/            Deleted-grader deep dive
    ├── semantic/                 Deleted semantic-scorer docs
    ├── calibration/              Deleted calibration-sweep docs
    ├── replay/                   Deleted replay docs
    ├── disagreements/            Deleted disagreement workflow
    ├── Operating_Manual.md       v1 maintainer manual
    ├── Instrument_Report.md      v1 baseline reports
    ├── IMPLEMENTATION_PLAN.md    v1 pass-rate plan
    ├── t0027_deepseek_arm.md     Provider bake-off record
    ├── V6_Grader_Audit_2026-08-23.md Grader audit record
    ├── v1_error_analysis.md
    ├── v1_scenario_matrix.md
    └── calibration_v6.yaml
```

## Multi-turn coverage

The v1 registry reserves `memory` for conversational scenarios: all 16 `type: conversational` scenarios declare it, and no single-turn scenario does.
A conversational scenario declares its turns as a list under `turns`; a single-turn scenario declares one `input`.
The capture records every turn in order, and `memory` judges the final answer against the accumulated conversation.
See [authoring/index.md](authoring/index.md) for the exact grammar.

## Historical records

The manuals that described the deleted v1 modules (`grader.py`, `driver.py`, `score.py`, `replay.py`, `execution_accuracy.py`, `scenarios_v1.yaml`, and their friends) are preserved in [`archive/`](archive/).
They are readable history, not current operating instructions.
Read [`docs/how-to/evaluate.md`](../docs/how-to/evaluate.md) for how evaluation works today.

Committed replays under [`replays/`](replays/) are sanitized evidence of earlier behavior.
Raw reports under [`runs/`](runs/) are local and gitignored because they can contain telemetry and trace identifiers.