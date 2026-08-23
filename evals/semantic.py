"""DeepEval-backed semantic grading for persisted conversational evidence."""

from __future__ import annotations

import json
from typing import Any

from deepeval.metrics import ConversationalGEval
from deepeval.test_case import MultiTurnParams, Turn
from deepeval.test_case.conversational_test_case import ConversationalTestCase

from evals.judge import build_judge
from evals.models import SemanticJudgeResult

AVAILABLE = "AVAILABLE"
UNAVAILABLE = "UNAVAILABLE"


def semantic_assertion(scenario: dict[str, Any]) -> dict[str, Any] | None:
    """Return the registry-owned semantic assertion, if the scenario has one."""
    for assertion in (scenario.get("grading") or {}).get("assertions", []):
        if assertion.get("type") == "semantic":
            return assertion
    return None


def build_conversation(repeat: dict[str, Any]) -> ConversationalTestCase:
    """Rebuild every completed exchange, not merely the final answer."""
    turns: list[Turn] = []
    for recorded_turn in repeat["turns"]:
        seams = recorded_turn.get("seams") or {}
        question = seams.get("question")
        answer = seams.get("answer")
        if not isinstance(question, str) or not isinstance(answer, str):
            raise ValueError("completed turn is missing a question or answer")
        turns.extend(
            (
                Turn(role="user", content=question),
                Turn(role="assistant", content=answer),
            )
        )
    return ConversationalTestCase(turns=turns)


def _criteria(scenario: dict[str, Any]) -> str:
    assertion = semantic_assertion(scenario)
    if assertion is None:
        raise ValueError("scenario has no semantic assertion")
    return "\n".join(
        (
            "Evaluate whether the assistant satisfies this semantic behavior requirement.",
            "Use the complete conversation, not only its final response.",
            "Do not score tool choice, SQL, formatting, or facts outside this requirement.",
            f"Expected behavior: {scenario['expected']}",
            f"Semantic assertion: {json.dumps(assertion, ensure_ascii=False)}",
        )
    )


def evaluate_semantic_repeat(
    scenario: dict[str, Any], repeat: dict[str, Any]
) -> SemanticJudgeResult | None:
    """Measure one semantic assertion, keeping provider failures rerunnable."""
    if semantic_assertion(scenario) is None:
        return None
    try:
        metric = ConversationalGEval(
            name="Semantic Behavior",
            criteria=_criteria(scenario),
            evaluation_params=[MultiTurnParams.CONTENT],
            model=build_judge(),
            async_mode=False,
        )
        metric.measure(build_conversation(repeat))
        return SemanticJudgeResult(
            AVAILABLE,
            float(metric.score),
            None,
            str(getattr(metric, "reason", "No judge rationale returned.")),
        )
    except Exception as exc:  # noqa: BLE001 - a failed judge pass must remain retryable.
        return SemanticJudgeResult(
            UNAVAILABLE, None, None, f"DeepEval unavailable: {exc}"
        )
