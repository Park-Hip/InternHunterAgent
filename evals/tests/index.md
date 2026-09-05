# Evaluation Tests

> **Source:** `tests/evals/`

## Test-to-module mapping

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

## Coverage gaps

| Gap | Status |
|---|---|
| No test for `harness.py::score_seams()` with live judge | Known — requires eval marker and judge provider |
| `test_fixture_counts.py` skipped without Postgres | Expected — fixture DB required |
| No offline test for `_RpmThrottle.wait()` timing | Low priority — timing is intrinsic to throttle behavior |
| No test for archived replay paths | Low — archived replays are read-only history |

## Offline vs live test split

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

## Running tests

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
