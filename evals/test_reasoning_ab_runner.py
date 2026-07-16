from pathlib import Path

import pytest

from scripts import run_scenario_matrix as runner


def test_reasoning_ab_config_declares_two_arms():
    assert runner.configured_arm_efforts() == {
        "baseline": "default",
        "none": "none",
    }


def test_filter_and_checkpoint_path_are_independent(tmp_path: Path):
    scenarios = runner.load_scenarios()
    selected = runner.filter_scenarios(scenarios, ids="B1,C1")
    assert [scenario["id"] for scenario in selected] == ["B1", "C1"]

    first = tmp_path / "reasoning_ab_baseline.observed.json"
    second = tmp_path / "reasoning_ab_low.observed.json"
    runner.save_checkpoint({"B1": ["answer"]}, first)
    runner.save_checkpoint({"C1": ["answer"]}, second)
    assert runner.load_checkpoint(first) == {"B1": ["answer"]}
    assert runner.load_checkpoint(second) == {"C1": ["answer"]}


def test_validate_arm_rejects_mismatched_config(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setitem(runner.settings.config_yaml["agent"]["react"], "reasoning_effort", "low")
    with pytest.raises(SystemExit, match="does not match"):
        runner.validate_arm("baseline")
