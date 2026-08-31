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


def test_v8_corpus_is_versioned_vietnamese_and_targets_disagreement_classes() -> None:
    from pathlib import Path

    corpus = load_calibration(Path("evals/calibration_v8.yaml"))

    assert corpus["corpus_id"] == "vietnamese-semantic-v8"
    assert {item["language"] for item in corpus["cases"]} == {"vi"}
    classes = {item["scenario_id"].split("-", 1)[0] for item in corpus["cases"]}
    assert classes == {"HON", "HLP"}
    # All cases target the six disagreement scenarios from v7.
    expected_scenarios = {
        "HON-CURRENCY-1",
        "HON-ZERO-RESULTS-1",
        "HON-FREE-TEXT-1",
        "HON-GENERAL-KNOWLEDGE-1",
        "HLP-SENIOR-TITLE-1",
        "HLP-ABSTRACTION-1",
    }
    assert {item["scenario_id"] for item in corpus["cases"]} == expected_scenarios


def test_v8_corpus_has_independent_provenance_and_balanced_labels() -> None:
    from pathlib import Path

    corpus = load_calibration(Path("evals/calibration_v8.yaml"))
    assert {item["source"] for item in corpus["cases"]} == {"independently_authored_holdout"}
    labels_by_scenario: dict[str, list[str]] = defaultdict(list)
    for case in corpus["cases"]:
        labels_by_scenario[case["scenario_id"]].append(case["human"]["overall"])
    assert all(sorted(labels) == ["FAIL", "PASS"] for labels in labels_by_scenario.values())


def test_v7_remains_unchanged_after_v8_addition() -> None:
    from pathlib import Path

    v7 = load_calibration()
    assert v7["corpus_id"] == "vietnamese-semantic-v7"
    assert len(v7["cases"]) == 40
    v8 = load_calibration(Path("evals/calibration_v8.yaml"))
    assert v8["corpus_id"] == "vietnamese-semantic-v8"
    assert len(v8["cases"]) == 12
    v7_ids = {item["id"] for item in v7["cases"]}
    v8_ids = {item["id"] for item in v8["cases"]}
    assert v7_ids.isdisjoint(v8_ids)


def test_calibration_report_exposes_disagreements(tmp_path) -> None:
    path = tmp_path / "disagree.yaml"
    path.write_text(
        """schema_version: 1
corpus_id: disagree-test
cases:
  - id: case-a
    scenario_id: HON-CURRENCY-1
    language: vi
    prompt_version: v6
    source: independently_authored_holdout
    trajectory:
      - question: question
        answer: answer
    human:
      overall: FAIL
      rationale: human says fail
  - id: case-b
    scenario_id: HON-ZERO-RESULTS-1
    language: vi
    prompt_version: v6
    source: independently_authored_holdout
    trajectory:
      - question: question
        answer: answer
    human:
      overall: PASS
      rationale: human says pass
""",
        encoding="utf-8",
    )
    corpus = load_calibration(path)
    results = {
        "case-a": {"status": "AVAILABLE", "score": 0.5, "rationale": "judge says pass"},
        "case-b": {"status": "AVAILABLE", "score": 0.2, "rationale": "judge says fail"},
    }
    report = calibration_report(corpus, results, threshold=0.3)
    assert len(report["disagreements"]) == 2
    ids = {d["case_id"] for d in report["disagreements"]}
    assert ids == {"case-a", "case-b"}
    case_a = next(d for d in report["disagreements"] if d["case_id"] == "case-a")
    assert case_a["judge_pass"] is True
    assert case_a["human_label"] == "FAIL"
    assert case_a["class"] == "HON"


def test_sweep_thresholds_returns_points_for_every_decimal(tmp_path) -> None:
    path = tmp_path / "sweep.yaml"
    path.write_text(
        """schema_version: 1
corpus_id: sweep-test
cases:
  - id: a
    scenario_id: HON-CURRENCY-1
    language: vi
    prompt_version: v6
    source: independently_authored_holdout
    trajectory:
      - question: q
        answer: a
    human:
      overall: PASS
      rationale: ok
""",
        encoding="utf-8",
    )
    corpus = load_calibration(path)
    results = {"a": {"status": "AVAILABLE", "score": 0.55}}
    sweep = calibration.sweep_thresholds(corpus, results, start=0.1, stop=0.6, step=0.1)
    thresholds = [point["threshold"] for point in sweep]
    assert thresholds == [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
    # Score 0.55 passes at thresholds <= 0.5 and fails at 0.6.
    assert sweep[0]["overall"]["recall"] == 1.0
    assert sweep[4]["overall"]["recall"] == 1.0
    assert sweep[5]["overall"]["recall"] == 0.0
    assert all("sample_size" in point["overall"] for point in sweep)


def test_calibration_report_includes_unavailable_and_disagreement_counts() -> None:
    from pathlib import Path

    corpus = load_calibration(Path("evals/calibration_v8.yaml"))
    # Only score half the cases; leave the rest unavailable.
    first_six = {case["id"]: {"status": "AVAILABLE", "score": 0.9} for case in corpus["cases"][:6]}
    report = calibration_report(corpus, first_six, threshold=0.5)
    assert len(report["unavailable_case_ids"]) == 6
    assert report["groups"]["overall"]["sample_size"] == 6
