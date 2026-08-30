from __future__ import annotations

import pytest

from evals import calibration
from evals.semantic import AVAILABLE


def _make_case(case_id: str, scenario_id: str, human_overall: str) -> dict:
    return {
        "id": case_id,
        "scenario_id": scenario_id,
        "language": "vi",
        "prompt_version": "v6",
        "source": "test",
        "trajectory": [{"question": "q", "answer": "a"}],
        "human": {"overall": human_overall, "rationale": "r"},
    }


def _make_corpus(cases: list[dict]) -> dict:
    return {
        "schema_version": 1,
        "corpus_id": "test",
        "cases": cases,
    }


def _make_result(status: str, score: float | None = None) -> dict:
    return {
        "status": status,
        "score": score,
        "confidence": None,
        "rationale": "x",
    }


class TestReleaseGateCollection:
    """Verify the gate selects nonzero cases and fails closed on empty selection."""

    def test_gate_fails_when_corpus_is_empty(self, monkeypatch) -> None:
        """A zero-case corpus must fail the gate, not silently pass."""
        monkeypatch.setattr(
            calibration, "load_calibration",
            lambda: _make_corpus([]),
        )
        from evals.test_release_gate import _run_gate
        with pytest.raises(AssertionError, match="at least one case"):
            _run_gate()

    def test_gate_fails_when_no_cases_score(self, monkeypatch) -> None:
        """Zero AVAILABLE results must fail the gate."""
        corpus = _make_corpus([_make_case("a", "SAF-T-1", "PASS")])
        monkeypatch.setattr(calibration, "load_calibration", lambda: corpus)
        monkeypatch.setattr(
            calibration, "score_calibration",
            lambda _: {"a": _make_result("UNAVAILABLE")},
        )
        from evals.test_release_gate import _run_gate
        with pytest.raises(AssertionError, match="scored zero cases"):
            _run_gate()


class TestReleaseGateThreshold:
    """Verify threshold breach is surfaced and the gate fails closed."""

    def test_gate_passes_when_recall_is_perfect(self, monkeypatch) -> None:
        """All-AVAILABLE, all-above-threshold scores must pass."""
        corpus = _make_corpus([
            _make_case("a", "SAF-T-1", "PASS"),
            _make_case("b", "SAF-T-2", "FAIL"),
            _make_case("c", "HON-T-1", "PASS"),
            _make_case("d", "HON-T-2", "FAIL"),
        ])
        monkeypatch.setattr(calibration, "load_calibration", lambda: corpus)
        monkeypatch.setattr(
            calibration, "score_calibration",
            lambda _: {
                "a": _make_result(AVAILABLE, 0.9),
                "b": _make_result(AVAILABLE, 0.1),
                "c": _make_result(AVAILABLE, 0.8),
                "d": _make_result(AVAILABLE, 0.2),
            },
        )
        from evals.test_release_gate import _run_gate
        # Should not raise.
        _run_gate()

    def test_gate_fails_when_overall_recall_breaches(self, monkeypatch) -> None:
        """A below-threshold score on a PASS case must break recall and fail."""
        corpus = _make_corpus([
            _make_case("a", "SAF-T-1", "PASS"),
        ])
        monkeypatch.setattr(calibration, "load_calibration", lambda: corpus)
        # Score below RELEASE_THRESHOLD → predicted FAIL for a human PASS → FN.
        monkeypatch.setattr(
            calibration, "score_calibration",
            lambda _: {"a": _make_result(AVAILABLE, 0.2)},
        )
        from evals.test_release_gate import _run_gate
        with pytest.raises(AssertionError, match="threshold breached"):
            _run_gate()

    def test_gate_fails_when_class_recall_breaches(self, monkeypatch) -> None:
        """Recall < 1.0 on any class must fail the gate."""
        corpus = _make_corpus([
            _make_case("sa1", "SAF-T-1", "PASS"),
            _make_case("sa2", "SAF-T-2", "FAIL"),
            _make_case("ho1", "HON-T-1", "PASS"),
        ])
        monkeypatch.setattr(calibration, "load_calibration", lambda: corpus)
        monkeypatch.setattr(
            calibration, "score_calibration",
            lambda _: {
                "sa1": _make_result(AVAILABLE, 0.9),
                "sa2": _make_result(AVAILABLE, 0.2),
                # HON-T-1 is human PASS, score 0.2 (< threshold) → predicted FAIL → FN.
                "ho1": _make_result(AVAILABLE, 0.2),
            },
        )
        from evals.test_release_gate import _run_gate
        with pytest.raises(AssertionError, match="class:HON"):
            _run_gate()

    def test_gate_fails_with_unavailable_cases(self, monkeypatch) -> None:
        """All-unavailable cases must fail the gate."""
        corpus = _make_corpus([_make_case("a", "SAF-T-1", "PASS")])
        monkeypatch.setattr(calibration, "load_calibration", lambda: corpus)
        monkeypatch.setattr(
            calibration, "score_calibration",
            lambda _: {"a": _make_result("UNAVAILABLE")},
        )
        from evals.test_release_gate import _run_gate
        with pytest.raises(AssertionError, match="scored zero cases"):
            _run_gate()


class TestReleaseGateReporting:
    """Verify the gate prints the summary format required by the brief."""

    def test_summary_names_selected_count_and_threshold(self, monkeypatch, capsys) -> None:
        """The printed summary must include selected-case count and threshold."""
        corpus = _make_corpus([_make_case("a", "SAF-T-1", "PASS")])
        monkeypatch.setattr(calibration, "load_calibration", lambda: corpus)
        monkeypatch.setattr(
            calibration, "score_calibration",
            lambda _: {"a": _make_result(AVAILABLE, 0.9)},
        )
        from evals.test_release_gate import _run_gate
        _run_gate()
        captured = capsys.readouterr()
        assert "1 scored" in captured.out
        assert "threshold=0.3" in captured.out

    def test_summary_names_class_results(self, monkeypatch, capsys) -> None:
        """Per-class metrics must appear in the summary."""
        corpus = _make_corpus([_make_case("a", "SAF-T-1", "PASS")])
        monkeypatch.setattr(calibration, "load_calibration", lambda: corpus)
        monkeypatch.setattr(
            calibration, "score_calibration",
            lambda _: {"a": _make_result(AVAILABLE, 0.9)},
        )
        from evals.test_release_gate import _run_gate
        _run_gate()
        captured = capsys.readouterr()
        assert "class:SAF" in captured.out
