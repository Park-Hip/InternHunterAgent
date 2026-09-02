from __future__ import annotations

import pytest

from evals import calibration
from evals.semantic import AVAILABLE


# Provide a dummy judge key so the live-prerequisite check in _run_gate does not
# raise during these unit tests.  The gate itself validates the real key at
# runtime; these tests exercise the recall/threshold/unavailable logic around it.
@pytest.fixture(autouse=True)
def _fake_judge_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "test-fake-key-for-unit-tests")


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


class TestReleaseGatePrerequisites:
    """Verify the gate fails early and clearly when required credentials are missing."""

    def test_gate_raises_when_judge_key_is_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A missing GOOGLE_API_KEY must produce a clear RuntimeError."""
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        from evals.test_release_gate import _check_prerequisites
        with pytest.raises(RuntimeError, match="missing required credential"):
            _check_prerequisites()

    def test_gate_raises_when_provider_is_unsupported(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An unsupported judge provider must fail with a named list of supported providers."""
        import src.core.config as config_mod
        # Patch load_settings to return a fake settings with an unknown provider,
        # bypassing the cache-clear logic inside _check_prerequisites.
        fake_settings = config_mod.Settings(
            DATABASE_URL="postgres://x/x",
            AGENT_DATABASE_URL="postgres://x/x",
        )
        fake_settings.config_yaml = {
            "api": {"stream_heartbeat_seconds": 15},
            "eval": {"judge": {"provider": "nonexistent"}},
        }
        monkeypatch.setattr(config_mod, "load_settings", lambda **kwargs: fake_settings)
        from evals.test_release_gate import _check_prerequisites
        with pytest.raises(RuntimeError, match="unsupported judge provider"):
            _check_prerequisites()


class TestReleaseGateCollection:
    """Verify the gate selects nonzero cases and fails closed on empty selection."""

    def test_gate_fails_when_corpus_is_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A zero-case corpus must fail the gate, not silently pass."""
        monkeypatch.setattr(
            calibration, "load_calibration",
            lambda path=None: _make_corpus([]),
        )
        from evals.test_release_gate import _run_gate
        with pytest.raises(AssertionError, match="at least one case"):
            _run_gate()

    def test_gate_fails_when_no_cases_score(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Zero AVAILABLE results must fail the gate."""
        corpus = _make_corpus([_make_case("a", "SAF-T-1", "PASS")])
        monkeypatch.setattr(calibration, "load_calibration", lambda path=None: corpus)
        monkeypatch.setattr(
            calibration, "score_calibration",
            lambda _: {"a": _make_result("UNAVAILABLE")},
        )
        from evals.test_release_gate import _run_gate
        with pytest.raises(AssertionError, match="unavailable"):
            _run_gate()


class TestReleaseGateThreshold:
    """Verify threshold breach is surfaced and the gate fails closed."""

    def test_gate_passes_when_recall_is_perfect(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """All-AVAILABLE, all-above-threshold scores must pass."""
        corpus = _make_corpus([
            _make_case("a", "SAF-T-1", "PASS"),
            _make_case("b", "SAF-T-2", "FAIL"),
            _make_case("c", "HON-T-1", "PASS"),
            _make_case("d", "HON-T-2", "FAIL"),
        ])
        monkeypatch.setattr(calibration, "load_calibration", lambda path=None: corpus)
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

    def test_gate_fails_when_overall_recall_breaches(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A below-threshold score on a PASS case must break recall and fail."""
        corpus = _make_corpus([
            _make_case("a", "SAF-T-1", "PASS"),
        ])
        monkeypatch.setattr(calibration, "load_calibration", lambda path=None: corpus)
        # Score below RELEASE_THRESHOLD → predicted FAIL for a human PASS → FN.
        monkeypatch.setattr(
            calibration, "score_calibration",
            lambda _: {"a": _make_result(AVAILABLE, 0.2)},
        )
        from evals.test_release_gate import _run_gate
        with pytest.raises(AssertionError, match="threshold breached"):
            _run_gate()

    def test_gate_fails_when_class_recall_breaches(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Recall < 1.0 on any class must fail the gate."""
        corpus = _make_corpus([
            _make_case("sa1", "SAF-T-1", "PASS"),
            _make_case("sa2", "SAF-T-2", "FAIL"),
            _make_case("ho1", "HON-T-1", "PASS"),
        ])
        monkeypatch.setattr(calibration, "load_calibration", lambda path=None: corpus)
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

    def test_gate_fails_with_unavailable_cases(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """All-unavailable cases must fail the gate."""
        corpus = _make_corpus([_make_case("a", "SAF-T-1", "PASS")])
        monkeypatch.setattr(calibration, "load_calibration", lambda path=None: corpus)
        monkeypatch.setattr(
            calibration, "score_calibration",
            lambda _: {"a": _make_result("UNAVAILABLE")},
        )
        from evals.test_release_gate import _run_gate
        with pytest.raises(AssertionError, match="unavailable"):
            _run_gate()

    def test_gate_fails_on_partial_outage(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Partial scoring loss (some unavailable, some scored) must fail closed.

        A judge outage on one class while the other scores perfectly must not
        let the gate pass — unavailable cases are dropped from every metric group
        and would otherwise leave recall at 1.0 on the scored subset.
        """
        corpus = _make_corpus([
            _make_case("a", "SAF-T-1", "PASS"),
            _make_case("b", "HON-T-1", "PASS"),
        ])
        monkeypatch.setattr(calibration, "load_calibration", lambda path=None: corpus)
        monkeypatch.setattr(
            calibration, "score_calibration",
            lambda _: {
                "a": _make_result(AVAILABLE, 0.9),
                # HON case is unavailable (provider/judge outage)
                "b": _make_result("UNAVAILABLE"),
            },
        )
        from evals.test_release_gate import _run_gate
        with pytest.raises(AssertionError, match="unavailable"):
            _run_gate()


class TestReleaseGateReporting:
    """Verify the gate prints the summary format required by the brief."""

    def test_summary_names_selected_count_and_threshold(self, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
        """The printed summary must include selected-case count and threshold."""
        corpus = _make_corpus([_make_case("a", "SAF-T-1", "PASS")])
        monkeypatch.setattr(calibration, "load_calibration", lambda path=None: corpus)
        monkeypatch.setattr(
            calibration, "score_calibration",
            lambda _: {"a": _make_result(AVAILABLE, 0.9)},
        )
        from evals.test_release_gate import _run_gate
        _run_gate()
        captured = capsys.readouterr()
        assert "1 scored" in captured.out
        assert "threshold=0.3" in captured.out

    def test_summary_names_class_results(self, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
        """Per-class metrics must appear in the summary."""
        corpus = _make_corpus([_make_case("a", "SAF-T-1", "PASS")])
        monkeypatch.setattr(calibration, "load_calibration", lambda path=None: corpus)
        monkeypatch.setattr(
            calibration, "score_calibration",
            lambda _: {"a": _make_result(AVAILABLE, 0.9)},
        )
        from evals.test_release_gate import _run_gate
        _run_gate()
        captured = capsys.readouterr()
        assert "class:SAF" in captured.out
