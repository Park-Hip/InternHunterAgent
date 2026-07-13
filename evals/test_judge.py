"""No-network unit test for `evals/judge.py`'s config-to-model wiring.

Constructing `ChatGoogleGenerativeAI` with a dummy key does not hit the
network (the key is only validated on invoke), so this runs in the plain
suite alongside `test_writeback.py`, not gated behind the `eval` marker.
"""

from __future__ import annotations

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
