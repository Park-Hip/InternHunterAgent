from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_scenario_matrix


PROBE_TRUE_IDS = {
    "C1",
    "C2",
    "C3",
    "C4",
    "C5",
    "C7",
    "D1",
    "D2",
    "D3",
    "M-G10",
    "M-G26d",
    "M-G29",
    "M-G44",
    "M-D4",
    "M-D3c",
}


def test_scenarios_v1_yaml_loads_and_matches_self_check() -> None:
    scenarios = run_scenario_matrix.load_scenarios()

    assert len(scenarios) == 29

    probe_true_ids = {scenario["id"] for scenario in scenarios if scenario["probe"]}
    assert len(probe_true_ids) == 15
    assert probe_true_ids == PROBE_TRUE_IDS

    conversational = {scenario["id"]: scenario for scenario in scenarios if scenario["type"] == "conversational"}
    assert set(conversational) == {"B1", "B2"}
    assert conversational["B1"]["turns"] == ["Which jobs need Python?", "Only the ones in Hanoi."]
    assert conversational["B2"]["turns"] == ["Show me the AI Engineer jobs.", "Which of those are internships?"]

    for scenario in scenarios:
        assert scenario["expected"]
        assert scenario["group"]
        if scenario["type"] == "single":
            assert scenario["input"]
            assert "turns" not in scenario
        else:
            assert scenario["turns"]
            assert "input" not in scenario


def test_repeat_count_uses_probe_flag() -> None:
    assert run_scenario_matrix.repeat_count({"probe": True}) == 3
    assert run_scenario_matrix.repeat_count({"probe": False}) == 2
