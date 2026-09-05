# `evals/` — The Evaluation Instrument

> **Last verified:** 2026-09-04.

> **Eviction:** This hub leaves when the evaluation layout, commands, evidence contract, or result terms change.

This directory measures the agent against the frozen fixture and the behavior contract.
Start with the role routing below, or jump to the [map](#the-map) to find a specific file.

## Role routing

| Role | Start here | Then read |
|---|---|---|
| **Operator** — runs baselines, scores, freezes replays | [pipeline.md](pipeline.md) | [Operating_Manual.md](Operating_Manual.md) |
| **Maintainer** — reviews results, authorizes thresholds | [Operating_Manual.md](Operating_Manual.md) | [calibration/thresholds.md](calibration/thresholds.md), [disagreements/](disagreements/) |
| **Contributor** — adds or edits scenarios | [authoring/](authoring/) | [pipeline.md](pipeline.md), [scenarios_v1.yaml](scenarios_v1.yaml) |
| **Auditor** — checks grading correctness, traceability | [deterministic/](deterministic/) | [semantic/](semantic/), [tests/](../tests/evals/) |

## Decision tree

```
I need to...
├── Run a baseline capture
│   └── pipeline.md → "Quick commands"
├── Understand how grading works (no model calls)
│   └── deterministic/index.md
├── Understand the semantic judge tier
│   └── semantic/index.md
├── Add or edit a scenario
│   └── authoring/index.md
├── Calibrate thresholds / score the corpus
│   └── calibration/index.md
├── Replay committed evidence / fix a replay
│   └── replay/index.md
├── Resolve a grader-vs-judge-vs-human disagreement
│   └── disagreements/index.md
├── Find which test pins which behavior
│   └── [tests/evals/](../tests/evals/) — see mapping below
├── Review a result as maintainer
│   └── Operating_Manual.md
├── See the current baseline and open cases
│   └── Instrument_Report.md
└── Learn the vocabulary (PASS/FAIL/INFRA/…)
    └── pipeline.md → "Result-term table"
```

## Quick commands (compact)

```powershell
# Fixture + deterministic suite
docker compose up -d
uv run python -m evals.fixtures.loader
uv run pytest -q tests/evals

# Capture (only serving-model call)
uv run python -m evals.driver --output evals/runs/<run>.json

# Score (semantic judge, after capture)
uv run python -m evals.score --run evals/runs/<run>.json

# Grade (no new model call; consumes persisted semantic scores)
uv run python -m evals.execution_accuracy evals/runs/<run>.json --output evals/runs/<run>-execution.json
uv run python -m evals.grader --run evals/runs/<run>.json --execution-accuracy evals/runs/<run>-execution.json --output evals/runs/<run>-grade.json

# Freeze + replay (CI gate)
uv run python -m evals.driver freeze evals/runs/<run>.json --grade evals/runs/<run>-grade.json -o evals/replays/<run>.json
uv run python -m evals.replay --all

# Calibration scoring
uv run python -m evals.calibration_score --corpus v7 --corpus v8 --out evals/runs/iha-v8-judge-combined-judge-scores.json
uv run python -m evals.calibration_score --agreement-of evals/runs/iha-v8-judge-combined-judge-scores.json --out evals/runs/iha-v8-judge-combined-agreement-report.json
```

`grader --output` writes UTF-8 JSON directly — use it instead of PowerShell `>` redirection, which can write UTF-16 and make the freeze step unreadable.

## Test-to-module mapping

Tests live in [`tests/evals/`](../tests/evals/); this table is kept here so the
auditor's decision tree does not require leaving `evals/` to find it.

| Test file | Production module | Behavior pinned |
|---|---|---|
| `test_grader.py` (~1480 lines) | `evals/grader.py` | Every check function, glossary resolution, edge cases, outcome assembly |
| `test_execution_accuracy.py` (~540 lines) | `evals/execution_accuracy.py` | All 7 SQL comparison modes, projection validation, fixture database execution |
| `test_scenarios.py` (~1770 lines) | `evals/scenarios.py` | Registry validation, id pattern, assertion field grammar, tool expectation validation |
| `test_semantic.py` (~1180 lines) | `evals/semantic.py` | `evaluate_semantic_repeat`, criteria assembly, exemplar selection, JUDGE-1..JUDGE-6 annotations |
| `test_judge.py` | `evals/judge.py` | Config-to-model wiring (no-network), provider arm selection, throttle config |
| `test_driver.py` (~41954 lines) | `evals/driver.py` | Manifest building, capture orchestration, freeze pipeline, retry logic, sanitization |
| `test_replay.py` (~10863 lines) | `evals/replay.py` | Schema validation, forbidden content rejection, outcome assertion, active replay discovery |
| `test_flywheel.py` (~13643 lines) | `evals/flywheel.py` | Calibration feedback loop, threshold updates, report generation |
| `test_calibration.py` (~14413 lines) | `evals/calibration.py` | Corpus loading, merge, sweep, selection, Wilson intervals, agreement report |
| `test_score.py` (~14461 lines) | `evals/score.py` | Scoring pipeline, rescore logic, Langfuse writeback, availability tracking |
| `test_viewer.py` (~23247 lines) | `evals/viewer.py` | HTML report generation, evidence rendering, comparison views |
| `test_writeback.py` (~9935 lines) | `evals/writeback.py` | Score posting, ingestion verification, trace linking |
| `test_holdout.py` (~1314 lines) | `evals/holdout.py` | Independent holdout view, compatibility checks |
| `test_caveats.py` (~6636 lines) | — | Edge-case regression guards across modules |
| `test_fixture_counts.py` (~3209 lines) | `evals/fixtures/loader.py` | Row counts, schema matches, role distribution (requires Postgres) |

### Coverage gaps

| Gap | Status |
|---|---|
| No test for `harness.py::score_seams()` with live judge | Known — requires eval marker and judge provider |
| `test_fixture_counts.py` skipped without Postgres | Expected — fixture DB required |
| No offline test for `_RpmThrottle.wait()` timing | Low priority — timing is intrinsic to throttle behavior |
| No test for archived replay paths | Low — archived replays are read-only history |

### Offline vs live test split

Tests run in the plain suite (no marker):
- `test_grader.py` — pure function tests, no provider needed
- `test_execution_accuracy.py` — SQL comparison, no provider needed
- `test_scenarios.py` — registry validation, no provider needed
- `test_semantic.py` — mock-based, no provider needed
- `test_judge.py` — no-network config tests
- `test_replay.py` — schema validation, no provider needed
- `test_writeback.py` — mock-based
- `test_caveats.py` — edge cases

Tests requiring `eval` marker (live judge/provider):
- `test_score.py` — calls real judge
- `test_driver.py` — runs capture loop
- `test_flywheel.py` — full calibration feedback
- `test_viewer.py` — HTML generation (some offline)
- `test_calibration.py` — scoring combined corpus
- `test_holdout.py` — holdout view
- `test_fixture_counts.py` — requires Postgres

### Running tests

```powershell
# Full suite (skips live tests without provider)
uv run pytest tests/evals -q

# Only deterministic tests (no provider needed)
uv run pytest tests/evals -m "not eval" -q

# Only live tests
uv run pytest tests/evals -m eval -q

# Specific module
uv run pytest tests/evals/test_grader.py -q
```

## The map

```
evals/
├── README.md                     ← this navigation hub
├── Operating_Manual.md           Maintainer review rules, authority boundary, outcome interpretation
├── Instrument_Report.md          Dated baseline, calibration, disagreements, unresolved cases
├── pipeline.md                   Five-step pipeline, result-term table, quick commands
├── scenarios_v1.yaml             Single source of truth: registry-owned cases, assertions, SQL, tools
│
├── semantic/                     Semantic judge tier and calibrated grading
│   ├── index.md                  What the tier is for; authority; D-042 relationship
│   ├── judge.md                  DeepEval judge wrapper, provider arms, throttle, config
│   ├── rubric.md                 SAF/HON/HLP rubrics, failure modes, anti-directives
│   ├── exemplars.md              PASS/FAIL exemplar selection per scenario
│   └── not-evaluated.md          Two NOT_EVALUATED senses and the invariant
│
├── calibration/                  Human-label corpus + threshold derivation
│   ├── index.md                  Why calibration exists; two immutable corpora
│   ├── corpus.md                 Case schema; v7 (44) + v8 (12) composition; id disjointness
│   └── thresholds.md             Recall-first rule; RELEASE_THRESHOLDS_BY_CLASS; Wilson intervals
│
├── replay/                       Frozen, sanitized evidence for CI
│   └── index.md                  Freeze→sanitize→replay contract; schema; CI gate
│
├── authoring/                    How to author and edit scenarios
│   └── index.md                  Grammar, id pattern, assertions, execution comparisons
│
├── disagreements/                Grader-vs-judge-vs-human workflow
│   └── index.md                  Decision tree; live register pointer
│
├── deterministic/                Deterministic grading deep dive (converted from HTML)
│   └── index.md                  Five steps, all checks, coverage map, known weaknesses
│
├── archive/                      Historical preserved evidence (readable history, not fixtures)
│   ├── replays/                  Archived replays (see replay/index.md)
│   ├── v1_error_analysis.md      Legacy v1 audit notes
│   ├── v1_scenario_matrix.md     Legacy v1 scenario matrix
│   └── calibration_v6.yaml       Superseded by v7/v8; no code references it
│
├── calibration_v7.yaml           Immutable human-labelled corpus (44 cases)
├── calibration_v8.yaml           Immutable independent holdout (12 cases)
├── calibration_release_gate.yaml Enforced per-class thresholds
│
├── *.py                          Implementation modules (driver, grader, score, replay, …)
│
├── runs/                         Raw captures — local, gitignored
├── replays/                      Committed sanitized replays — CI reproduces these
```

## Start-here context (kept from the pre-hub README)

The registry in [`scenarios_v1.yaml`](scenarios_v1.yaml) is the single source of truth for the evaluation scenarios.
The frozen target is [`docs/reference/agent-behavior.md`](../docs/reference/agent-behavior.md).
Open evaluation issues are tracked on GitHub; see [CONTRIBUTING.md](../CONTRIBUTING.md) for the change workflow.

The named runtime environment must contain the normal application configuration, including `DATABASE_URL` and
`AGENT_DATABASE_URL`; runtime settings fail closed without them. The values may point at the local
`docker compose` database because the driver replaces both database URLs with the fixture DSN before it
imports the agent, so a capture does not query a serving database.
The evaluator also needs the serving-provider credentials for capture and the judge-provider credentials for semantic scoring.

Raw captures under `evals/runs/` are local and ignored by Git because they can contain telemetry, trace identifiers, and tool output.
Committed replays under `evals/replays/` are sanitized evidence that CI can reproduce without a serving model or judge call.
The replay gate discovers and validates **every** artifact in `evals/replays/`, so a stale or newly added file fails loudly instead of being silently skipped.

Historical replays cited as durable evidence but no longer valid against the current registry are preserved byte-for-byte with their provenance in [`archive/replays/`](archive/replays/README.md).
They are readable history, not active regression fixtures.

### Recent change: Seam 2 literal-pattern removal (2026-09-04)

The Seam 2 (Literal) audit identified 4 scenarios where literal patterns systematically produced wrong grades. These literal checks have been removed, letting the semantic judge handle the behavioral contracts instead:

| Scenario | Problem |
|---|---|
| `HON-NEGOTIABLE-SALARY-1` | All 6 forbidden patterns missed Vietnamese refusals like "Trong dữ liệu không có thông tin về mức lương…" — systemic false pass |
| `HON-FREE-TEXT-1` | All 3 required hedge patterns missed natural Vietnamese hedging like "chưa chắc là danh sách đầy đủ hay chính xác" — systemic false fail |
| `HON-CURRENCY-1` | Salary-period patterns triggered on non-salary context ("maximum salary of …") — false positive |
| `HLP-ROLE-FALLBACK-1` | "khác" in "một cách khác" (a different way) falsely triggered the fallback pattern — false positive |

After this change, these scenarios rely solely on their structural and semantic assertions. Answers that previously failed or passed on literal patterns are evaluated by the semantic tier when a persisted numeric judge score is available; otherwise their semantic check is `NOT_EVALUATED`.
