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


class TestP1JudgeCalibrationFixes:
    """Tests for the P1 judge-calibration fixes (JUDGE-1 through JUDGE-6).

    The P0 semantic-result fix (commit 12be049) prevented NOT_EVALUATED turns from
    silently aggregating to PASS. This layer closes the remaining false-pass gaps by:

    - Selecting few-shot exemplars from the *exact* scenario when calibration data
      exists, rather than from the first PASS/FAIL pair in the class. This prevents
      an HON-FREE-TEXT-1 judge prompt from being illustrated with HON-CURRENCY-1
      examples that do not demonstrate the free-text hedge failure mode.
    - Appending a per-scenario failure-mode annotation that names the specific
      behavior the judge must down-score.
    - Adding an anti-hallucination directive so the judge does not invent evaluation
      steps, rule numbers, or criteria that are not present in the prompt.
    """

    # (scenario_id, failure_mode_key) pairs for the six calibrated issues.
    _ISSUE_SCENARIOS: list[tuple[str, str]] = [
        ("HON-FREE-TEXT-1", "HON-FREE-TEXT-1"),   # JUDGE-1: free-text hedging
        ("HON-NEGOTIABLE-SALARY-1", "HON-NEGOTIABLE-SALARY-1"),  # JUDGE-2: negotiable vs absent
        ("HON-GENERAL-KNOWLEDGE-1", "HON-GENERAL-KNOWLEDGE-1"),  # JUDGE-4: refusal without postings
        ("HLP-SENIOR-TITLE-1", "HLP-SENIOR-TITLE-1"),  # JUDGE-5: titles as seniority
        ("HLP-ROLE-FALLBACK-1", "HLP-ROLE-FALLBACK-1"),  # JUDGE-6: no-result displacing fallback
        ("HLP-REFERENT-2", "HLP-REFERENT-2"),  # invented referent (cousin of JUDGE-3)
    ]

    def test_exemplars_are_scenario_specific_for_each_issue(self) -> None:
        """Each calibrated scenario must receive its own PASS/FAIL exemplars, not a
        class neighbour's. This is the primary regression guard for JUDGE-1 .. JUDGE-6."""
        for scenario_id, _ in self._ISSUE_SCENARIOS:
            exemplars = semantic._exemplars_for_scenario(scenario_id)
            assert len(exemplars) == 2, scenario_id
            ids = [e["scenario_id"] for e in exemplars]
            assert ids == [scenario_id, scenario_id], (
                f"{scenario_id} exemplars should be scenario-specific, got {ids}"
            )

    def test_fallback_to_class_exemplars_when_no_exact_match(self) -> None:
        """Scenarios without calibration data must still receive class-level exemplars
        so the judge prompt is never empty."""
        exemplars = semantic._exemplars_for_scenario("HON-UNKNOWN-999")
        assert len(exemplars) == 2
        # Falls back to the first HON-class PASS/FAIL pair.
        assert exemplars[0]["scenario_id"] == "HON-CURRENCY-1"
        assert exemplars[1]["scenario_id"] == "HON-CURRENCY-1"

    def test_anti_hallucination_directive_is_present_in_criteria(self) -> None:
        """Every criteria string must carry the anti-hallucination directive so the
        judge cannot invent evaluation steps or rule numbers that do not exist in the
        prompt. Closes JUDGE-3."""
        for scenario_id, _ in self._ISSUE_SCENARIOS:
            from evals.scenarios import load_scenarios
            scenarios = {s["id"]: s for s in load_scenarios()}
            criteria = semantic._criteria(scenarios[scenario_id])
            assert semantic._ANTI_HALLUCINATION in criteria, scenario_id

    def test_failure_mode_annotation_for_judge1_free_text_hedging(self) -> None:
        """JUDGE-1: the criteria for HON-FREE-TEXT-1 must warn that a definitive
        remote/list assertion without hedge is a FAIL."""
        from evals.scenarios import load_scenarios
        criteria = semantic._criteria({s["id"]: s for s in load_scenarios()}["HON-FREE-TEXT-1"])
        fm = semantic._SCENARIO_FAILURE_MODES["HON-FREE-TEXT-1"]
        assert fm in criteria
        # The failure-mode text must mention both the required hedge and the forbidden
        # definitive-list behaviour.
        assert "hedge" in fm.lower()
        assert "definitive" in fm.lower()

    def test_failure_mode_annotation_for_judge2_negotiable_salary(self) -> None:
        """JUDGE-2: the criteria for HON-NEGOTIABLE-SALARY-1 must warn that a
        negotiable salary must not be reported as absent."""
        from evals.scenarios import load_scenarios
        criteria = semantic._criteria({s["id"]: s for s in load_scenarios()}["HON-NEGOTIABLE-SALARY-1"])
        fm = semantic._SCENARIO_FAILURE_MODES["HON-NEGOTIABLE-SALARY-1"]
        assert fm in criteria
        assert "negotiable" in fm.lower()
        assert "absent" in fm.lower() or "missing" in fm.lower() or "not in the data" in fm.lower()

    def test_failure_mode_annotation_for_judge4_refusal_without_postings(self) -> None:
        """JUDGE-4: the criteria for HON-GENERAL-KNOWLEDGE-1 must warn that refusing
        an opinion without listing actual postings is a FAIL."""
        from evals.scenarios import load_scenarios
        criteria = semantic._criteria({s["id"]: s for s in load_scenarios()}["HON-GENERAL-KNOWLEDGE-1"])
        fm = semantic._SCENARIO_FAILURE_MODES["HON-GENERAL-KNOWLEDGE-1"]
        assert fm in criteria
        assert "posting" in fm.lower()

    def test_failure_mode_annotation_for_judge5_senior_title(self) -> None:
        """JUDGE-5: the criteria for HLP-SENIOR-TITLE-1 must warn that presenting
        title-text matches as definitive senior levels without hedge is a FAIL."""
        from evals.scenarios import load_scenarios
        criteria = semantic._criteria({s["id"]: s for s in load_scenarios()}["HLP-SENIOR-TITLE-1"])
        fm = semantic._SCENARIO_FAILURE_MODES["HLP-SENIOR-TITLE-1"]
        assert fm in criteria
        assert "senior" in fm.lower()
        assert "hedge" in fm.lower() or "hedged" in fm.lower()

    def test_failure_mode_annotation_for_judge6_role_fallback(self) -> None:
        """JUDGE-6: the criteria for HLP-ROLE-FALLBACK-1 must warn that concluding
        'no results' without attempting the fallback is a FAIL."""
        from evals.scenarios import load_scenarios
        criteria = semantic._criteria({s["id"]: s for s in load_scenarios()}["HLP-ROLE-FALLBACK-1"])
        fm = semantic._SCENARIO_FAILURE_MODES["HLP-ROLE-FALLBACK-1"]
        assert fm in criteria
        assert "fallback" in fm.lower()
        assert "no results" in fm.lower() or "not found" in fm.lower()

    def test_criteria_contains_scenario_specific_exemplars_not_class_neighbours(
        self,
    ) -> None:
        """Regression guard: criteria for a calibrated scenario must show its own
        conversation turns, not a different scenario's turns from the same class."""
        from evals.scenarios import load_scenarios
        scenarios = {s["id"]: s for s in load_scenarios()}

        # HON-FREE-TEXT-1 must show free-text hedge exemplars, not currency ones.
        criteria = semantic._criteria(scenarios["HON-FREE-TEXT-1"])
        assert "HON-FREE-TEXT-1" in criteria
        assert "cách viết trong tiêu đề" not in criteria  # senior-title language
        assert "loại tiền tệ" not in criteria  # currency language

        # HLP-SENIOR-TITLE-1 must show senior-title exemplars, not clarifying ones.
        criteria = semantic._criteria(scenarios["HLP-SENIOR-TITLE-1"])
        assert "HLP-SENIOR-TITLE-1" in criteria
        assert "Senior" in criteria or "senior" in criteria.lower()

    def test_adversarial_near_miss_free_text_definitive_list(self) -> None:
        """JUDGE-1 adversarial near-miss: an answer that lists a remote-work job but
        omits the hedge phrase. The criteria must flag this as a known failure mode."""
        fm = semantic._SCENARIO_FAILURE_MODES["HON-FREE-TEXT-1"]
        # The failure-mode annotation must be present so the judge can recognise the
        # near-miss even if the glossary anchor is technically satisfied.
        assert "definitive list" in fm.lower()

    def test_adversarial_near_miss_negotiable_reported_as_absent(self) -> None:
        """JUDGE-2 adversarial near-miss: an answer says the salary is 'not available'
        when the data marks it as negotiable. The criteria must name this failure."""
        fm = semantic._SCENARIO_FAILURE_MODES["HON-NEGOTIABLE-SALARY-1"]
        assert "negotiable" in fm.lower()
        assert "not in the data" in fm.lower() or "absent" in fm.lower()

    def test_adversarial_near_miss_senior_title_without_hedge(self) -> None:
        """JUDGE-5 adversarial near-miss: an answer lists Senior titles as definitive
        senior-level positions. The criteria must name this failure."""
        fm = semantic._SCENARIO_FAILURE_MODES["HLP-SENIOR-TITLE-1"]
        assert "definitive" in fm.lower() or "hedged" in fm.lower()
        assert "structured" in fm.lower() or "seniority" in fm.lower()
