"""Offline tests for evals.datasets — swappable dataset registry.

No network calls, no provider credentials, no database required.
"""

from __future__ import annotations

import pytest

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

    def test_scenario_index(self) -> None:
        spec = dataset("default")
        first = spec.scenario(0)
        assert first["id"] == spec.scenarios()[0]["id"]

    def test_metrics_match_available_evidence(self) -> None:
        for scenario in dataset("default").scenarios():
            assert ("sql_accuracy" in scenario["metrics"]) == bool(scenario.get("reference_sql"))
            assert ("memory" in scenario["metrics"]) == (scenario["type"] == "conversational")
            assert isinstance(scenario["rubric"], str) and scenario["rubric"]


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
