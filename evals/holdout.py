"""Compatibility view over the versioned Vietnamese calibration corpus."""

from __future__ import annotations

from dataclasses import dataclass

from evals.calibration import calibration_report, load_calibration
from evals.grader import Evidence


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


def calibrate_holdout(results: dict[str, dict], threshold: float | None = None) -> dict:
    """Report against human labels after the maintainer supplies a calibration bar."""
    return calibration_report(load_calibration(), results, threshold)
