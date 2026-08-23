"""Project the versioned scenario registry into a Langfuse dataset.

The YAML registry remains authoritative.
Langfuse receives a checked, derived projection used only to group existing
driver captures and their scores.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from langfuse.api import NotFoundError

from src.core.logger import logger

DATASET_NAME = "internhunteragent-scenarios-v1"
DATASET_DESCRIPTION = (
    "Derived mirror of evals/scenarios_v1.yaml. Do not edit in Langfuse."
)
ITEM_ID_PREFIX = "internhunteragent-scenarios-v1:"


class DatasetRunItemsAPI(Protocol):
    def create(self, **kwargs: Any) -> Any: ...


class DatasetAPI(Protocol):
    dataset_run_items: DatasetRunItemsAPI


class LangfuseDatasetClient(Protocol):
    api: DatasetAPI

    def create_dataset(self, **kwargs: Any) -> Any: ...

    def create_dataset_item(self, **kwargs: Any) -> Any: ...

    def get_dataset(self, name: str, **kwargs: Any) -> Any: ...


@dataclass(frozen=True)
class DatasetItem:
    """The deterministic Langfuse projection for one scenario turn."""

    id: str
    input: dict[str, Any]
    expected_output: dict[str, Any]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class DatasetMirror:
    """Item identifiers used to attach captures to derived dataset runs."""

    item_ids: dict[tuple[str, int], str]


def _item_id(scenario_id: str, turn: int) -> str:
    return f"{ITEM_ID_PREFIX}{scenario_id}:t{turn}"


def dataset_run_name(capture_run_id: str, repeat: int) -> str:
    """Name one experiment run per driver repeat.

    Langfuse permits one instance of a dataset item per dataset run.
    Repeats are therefore separate runs, while the dataset itself keeps one
    item per scenario turn for direct run-to-run comparison.
    """
    return f"{capture_run_id}:repeat:{repeat}"


def build_dataset_items(scenarios: list[dict[str, Any]]) -> list[DatasetItem]:
    """Derive each scenario turn once, independently of its repeat count."""
    items: list[DatasetItem] = []
    for scenario in scenarios:
        messages = (
            [scenario["input"]] if scenario["type"] == "single" else scenario["turns"]
        )
        for turn, message in enumerate(messages, start=1):
            turn_expectations = scenario.get("turn_tool_expectations")
            tool_expectation = (
                turn_expectations[turn - 1]
                if turn_expectations is not None
                else scenario.get("tool_expectation")
            )
            items.append(
                DatasetItem(
                    id=_item_id(scenario["id"], turn),
                    input={
                        "scenario_id": scenario["id"],
                        "turn": turn,
                        "question": message,
                    },
                    expected_output={
                        "behavior": scenario["expected"],
                        "expected_tools": scenario["expected_tools"],
                        "tool_expectation": tool_expectation,
                        "reference_sql": scenario.get("reference_sql"),
                        "execution_accuracy_exempt": scenario.get(
                            "execution_accuracy_exempt"
                        ),
                    },
                    metadata={
                        "source": "evals/scenarios_v1.yaml",
                        "scenario_id": scenario["id"],
                        "scenario_name": scenario["name"],
                        "scenario_type": scenario["type"],
                        "turn": turn,
                        "probe": scenario["probe"],
                        "requirements": scenario["requirements"],
                        "decision": scenario["decision"],
                        "grading": scenario.get("grading"),
                    },
                )
            )
    return items


def _field(value: Any, name: str) -> Any:
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _mirror(items: list[DatasetItem]) -> DatasetMirror:
    return DatasetMirror(
        item_ids={
            (item.input["scenario_id"], item.input["turn"]): item.id for item in items
        }
    )


def _matches(remote: Any, expected: DatasetItem) -> bool:
    return all(
        _field(remote, field) == value
        for field, value in (
            ("input", expected.input),
            ("expected_output", expected.expected_output),
            ("metadata", expected.metadata),
        )
    )


def synchronize_dataset(
    client: LangfuseDatasetClient, scenarios: list[dict[str, Any]]
) -> DatasetMirror:
    """Create the dataset and upsert only missing or changed derived items."""
    items = build_dataset_items(scenarios)
    try:
        remote_dataset = client.get_dataset(DATASET_NAME)
    except NotFoundError:
        client.create_dataset(
            name=DATASET_NAME,
            description=DATASET_DESCRIPTION,
            metadata={"source": "evals/scenarios_v1.yaml", "authoritative": "git"},
        )
        remote_items: dict[str, Any] = {}
    else:
        remote_items = {_field(item, "id"): item for item in remote_dataset.items}

    for item in items:
        if _matches(remote_items.get(item.id), item):
            continue
        client.create_dataset_item(
            dataset_name=DATASET_NAME,
            id=item.id,
            input=item.input,
            expected_output=item.expected_output,
            metadata=item.metadata,
        )
    return _mirror(items)


def verify_dataset_mirror(
    client: LangfuseDatasetClient, scenarios: list[dict[str, Any]]
) -> None:
    """Raise when the remote dataset differs from its YAML-derived projection."""
    expected = {item.id: item for item in build_dataset_items(scenarios)}
    remote_items = {
        _field(item, "id"): item for item in client.get_dataset(DATASET_NAME).items
    }
    remote_ids = set(remote_items)
    if remote_ids != set(expected):
        missing = sorted(set(expected) - remote_ids)
        extra = sorted(remote_ids - set(expected))
        raise ValueError(f"Langfuse dataset drift: missing={missing}, extra={extra}")
    for item_id, expected_item in expected.items():
        if not _matches(remote_items[item_id], expected_item):
            raise ValueError(f"Langfuse dataset drift in {item_id}")


def mirror_for_capture(
    client: LangfuseDatasetClient, scenarios: list[dict[str, Any]]
) -> DatasetMirror | None:
    """Return an intact mirror or reconcile it without blocking a capture."""
    items = build_dataset_items(scenarios)
    try:
        verify_dataset_mirror(client, scenarios)
        return _mirror(items)
    except NotFoundError:
        pass
    except ValueError as exc:
        logger.info("Langfuse dataset drift detected; reconciling", error=str(exc))
    except Exception as exc:  # noqa: BLE001 - remote observability is non-fatal
        logger.warning("Langfuse dataset verification failed", error=str(exc))
        return None

    try:
        return synchronize_dataset(client, scenarios)
    except Exception as exc:  # noqa: BLE001 - remote observability is non-fatal
        logger.warning("Langfuse dataset synchronization failed", error=str(exc))
        return None


def link_capture(
    client: LangfuseDatasetClient,
    mirror: DatasetMirror | None,
    *,
    capture_run_id: str,
    scenario_id: str,
    repeat: int,
    turn: int,
    trace_id: str | None,
) -> str | None:
    """Attach an existing trace to its scenario turn in that repeat's run."""
    if mirror is None or trace_id is None:
        return None
    item_id = mirror.item_ids.get((scenario_id, turn))
    if item_id is None:
        logger.warning(
            "Langfuse dataset link skipped: no derived item",
            scenario_id=scenario_id,
            repeat=repeat,
            turn=turn,
        )
        return None
    try:
        run_item = client.api.dataset_run_items.create(
            run_name=dataset_run_name(capture_run_id, repeat),
            run_description="InternHunterAgent scenario-driver capture repeat",
            metadata={
                "source": "evals/driver.py",
                "capture_run_id": capture_run_id,
                "repeat": repeat,
            },
            dataset_item_id=item_id,
            trace_id=trace_id,
        )
        dataset_run_id = _field(run_item, "dataset_run_id")
        return dataset_run_id if isinstance(dataset_run_id, str) else None
    except Exception as exc:  # noqa: BLE001 - remote observability is non-fatal
        logger.warning(
            "Langfuse dataset-run link failed",
            scenario_id=scenario_id,
            repeat=repeat,
            turn=turn,
            error=str(exc),
        )
        return None
