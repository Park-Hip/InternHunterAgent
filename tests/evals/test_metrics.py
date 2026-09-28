"""Credential-free metric construction and field adaptation."""

from deepeval.metrics import ToolCorrectnessMetric

from evals.metrics import METRIC_BY_NAME, METRICS, MetricKind, NO_JUDGE, judge_case, tool_case


def test_registry() -> None:
    assert len(METRICS) == 6
    assert {m.name for m in METRICS if m.kind == MetricKind.DETERMINISTIC} == {"tool_correctness", "sql_accuracy"}


def test_tool_metric_never_calls_provider() -> None:
    capture = {"question": "Jobs?", "answer": "One", "tools_called": ["query_clean_jobs"]}
    case = {"expected_tools": ["query_clean_jobs"]}
    measure = ToolCorrectnessMetric(model=NO_JUDGE, async_mode=False)
    measure.measure(tool_case(capture, case, 0), _show_indicator=False)
    assert measure.score == 1.0


def test_rubric_comes_from_dataset_not_scenario_id() -> None:
    capture = {"question": "Hello", "answer": "world", "conversation_history": []}
    scenario = {"id": "arbitrary", "expected": "world", "rubric": "Say hello"}
    _, params, criteria = judge_case(capture, scenario, METRIC_BY_NAME["rubric"])
    assert "Say hello" in criteria
    assert len(params) == 3
