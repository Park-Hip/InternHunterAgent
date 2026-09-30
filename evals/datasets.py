"""Dataset registry and the validation the evaluation harness relies on.

Each dataset is keyed by a short name and points at one YAML file of
scenarios. ``default`` is the v1 registry; ``v0`` is the v0 acceptance set
derived from docs/refactor/agent-v0-contract.md. The two never mix: a new
version is a new entry, never an edit to the registry that is already
selectable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from evals._paths import EVALS_ROOT
import yaml

DATASETS_DIR = EVALS_ROOT / "datasets"

_DEFAULT_DATASET = "default"

_TOOL_KEYS = frozenset({"expected_tools", "tool_expectation", "turn_tool_expectations", "tool_order"})
_TOOL_FIELDS = frozenset({"required", "allowed"})


def _validate_tool_expectations(sid: str, scenario: dict[str, Any]) -> None:
    """Reject tool keys and expectations the harness would silently ignore."""
    for key in scenario:
        if "tool" in key and key not in _TOOL_KEYS:
            raise ValueError(f"Scenario {sid} declares unread tool key {key!r}; expected one of {sorted(_TOOL_KEYS)}")
    expectations = [scenario["tool_expectation"]] if scenario.get("tool_expectation") else []
    expectations.extend(scenario.get("turn_tool_expectations") or [])
    for expectation in expectations:
        if not isinstance(expectation, dict) or set(expectation) - _TOOL_FIELDS:
            raise ValueError(f"Scenario {sid} has an invalid tool expectation: {expectation}")
        for field in _TOOL_FIELDS & set(expectation):
            if not isinstance(expectation[field], list):
                raise ValueError(f"Scenario {sid} must list {field} tools, got {expectation[field]!r}")
    turns = len(scenario.get("turns") or [scenario.get("input")])
    if scenario.get("turn_tool_expectations") and len(scenario["turn_tool_expectations"]) != turns:
        raise ValueError(f"Scenario {sid} declares tool expectations for {len(scenario['turn_tool_expectations'])} of {turns} turns")


class DatasetSpec:
    """A single dataset reference: one scenario file and its grammar."""

    def __init__(self, path: Path) -> None:
        self.path = path

    @property
    def is_v0(self) -> bool:
        """Whether this dataset describes the governed v0 path rather than a replay."""
        return self.path.name.startswith("v0_")

    def scenarios(self) -> list[dict[str, Any]]:
        payload = yaml.safe_load(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError(f"Dataset {self.path} must be a YAML list of scenarios")
        from evals.metrics import LEGACY_METRICS, METRIC_BY_NAME

        seen: set[str] = set()
        for scenario in payload:
            if not isinstance(scenario, dict) or not isinstance(scenario.get("id"), str):
                raise ValueError("Every scenario needs a string id")
            sid = scenario["id"]
            if sid in seen:
                raise ValueError(f"Duplicate scenario id: {sid}")
            seen.add(sid)
            if not scenario.get("input") and not scenario.get("turns"):
                raise ValueError(f"Scenario {sid} has no input or turns")
            if not isinstance(scenario.get("expected"), str):
                raise ValueError(f"Scenario {sid} has no expected answer")
            names = scenario.get("metrics")
            if not isinstance(names, list) or not names or set(names) - METRIC_BY_NAME.keys():
                raise ValueError(f"Scenario {sid} has invalid metrics: {names}")
            if self.is_v0 and set(names) & LEGACY_METRICS:
                # #487 decided a no-go on the SQL path, and v0 is single-turn, so a
                # governed case may not ask for a metric that scores either one.
                raise ValueError(
                    f"Scenario {sid} declares retired metrics {sorted(set(names) & LEGACY_METRICS)}; "
                    "the v0 dataset may not score the SQL path or multi-turn memory"
                )
            if "sql_accuracy" in names and not scenario.get("reference_sql"):
                raise ValueError(f"Scenario {sid} has no reference SQL")
            if "rubric" in names and not scenario.get("rubric"):
                raise ValueError(f"Scenario {sid} has no rubric")
            _validate_tool_expectations(sid, scenario)
        return payload


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, DatasetSpec] = {
    "default": DatasetSpec(DATASETS_DIR / "scenarios.yaml"),
    "v0": DatasetSpec(DATASETS_DIR / "v0_acceptance.yaml"),
}


def dataset(name: str) -> DatasetSpec:
    return _REGISTRY[name]


def list_datasets() -> list[str]:
    return sorted(_REGISTRY)


def default_dataset_name() -> str:
    return _DEFAULT_DATASET
