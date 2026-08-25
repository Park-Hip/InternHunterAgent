"""No-network unit test for `evals/judge.py`'s config-to-model wiring.

Constructing `ChatOpenAI` with a dummy key does not hit the network (the key
is only validated on invoke), so this runs in the plain suite alongside
`test_writeback.py`, not gated behind the `eval` marker.
"""

from __future__ import annotations

import pytest
from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, SingleTurnParams

from evals.judge import build_judge
from src.core.config import settings


def test_build_judge_targets_openrouter_base_url(monkeypatch):
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "dummy-key")
    monkeypatch.setattr(
        settings,
        "config_yaml",
        {
            "eval": {
                "judge": {
                    "provider": "openrouter",
                    "model": "ox-alpha",
                    "temperature": 0.0,
                    "rpm": 20,
                }
            }
        },
    )

    judge = build_judge()

    assert judge.get_model_name() == "openrouter/ox-alpha"
    assert str(judge._chat_model.openai_api_base).rstrip("/") == "https://openrouter.ai/api/v1"
    assert judge._throttle._rpm == 20


def test_build_judge_fails_loud_without_openrouter_key(monkeypatch):
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", None)
    monkeypatch.setattr(
        settings,
        "config_yaml",
        {"eval": {"judge": {"provider": "openrouter", "model": "ox-alpha"}}},
    )

    with pytest.raises(ValueError, match="OPENROUTER_API_KEY is unset"):
        build_judge()


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
