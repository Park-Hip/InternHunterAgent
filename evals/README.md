# `evals/` - The Evaluation Instrument

> **Last verified:** 2026-08-22.

> **Eviction:** A description here leaves when its module is removed or its command changes.
> This file describes the layout only; findings live in the records listed at the bottom.

How agent behavior is measured. The strategy behind it is
[`research/evaluation-strategy.md`](../research/evaluation-strategy.md); the frozen target it
measures against is [`docs/Agent_Behavior_Spec.md`](../docs/Agent_Behavior_Spec.md); why the
instrument is built the way it is, and what it can't yet tell you, is
[`Operating_Manual.md`](Operating_Manual.md).

## New to evaluation?

Start with this file for the module layout, exact commands, and evidence boundary.

Then read the [Operating Manual](Operating_Manual.md) for the three-seam model, verdict
interpretation, and current limits.

Read the [Agent Behavior Spec](../docs/Agent_Behavior_Spec.md) for the behavior under test, and
the [scenario registry](scenarios_v1.yaml) for the exact scenarios and deterministic rules.

Before changing or running an evaluation, read [Known Issues](../docs/Known_Issues.md), the
[Decision Log](../docs/Decision_Log.md), and the relevant record in the
[research index](../research/README.md).

Raw captures in `evals/runs/` are local and must never be committed because they can contain
telemetry, trace identifiers, and tool output.

Committed replays in `evals/replays/` are the sanitized evidence that CI can reproduce without a
model call.

Do not start a baseline capture while its instrument blockers remain open.

## Read this first: what costs quota

Only two things call a model. Everything else runs offline against recorded evidence, which is
the point of the design - a capture is expensive and rare, and grading it is free and repeatable.

| Command | Spends |
|---|---|
| `uv run python -m evals.driver` | **Serving credit.** The full 29-scenario registry is 77 turns for about $0.04 on DeepSeek (D-045) |
| `uv run python -m evals.score --run run.json` | **Gemini judge quota.** An offline pass over a recorded capture, throttled to the free tier's RPM |
| `uv run pytest -m eval` / `deepeval test run evals/test_three_seams.py` | **Gemini judge quota** |
| everything below | nothing - no network, no provider |

Capture and scoring are separate commands on purpose. Capture is minutes and cents; scoring the
same registry is hundreds of throttled judge calls and can take the better part of an hour, so it
runs over the artifact afterwards rather than holding the capture open.

```powershell
docker compose up -d                          # fixture Postgres on 5433
uv run python -m evals.fixtures.loader        # build/reset the frozen fixture
uv run python -m evals.replay                 # the CI gate: replay committed evidence
uv run python -m evals.scenarios --scenario HON-CURRENCY-1
uv run python -m evals.viewer --sample        # a viewer sample with no recorded run
```

Grade a recorded capture with execution accuracy, then view it with the deterministic verdict
joined:

```powershell
uv run python -m evals.execution_accuracy evals/runs/<run>.json --output evals/runs/<run>-execution.json
uv run python -m evals.grader --run evals/runs/<run>.json --execution-accuracy evals/runs/<run>-execution.json > evals/runs/<run>-grade.json
uv run python -m evals.viewer evals/runs/<run>.json --grade evals/runs/<run>-grade.json
uv run python -m evals.driver freeze evals/runs/<run>.json --grade evals/runs/<run>-grade.json -o evals/replays/<run>.json
```

`uv run python -m evals.score --run evals/runs/<run>.json` is an optional, separate judge pass.
It does not determine the current deterministic verdict because no scenario activates a judge rule.

`--grade` is optional; without it the viewer shows the capture and marks every turn `UNGRADED`.
With it, each turn carries its `PASS`/`FAIL`/`INFRA`/`UNRUN` verdict and tier, the grade filter in
the toolbar narrows the run to one status, and every check that did not pass is drawn beside the
seam it judges with the `detail` that says what the rule wanted. The run header names the provider,
model, and sampling per profile, so two arms are told apart on screen.

## Capture lineage

Every capture manifest records `prompt_version` from `config/prompts.yaml`, and `freeze` carries it
into the replay manifest, which is `schema_version` 2.
`prompt_hash` already proves that two runs used different prompts; the version says which prompt
each one ran, so a baseline is never read as comparable across a prompt change.
The viewer draws it in the run header beside the Git SHA.

`freeze` refuses a capture that has no `prompt_version`, and the replay validator refuses a manifest
that omits it or that still declares `schema_version` 1.
The three replays recorded before the stamp were labelled from the prompt version in the commit
each capture ran at: `v1` for `t0025.7-acceptance.json` and `t0025.9-committed.json`, `v3` for
`t0024.4-v3-obligations.json`.

## The pipeline

```text
scenarios_v1.yaml -> driver.py -> execution_accuracy.py -> grader.py
      (registry)     (capture)        (is the SQL right?)   (verdict)
                         |                    |                 |    ^
                         v                    v                 |    |
                     score.py             viewer.py <-----------+  replay.py
                 (optional judge)  (read the turns and verdict)    (CI, no model)
```

The split is deliberate. Capture spends serving credit once and writes evidence to disk; every
later stage reads that evidence and can be re-run for free. A change to a grading rule is
therefore verified against recorded turns, not by paying for a new capture.
Judging is on the same side of that line: `score.py` is an offline pass over a recorded
artifact, resumable and re-runnable, so a re-grade never costs a new capture.

## Modules

| File | Role |
|---|---|
| `scenarios_v1.yaml` | **The registry.** 29 scenarios with probe flags, requirements, reference SQL, `expected_tools`, and a `grading:` block holding what each answer must and must not say. The single source of truth (D-041) |
| `scenarios.py` | Loads and validates the registry, rejecting an unknown tool or grading field; generates DeepEval goldens from it; no-model CLI |
| `harness.py` | Three-seam capture and the DeepEval metrics. Owns the seam definitions so pytest and recorded runs cannot diverge |
| `driver.py` | Orchestration: runs the registry over the harness, owns retries and the backoff ladder, writes a manifest, checkpoints and resumes, and freezes completed evidence into a sanitized replay. Turn pacing survives for the Groq branch and is 0 on the serving default |
| `viewer.py` | Single-file HTML viewer - one turn per screen, all three seams, the joined grade verdict, run header, telemetry, and operator notes |
| `execution_accuracy.py` | Executes generated and reference SQL against the fixture and compares result sets as unordered multisets |
| `grader.py` | Deterministic three-tier grading (structural, textual, judge) with `PASS`/`FAIL`/`INFRA`/`UNRUN`. The last two are excluded from denominators. Owns how a rule is applied, never what a scenario expects |
| `holdout.py` | Six-scenario contract suite, authored against the behavior spec rather than from the registry or the recorded answers |
| `replay.py` | Validates the committed artifact, executes its SQL, grades it, and checks expected PASS, FAIL, or EXEMPT execution outcomes. What CI runs |
| `replays/` | The committed sanitized evidence the gate replays. It retains questions, answers, tools, SQL, expected outcomes, and the `prompt_version` its capture ran, never telemetry or trace identifiers |
| `judge.py` | `DeepEvalBaseLLM` adapter with an RPM throttle. No scenario rule reaches the judge tier yet |
| `score.py` | The offline judge pass over a recorded capture. Resumable, re-runnable, and the only caller of the writeback |
| `writeback.py` | Langfuse score writeback and the ingestion probe. Called by `score.py` and `driver.py`; not part of the deterministic path |
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

**Two scenarios do not fit a per-minute token ceiling.** `HLP-CONTEXT-1` and `HLP-COMPOUND-1`
exceed an 8000 TPM admission ceiling inside a single turn, so they cannot be captured on the Groq
free-tier branch. This is a property of that branch, not of the instrument: D-045 moved serving to
DeepSeek, which publishes no TPM or TPD limit, and the full 29-scenario registry captured 77 of 77
turns there. Lowering `max_tokens` or `agent.query.max_rows` would admit them on Groq and change
what the instrument measures; see [Known Issues](../docs/Known_Issues.md).
