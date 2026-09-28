"""Declared metrics and their required capture fields."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from deepeval.models.base_model import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCase, SingleTurnParams, ToolCall


class MetricKind(Enum):
    DETERMINISTIC = "deterministic"
    JUDGE = "judge"


@dataclass(frozen=True)
class MetricSpec:
    name: str
    kind: MetricKind
    criteria: str
    required_fields: tuple[str, ...] = ()


METRICS = (
    MetricSpec("tool_correctness", MetricKind.DETERMINISTIC, "Required tools were called, with no unexpected tools.", ("tools_called", "expected_tools")),
    MetricSpec("sql_accuracy", MetricKind.DETERMINISTIC, "SQL returns the reference result on the fixture.", ("sql_text", "reference_sql")),
    MetricSpec("grounded", MetricKind.JUDGE, "Judge whether the answer is supported by the retrieved tool output without invented facts.", ("question", "answer", "retrieval_context")),
    MetricSpec("on_topic", MetricKind.JUDGE, "Judge whether the answer responds to the user's question and constraints.", ("question", "answer")),
    MetricSpec("memory", MetricKind.JUDGE, "Judge whether the answer correctly uses the previous conversation turns and their constraints.", ("question", "answer", "conversation_history")),
    MetricSpec("rubric", MetricKind.JUDGE, "Judge the answer against this scenario's rubric.", ("question", "answer", "rubric")),
)
METRIC_BY_NAME = {spec.name: spec for spec in METRICS}


def metric(name: str) -> MetricSpec:
    try:
        return METRIC_BY_NAME[name]
    except KeyError:
        raise ValueError(f"Unknown metric {name!r}; available: {', '.join(METRIC_BY_NAME)}") from None


class NoJudge(DeepEvalBaseLLM):
    """Explicit model handle that fails closed if a deterministic check calls a judge."""

    def load_model(self):
        return self

    def generate(self, prompt: str) -> str:
        raise AssertionError("Deterministic metric must not invoke a judge")

    async def a_generate(self, prompt: str) -> str:
        raise AssertionError("Deterministic metric must not invoke a judge")

    def get_model_name(self) -> str:
        return "offline-no-judge"


NO_JUDGE = NoJudge(model="offline-no-judge")


PARAMETERS = {
    "question": SingleTurnParams.INPUT,
    "answer": SingleTurnParams.ACTUAL_OUTPUT,
    "retrieval_context": SingleTurnParams.RETRIEVAL_CONTEXT,
    "rubric": SingleTurnParams.EXPECTED_OUTPUT,
    "conversation_history": SingleTurnParams.INPUT,
}


def judge_case(capture: dict, scenario: dict, spec: MetricSpec) -> tuple[LLMTestCase, list[SingleTurnParams], str]:
    """Adapt a captured turn to precisely the inputs declared by the metric."""
    fields = set(spec.required_fields)
    question = capture["question"]
    if "conversation_history" in fields:
        question = f"Conversation so far: {capture.get('conversation_history', [])}\nCurrent question: {question}"
    kwargs = {"input": question, "actual_output": capture["answer"]}
    if "retrieval_context" in fields:
        kwargs["retrieval_context"] = [capture["tool_output"]] if capture.get("tool_output") else ["No tool result was captured."]
    criteria = spec.criteria
    if "rubric" in fields:
        criteria += f" Scenario rubric: {scenario['rubric']}"
        kwargs["expected_output"] = scenario["expected"]
    params = list(dict.fromkeys(PARAMETERS[field] for field in spec.required_fields))
    return LLMTestCase(**kwargs), params, criteria


def tool_case(capture: dict, scenario: dict, turn_index: int) -> LLMTestCase:
    expectation = scenario.get("turn_tool_expectations")
    required = expectation[turn_index]["required"] if expectation else scenario.get("expected_tools", [])
    return LLMTestCase(
        input=capture["question"], actual_output=capture["answer"],
        tools_called=[ToolCall(name=name) for name in capture["tools_called"]],
        expected_tools=[ToolCall(name=name) for name in required],
    )
