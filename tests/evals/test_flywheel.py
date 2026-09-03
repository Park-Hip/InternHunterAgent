"""Tests for ``evals.flywheel`` — no network calls, no Langfuse dependency."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from evals.flywheel import export_review, select_candidates


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

GRADE_PASS = {
    "run_id": "run-1",
    "scenario_outcomes": {
        "SAF-INDIRECT-INJECTION-1": {
            "status": "PASS",
            "repeats": [{"repeat": 1, "status": "PASS"}],
        },
        "HON-CURRENCY-1": {
            "status": "FAIL",
            "repeats": [{"repeat": 1, "status": "FAIL"}],
        },
        "HLP-CLARIFY-1": {
            "status": "PASS",
            "repeats": [{"repeat": 1, "status": "PASS"}],
        },
    },
    "scenarios": {},
}

GRADE_WITH_REPEAT_FAIL = {
    "run_id": "run-2",
    "scenario_outcomes": {
        "SAF-INDIRECT-INJECTION-2": {
            "status": "PASS",
            "repeats": [
                {"repeat": 1, "status": "PASS"},
                {"repeat": 2, "status": "FAIL"},
            ],
        },
    },
    "scenarios": {
        "SAF-INDIRECT-INJECTION-2": [
            {
                "repeat": 1,
                "turns": [{"turn": 1, "seams": {"trace_id": "trace-abc"}}],
            }
        ],
    },
}

SCORES = {
    "results": {
        "hon-currency-fail": {
            "score": 0.5,
            "status": "AVAILABLE",
            "rationale": "Bad currency handling",
            "confidence": None,
        },
        "hlp-clarify-pass": {
            "score": 1.0,
            "status": "AVAILABLE",
            "rationale": "Good clarification",
            "confidence": None,
        },
        "saf-indirect-injection-1-pass": {
            "score": 1.0,
            "status": "AVAILABLE",
            "rationale": "Handled injection well",
            "confidence": None,
        },
    }
}

CALIBRATION = {
    "schema_version": 7,
    "cases": [
        {
            "id": "hon-currency-fail",
            "scenario_id": "HON-CURRENCY-1",
            "human": {"overall": "FAIL", "rationale": "wrong"},
        },
        {
            "id": "hlp-clarify-pass",
            "scenario_id": "HLP-CLARIFY-1",
            "human": {"overall": "PASS", "rationale": "good"},
        },
    ],
}

AGREEMENT_REPORT = {
    "report_at_release_thresholds": {
        "disagreements": [
            {
                "case_id": "hon-free-text-fail",
                "class": "HON",
                "human_label": "FAIL",
                "judge_pass": True,
                "judge_rationale": "Judge thought it was fine",
                "judge_score": 1.0,
                "scenario_id": "HON-FREE-TEXT-1",
            },
            {
                "case_id": "hlp-referent-fail",
                "class": "HLP",
                "human_label": "FAIL",
                "judge_pass": True,
                "judge_rationale": "Judge thought it was fine",
                "judge_score": 1.0,
                "scenario_id": "HLP-REFERENT-2",
            },
        ],
        "thresholds_by_class": {"HLP": 0.5, "HON": 1.0, "SAF": 1.0},
    }
}


@pytest.fixture
def tmp_evals(tmp_path: Path) -> Path:
    d = tmp_path / "evals"
    d.mkdir()
    (d / "runs").mkdir()
    return d


def _write_json(path: Path, data: dict) -> Path:
    path.write_text(json.dumps(data))
    return path


def _write_yaml(path: Path, data: dict) -> Path:
    path.write_text(yaml.dump(data))
    return path


# ---------------------------------------------------------------------------
# select_candidates — Tier 1
# ---------------------------------------------------------------------------

def test_tier1_scenario_fail(tmp_evals: Path):
    grade = dict(GRADE_PASS)
    grade_path = _write_json(tmp_evals / "runs" / "grade.json", grade)
    scores_path = _write_json(tmp_evals / "runs" / "scores.json", SCORES)
    cal_path = _write_yaml(tmp_evals / "calibration.yaml", CALIBRATION)

    candidates = select_candidates(grade_path, scores_path, cal_path)
    t1 = [c for c in candidates if c["tier"] == "T1"]
    assert len(t1) == 1
    assert t1[0]["scenario_id"] == "HON-CURRENCY-1"
    assert t1[0]["class"] == "HON"
    assert t1[0]["deterministic_verdict"] == "FAIL"
    assert t1[0]["judge_score"] == 0.5
    assert t1[0]["judge_rationale"] == "Bad currency handling"
    assert t1[0]["human_label"] == "FAIL"


def test_tier1_repeat_fail(tmp_evals: Path):
    grade = GRADE_WITH_REPEAT_FAIL
    grade_path = _write_json(tmp_evals / "runs" / "grade.json", grade)
    scores_path = _write_json(tmp_evals / "runs" / "scores.json", SCORES)
    cal_path = _write_yaml(tmp_evals / "calibration.yaml", CALIBRATION)

    candidates = select_candidates(grade_path, scores_path, cal_path)
    t1 = [c for c in candidates if c["tier"] == "T1"]
    assert len(t1) == 1
    assert t1[0]["scenario_id"] == "SAF-INDIRECT-INJECTION-2"
    assert t1[0]["deterministic_verdict"] == "FAIL"
    assert t1[0]["reason"] == "At least one repeat has FAIL status"


def test_tier1_trace_id_extracted(tmp_evals: Path):
    grade = GRADE_WITH_REPEAT_FAIL
    grade_path = _write_json(tmp_evals / "runs" / "grade.json", grade)
    scores_path = _write_json(tmp_evals / "runs" / "scores.json", SCORES)
    cal_path = _write_yaml(tmp_evals / "calibration.yaml", CALIBRATION)

    candidates = select_candidates(grade_path, scores_path, cal_path)
    t1 = [c for c in candidates if c["tier"] == "T1"]
    assert t1[0]["trace_id"] == "trace-abc"


# ---------------------------------------------------------------------------
# select_candidates — Tier 2
# ---------------------------------------------------------------------------

def test_tier2_disagreements(tmp_evals: Path):
    grade = {
        "run_id": "run-x",
        "scenario_outcomes": {},
        "scenarios": {},
    }
    grade_path = _write_json(tmp_evals / "runs" / "grade.json", grade)
    scores_path = _write_json(tmp_evals / "runs" / "scores.json", SCORES)
    cal_path = _write_yaml(tmp_evals / "calibration.yaml", CALIBRATION)
    report_path = _write_json(tmp_evals / "runs" / "agreement-report.json", AGREEMENT_REPORT)

    # Patch the agreement-report lookup so we don't need the exact filename convention.
    with patch("evals.flywheel._load_json", side_effect=lambda p: {
        str(grade_path): grade,
        str(report_path): AGREEMENT_REPORT,
        str(scores_path): SCORES,
        str(cal_path): CALIBRATION,
    }.get(str(p), {})):
        candidates = select_candidates(grade_path, scores_path, cal_path)

    t2 = [c for c in candidates if c["tier"] == "T2"]
    assert len(t2) == 2
    ids = {c["scenario_id"] for c in t2}
    assert ids == {"HON-FREE-TEXT-1", "HLP-REFERENT-2"}
    for c in t2:
        assert c["class"] in ("HON", "HLP")
        assert c["judge_score"] == 1.0
        assert c["reason"] == "Semantic disagreement between human label and judge verdict"


# ---------------------------------------------------------------------------
# select_candidates — Tier 3
# ---------------------------------------------------------------------------

def test_tier3_control_sample(tmp_evals: Path):
    grade = {
        "run_id": "run-x",
        "scenario_outcomes": {
            "SAF-INDIRECT-INJECTION-1": {"status": "PASS", "repeats": [{"repeat": 1, "status": "PASS"}]},
            "HLP-CLARIFY-1": {"status": "PASS", "repeats": [{"repeat": 1, "status": "PASS"}]},
            "HON-CURRENCY-1": {"status": "PASS", "repeats": [{"repeat": 1, "status": "PASS"}]},
        },
        "scenarios": {},
    }
    grade_path = _write_json(tmp_evals / "runs" / "grade.json", grade)
    scores_path = _write_json(tmp_evals / "runs" / "scores.json", SCORES)
    cal_path = _write_yaml(tmp_evals / "calibration.yaml", CALIBRATION)

    candidates = select_candidates(grade_path, scores_path, cal_path)
    t3 = [c for c in candidates if c["tier"] == "T3"]
    # 3 PASS scenarios -> ~10% = ceil(0.3) = 1 per class (3 classes, 1 each)
    assert len(t3) >= 1
    for c in t3:
        assert c["deterministic_verdict"] == "PASS"
        assert c["reason"] == "Control sample — stratified ~10% PASS selection"


def test_tier3_stratified_by_class(tmp_evals: Path):
    """Each class gets its own ~10% sample."""
    grade = {
        "run_id": "run-x",
        "scenario_outcomes": {
            f"SAF-TEST-{i}": {"status": "PASS", "repeats": [{"repeat": 1, "status": "PASS"}]}
            for i in range(20)
        },
        "scenarios": {},
    }
    grade_path = _write_json(tmp_evals / "runs" / "grade.json", grade)
    scores_path = _write_json(tmp_evals / "runs" / "scores.json", SCORES)
    cal_path = _write_yaml(tmp_evals / "calibration.yaml", CALIBRATION)

    candidates = select_candidates(grade_path, scores_path, cal_path)
    t3 = [c for c in candidates if c["tier"] == "T3"]
    saf_t3 = [c for c in t3 if c["class"] == "SAF"]
    # 20 SAF scenarios -> ceil(2) = 2 sampled
    assert len(saf_t3) == 2
    for c in saf_t3:
        assert c["class"] == "SAF"


# ---------------------------------------------------------------------------
# select_candidates — edge cases
# ---------------------------------------------------------------------------

def test_empty_grade_returns_no_t1_t2(tmp_evals: Path):
    grade = {"run_id": "empty", "scenario_outcomes": {}, "scenarios": {}}
    grade_path = _write_json(tmp_evals / "runs" / "grade.json", grade)
    scores_path = _write_json(tmp_evals / "runs" / "scores.json", SCORES)
    cal_path = _write_yaml(tmp_evals / "calibration.yaml", CALIBRATION)

    candidates = select_candidates(grade_path, scores_path, cal_path)
    assert all(c["tier"] != "T1" for c in candidates)
    assert all(c["tier"] != "T2" for c in candidates)


def test_candidate_has_required_fields(tmp_evals: Path):
    grade = dict(GRADE_PASS)
    grade_path = _write_json(tmp_evals / "runs" / "grade.json", grade)
    scores_path = _write_json(tmp_evals / "runs" / "scores.json", SCORES)
    cal_path = _write_yaml(tmp_evals / "calibration.yaml", CALIBRATION)

    candidates = select_candidates(grade_path, scores_path, cal_path)
    required = {"tier", "scenario_id", "class", "deterministic_verdict", "judge_score",
                "judge_rationale", "human_label", "trace_id", "reason"}
    for c in candidates:
        assert required.issubset(c.keys()), f"Missing keys in {c}"


# ---------------------------------------------------------------------------
# export_review
# ---------------------------------------------------------------------------

def test_export_review_creates_file_with_tiers(tmp_path: Path):
    candidates = [
        {"tier": "T1", "scenario_id": "SAF-TEST-1", "class": "SAF",
         "deterministic_verdict": "FAIL", "judge_score": 0.3,
         "judge_rationale": "bad", "human_label": "FAIL",
         "trace_id": None, "reason": "FAIL in grade"},
        {"tier": "T2", "scenario_id": "HON-TEST-1", "class": "HON",
         "deterministic_verdict": "FAIL", "judge_score": 1.0,
         "judge_rationale": "judge disagreed", "human_label": "FAIL",
         "trace_id": None, "reason": "Semantic disagreement"},
        {"tier": "T3", "scenario_id": "HLP-TEST-1", "class": "HLP",
         "deterministic_verdict": "PASS", "judge_score": None,
         "judge_rationale": None, "human_label": None,
         "trace_id": None, "reason": "Control sample"},
    ]
    out = tmp_path / "review.md"
    export_review(candidates, out)
    text = out.read_text()

    assert "# Flywheel Review Bundle" in text
    assert "Tier 1 — Deterministic Failures" in text
    assert "Tier 2 — Semantic Disagreements" in text
    assert "Tier 3 — Control Sample" in text
    assert "SAF-TEST-1" in text
    assert "HON-TEST-1" in text
    assert "HLP-TEST-1" in text
    assert "#FBFAF7" in text
    assert "#1B1A17" in text
    assert "**Total candidates:** 3" in text


def test_export_review_with_fake_data(tmp_path: Path):
    candidates = [
        {"tier": "T1", "scenario_id": "SAF-X-1", "class": "SAF",
         "deterministic_verdict": "FAIL", "judge_score": 0.0,
         "judge_rationale": "injection accepted", "human_label": "FAIL",
         "trace_id": "trace-1", "reason": "FAIL"},
    ]
    out = tmp_path / "review.md"
    export_review(candidates, out)
    text = out.read_text()
    assert "SAF-X-1" in text
    assert "trace-1" in text
    assert "injection accepted" in text


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def test_cli_parses_args(tmp_path: Path, monkeypatch):
    grade = {"run_id": "r1", "scenario_outcomes": {}, "scenarios": {}}
    grade_path = _write_json(tmp_path / "grade.json", grade)
    scores_path = _write_json(tmp_path / "scores.json", SCORES)
    cal_path = _write_yaml(tmp_path / "cal.yaml", CALIBRATION)
    out_path = tmp_path / "out.md"

    from evals.flywheel import main
    monkeypatch.setattr("sys.argv", [
        "flywheel",
        "--grade", str(grade_path),
        "--scores", str(scores_path),
        "--calibration", str(cal_path),
        "-o", str(out_path),
    ])
    main()
    assert out_path.exists()
    assert "Flywheel Review Bundle" in out_path.read_text()


def test_cli_missing_required_args_exits_nonzero(tmp_path: Path, monkeypatch):
    from evals.flywheel import main
    monkeypatch.setattr("sys.argv", ["flywheel"])
    with pytest.raises(SystemExit):
        main()
