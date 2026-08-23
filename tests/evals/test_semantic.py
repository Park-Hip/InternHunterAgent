from __future__ import annotations

from evals import semantic


def _scenario() -> dict:
    return {
        "id": "HLP-CONTEXT-1",
        "expected": "Keep the earlier Python filter when adding Hanoi.",
        "grading": {
            "assertions": [
                {"type": "semantic", "required_any": [{"lexicon": ["Python"]}]}
            ]
        },
    }


def _repeat() -> dict:
    return {
        "turns": [
            {"seams": {"question": "Python jobs?", "answer": "I found Python jobs."}},
            {
                "seams": {
                    "question": "Only Hanoi.",
                    "answer": "I kept Python and added Hanoi.",
                }
            },
        ]
    }


def test_semantic_repeat_uses_deepevals_conversational_metric_and_all_turns(
    monkeypatch,
) -> None:
    observed = {}

    class Metric:
        score = 0.8
        reason = "The second answer retains the first constraint."

        def __init__(self, **kwargs) -> None:
            observed["kwargs"] = kwargs

        def measure(self, conversation) -> None:
            observed["conversation"] = conversation

    monkeypatch.setattr(semantic, "ConversationalGEval", Metric)
    monkeypatch.setattr(semantic, "build_judge", lambda: "independent-judge")

    result = semantic.evaluate_semantic_repeat(_scenario(), _repeat())

    assert result is not None
    assert result.status == semantic.AVAILABLE
    assert result.score == 0.8
    assert len(observed["conversation"].turns) == 4
    assert observed["kwargs"]["model"] == "independent-judge"


def test_semantic_provider_failure_is_explicitly_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(
        semantic, "build_judge", lambda: (_ for _ in ()).throw(RuntimeError("quota"))
    )

    result = semantic.evaluate_semantic_repeat(_scenario(), _repeat())

    assert result is not None
    assert result.status == semantic.UNAVAILABLE
    assert "quota" in result.rationale
