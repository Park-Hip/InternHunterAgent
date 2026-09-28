"""Offline SQL contract tests with query results stubbed at the DB boundary."""

import pytest

from evals import sql_check


def test_projection() -> None:
    assert sql_check.projected_columns("SELECT id, title FROM clean_jobs") == ["id", "title"]
    assert sql_check.projected_columns("SELECT j.id AS job_id FROM clean_jobs j") == ["job_id"]


def test_identity_not_row_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sql_check, "execute_query", lambda sql, _: [{"id": 1, "title": "different"}] if sql.startswith("generated") else [{"id": 1}])
    assert sql_check.compare_result_sets("SELECT id, title FROM generated", "SELECT id FROM reference")["status"] == "PASS"


def test_missing_id_fails_even_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sql_check, "execute_query", lambda *_: [])
    assert sql_check.compare_result_sets("SELECT title FROM clean_jobs", "SELECT id FROM clean_jobs")["status"] == "FAIL"


def test_extra_ids_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sql_check, "execute_query", lambda sql, _: [{"id": 1}, {"id": 2}] if "generated" in sql else [{"id": 1}])
    result = sql_check.compare_result_sets("SELECT id FROM generated", "SELECT id FROM reference")
    assert result["status"] == "FAIL"
    assert result["unexpected_ids"] == [2]


def test_display_limit_matches_user_visible_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sql_check, "execute_query", lambda sql, _: [{"id": 1}, {"id": 2}] if "generated" in sql else [{"id": 1}])
    assert sql_check.compare_result_sets("SELECT id FROM generated", "SELECT id FROM reference", display_limit=1)["status"] == "PASS"
    assert sql_check.compare_result_sets("SELECT id FROM generated", "SELECT id FROM reference")["status"] == "FAIL"


def test_invalid_mode_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown"):
        sql_check.compare_result_sets("", "", mode="cross_currency")


def test_count_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sql_check, "execute_query", lambda *_: [{"count": 5}])
    assert sql_check.compare_result_sets("SELECT COUNT(*) AS count FROM clean_jobs", "SELECT COUNT(*) AS count FROM clean_jobs", mode="aggregate_count", expected_count=5)["status"] == "PASS"
    assert sql_check.compare_result_sets("SELECT id FROM clean_jobs", "SELECT COUNT(*) AS count FROM clean_jobs", mode="aggregate_count")["status"] == "FAIL"


def test_zero_results(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sql_check, "execute_query", lambda *_: [])
    assert sql_check.compare_result_sets("SELECT id FROM clean_jobs", "SELECT id FROM clean_jobs", mode="zero_results")["status"] == "PASS"
