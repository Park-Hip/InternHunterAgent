"""End-to-end offline harness tests with the database boundary stubbed."""

import asyncio
from pathlib import Path

import pytest

from evals.datasets import dataset
from evals import run


CAPTURE = Path("evals/replays/t0025.9-committed.json")


def test_offline_only_scores_captured_scenarios(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run, "grade_sql", lambda *_args, **_kw: {"status": "PASS"})
    report = asyncio.run(run.run_dataset(dataset("default"), metric_names=["tool_correctness", "sql_accuracy"], ids=["HLP-CONTEXT-1"], capture_path=CAPTURE))
    assert {row["scenario_id"] for row in report["results"]} == {"HLP-CONTEXT-1"}
    assert {row["metric"] for row in report["results"]} == {"tool_correctness", "sql_accuracy"}
    assert len(report["captures"]["HLP-CONTEXT-1"]) == 2
    assert all(row["score"] == 1 for row in report["results"])


def test_sql_failure_is_a_finding_not_a_silent_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run, "grade_sql", lambda *_args, **_kw: {"status": "FAIL", "unexpected_ids": [13]})
    case = next(s for s in dataset("default").scenarios() if s["id"] == "HLP-LIST-1")
    capture = {"question": case["input"], "answer": "Wrong list", "tools_called": ["query_clean_jobs"], "sql_text": "SELECT id FROM clean_jobs"}
    result = run.score_turn(capture, case, ["sql_accuracy"], 0)
    assert result[0]["score"] == 0.0
    assert result[0]["details"]["unexpected_ids"] == [13]


def test_explicit_id_missing_from_capture_fails() -> None:
    with pytest.raises(ValueError, match="absent from capture"):
        asyncio.run(run.run_dataset(dataset("default"), metric_names=["tool_correctness"], ids=["HLP-LIST-1"], capture_path=CAPTURE))


def test_offline_does_not_start_judge() -> None:
    with pytest.raises(ValueError, match="deterministic"):
        asyncio.run(run.run_dataset(dataset("default"), metric_names=["grounded"], capture_path=CAPTURE))


def test_nested_sql_trace_is_not_dropped() -> None:
    parsed = run.extract_trace({
        "toolsCalled": [{"name": "query_clean_jobs"}],
        "toolSpans": [{"name": "query_clean_jobs", "parentUuid": "node", "output": {"content": "five jobs"}}],
        "llmSpans": [{"parentUuid": "node", "output": {"content": "SELECT id FROM clean_jobs"}}],
    })
    assert parsed == {"tools_called": ["query_clean_jobs"], "sql_text": "SELECT id FROM clean_jobs", "tool_output": "five jobs"}


def test_retry_three_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = []

    async def failed_capture(*_args):
        attempts.append(1)
        raise RuntimeError("429 quota")

    async def no_sleep(_delay):
        return None

    monkeypatch.setattr(run, "capture_turn", failed_capture)
    with pytest.raises(run.QuotaError):
        asyncio.run(run.capture_with_retry(None, "question", {}, sleep=no_sleep))
    assert len(attempts) == 3


def test_quota_halts_and_marks_remaining_unrun(monkeypatch: pytest.MonkeyPatch) -> None:
    scenarios = [dict(id=str(i), input="x", type="single", metrics=["tool_correctness"], expected_tools=[]) for i in range(4)]
    class FixtureDataset:
        path = Path("fixture.yaml")
        def scenarios(self):
            return scenarios

    async def prompts():
        return None

    async def quota(*_args):
        raise run.QuotaError("429")

    monkeypatch.setattr("src.agents.runtime.prompts.resolve_prompt_bundle_async", prompts)
    monkeypatch.setattr(run, "capture_scenario", quota)
    report = asyncio.run(run.run_dataset(FixtureDataset(), metric_names=["tool_correctness"]))
    assert len(report["results"]) == 4
    assert report["results"][-1]["reason"] == "UNRUN"
