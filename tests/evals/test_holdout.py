"""Offline tests for the independent semantic holdout (evals/holdout.py)."""

from __future__ import annotations

from evals import holdout
from evals.calibration import load_calibration


def test_semantic_holdout_is_v8_and_disjoint_from_calibration() -> None:
    cal = load_calibration()
    held = holdout.load_semantic_holdout()

    assert held["corpus_id"] == "vietnamese-semantic-v8"
    assert len(held["cases"]) == 12
    assert {case["source"] for case in held["cases"]} == {
        "independently_authored_holdout",
    }
    cal_ids = {case["id"] for case in cal["cases"]}
    held_ids = {case["id"] for case in held["cases"]}
    assert cal_ids.isdisjoint(held_ids)


def test_holdout_report_is_a_score_only_view_with_per_class_bars() -> None:
    held = holdout.load_semantic_holdout()
    results = {
        case["id"]: {"status": "AVAILABLE", "score": 0.9}
        for case in held["cases"]
    }

    report = holdout.holdout_report(
        results,
        threshold=0.5,
        thresholds_by_class={"HON": 0.8, "HLP": 0.8},
    )

    assert report["groups"]["overall"]["sample_size"] == 12
    assert set(report["groups"]) >= {"class:HON", "class:HLP", "overall"}
    # The holdout has no SAF cases, so no SAF group is reported.
    assert any("SAF" not in key for key in report["groups"])