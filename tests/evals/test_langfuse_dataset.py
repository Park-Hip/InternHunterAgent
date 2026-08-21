"""Offline contracts for the YAML-to-Langfuse dataset projection."""

from __future__ import annotations

from types import SimpleNamespace

from langfuse.api import NotFoundError

from evals import langfuse_dataset as dataset


class FakeRunItems:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(dataset_run_id="dataset-run-123")


class FakeLangfuse:
    def __init__(self) -> None:
        self.created_datasets: list[dict] = []
        self.created_items: list[dict] = []
        self.items: dict[str, SimpleNamespace] = {}
        self.exists = False
        self.api = SimpleNamespace(dataset_run_items=FakeRunItems())

    def get_dataset(self, name: str, **kwargs):
        assert name == dataset.DATASET_NAME
        if not self.exists:
            raise NotFoundError({"message": "missing"})
        return SimpleNamespace(items=list(self.items.values()))

    def create_dataset(self, **kwargs):
        self.exists = True
        self.created_datasets.append(kwargs)

    def create_dataset_item(self, **kwargs):
        self.created_items.append(kwargs)
        self.items[kwargs["id"]] = SimpleNamespace(
            id=kwargs["id"],
            input=kwargs["input"],
            expected_output=kwargs["expected_output"],
            metadata=kwargs["metadata"],
        )


def _scenarios() -> list[dict]:
    return [
        {
            "id": "HLP-ONE-1",
            "name": "One turn",
            "type": "single",
            "input": "How many jobs are there?",
            "expected": "Answer with a count.",
            "expected_tools": ["query_clean_jobs"],
            "probe": False,
            "requirements": ["G-1"],
            "decision": 1,
            "reference_sql": "SELECT count(*) FROM clean_jobs",
        },
        {
            "id": "HON-MULTI-1",
            "name": "Two turns",
            "type": "conversational",
            "turns": ["First question", "Second question"],
            "expected": "Preserve context.",
            "expected_tools": [],
            "probe": True,
            "requirements": ["G-2"],
            "decision": None,
            "execution_accuracy_exempt": {"reason": "No SQL."},
        },
    ]


def test_projection_has_one_stable_item_per_scenario_turn() -> None:
    items = dataset.build_dataset_items(_scenarios())

    assert [item.id for item in items] == [
        "internhunteragent-scenarios-v1:HLP-ONE-1:t1",
        "internhunteragent-scenarios-v1:HON-MULTI-1:t1",
        "internhunteragent-scenarios-v1:HON-MULTI-1:t2",
    ]
    assert items[-1].input == {
        "scenario_id": "HON-MULTI-1",
        "turn": 2,
        "question": "Second question",
    }
    assert all("repeat" not in item.input for item in items)


def test_mirror_verification_skips_a_no_op_sync_and_selectively_repairs_drift() -> None:
    fake = FakeLangfuse()

    first = dataset.mirror_for_capture(fake, _scenarios())
    created_after_first_sync = len(fake.created_items)
    second = dataset.mirror_for_capture(fake, _scenarios())

    assert first == second
    assert len(fake.created_datasets) == 1
    assert created_after_first_sync == 3
    assert len(fake.created_items) == created_after_first_sync

    fake.items["internhunteragent-scenarios-v1:HLP-ONE-1:t1"].metadata = {"drift": True}
    repaired = dataset.mirror_for_capture(fake, _scenarios())

    assert repaired == first
    assert len(fake.created_items) == created_after_first_sync + 1
    dataset.verify_dataset_mirror(fake, _scenarios())


def test_missing_dataset_uses_the_sdk_not_found_exception() -> None:
    fake = FakeLangfuse()

    mirror = dataset.mirror_for_capture(fake, _scenarios())

    assert mirror is not None
    assert fake.created_datasets == [
        {
            "name": dataset.DATASET_NAME,
            "description": dataset.DATASET_DESCRIPTION,
            "metadata": {"source": "evals/scenarios_v1.yaml", "authoritative": "git"},
        }
    ]


def test_repeats_reuse_the_dataset_item_and_create_separate_dataset_runs() -> None:
    fake = FakeLangfuse()
    mirror = dataset.synchronize_dataset(fake, _scenarios())

    first = dataset.link_capture(
        fake,
        mirror,
        capture_run_id="capture-123",
        scenario_id="HLP-ONE-1",
        repeat=1,
        turn=1,
        trace_id="trace-one",
    )
    second = dataset.link_capture(
        fake,
        mirror,
        capture_run_id="capture-123",
        scenario_id="HLP-ONE-1",
        repeat=2,
        turn=1,
        trace_id="trace-two",
    )

    assert first == second == "dataset-run-123"
    assert [call["dataset_item_id"] for call in fake.api.dataset_run_items.calls] == [
        "internhunteragent-scenarios-v1:HLP-ONE-1:t1",
        "internhunteragent-scenarios-v1:HLP-ONE-1:t1",
    ]
    assert [call["run_name"] for call in fake.api.dataset_run_items.calls] == [
        "capture-123:repeat:1",
        "capture-123:repeat:2",
    ]
