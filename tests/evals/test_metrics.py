"""Credential-free metric construction and field adaptation."""

from deepeval.metrics import ToolCorrectnessMetric

from evals.metrics import LEGACY_METRICS, METRICS, NO_JUDGE, ToolExpectation, MetricKind, judge_case, metric, not_applicable_reason, tool_case, tool_expectation


def test_registry() -> None:
    # Four capture-time metrics and two v0-gate metrics, plus the pair retired for
    # the governed path by the Stage 4 decision.
    assert len(METRICS) == 8
    assert {m.name for m in METRICS if m.kind == MetricKind.DETERMINISTIC} == {
        "tool_correctness",
        "sql_accuracy",
        "plan_correctness",
        "result_equivalence",
    }
    assert LEGACY_METRICS == {"sql_accuracy", "memory"}
    assert LEGACY_METRICS <= {m.name for m in METRICS}


def test_tool_metric_never_calls_provider() -> None:
    capture = {"question": "Jobs?", "answer": "One", "tools_called": ["query_clean_jobs"]}
    case = {"expected_tools": ["query_clean_jobs"]}
    measure = ToolCorrectnessMetric(model=NO_JUDGE, async_mode=False)
    measure.measure(tool_case(capture, case, 0), _show_indicator=False)
    assert measure.score == 1.0


def test_rubric_comes_from_dataset_not_scenario_id() -> None:
    capture = {"question": "Hello", "answer": "world", "conversation_history": []}
    scenario = {"id": "arbitrary", "expected": "world", "rubric": "Say hello"}
    _, params, criteria = judge_case(capture, scenario, metric("rubric"))
    assert "Say hello" in criteria
    assert len(params) == 3


def test_turn_expectation_wins_over_expected_tools() -> None:
    scenario = {"expected_tools": ["query_clean_jobs"], "turn_tool_expectations": [{"required": ["get_job_details"], "allowed": ["query_clean_jobs", "get_job_details"]}]}
    assert tool_expectation(scenario, 0) == ToolExpectation(("get_job_details",), ("query_clean_jobs", "get_job_details"))


def test_scenario_override_applies_to_every_turn() -> None:
    scenario = {"expected_tools": ["query_clean_jobs"], "tool_expectation": {"required": [], "allowed": ["query_clean_jobs"]}}
    assert tool_expectation(scenario, 0) == ToolExpectation((), ("query_clean_jobs",))


def test_expected_tools_are_the_fallback_contract() -> None:
    assert tool_expectation({"expected_tools": ["query_clean_jobs"]}, 0) == ToolExpectation(("query_clean_jobs",), ("query_clean_jobs",))


def test_grounded_is_not_applicable_without_tool_output() -> None:
    assert not_applicable_reason({"question": "q", "answer": "a"}, metric("grounded")) is not None
    assert not_applicable_reason({"question": "q", "answer": "a", "tool_output": "{}"}, metric("grounded")) is None
    assert not_applicable_reason({"question": "q", "answer": "a"}, metric("rubric")) is None
