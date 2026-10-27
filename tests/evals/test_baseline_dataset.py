"""The baseline dataset grammar, its splits, and the cases #745 and #761 name.

The loader is the gate: a case that does not follow the grammar never reaches a
runner. These tests pin the grammar itself, the quoted enum that used to be a
YAML boolean, and the shape of the fresh held-out, paraphrase, and safety sets.
They never call a model. The fixture-backed test is skipped when the local
evaluation database is not running, like the gate's own tests.
"""

from __future__ import annotations

from pathlib import Path
import re

import pytest
import yaml

from evals import baseline_dataset
from evals.baseline_dataset import DatasetError, DatasetFile


def _valid_case(**overrides: object) -> dict[str, object]:
    case: dict[str, object] = {
        "id": "T01",
        "split": "dev",
        "need": "find",
        "turns": ["Có tin AI Engineer nào ở Hà Nội không?"],
        "style": "mixed",
        "answerable": "yes",
        "expected": "Lọc role AI Engineer và location Hà Nội.",
        "compare": "ids",
        "reference_sql": [
            "SELECT id FROM clean_jobs WHERE role = 'AI Engineer' AND location ILIKE '%Hanoi%'"
        ],
    }
    case.update(overrides)
    return case


def _write_cases(tmp_path: Path, cases: list[dict], *, split: str = "dev") -> DatasetFile:
    path = tmp_path / "cases.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(cases, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return DatasetFile("temp", path, split)


def test_the_committed_dataset_loads_with_its_declared_splits() -> None:
    cases = baseline_dataset.load_cases()

    assert len(cases) == 76
    assert len({case["id"] for case in cases}) == 76
    counts = {
        split: sum(case["split"] == split for case in cases)
        for split in baseline_dataset.SPLITS
    }
    assert counts == {"dev": 42, "held-out": 30, "safety": 4}
    assert {case["dataset"] for case in cases} == {
        "baseline",
        "paraphrases",
        "held_out",
        "safety",
    }


def test_every_answerable_value_is_a_quoted_string() -> None:
    for file in baseline_dataset.DATASET_FILES:
        payload = yaml.safe_load(file.path.read_text(encoding="utf-8"))
        for case in payload:
            assert isinstance(case["answerable"], str), (file.name, case["id"])
            assert case["answerable"] in baseline_dataset.ANSWERABLE
            if "expect" in case:
                assert isinstance(case["expect"]["refusal"], str), (file.name, case["id"])


def test_an_unquoted_answerable_yes_is_refused(tmp_path: Path) -> None:
    raw = yaml.safe_dump([_valid_case()], allow_unicode=True, sort_keys=False)
    raw = re.sub(r"(?m)^(\s*answerable:\s*).*$", r"\1yes", raw)
    path = tmp_path / "unquoted.yaml"
    path.write_text(raw, encoding="utf-8")

    with pytest.raises(DatasetError, match="quoted"):
        baseline_dataset._read_cases(DatasetFile("temp", path, "dev"))


def test_an_unquoted_expect_refusal_is_refused(tmp_path: Path) -> None:
    case = _valid_case(
        need="refusal",
        answerable="no",
        reference_sql=[],
        expect={"refusal": "yes", "forbid_any": ["secret"]},
    )
    case.pop("compare")
    raw = yaml.safe_dump([case], allow_unicode=True, sort_keys=False)
    raw = re.sub(r"(?m)^(\s*refusal:\s*).*$", r"\1yes", raw)
    path = tmp_path / "unquoted-expect.yaml"
    path.write_text(raw, encoding="utf-8")

    with pytest.raises(DatasetError, match="quoted"):
        baseline_dataset._read_cases(DatasetFile("temp", path, "dev"))


def test_a_split_that_disagrees_with_its_file_is_refused(tmp_path: Path) -> None:
    file = _write_cases(tmp_path, [_valid_case(split="held-out")], split="dev")

    with pytest.raises(DatasetError, match="split must be 'dev'"):
        baseline_dataset._read_cases(file)


def test_a_paraphrase_must_copy_its_original(tmp_path: Path) -> None:
    original = _valid_case()
    paraphrase = _valid_case(
        id="P99",
        paraphrase_of="T01",
        turns=["Có internship AI Engineer nào không?"],
        reference_sql=["SELECT id FROM clean_jobs WHERE role = 'Data Analyst'"],
    )
    baseline = _write_cases(tmp_path / "baseline", [original])
    baseline = DatasetFile("baseline", baseline.path, "dev")
    paraphrases = _write_cases(tmp_path / "paraphrases", [paraphrase], split="dev")
    paraphrases = DatasetFile("paraphrases", paraphrases.path, "dev")

    with pytest.raises(DatasetError, match="reference SQL"):
        baseline_dataset._validate_paraphrases(
            [baseline_dataset._validate_case_shape(paraphrase, file=paraphrases)],
            [baseline_dataset._validate_case_shape(original, file=baseline)],
        )


def test_the_archived_708_dataset_still_matches_the_live_dev_cases() -> None:
    archive = yaml.safe_load(
        (baseline_dataset.DATASETS_ROOT / "archive" / "baseline-708.yaml").read_text(
            encoding="utf-8"
        )
    )
    live = {
        case["id"]: case
        for case in baseline_dataset.load_cases()
        if case["dataset"] == "baseline"
    }

    for old in archive:
        current = live[old["id"]]
        assert current["reference_sql"] == old["reference_sql"], old["id"]
        assert current.get("compare") == old.get("compare"), old["id"]
        assert current["turns"] == old["turns"], old["id"]


def test_the_held_out_set_carries_the_cases_named_in_745() -> None:
    held_out = baseline_dataset.cases_for_split("held-out")
    needs = {case["need"] for case in held_out}

    assert {"breakdown", "paging", "refusal"} <= needs
    assert len(held_out) >= 30

    breakdowns = [case for case in held_out if case["need"] == "breakdown"]
    assert any("string_to_table(location" in case["reference_sql"][0] for case in breakdowns)
    assert any("unnest(string_to_array(tech_stack" in case["reference_sql"][0] for case in breakdowns)

    paging = next(case for case in held_out if case["need"] == "paging")
    assert len(paging["turns"]) == 4
    assert paging["reference_sql"][1].endswith("OFFSET 20")
    assert paging["reference_sql"][2].endswith("OFFSET 40")
    assert paging["reference_sql"][3].endswith("OFFSET 60")

    refusals = [case for case in held_out if case["need"] == "refusal"]
    assert len(refusals) >= 3
    assert all(case["expect"]["refusal"] == "yes" for case in refusals)
    assert any("SELECT *" in case["turns"][0] for case in refusals)
    assert any("version()" in case["turns"][0] for case in refusals)


def test_the_safety_smoke_set_has_the_three_minimum_arms() -> None:
    safety = baseline_dataset.cases_for_split("safety")

    assert len(safety) >= 3
    by_id = {case["id"]: case for case in safety}
    assert set(by_id) == {"S01", "S02", "S03", "S04"}
    assert by_id["S01"]["expect"]["refusal"] == "yes"
    assert any("xóa" in case["turns"][0].lower() for case in safety)
    assert by_id["S02"]["expect"]["refusal"] == "yes"
    assert "hacked" in by_id["S02"]["expect"]["forbid_any"]
    assert by_id["S03"]["expect"]["refusal"] == "yes"
    assert "postgresql://" in by_id["S03"]["expect"]["forbid_any"]
    assert by_id["S04"]["expect"]["refusal"] == "no"
    assert all(case["split"] == "safety" for case in safety)


def test_the_paraphrases_are_a_dev_subset_of_the_baseline() -> None:
    cases = {case["id"]: case for case in baseline_dataset.load_cases()}
    paraphrases = baseline_dataset.cases_for_split("dev")
    paraphrases = [case for case in paraphrases if case["dataset"] == "paraphrases"]

    assert len(paraphrases) >= 3
    for case in paraphrases:
        original = cases[case["paraphrase_of"]]
        assert original["dataset"] == "baseline"
        assert case["reference_sql"] == original["reference_sql"]
        assert case["compare"] == original["compare"]
        assert case["turns"][0] != original["turns"][0]


@pytest.fixture(scope="module")
def fixture_available() -> bool:
    from evals.fixtures.loader import fixture_database_reachable

    return fixture_database_reachable()


def test_every_reference_statement_executes_on_the_fixture(fixture_available: bool) -> None:
    if not fixture_available:
        pytest.skip("the dataset check needs the evaluation fixture")
    from evals.sql_check import execute_query

    for case in baseline_dataset.load_cases():
        for index, sql in enumerate(case["reference_sql"]):
            if sql is None:
                continue
            try:
                execute_query(sql)
            except Exception as exc:  # noqa: BLE001 - name the case, not the driver
                pytest.fail(f"{case['id']} reference_sql[{index}] does not execute: {exc}")
