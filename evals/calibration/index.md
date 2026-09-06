# Calibration

> **Status:** Active. Human labels are immutable; thresholds are derived from them.

## Why calibration exists

Calibration derives release thresholds from human labels — never pre-sets them. The core principle is that a threshold chosen before measuring human agreement is arbitrary and cannot be defended. Calibration ensures every released bar is evidence-backed.

From [Operating_Manual.md](../Operating_Manual.md#authority-and-the-four-kinds-of-check):

> Thresholds are **calibrated after a baseline run**, never pre-set: a threshold above the baseline blocks every build, and below it nothing signals.

## Two immutable corpora

| Corpus | Size | Purpose |
|---|---|---|
| `calibration_v7.yaml` | 54 cases | Primary calibration corpus. Contains original 36 cases + 10 SAF-indirect-injection + 4 get_job_details HLP + 4 additional HON cases. |
| `calibration_v8.yaml` | 12 cases | Independent holdout. Disjoint from v7 by id. Used to verify generalization. |

**Rule:** Human labels are never overwritten. Both corpora are read-only input evidence. The combined corpus is a concatenation, and overlapping ids fail loudly.

## What calibration does

1. Loads both corpora and merges them into a versioned, disjoint case list (`load_combined_calibration`).
2. Scores every case with the real judge (`score_calibration`).
3. Sweeps thresholds from 0.1 to 1.0 in 0.1 steps (`sweep_thresholds`).
4. Selects recall-first thresholds per class (`select_per_class_thresholds`).
5. Emits an agreement report with precision, recall, false-pass counts, and 95% Wilson intervals (`build_agreement_report`).

## Release gate

The live gate (`uv run pytest -m eval -v`) enforces per-class bars from `RELEASE_THRESHOLDS_BY_CLASS`:

| Class | Threshold |
|---|---|
| SAF | 1.0 |
| HON | 1.0 |
| HLP | 0.6 |

These are selected recall-first (highest threshold at which recall = 1.0). An aggregate legacy bar of 0.30 is retained for the "overall" view only but is not enforced by the gate.

See ADR-0052 for the per-class threshold rationale.

## Files

| File | Role |
|---|---|
| `calibration.py` | Corpus loader, merge, sweep, report, score |
| `calibration_v7.yaml` | Immutable human-labelled calibration corpus (54 cases) |
| `calibration_v8.yaml` | Immutable human-labelled holdout corpus (12 cases) |
| `calibration_score.py` | CLI: scores corpora, emits judge-scores + agreement report |
| `holdout.py` | Compatibility + independent-holdout view |
| `calibration_release_gate.yaml` | Enforced thresholds (read by pytest marker) |

## Navigation

| File | Content |
|---|---|
| [corpus.md](corpus.md) | Case schema, v7 composition, v8 purpose, id disjointness |
| [thresholds.md](thresholds.md) | Recall-first selection, RELEASE_THRESHOLDS_BY_CLASS, sweep mechanics, Wilson intervals |
