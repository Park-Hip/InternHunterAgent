"""End-to-end harness tests with the database boundary stubbed.

The offline layers (capture replay, scoring, reporting, exit codes) are covered
against the retained capture. The live capture path - `capture_scenario` building
a real agent over the real discovered tool list - is covered too, with only the
provider round trip stubbed, because that path is what issue #570 broke and a
harness that only ever replays cannot see it.
"""

from __future__ import annotations

import asyncio
import copy
import json
from pathlib import Path
from typing import Any

import pytest

from evals.datasets import dataset
from evals import run
from evals.__main__ import _exit_code, main


CAPTURE = Path("evals/replays/t0025.9-committed.json")
LIVE_SCENARIO_ID = "V0-LIST-ROLE-CITY"


def scenario(scenario_id: str) -> dict:
    return next(item for item in dataset("default").scenarios() if item["id"] == scenario_id)


def live_scenario() -> dict:
    """A governed v0 case, so the live path runs against the bundle under test."""
    return next(item for item in dataset("v0").scenarios() if item["id"] == LIVE_SCENARIO_ID)


def test_offline_only_scores_captured_scenarios(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run, "compare_result_sets", lambda *_args, **_kw: {"status": "PASS"})
    report = asyncio.run(run.run_dataset(dataset("default"), metric_names=["tool_correctness", "sql_accuracy"], ids=["HLP-CONTEXT-1"], capture_path=CAPTURE))
    rows = [row for rows in report["by_metric"].values() for row in rows]
    assert {row["scenario_id"] for row in rows} == {"HLP-CONTEXT-1"}
    assert set(report["by_metric"]) == {"tool_correctness", "sql_accuracy"}
    assert all(row["metric"] == "tool_correctness" for row in report["by_metric"]["tool_correctness"])
    assert len(report["captures"]["HLP-CONTEXT-1"]) == 2
    assert all(row["score"] == 1 for row in rows)


def test_sql_failure_is_a_finding_not_a_silent_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run, "compare_result_sets", lambda *_args, **_kw: {"status": "FAIL", "unexpected_ids": [13]})
    case = scenario("HLP-LIST-1")
    capture = {"question": case["input"], "answer": "Wrong list", "tools_called": ["query_clean_jobs"], "sql_text": "SELECT id FROM clean_jobs"}
    result = run.score_turn(capture, case, ["sql_accuracy"], 0)
    assert result[0]["score"] == 0.0
    assert result[0]["details"]["unexpected_ids"] == [13]


def test_infrastructure_failure_exits_nonzero(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(run, "compare_result_sets", lambda *_args, **_kw: {"status": "INFRA", "error": "connection refused"})
    out = tmp_path / "report.json"
    code = main(["--only", "sql_accuracy", "--capture", str(CAPTURE), "--ids", "HLP-CONTEXT-1", "--out", str(out)])
    assert code == 1
    persisted = json.loads(out.read_text(encoding="utf-8"))["by_metric"]["sql_accuracy"]
    assert {row["error"] for row in persisted} == {"connection refused"}
    assert all(row["score"] is None for row in persisted)


def test_persisted_artifact_is_grouped_by_metric(tmp_path: Path) -> None:
    out = tmp_path / "report.json"
    assert main(["--only", "tool_correctness", "--capture", str(CAPTURE), "--ids", "SAF-DESTRUCTIVE-REFUSAL-1", "--out", str(out)]) == 0
    artifact = json.loads(out.read_text(encoding="utf-8"))
    assert set(artifact["by_metric"]) == {"tool_correctness"}
    assert artifact["by_metric"]["tool_correctness"][0]["score"] == 1.0


def test_requested_metric_no_scenario_declares_is_refused() -> None:
    """A gate must not pass by scoring nothing.

    SAF-DESTRUCTIVE-REFUSAL-1 declares no sql_accuracy, so requesting it used to
    filter every scenario to nothing and report an empty, vacuously passing run.
    """
    with pytest.raises(ValueError, match="never scored"):
        asyncio.run(run.run_dataset(dataset("default"), metric_names=["sql_accuracy"], ids=["SAF-DESTRUCTIVE-REFUSAL-1"], capture_path=CAPTURE))


def test_refused_metric_names_the_metric_and_the_scenarios() -> None:
    with pytest.raises(ValueError) as excinfo:
        asyncio.run(run.run_dataset(dataset("default"), metric_names=["sql_accuracy"], ids=["SAF-DESTRUCTIVE-REFUSAL-1"], capture_path=CAPTURE))
    assert "sql_accuracy" in str(excinfo.value)
    assert "SAF-DESTRUCTIVE-REFUSAL-1" in str(excinfo.value)


def test_refused_metric_exits_nonzero_from_the_cli(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--only", "sql_accuracy", "--capture", str(CAPTURE), "--ids", "SAF-DESTRUCTIVE-REFUSAL-1", "--out", str(tmp_path / "report.json")])
    assert excinfo.value.code != 0


def test_below_threshold_deterministic_metric_exits_nonzero_without_a_flag(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The documented command and its exit code must not disagree."""
    monkeypatch.setattr(run, "compare_result_sets", lambda *_args, **_kw: {"status": "FAIL", "unexpected_ids": [13]})
    code = main(["--only", "sql_accuracy", "--capture", str(CAPTURE), "--ids", "HLP-CONTEXT-1", "--out", str(tmp_path / "report.json")])
    assert code == 1


def test_allow_fail_reports_a_below_threshold_finding_without_failing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(run, "compare_result_sets", lambda *_args, **_kw: {"status": "FAIL", "unexpected_ids": [13]})
    code = main(["--allow-fail", "--only", "sql_accuracy", "--capture", str(CAPTURE), "--ids", "HLP-CONTEXT-1", "--out", str(tmp_path / "report.json")])
    assert code == 0


def test_allow_fail_does_not_excuse_a_metric_that_could_not_be_evaluated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(run, "compare_result_sets", lambda *_args, **_kw: {"status": "INFRA", "error": "connection refused"})
    code = main(["--allow-fail", "--only", "sql_accuracy", "--capture", str(CAPTURE), "--ids", "HLP-CONTEXT-1", "--out", str(tmp_path / "report.json")])
    assert code == 1


def test_judge_score_is_reported_but_does_not_gate() -> None:
    """A judge score is continuous; requiring 1.0 of it would fail every run."""
    assert _exit_code({"grounded": [{"scenario_id": "HLP-CONTEXT-1", "score": 0.42, "reason": "partially grounded"}]}, allow_fail=False) == 0


def test_error_and_unrun_rows_fail_the_exit_code() -> None:
    assert _exit_code({"sql_accuracy": [{"scenario_id": "A", "error": "boom"}]}, allow_fail=True) == 1
    assert _exit_code({"sql_accuracy": [{"scenario_id": "A", "reason": "UNRUN"}]}, allow_fail=True) == 1


def test_explicit_id_missing_from_capture_fails() -> None:
    with pytest.raises(ValueError, match="absent from capture"):
        asyncio.run(run.run_dataset(dataset("default"), metric_names=["tool_correctness"], ids=["HLP-LIST-1"], capture_path=CAPTURE))


def test_offline_does_not_start_judge() -> None:
    with pytest.raises(ValueError, match="deterministic"):
        asyncio.run(run.run_dataset(dataset("default"), metric_names=["grounded"], capture_path=CAPTURE))


def test_unknown_metric_name_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown metric"):
        run.score_turn({"question": "q", "answer": "a", "tools_called": []}, scenario("HLP-LIST-1"), ["no_such_metric"], 0)


def test_scenario_level_tool_expectation_is_honored() -> None:
    """HON-GENERAL-KNOWLEDGE-1 requires no tool; declining with none is correct."""
    case = scenario("HON-GENERAL-KNOWLEDGE-1")
    capture = {"question": case["input"], "answer": "Chỉ có tin tuyển dụng trong dữ liệu.", "tools_called": []}
    assert run.score_turn(capture, case, ["tool_correctness"], 0)[0]["score"] == 1.0


def test_allowed_tool_call_is_not_a_finding() -> None:
    case = scenario("HLP-REFERENT-1")
    assert case["turn_tool_expectations"][1] == {"required": [], "allowed": ["query_clean_jobs"]}
    capture = {"question": case["turns"][1], "answer": "Vị trí đầu tiên.", "tools_called": ["query_clean_jobs"]}
    assert run.score_turn(capture, case, ["tool_correctness"], 1)[0]["score"] == 1.0


def test_tool_outside_allowed_is_a_finding() -> None:
    case = scenario("HLP-REFERENT-1")
    capture = {"question": case["turns"][1], "answer": "Xoá hết.", "tools_called": ["delete_jobs"]}
    row = run.score_turn(capture, case, ["tool_correctness"], 1)[0]
    assert row["score"] == 0.0
    assert row["reason"] == "Unexpected tool call"


def test_grounded_without_tool_output_is_not_applicable() -> None:
    case = scenario("HLP-DETAIL-1")
    capture = {"question": case["input"], "answer": "Chi tiết vị trí 1.", "tools_called": ["get_job_details"], "sql_text": None, "tool_output": None}
    row = run.score_turn(capture, case, ["grounded"], 0)[0]
    assert row["score"] is None
    assert row["reason"].startswith("NOT_APPLICABLE:")
    assert "error" not in row


def test_nested_sql_trace_is_not_dropped() -> None:
    parsed = run.extract_trace({
        "toolsCalled": [{"name": "query_clean_jobs"}],
        "toolSpans": [{"name": "query_clean_jobs", "parentUuid": "node", "output": {"content": "five jobs"}}],
        "llmSpans": [{"parentUuid": "node", "output": {"content": "SELECT id FROM clean_jobs"}}],
    })
    assert parsed == {"tools_called": ["query_clean_jobs"], "sql_text": "SELECT id FROM clean_jobs", "tool_output": "five jobs"}


def test_child_sql_span_wins_over_sibling_in_the_same_trace() -> None:
    parsed = run.extract_trace({
        "toolsCalled": [{"name": "query_clean_jobs"}],
        "toolSpans": [{"name": "query_clean_jobs", "uuid": "tool", "parentUuid": "node", "output": {"content": "five jobs"}}],
        "llmSpans": [
            {"parentUuid": "node", "output": {"content": "SELECT sibling"}},
            {"parentUuid": "tool", "output": {"content": "SELECT id FROM clean_jobs"}},
        ],
    })
    assert parsed["sql_text"] == "SELECT id FROM clean_jobs"


def test_tool_span_without_uuid_does_not_match_unrelated_llm_spans() -> None:
    parsed = run.extract_trace({
        "toolsCalled": [{"name": "query_clean_jobs"}],
        "toolSpans": [{"name": "query_clean_jobs", "parentUuid": "node", "output": {"content": "five jobs"}}],
        "llmSpans": [
            {"parentUuid": None, "output": {"content": "SELECT unrelated"}},
            {"parentUuid": "other-node", "output": {"content": "SELECT also unrelated"}},
        ],
    })
    assert parsed["sql_text"] is None


def test_malformed_trace_entries_never_become_sql_text() -> None:
    parsed = run.extract_trace({
        "toolsCalled": [{"name": "query_clean_jobs"}],
        "toolSpans": ["not-a-span", {"name": "query_clean_jobs", "parentUuid": "node", "output": {"content": "five jobs"}}],
        "llmSpans": ["not-a-span", {"parentUuid": "node"}, {"parentUuid": "node", "output": {"reasoning": "no content"}}],
    })
    assert parsed == {"tools_called": ["query_clean_jobs"], "sql_text": None, "tool_output": "five jobs"}


def test_tool_span_without_any_id_matches_no_root_llm_span() -> None:
    parsed = run.extract_trace({
        "toolsCalled": [{"name": "query_clean_jobs"}],
        "toolSpans": [{"name": "query_clean_jobs", "output": {"content": "five jobs"}}],
        "llmSpans": [{"parentUuid": None, "output": {"content": "SELECT unrelated"}}],
    })
    assert parsed["sql_text"] is None


def test_captured_sql_is_trimmed() -> None:
    parsed = run.extract_trace({
        "toolsCalled": [{"name": "query_clean_jobs"}],
        "toolSpans": [{"name": "query_clean_jobs", "uuid": "tool", "parentUuid": "node", "output": {"content": "five jobs"}}],
        "llmSpans": [{"parentUuid": "tool", "output": {"content": "  SELECT id FROM clean_jobs\n"}}],
    })
    assert parsed["sql_text"] == "SELECT id FROM clean_jobs"


def test_absent_sql_scores_zero_with_a_reason_rather_than_an_error() -> None:
    case = scenario("HLP-LIST-1")
    capture = {"question": case["input"], "answer": "Unknown.", "tools_called": ["query_clean_jobs"], "sql_text": None}
    row = run.score_turn(capture, case, ["sql_accuracy"], 0)[0]
    assert row["score"] == 0.0
    assert row["reason"] == "No generated SQL captured"
    assert "error" not in row


def test_tool_output_is_captured_whichever_tool_ran() -> None:
    parsed = run.extract_trace({
        "toolsCalled": [{"name": "get_job_details"}],
        "toolSpans": [{"name": "get_job_details", "parentUuid": "node", "output": {"content": "{'id': 1}"}}],
        "llmSpans": [],
    })
    assert parsed["tool_output"] == "{'id': 1}"


def test_turn_that_calls_no_tool_still_extracts() -> None:
    parsed = run.extract_trace({"toolsCalled": [], "toolSpans": [], "llmSpans": [{"output": {"content": "no tool needed"}}]})
    assert parsed == {"tools_called": [], "sql_text": None, "tool_output": None}


def test_missing_trace_is_not_scored_as_a_clean_capture() -> None:
    with pytest.raises(RuntimeError, match="No trace was captured"):
        run.extract_trace({})


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
    rows = report["by_metric"]["tool_correctness"]
    assert len(rows) == 4
    assert rows[-1]["reason"] == "UNRUN"


# --- The live capture path (issue #570) ---
#
# Everything below drives `capture_scenario` itself rather than replaying a
# capture around it. Tool discovery, the awaited factory call, and the resolved
# prompt bundle are the real ones; only the provider round trip and the DeepEval
# trace wait are stubbed, so the tests need no credential and no network.


def set_agent_v0(monkeypatch: pytest.MonkeyPatch, value: bool) -> None:
    """Flip `agent.agent_v0` in the cached settings, without touching the file.

    `v0_agent_enabled` and `create_job_mcp_server` read this one key, so the
    discovered surface follows the switch exactly as it does in serving. The
    checked-in file is left alone and the original mapping is restored by
    monkeypatch, so the rest of the suite is unaffected.
    """
    from src.core.config import settings

    config = copy.deepcopy(settings.config_yaml)
    config["agent"]["agent_v0"] = value
    monkeypatch.setattr(settings, "config_yaml", config)


def drive_live_capture(monkeypatch: pytest.MonkeyPatch, scenario_case: dict) -> dict[str, Any]:
    """Run the live capture path and record what it actually bound.

    `create_agent` is the composition seam the tool list passes through, so
    recording its keyword arguments observes the real binding without reaching
    into LangGraph internals for the compiled graph's shape.
    """
    from src.agents.runtime.prompts import resolve_prompt_bundle_async

    record: dict[str, Any] = {}
    built_agent = object()

    def fake_create_agent(**kwargs: Any) -> Any:
        record["factory_kwargs"] = kwargs
        return built_agent

    async def fake_capture_turn(agent: Any, question: str, _config: dict[str, Any]) -> dict[str, Any]:
        record["agent"] = agent
        record["bound_tool_names"] = sorted(tool.name for tool in record["factory_kwargs"]["tools"])
        return {"question": question, "answer": "stubbed answer", "tools_called": [], "sql_text": None, "tool_output": None}

    monkeypatch.setattr("src.agents.runtime.factory.create_agent", fake_create_agent)
    monkeypatch.setattr(run, "capture_turn", fake_capture_turn)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-not-a-real-key")  # never dispatched: no model call is made

    async def drive() -> list[dict[str, Any]]:
        return await run.capture_scenario(scenario_case, await resolve_prompt_bundle_async())

    record["turns"] = asyncio.run(drive())
    record["built_agent"] = built_agent
    return record


def test_live_capture_path_awaits_the_factory_and_binds_the_discovered_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    """`agent_factory` is a coroutine function; an un-awaited call binds a coroutine.

    The capture path used to bind one where a graph is expected, so every live
    scenario died on `'coroutine' object has no attribute 'ainvoke'` before a
    model was ever built. The bound tool list is asserted too, because fixing
    only the await turns the crash into a run whose model can never call the one
    tool the v0 prompt names.
    """
    record = drive_live_capture(monkeypatch, live_scenario())

    assert record["agent"] is record["built_agent"]
    assert not asyncio.iscoroutine(record["agent"])
    assert record["bound_tool_names"] == ["query_jobs"]
    assert len(record["turns"]) == 1


@pytest.mark.parametrize(
    ("agent_v0", "expected"),
    [
        (True, ["query_jobs"]),
        (False, ["get_job_details", "query_clean_jobs"]),
    ],
)
def test_live_capture_path_tool_surface_follows_the_bundle_switch(monkeypatch: pytest.MonkeyPatch, agent_v0: bool, expected: list[str]) -> None:
    """The same fix serves both bundle positions, so the rollback is rehearsed here too.

    Discovery is the only source of the tool list, so asserting it under both
    switch positions is what keeps the eval agent and its system prompt from
    diverging the way the served agent is prevented from diverging.
    """
    set_agent_v0(monkeypatch, agent_v0)

    record = drive_live_capture(monkeypatch, live_scenario())

    assert record["bound_tool_names"] == expected


def test_live_capture_path_without_a_credential_fails_on_the_secret_not_the_graph(monkeypatch: pytest.MonkeyPatch) -> None:
    """The missing credential must surface as a config error naming the variable.

    This is the credential-free way to reach the real factory. Before the fix the
    same command failed with `'coroutine' object has no attribute 'ainvoke'`,
    which is a type error rather than the missing secret it actually was.
    """
    from src.agents.runtime.prompts import resolve_prompt_bundle_async

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr("src.agents.runtime.provider.get_configured_secret", lambda _name: None)

    async def drive() -> None:
        await run.capture_scenario(live_scenario(), await resolve_prompt_bundle_async())

    with pytest.raises(ValueError, match="DEEPSEEK_API_KEY is unset"):
        asyncio.run(drive())
