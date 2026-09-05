# Evaluation Pipeline

> **Source:** `evals/driver.py`, `evals/grader.py`, `evals/execution_accuracy.py`, `evals/score.py`, `evals/replay.py`

## Five-step pipeline

```text
registry → capture → execution accuracy → deterministic grade → freeze → replay
                  \→ semantic score ---------------------------> human review
```

| Step | Input | Output | Authority |
|---|---|---|---|
| 1. Capture | Scenario registry + frozen fixture | Raw JSON artifact (`evals/runs/*.json`) | Only model call in entire pipeline |
| 2. Execution accuracy | Raw capture + fixture DB | SQL comparison report | Deterministic, no provider |
| 3. Deterministic grade | Raw capture + execution accuracy | Grade report (PASS/FAIL/INFRA/NOT_EVALUATED) | Deterministic, no provider |
| 4. Freeze | Capture + grade | Sanitized replay (`evals/replays/*.json`) | Provenance-locked, no provider |
| 5. Replay | Replay artifact | Verification report | CI gate, no provider |
| 6. Semantic score | Raw capture | Judge scores + rationale | Separate pass, uses judge provider |

## Step details

### Step 1: Capture

**Command:**
```powershell
uv run python -m evals.driver --output evals/runs/<run>.json
```

**Input:** `evals/scenarios_v1.yaml` + frozen 24-row fixture database
**Output:** Raw JSON with manifest, scenario records, repeat turns, seam evidence
**Authority:** Runs the actual product agent (not a test double) against the fixture
**Invariant:** Capture is the only serving-model call in the entire pipeline

Key manifest fields:
- `baseline_eligible: true` (requires clean worktree)
- `prompt_versions` (named surfaces with hashes)
- `fixture_hash`, `scenario_registry_hash` (comparability keys)
- `providers`, `models`, `sampling` (lineage)

### Step 2: Execution accuracy

**Command:**
```powershell
uv run python -m evals.execution_accuracy evals/runs/<run>.json --output evals/runs/<run>-execution.json
```

**Input:** Raw capture artifact
**Output:** Execution accuracy report per turn
**Authority:** Deterministic — executes generated SQL and reference SQL against fixture, compares using scenario-declared contract
**Modes:** exact, contains_reference, ids_only, limited_ids, aggregate_count, zero_results, cross_currency

### Step 3: Deterministic grade

**Command:**
```powershell
uv run python -m evals.grader --run evals/runs/<run>.json --execution-accuracy evals/runs/<run>-execution.json --output evals/runs/<run>-grade.json
```

**Input:** Raw capture + execution accuracy report
**Output:** Grade report with per-turn checks and outcomes
**Authority:** Purely mechanical — structural checks win over literal wins over semantic
**Outputs:** PASS, FAIL, INFRA, NOT_EVALUATED per turn; first_failing_seam

### Step 4: Freeze

**Command:**
```powershell
uv run python -m evals.driver freeze evals/runs/<run>.json --grade evals/runs/<run>-grade.json -o evals/replays/<run>.json
```

**Input:** Raw capture + grade report
**Output:** Sanitized replay artifact
**Authority:** Strips all trace identifiers, validates forbidden content, enforces replay schema
**Invariant:** Commits only the replay, not the raw capture

### Step 5: Replay (CI gate)

**Command:**
```powershell
uv run python -m evals.replay --all
```

**Input:** Every artifact in `evals/replays/`
**Output:** Verification report (or failure)
**Authority:** Discovers and validates every artifact — stale or newly added files fail loudly
**Invariant:** No model call, no judge call

### Step 6: Semantic score

**Command:**
```powershell
uv run python -m evals.score --run evals/runs/<run>.json
```

**Input:** Raw capture artifact
**Output:** Judge scores written into capture + Langfuse writeback
**Authority:** Separate pass over recorded evidence; resumable and re-runnable
**Cost:** ~120 judge calls, ~40 minutes at 10 RPM throttle

## Result-term table

| Term | Meaning | Enters pass-rate denominator? |
|---|---|---|
| `PASS` | All evaluated deterministic checks passed | Yes |
| `FAIL` | A check under the agent's control failed | Yes (as failure) |
| `INFRA` | Required evidence missing due to external failure | No |
| `UNRUN` | Turn or scenario was never attempted | No |
| `NOT_EVALUATED` | Check inapplicable to evidence, or behavioral contract deferred to semantic judge | No |
| `EXEMPT` | Execution accuracy intentionally absent (no SQL contract) | Yes (as pass) |
| `AVAILABLE` | Semantic judge returned a score | Diagnostic only |
| `UNAVAILABLE` | Semantic judge did not produce a usable result | Diagnostic only |

## Key invariants

1. **Capture is the only serving-model call.** Everything after capture is purely mechanical.
2. **Structural checks win over literal wins over semantic.** A failed structural check overrides all lower-tier results.
3. **NOT_EVALUATED never becomes INFRA or PASS.** A scenario whose decisive behavior is semantic-only stays NOT_EVALUATED.
4. **Human labels are immutable.** Calibration scores never overwrite human annotations.
5. **Replay is provider-free.** CI validates committed replays without any model or judge credentials.
6. **Semantic scoring is a later pass.** It runs over recorded evidence, never inside the capture loop.

## Commands quick reference

```powershell
# Full baseline workflow
docker compose up -d
uv run python -m evals.fixtures.loader
uv run pytest -q tests/evals

# Capture
uv run python -m evals.driver --output evals/runs/<run>.json

# Grade
uv run python -m evals.execution_accuracy evals/runs/<run>.json --output evals/runs/<run>-execution.json
uv run python -m evals.grader --run evals/runs/<run>.json --execution-accuracy evals/runs/<run>-execution.json --output evals/runs/<run>-grade.json

# Score (semantic, after capture)
uv run python -m evals.score --run evals/runs/<run>.json

# Freeze and replay
uv run python -m evals.driver freeze evals/runs/<run>.json --grade evals/runs/<run>-grade.json -o evals/replays/<run>.json
uv run python -m evals.replay --all

# Calibration scoring
uv run python -m evals.calibration_score --corpus v7 --corpus v8 --out evals/runs/iha-v8-judge-combined-judge-scores.json
uv run python -m evals.calibration_score --agreement-of evals/runs/iha-v8-judge-combined-judge-scores.json --out evals/runs/iha-v8-judge-combined-agreement-report.json
```
