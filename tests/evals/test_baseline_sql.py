from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from evals import baseline_sql
from evals.sql_check import projected_columns


def dataset() -> list[dict]:
    return yaml.safe_load(baseline_sql.DATASET.read_text(encoding="utf-8"))


def test_the_baseline_dataset_follows_its_grammar() -> None:
    questions = dataset()
    ids = [q["id"] for q in questions]

    assert len(ids) == len(set(ids)) == 36
    assert {q["split"] for q in questions} == {"dev", "held-out"}
    for q in questions:
        assert not q["reference_sql"] or len(q["reference_sql"]) == len(q["turns"]), q["id"]
        if not q["reference_sql"]:
            assert q["need"] == "out_of_scope", q["id"]
            continue
        assert q["compare"] in baseline_sql.COMPARE_MODES, q["id"]
        for sql in filter(None, q["reference_sql"]):
            columns = projected_columns(sql)
            assert sql.lstrip().upper().startswith("SELECT") and ";" not in sql, q["id"]
            if q["compare"] == "ids":
                assert columns == ["id"], q["id"]
            if q["compare"] == "count":
                assert columns == ["count"], q["id"]


def test_score_replaces_current_date_and_reports_each_question(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    question = next(q for q in dataset() if q["compare"] == "ids")
    run = tmp_path / "run.json"
    run.write_text(json.dumps({"records": [
        {"id": question["id"], "question": "q", "error": None,
         "sql": "SELECT id FROM clean_jobs WHERE listing_expires_on >= CURRENT_DATE"},
    ]}), encoding="utf-8")
    calls = []

    def fake_compare(generated, reference, database_url, mode):
        calls.append((generated, reference, mode))
        return {"status": "PASS"}

    monkeypatch.setattr(baseline_sql, "compare_result_sets", fake_compare)
    monkeypatch.setattr(baseline_sql, "verify_snapshot", lambda url: None)
    baseline_sql.score(run, "postgresql://unused")

    assert calls == [(
        f"SELECT id FROM clean_jobs WHERE listing_expires_on >= DATE '{baseline_sql.SNAPSHOT_DATE}'",
        question["reference_sql"][0],
        "ids_only",
    )]
    scored = json.loads(run.with_suffix(".score.json").read_text(encoding="utf-8"))
    assert scored[0]["status"] == "PASS"
    assert scored[0]["validator"] == "accepted"


def test_score_records_a_failed_generation_without_executing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    question = dataset()[0]
    run = tmp_path / "run.json"
    run.write_text(json.dumps({"records": [
        {"id": question["id"], "question": "q", "sql": None, "error": "TimeoutError: slow"},
    ]}), encoding="utf-8")
    monkeypatch.setattr(baseline_sql, "compare_result_sets", lambda *a, **k: pytest.fail("executed"))
    monkeypatch.setattr(baseline_sql, "verify_snapshot", lambda url: None)

    baseline_sql.score(run, "postgresql://unused")

    scored = json.loads(run.with_suffix(".score.json").read_text(encoding="utf-8"))
    assert scored[0] == {**scored[0], "status": "ERROR", "reason": "TimeoutError: slow"}
