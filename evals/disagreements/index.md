# Disagreements

> **Source:** Calibration agreement reports, [Operating_Manual.md](../Operating_Manual.md#disagreement-workflow)

## Grader-vs-judge-vs-human workflow

Disagreements occur when the deterministic grader, semantic judge, and human label diverge. The workflow is a decision tree:

```
Disagreement detected
├── Is it a structural check failure?
│   └── YES → Agent behavior failure (route as product work)
│   └── NO → Continue
├── Is the disputed assertion applicable?
│   └── NO → Check-level NOT_EVALUATED (document and move on)
│   └── YES → Continue
├── Is the human label PASS and judge score below threshold?
│   └── YES → Judge disagreement (add to calibration corpus)
│   └── NO → Continue
├── Is the deterministic grade FAIL but human says PASS?
│   └── YES → Grader defect (fix pattern/rule)
│   └── NO → Continue
└── Is it infrastructure?
    └── YES → INFRA (repair or rerun)
```

## Decision rules

1. **Read the scenario contract and complete turn trajectory** in the viewer before classifying.
2. **Check structural evidence first** — tool calls, execution rows. Structural results override everything.
3. **Compare human judgement with semantic score and rationale** when the judge result is `AVAILABLE`.
4. **Label the disagreement** as one of:
   - Agent behavior failure
   - Deterministic grader defect
   - Semantic judge disagreement
   - Infrastructure
5. **Add an independently written labelled case** to `calibration_v8.yaml` when the disagreement tests semantic behavior.
6. **Record why the label won** and rerun only the appropriate offline stage.

## Hard rules

- A judge score must never silently replace a human label.
- A failed structural check must never be waived by a favorable semantic score.
- An unavailable judge result is rerunnable evidence, not a pass or a failure.

## Live register

The current register of unresolved disagreements is maintained in the [Instrument_Report.md](../Instrument_Report.md). As of the last update, there are **eight unresolved false passes** — cases where the deterministic grader reported PASS but human review determined the answer should have failed.

These false passes are primarily in the semantic tier, where the judge has not yet been authorized as a release gate. Each unresolved case has a written disposition explaining why the human label won.

## Resolving a disagreement

```powershell
# 1. Open the viewer for the specific scenario
uv run python -m evals.viewer evals/runs/<run>.json --grade evals/runs/<run>-grade.json

# 2. Add a new labelled case to v8 holdout
# Edit evals/calibration_v8.yaml with a unique id and source

# 3. Re-score to incorporate the new case
uv run python -m evals.calibration_score --corpus v7 --corpus v8 --out evals/runs/updated-judge-scores.json
uv run python -m evals.calibration_score --agreement-of evals/runs/updated-judge-scores.json --out evals/runs/updated-agreement-report.json

# 4. Update the instrument report with the disposition
```

## Categories of false passes (from grading research)

| Category | Count | Example |
|---|---|---|
| Judge accepted structurally-violating answers | 8 | Answers that claimed performed mutations or fabricated results |
| Literal pattern misses (Vietnamese paraphrases) | 3 | HON-FREE-TEXT-1, HON-NEGOTIABLE-SALARY-1, HLP-SENIOR-TITLE-1 |
| Semantic-only scenarios reported as PASS | 0 (fixed in P0) | Semantic-only scenarios without an available numeric score report `NOT_EVALUATED` |

The P0 fix (commit 12be049) closed semantic-only PASS inflation when no judge score is available. An available score is now evaluated by the grader against its calibrated class threshold. The remaining false passes are in the judge tier and are being addressed through calibration (P1) and judge prompt hardening (P3).
