# `evals/` - The Evaluation Instrument

> **Last verified:** 2026-08-17.

> **Eviction:** A description here leaves when its module is removed or its command changes.
> This file describes the layout only; findings live in the records listed at the bottom.

How agent behavior is measured. The strategy behind it is
[`research/evaluation-strategy.md`](../research/evaluation-strategy.md); the frozen target it
measures against is [`docs/Agent_Behavior_Spec.md`](../docs/Agent_Behavior_Spec.md); why the
instrument is built the way it is, and what it can't yet tell you, is
[`Operating_Manual.md`](Operating_Manual.md).

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

Reading a recorded capture takes two commands - grade it, then view it with the verdict joined:

```powershell
uv run python -m evals.grader --run evals/runs/<run>.json > evals/runs/<run>-grade.json
uv run python -m evals.viewer evals/runs/<run>.json --grade evals/runs/<run>-grade.json
uv run python -m evals.driver freeze evals/runs/<run>.json --grade evals/runs/<run>-grade.json -o evals/replays/<run>.json
```

`--grade` is optional; without it the viewer shows the capture and marks every turn `UNGRADED`.
With it, each turn carries its `PASS`/`FAIL`/`INFRA`/`UNRUN` verdict and tier, the grade filter in
the toolbar narrows the run to one status, and every check that did not pass is drawn beside the
seam it judges with the `detail` that says what the rule wanted. The run header names the provider,
model, and sampling per profile, so two arms are told apart on screen.

## The pipeline

```text
scenarios_v1.yaml -> driver.py -> execution_accuracy.py -> grader.py
      (registry)     (capture)        (is the SQL right?)   (verdict)
                         |                                    |    ^
                         v                                    |    |
                     viewer.py <----- grade report -----------+  replay.py
           (read the turns and their verdict)          (re-grade in CI, no model)
```

The split is deliberate. Capture spends quota once and writes evidence to disk; every later stage
reads that evidence and can be re-run for free. A change to a grading rule is therefore verified
against recorded turns, not by paying for a new capture.

## Modules

| File | Role |
|---|---|
| `scenarios_v1.yaml` | **The registry.** 29 scenarios with probe flags, requirements, reference SQL, `expected_tools`, and a `grading:` block holding what each answer must and must not say. The single source of truth (D-041) |
| `scenarios.py` | Loads and validates the registry, rejecting an unknown tool or grading field; generates DeepEval goldens from it; no-model CLI |
| `harness.py` | Three-seam capture and the DeepEval metrics. Owns the seam definitions so pytest and recorded runs cannot diverge |
| `driver.py` | Orchestration: runs the registry over the harness, paces turns to fit the quota window, owns retries, writes a manifest, checkpoints and resumes, and freezes completed evidence into a sanitized replay |
| `viewer.py` | Single-file HTML viewer - one turn per screen, all three seams, the joined grade verdict, run header, telemetry, and operator notes |
| `execution_accuracy.py` | Executes generated and reference SQL against the fixture and compares result sets as unordered multisets |
| `grader.py` | Deterministic three-tier grading (structural, textual, judge) with `PASS`/`FAIL`/`INFRA`/`UNRUN`. The last two are excluded from denominators. Owns how a rule is applied, never what a scenario expects |
| `holdout.py` | Six-scenario contract suite, authored against the behavior spec rather than from the registry or the recorded answers |
| `replay.py` | Validates the committed artifact, executes its SQL, grades it, and checks expected PASS, FAIL, or EXEMPT execution outcomes. What CI runs |
| `replays/` | The committed sanitized evidence the gate replays. It retains questions, answers, tools, SQL, and expected outcomes, never telemetry or trace identifiers |
| `judge.py` | `DeepEvalBaseLLM` adapter with an RPM throttle. No scenario rule reaches the judge tier yet |
| `writeback.py` | Langfuse score writeback. Called by `harness.py`; not part of the deterministic path |
| `fixtures/loader.py` | Builds and resets the frozen fixture through Alembic plus `seed_eval_db.sql`. Owns `fixture_database_url()` |
| `runs/` | Capture artifacts. **Git-ignored** - turns carry latency, token usage, and finish reasons |
| `conftest.py` | Binds the two live test modules below to the fixture database, for the duration of each test |

## Changing what a scenario expects

Edit that scenario's `grading:` block in the registry, not `grader.py`.

```yaml
  grading:
    expected_answer_count: 5          # the answer must state this number
    required_any:                     # every group must match; a group is an OR
      - ["recorded", "created_on"]
    forbidden_any: ["posted on"]      # plain substrings, case-insensitive
    forbidden_patterns: ["\\bselect\\b.+\\bfrom\\b"]
```

A term may be `{"glossary": "NAME"}` instead of a literal, which resolves to the canonical
phrasing in `config/prompts.yaml`. Reference the glossary rather than pasting its sentence, so the
prompt and the rule cannot drift apart. The loader rejects an unknown field, an empty required
group, and a pattern that does not compile.

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
| [`Instrument_Report.md`](Instrument_Report.md) | The 29-rule grader audit, the 13 human turn labels, and the six-case holdout calibration |
| [`archive/v1_scenario_matrix.md`](archive/v1_scenario_matrix.md) | The 2026-07-14 measurement, sealed as dated evidence |
| [`archive/v1_error_analysis.md`](archive/v1_error_analysis.md) | Open-coded failure modes from those recovered answers, sealed |

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
