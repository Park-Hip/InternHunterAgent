"""Offline tests for evals.datasets — dataset registry and scenario grammar.

No network calls, no provider credentials, no database required.
"""

from __future__ import annotations

import pytest
import yaml

from evals.datasets import DATASETS_DIR, DatasetSpec, dataset, default_dataset_name, list_datasets


class TestDatasetSpec:
    def test_default_dataset_exists(self) -> None:
        path = DATASETS_DIR / "scenarios.yaml"
        assert path.exists()

    def test_load_default_scenarios(self) -> None:
        spec = dataset("default")
        scenarios = spec.scenarios()
        assert len(scenarios) == 50

    def test_scenario_has_required_fields(self) -> None:
        spec = dataset("default")
        for s in spec.scenarios():
            assert "id" in s
            assert s.get("input") or s.get("turns")
            assert s.get("language", "vi") in {"vi", "en"}
            assert "metrics" in s

    def test_scenario_ids_are_unique(self) -> None:
        spec = dataset("default")
        ids = [s["id"] for s in spec.scenarios()]
        assert len(ids) == len(set(ids))

    def test_metrics_match_available_evidence(self) -> None:
        for scenario in dataset("default").scenarios():
            assert ("sql_accuracy" in scenario["metrics"]) == bool(scenario.get("reference_sql"))
            assert ("memory" in scenario["metrics"]) == (scenario["type"] == "conversational")
            assert isinstance(scenario["rubric"], str) and scenario["rubric"]


def write_dataset(tmp_path, *scenarios) -> DatasetSpec:
    path = tmp_path / "scenarios.yaml"
    path.write_text(yaml.safe_dump(list(scenarios), allow_unicode=True), encoding="utf-8")
    return DatasetSpec(path)


def write_governed_dataset(tmp_path, *scenarios) -> DatasetSpec:
    """A dataset whose file name makes it governed, so is_v0 is true."""
    path = tmp_path / "v0_cases.yaml"
    path.write_text(yaml.safe_dump(list(scenarios), allow_unicode=True), encoding="utf-8")
    return DatasetSpec(path)


def test_unread_tool_key_is_rejected(tmp_path) -> None:
    spec = write_dataset(tmp_path, {"id": "X-1", "input": "q", "expected": "a", "metrics": ["tool_correctness"], "tool_expectations": {"required": []}})
    with pytest.raises(ValueError, match="unread tool key"):
        spec.scenarios()


def test_turn_expectation_must_cover_every_turn(tmp_path) -> None:
    spec = write_dataset(tmp_path, {"id": "X-1", "turns": ["a", "b"], "expected": "a", "metrics": ["tool_correctness"], "turn_tool_expectations": [{"required": [], "allowed": []}]})
    with pytest.raises(ValueError, match="1 of 2 turns"):
        spec.scenarios()


def test_tool_expectation_fields_are_lists(tmp_path) -> None:
    spec = write_dataset(tmp_path, {"id": "X-1", "input": "q", "expected": "a", "metrics": ["tool_correctness"], "tool_expectation": {"required": [], "allowed": "query_clean_jobs"}})
    with pytest.raises(ValueError, match="must list allowed tools"):
        spec.scenarios()


class TestGovernedToolContract:
    """#585: a governed case that declares no tool contract must not load.

    An absent declaration resolves to "nothing required, nothing allowed", which
    inverts tool_correctness: a correct call scores 0.0 and a turn that called
    nothing scores 1.0. The replay registry is not governed and keeps its
    permissive default, so these cases name the v0 file only.
    """

    def test_missing_tool_contract_is_rejected(self, tmp_path) -> None:
        spec = write_governed_dataset(tmp_path, {"id": "X-1", "input": "q", "expected": "a", "metrics": ["tool_correctness"]})
        with pytest.raises(ValueError, match="declares no tool contract"):
            spec.scenarios()

    def test_an_empty_expected_tools_list_is_still_no_declaration(self, tmp_path) -> None:
        # `expected_tools: []` is falsy, so it resolves exactly like an absent
        # key. Treating it as a declaration would reopen the inversion through
        # the same door.
        spec = write_governed_dataset(tmp_path, {"id": "X-1", "input": "q", "expected": "a", "metrics": ["tool_correctness"], "expected_tools": []})
        with pytest.raises(ValueError, match="declares no tool contract"):
            spec.scenarios()

    def test_an_explicit_no_tool_contract_is_accepted(self, tmp_path) -> None:
        spec = write_governed_dataset(tmp_path, {"id": "X-1", "input": "q", "expected": "a", "metrics": ["tool_correctness"], "tool_expectation": {"required": [], "allowed": []}})
        assert [c["id"] for c in spec.scenarios()] == ["X-1"]

    def test_a_case_not_scored_on_tools_needs_no_contract(self, tmp_path) -> None:
        spec = write_governed_dataset(tmp_path, {"id": "X-1", "input": "q", "expected": "a", "metrics": ["rubric"], "rubric": "r"})
        assert [c["id"] for c in spec.scenarios()] == ["X-1"]

    def test_the_replay_registry_keeps_its_permissive_default(self, tmp_path) -> None:
        # The v1 registry has 7 cases that declare none. This fix is scoped to
        # the governed dataset; the gap there is tracked on its own issue.
        spec = write_dataset(tmp_path, {"id": "X-1", "input": "q", "expected": "a", "metrics": ["tool_correctness"]})
        assert [c["id"] for c in spec.scenarios()] == ["X-1"]

    def test_tool_order_alone_is_not_a_declaration(self, tmp_path) -> None:
        spec = write_governed_dataset(tmp_path, {"id": "X-1", "input": "q", "expected": "a", "metrics": ["tool_correctness"], "tool_order": True})
        with pytest.raises(ValueError, match="declares no tool contract"):
            spec.scenarios()


class TestRegistry:
    def test_list_datasets(self) -> None:
        names = list_datasets()
        assert "default" in names

    def test_default_dataset_name(self) -> None:
        assert default_dataset_name() == "default"

    def test_dataset_lookup(self) -> None:
        spec = dataset("default")
        assert isinstance(spec, DatasetSpec)

    def test_unknown_dataset_raises(self) -> None:
        with pytest.raises(KeyError):
            dataset("nonexistent")
