"""Compatibility view over the versioned Vietnamese calibration corpus."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evals.calibration import calibration_report, load_calibration
from evals.grader import Evidence

# The independent semantic holdout: 12 cases authored with
# ``source: independently_authored_holdout`` against the six v7 disagreements
# (ADR-0051). It is never used to re-derive a human label.
SEMANTIC_HOLDOUT_PATH = Path(__file__).with_name("calibration_v8.yaml")


@dataclass(frozen=True)
class HoldoutCase:
    scenario_id: str
    evidence: Evidence
    human_overall: str


def _load_holdout() -> tuple[HoldoutCase, ...]:
    return tuple(
        HoldoutCase(
            scenario_id=case["scenario_id"],
            evidence=Evidence(answer=case["trajectory"][-1]["answer"]),
            human_overall=case["human"]["overall"],
        )
        for case in load_calibration()["cases"]
    )


HOLDOUT = _load_holdout()


def load_semantic_holdout() -> dict[str, Any]:
    """Return the independent semantic holdout corpus (v8, 12 cases)."""
    return load_calibration(SEMANTIC_HOLDOUT_PATH)


def holdout_report(
    results: dict[str, dict],
    threshold: float | None = None,
    *,
    thresholds_by_class: dict[str, float] | None = None,
) -> dict:
    """Score-only view of the holdout corpus against human labels."""
    return calibration_report(
        load_semantic_holdout(),
        results,
        threshold,
        thresholds_by_class=thresholds_by_class,
    )


def calibrate_holdout(results: dict[str, dict], threshold: float | None = None) -> dict:
    """Report against human labels after the maintainer supplies a calibration bar."""
    return calibration_report(load_calibration(), results, threshold)
