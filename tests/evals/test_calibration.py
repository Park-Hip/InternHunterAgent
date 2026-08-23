from __future__ import annotations

import pytest

from evals import calibration
from evals.calibration import calibration_report, load_calibration


def test_calibration_corpus_is_versioned_vietnamese_and_covers_every_release_class() -> (
    None
):
    corpus = load_calibration()

    assert corpus["corpus_id"] == "vietnamese-semantic-v6"
    assert {item["language"] for item in corpus["cases"]} == {"vi"}
    assert {item["scenario_id"].split("-", 1)[0] for item in corpus["cases"]} == {
        "SAF",
        "HON",
        "HLP",
    }


def test_calibration_report_requires_a_maintainer_threshold_before_classifying_scores() -> (
    None
):
    corpus = load_calibration()
    results = {
        item["id"]: {
            "status": "AVAILABLE",
            "score": 0.9 if item["human"]["overall"] == "PASS" else 0.1,
        }
        for item in corpus["cases"]
    }

    assert calibration_report(corpus, results)["groups"] == {}
    report = calibration_report(corpus, results, threshold=0.5)
    assert report["groups"]["overall"]["precision"] == 1.0
    assert report["groups"]["assertion_type:semantic"]["recall"] == 1.0


def test_calibration_loader_rejects_an_empty_corpus(tmp_path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("schema_version: 1\ncorpus_id: bad\ncases: []\n", encoding="utf-8")

    with pytest.raises(ValueError, match="non-empty"):
        load_calibration(path)


def test_calibration_scoring_keeps_human_labels_separate_from_judge_results(
    monkeypatch,
) -> None:
    corpus = load_calibration()

    class Result:
        def to_dict(self):
            return {
                "status": "AVAILABLE",
                "score": 0.8,
                "confidence": None,
                "rationale": "ok",
            }

    monkeypatch.setattr(
        calibration, "evaluate_semantic_repeat", lambda scenario, repeat: Result()
    )

    results = calibration.score_calibration(corpus)

    assert set(results) == {item["id"] for item in corpus["cases"]}
    assert all("human" not in result for result in results.values())
