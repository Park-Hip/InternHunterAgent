"""No-network unit test for `evals/judge.py`'s config-to-model wiring.

Constructing `ChatGoogleGenerativeAI` with a dummy key does not hit the
network (the key is only validated on invoke), so this runs in the plain
suite alongside `test_writeback.py`, not gated behind the `eval` marker.
"""

from __future__ import annotations

import pytest
from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, SingleTurnParams

from evals.judge import build_judge
from src.core.config import settings


def test_build_judge_forwards_thinking_budget_for_google(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "dummy-key")
    monkeypatch.setattr(
        settings,
        "config_yaml",
        {
            "eval": {
                "judge": {
                    "provider": "google",
                    "model": "gemini-2.5-flash",
                    "temperature": 0.0,
                    "rpm": 8,
                    "thinking_budget": 0,
                }
            }
        },
    )

    judge = build_judge()

    assert judge._chat_model.thinking_budget == 0


@pytest.mark.eval
def test_judge_scaffold() -> None:
    test_case = LLMTestCase(
        input="Say hello to a new user.",
        actual_output="Hi there! It's great to have you here.",
    )
    metric = GEval(
        name="PoliteGreeting",
        criteria="Is the output a polite greeting? Score 0-1.",
        evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
        model=build_judge(),
        threshold=0.05,
    )
    assert_test(test_case, [metric])
