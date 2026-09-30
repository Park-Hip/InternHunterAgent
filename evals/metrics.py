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


@dataclass(frozen=True)
class ToolExpectation:
    """The tools a turn must call, and the tools it is allowed to call."""

    required: tuple[str, ...]
    allowed: tuple[str, ...]


# Metrics for the governed v0 path. Both are credential-free and are the CI gate.
# `plan_correctness` grades the criteria the core applied against the case's reviewed
# plan; `result_equivalence` grades the rows, aggregates, total, answer state, and
# evidence labels against the case's golden. Neither asks a model anything, because
# the governed path compiles a typed plan rather than a SQL string.
V0_METRICS = (
    MetricSpec(
        "plan_correctness",
        MetricKind.DETERMINISTIC,
        "The core applied the reviewed filters, resolved the same way.",
        ("applied", "expected_filters"),
    ),
    MetricSpec(
        "result_equivalence",
        MetricKind.DETERMINISTIC,
        "The rows, aggregates, total, state, and evidence labels are the reviewed ones.",
        ("result", "golden"),
    ),
)

# Retired for the governed path by the Stage 4 decision (#487): there is no SQL path
# to score, and a typed plan is never compared to a SQL string. They stay for the v1
# replays, and a v0 case may not declare them.
LEGACY_METRICS = frozenset({"sql_accuracy", "memory"})

METRICS = (
    MetricSpec("tool_correctness", MetricKind.DETERMINISTIC, "Required tools were called, with no unexpected tools.", ("tools_called", "expected_tools")),
    MetricSpec("sql_accuracy", MetricKind.DETERMINISTIC, "SQL returns the reference result on the fixture.", ("sql_text", "reference_sql")),
    MetricSpec("grounded", MetricKind.JUDGE, "Judge whether the answer is supported by the retrieved tool output without invented facts.", ("question", "answer", "retrieval_context")),
    MetricSpec("on_topic", MetricKind.JUDGE, "Judge whether the answer responds to the user's question and constraints.", ("question", "answer")),
    MetricSpec("memory", MetricKind.JUDGE, "Judge whether the answer correctly uses the previous conversation turns and their constraints.", ("question", "answer", "conversation_history")),
    MetricSpec("rubric", MetricKind.JUDGE, "Judge the answer against this scenario's rubric.", ("question", "answer", "rubric")),
)
METRICS = METRICS + V0_METRICS
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


def not_applicable_reason(capture: dict, spec: MetricSpec) -> str | None:
    """Why the captured turn cannot be scored for this metric, or None."""
    if "retrieval_context" in spec.required_fields and not capture.get("tool_output"):
        return "no tool output was captured, so there is no retrieval context to ground the answer in"
    return None


def judge_case(capture: dict, scenario: dict, spec: MetricSpec) -> tuple[LLMTestCase, list[SingleTurnParams], str]:
    """Adapt a captured turn to precisely the inputs declared by the metric."""
    fields = set(spec.required_fields)
    question = capture["question"]
    if "conversation_history" in fields:
        question = f"Conversation so far: {capture.get('conversation_history', [])}\nCurrent question: {question}"
    kwargs = {"input": question, "actual_output": capture["answer"]}
    if "retrieval_context" in fields:
        kwargs["retrieval_context"] = [capture["tool_output"]]
    criteria = spec.criteria
    if "rubric" in fields:
        criteria += f" Scenario rubric: {scenario['rubric']}"
        kwargs["expected_output"] = scenario["expected"]
    params = list(dict.fromkeys(PARAMETERS[field] for field in spec.required_fields))
    return LLMTestCase(**kwargs), params, criteria


def tool_expectation(scenario: dict, turn_index: int) -> ToolExpectation:
    """Resolve a turn's tool contract: the per-turn declaration wins, then the
    scenario-level override, then the scenario's expected tools."""
    per_turn = scenario.get("turn_tool_expectations")
    if per_turn:
        declared: dict = per_turn[turn_index]
    elif scenario.get("tool_expectation"):
        declared = scenario["tool_expectation"]
    else:
        declared = {"required": scenario.get("expected_tools", [])}
    required = tuple(declared.get("required", ()))
    return ToolExpectation(required, tuple(declared["allowed"]) if "allowed" in declared else required)


def tool_case(capture: dict, scenario: dict, turn_index: int) -> LLMTestCase:
    required = tool_expectation(scenario, turn_index).required
    return LLMTestCase(
        input=capture["question"], actual_output=capture["answer"],
        tools_called=[ToolCall(name=name) for name in capture["tools_called"]],
        expected_tools=[ToolCall(name=name) for name in required],
    )
