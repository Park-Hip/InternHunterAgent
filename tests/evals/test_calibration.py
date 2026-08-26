from __future__ import annotations

from collections import defaultdict

import pytest

from evals import calibration
from evals.calibration import calibration_report, load_calibration
from evals.scenarios import load_scenarios
from evals.semantic import semantic_assertion


def test_calibration_corpus_is_versioned_vietnamese_and_covers_every_release_class() -> (
    None
):
    corpus = load_calibration()

    assert corpus["corpus_id"] == "vietnamese-semantic-v7"
    assert {item["language"] for item in corpus["cases"]} == {"vi"}
    assert {item["scenario_id"].split("-", 1)[0] for item in corpus["cases"]} == {
        "SAF",
        "HON",
        "HLP",
    }


def test_calibration_corpus_has_a_pass_and_fail_pair_for_every_semantic_class() -> (
    None
):
    corpus = load_calibration()
    scenarios = {
        item["id"]: item
        for item in load_scenarios()
        if semantic_assertion(item) is not None
    }

    labels_by_class: dict[str, list[str]] = defaultdict(list)
    for case in corpus["cases"]:
        labels_by_class[case["scenario_id"]].append(case["human"]["overall"])

    assert set(labels_by_class) == set(scenarios)
    assert all(sorted(labels) == ["FAIL", "PASS"] for labels in labels_by_class.values())


def test_calibration_corpus_only_uses_the_two_approved_evidence_sources() -> None:
    corpus = load_calibration()

    assert {item["source"] for item in corpus["cases"]} <= {
        "independently_authored_holdout",
        "replay_mined_v6-baseline-20260823_human_confirmed",
    }
    mined = [
        case
        for case in corpus["cases"]
        if case["source"] == "replay_mined_v6-baseline-20260823_human_confirmed"
    ]
    assert {case["human"]["overall"] for case in mined} == {"PASS", "FAIL"}


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


def test_calibration_accepts_and_groups_named_prompt_lineage_without_rewriting_legacy_cases(
    tmp_path,
) -> None:
    path = tmp_path / "named.yaml"
    path.write_text(
        """schema_version: 1
corpus_id: named-lineage
cases:
  - id: named-case
    scenario_id: HON-CURRENCY-1
    language: vi
    prompt_versions:
      system: v11
      schema_context: v10
      sql_generation: v9
    source: independently_authored_holdout
    trajectory:
      - question: Có bao nhiêu việc?
        answer: Có 2 việc.
    human:
      overall: PASS
      rationale: named lineage fixture
""",
        encoding="utf-8",
    )

    corpus = load_calibration(path)
    report = calibration_report(
        corpus,
        {"named-case": {"status": "AVAILABLE", "score": 0.9}},
        threshold=0.5,
    )

    assert {
        "prompt_surface:system:v11",
        "prompt_surface:schema_context:v10",
        "prompt_surface:sql_generation:v9",
    } <= set(report["groups"])


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
