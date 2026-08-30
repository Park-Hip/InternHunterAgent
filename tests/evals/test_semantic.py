from __future__ import annotations

import pytest

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


def _criteria_scenario(scenario_class: str) -> dict:
    return {
        "id": f"{scenario_class}-SYNTHETIC-1",
        "expected": "synthetic expected behavior",
        "grading": {
            "assertions": [
                {"type": "semantic", "required_any": [{"lexicon": ["synthetic"]}]}
            ]
        },
    }


@pytest.mark.parametrize("scenario_class", ["SAF", "HON", "HLP"])
def test_criteria_carries_class_rubric_exemplars_and_anti_fabrication(
    scenario_class: str,
) -> None:
    criteria = semantic._criteria(_criteria_scenario(scenario_class))

    assert semantic._CLASS_RUBRICS[scenario_class] in criteria
    assert semantic._ANTI_FABRICATION in criteria
    assert "Few-shot exemplars:" in criteria
    assert "Exemplar (PASS):" in criteria
    assert "Exemplar (FAIL):" in criteria


def test_criteria_exemplars_are_drawn_only_from_the_scenario_class() -> None:
    criteria = semantic._criteria(_criteria_scenario("HLP"))

    assert "scenario: HLP-" in criteria
    assert "scenario: HON-" not in criteria
    assert "scenario: SAF-" not in criteria
