# `evals/` - The Evaluation Instrument

> **Last verified:** 2026-08-14.

> **Eviction:** A description here leaves when its module is removed or its command changes.
> This file describes the layout only; findings live in the records listed at the bottom.

How agent behavior is measured. The strategy behind it is
[`research/evaluation-strategy.md`](../research/evaluation-strategy.md); the frozen target it
measures against is [`docs/Agent_Behavior_Spec.md`](../docs/Agent_Behavior_Spec.md).

## Read this first: what costs quota

Only two things call a model. Everything else runs offline against recorded evidence, which is
the point of the design - a capture is expensive and rare, and grading it is free and repeatable.

| Command | Spends |
|---|---|
| `uv run python -m evals.driver` | **Groq serving quota.** One turn reserves ~9.2K tokens against an 8000 TPM ceiling |
| `uv run python -m evals.driver --score` | Groq **and** Gemini judge quota |
| `uv run pytest -m eval` / `deepeval test run evals/test_three_seams.py` | **Gemini judge quota** |
| everything below | nothing - no network, no provider |

```powershell
docker compose up -d                          # fixture Postgres on 5433
uv run python -m evals.fixtures.loader        # build/reset the frozen fixture
uv run python -m evals.replay                 # the CI gate: replay committed evidence
uv run python -m evals.scenarios --scenario HON-CURRENCY-1
uv run python -m evals.viewer --sample        # a viewer sample with no recorded run
```

## The pipeline

```text
scenarios_v1.yaml -> driver.py -> execution_accuracy.py -> grader.py
      (registry)     (capture)        (is the SQL right?)   (verdict)
                         |                                      ^
                         v                                      |
                     viewer.py                              replay.py
                  (read the turns)                     (re-grade in CI, no model)
```

The split is deliberate. Capture spends quota once and writes evidence to disk; every later stage
reads that evidence and can be re-run for free. A change to a grading rule is therefore verified
against recorded turns, not by paying for a new capture.

## Modules

| File | Role |
|---|---|
| `scenarios_v1.yaml` | **The registry.** 29 scenarios with probe flags, requirements, reference SQL, and `expected_tools`. The single source of truth (D-041) |
| `scenarios.py` | Loads and validates the registry; generates DeepEval goldens from it; no-model CLI |
| `harness.py` | Three-seam capture and the DeepEval metrics. Owns the seam definitions so pytest and recorded runs cannot diverge |
| `driver.py` | Orchestration: runs the registry over the harness, paces turns to fit the quota window, owns retries, writes a manifest, checkpoints and resumes |
| `viewer.py` | Single-file HTML viewer - one turn per screen, all three seams, operator notes |
| `execution_accuracy.py` | Executes generated and reference SQL against the fixture and compares result sets as unordered multisets |
| `grader.py` | Deterministic three-tier grading (structural, textual, judge) with `PASS`/`FAIL`/`INFRA`/`UNRUN`. The last two are excluded from denominators |
| `holdout.py` | Six-scenario contract suite, authored without reference to recorded answers |
| `replay.py` | Validates the committed artifact, executes its SQL, grades it. What CI runs |
| `replays/` | The committed sanitized evidence the gate replays |
| `judge.py` | `DeepEvalBaseLLM` adapter with an RPM throttle. No scenario rule reaches the judge tier yet |
| `writeback.py` | Langfuse score writeback. Called by `harness.py`; not part of the deterministic path |
| `fixtures/loader.py` | Builds and resets the frozen fixture through Alembic plus `seed_eval_db.sql`. Owns `fixture_database_url()` |
| `runs/` | Capture artifacts. **Git-ignored** - turns carry latency, token usage, and finish reasons |
| `conftest.py` | Binds the two live test modules below to the fixture database, for the duration of each test |

## Where the tests are

The deterministic tests for every module above live in
[`tests/evals/`](../tests/evals) and run in the default `uv run pytest -q` suite.

Two modules stay here because they call a provider: `test_three_seams.py`, which
`deepeval test run` addresses by path, and `test_judge.py`, whose live case is `eval`-marked.
Both are deselected by default.

## Records

Findings, not guidance. Each has an owner and a cap in the
[documentation map](../docs/README.md).

| File | What it holds |
|---|---|
| [`grader_audit.md`](grader_audit.md) | The 29-rule audit and the 13 human turn labels behind the grader |
| [`v1_scenario_matrix.md`](v1_scenario_matrix.md) | The 2026-07-14 measurement, kept as dated evidence |
| [`v1_error_analysis.md`](v1_error_analysis.md) | Open-coded failure modes from those recovered answers |
| [`holdout_report.md`](holdout_report.md) | The holdout's calibration output |

## Two constraints worth knowing before you change anything

**Resolve the fixture DSN through `fixtures.loader.fixture_database_url()`, never through
`src.core.config.settings`.** `load_settings()` caches `Settings()` from the environment and
`.env`. The driver reads the fixture DSN *before* it writes `DATABASE_URL`, so resolving through
`settings` would freeze the cache against the serving database and make the bind a no-op - a
capture would silently run against production data. `tests/evals/test_driver.py` pins this.

**The free tier cannot run every scenario.** `HLP-CONTEXT-1` and `HLP-COMPOUND-1` exceed the
8000 TPM admission ceiling inside a single turn. Lowering `max_tokens` or `agent.query.max_rows`
would admit them and change what the instrument measures; see
[Known Issues](../docs/Known_Issues.md).
