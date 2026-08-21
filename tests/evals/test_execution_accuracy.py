from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import pytest

from evals.execution_accuracy import (
    compare_result_sets,
    grade_turn,
    selects_id,
    validate_execution_comparison,
)


def test_equivalent_queries_pass_when_where_terms_are_reordered(monkeypatch) -> None:
    rows = [{"id": 1, "title": "One"}, {"id": 2, "title": "Two"}]
    calls = []

    def fake_execute(sql: str, database_url=None):
        calls.append(sql)
        return list(reversed(rows)) if "title = 'Two' AND id > 0" in sql else rows

    monkeypatch.setattr("evals.execution_accuracy.execute_query", fake_execute)
    result = compare_result_sets(
        "SELECT id, title FROM clean_jobs WHERE title = 'Two' AND id > 0",
        "SELECT id, title FROM clean_jobs WHERE id > 0 AND title = 'Two'",
    )

    assert result["status"] == "PASS"
    assert len(calls) == 2


def test_duplicate_rows_are_compared_as_a_multiset(monkeypatch) -> None:
    monkeypatch.setattr(
        "evals.execution_accuracy.execute_query",
        lambda sql, database_url=None: [{"value": 1}] * (2 if sql == "generated" else 1),
    )

    assert compare_result_sets("generated", "reference")["status"] == "FAIL"


def test_id_projection_ignores_extra_columns_and_aliases(monkeypatch) -> None:
    monkeypatch.setattr(
        "evals.execution_accuracy.execute_query",
        lambda sql, database_url=None: (
            [{"id": 1, "title": "One", "tech_stack": "Python"}]
            if sql == "generated"
            else [{"id": 1, "title": "One"}]
        ),
    )

    assert compare_result_sets("generated", "reference")["status"] == "FAIL"
    assert compare_result_sets("generated", "reference", comparison_mode="ids_only")["status"] == "PASS"


def test_ids_only_passes_a_superset_projection_over_the_same_rows(monkeypatch) -> None:
    """The 2026-08-21 probe's failure: same postings, the model's own wider column list."""
    reference = [
        {"id": 3, "title": "AI Engineer", "company": "One", "location": "Hanoi"},
        {"id": 7, "title": "AI Engineer Intern", "company": "Two", "location": "Da Nang"},
    ]
    generated = [
        {"id": 7, "location": "Da Nang", "title": "AI Engineer Intern", "company": "Two",
         "tech_stack": "Python", "is_salary_negotiable": True},
        {"id": 3, "location": "Hanoi", "title": "AI Engineer", "company": "One",
         "tech_stack": "Python", "is_salary_negotiable": False},
    ]
    monkeypatch.setattr(
        "evals.execution_accuracy.execute_query",
        lambda sql, database_url=None: generated if sql == "generated" else reference,
    )

    assert compare_result_sets("generated", "reference")["status"] == "FAIL"
    assert compare_result_sets("generated", "reference", comparison_mode="ids_only")["status"] == "PASS"


def test_ids_only_still_fails_a_different_row_set(monkeypatch) -> None:
    monkeypatch.setattr(
        "evals.execution_accuracy.execute_query",
        lambda sql, database_url=None: (
            [{"id": 3}, {"id": 8}] if sql == "generated" else [{"id": 3}, {"id": 7}]
        ),
    )

    assert compare_result_sets("generated", "reference", comparison_mode="ids_only")["status"] == "FAIL"


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        ("SELECT id, title FROM clean_jobs", True),
        ("select ID from clean_jobs", True),
        ("SELECT DISTINCT id FROM clean_jobs", True),
        ("SELECT clean_jobs.id, title FROM clean_jobs", True),
        ("SELECT job_id AS id FROM clean_jobs", True),
        ("SELECT * FROM clean_jobs", True),
        ("SELECT COUNT(*) AS count FROM clean_jobs", False),
        ("SELECT title, company FROM clean_jobs", False),
        ("SELECT MAX(id) FROM clean_jobs", False),
        ("not a select statement", False),
    ],
)
def test_selects_id_reads_the_reference_projection(sql: str, expected: bool) -> None:
    assert selects_id(sql) is expected


def test_ids_only_over_a_count_reference_is_rejected() -> None:
    scenario = {
        "id": "HLP-COUNT-1",
        "reference_sql": "SELECT COUNT(*) AS count FROM clean_jobs",
        "grading": {"execution_comparison": "ids_only"},
    }

    with pytest.raises(ValueError, match="does not select id"):
        grade_turn(scenario, "SELECT COUNT(*) FROM clean_jobs")


def test_ids_only_over_a_count_reference_would_otherwise_pass_anything(monkeypatch) -> None:
    """Why the guard exists: with no id column, both multisets are empty and everything matches."""
    monkeypatch.setattr(
        "evals.execution_accuracy.execute_query",
        lambda sql, database_url=None: [{"count": 999}] if sql == "generated" else [{"count": 5}],
    )

    assert compare_result_sets("generated", "reference", comparison_mode="ids_only")["status"] == "PASS"


def test_ids_only_guard_checks_every_conversational_turn() -> None:
    scenario = {
        "id": "HLP-CONTEXT-1",
        "reference_sql": [
            "SELECT id, title FROM clean_jobs",
            "SELECT title FROM clean_jobs WHERE location ILIKE '%Hanoi%'",
        ],
        "grading": {"execution_comparison": "ids_only"},
    }

    with pytest.raises(ValueError, match="turn 2"):
        validate_execution_comparison(scenario)


def test_the_guard_leaves_the_other_comparison_modes_alone() -> None:
    for mode in ("exact", "contains_reference"):
        validate_execution_comparison(
            {
                "id": "HLP-COUNT-1",
                "reference_sql": "SELECT COUNT(*) AS count FROM clean_jobs",
                "grading": {"execution_comparison": mode},
            }
        )


def test_contains_reference_accepts_extra_generated_rows(monkeypatch) -> None:
    monkeypatch.setattr(
        "evals.execution_accuracy.execute_query",
        lambda sql, database_url=None: (
            [{"id": 1, "created_on": "2026-01-02", "title": "One"},
             {"id": 2, "created_on": "2026-01-01", "title": "Two"}]
            if sql == "generated"
            else [{"id": 1, "created_on": "2026-01-02", "title": "One"}]
        ),
    )

    assert compare_result_sets(
        "generated", "reference", comparison_mode="contains_reference"
    )["status"] == "PASS"


def test_aggregate_aliases_are_not_part_of_the_result_identity(monkeypatch) -> None:
    monkeypatch.setattr(
        "evals.execution_accuracy.execute_query",
        lambda sql, database_url=None: (
            [{"total": 5}] if sql == "generated" else [{"count": 5}]
        ),
    )

    assert compare_result_sets("generated", "reference")["status"] == "PASS"


def test_wrong_reference_is_a_sql_failure_independent_of_answer(monkeypatch) -> None:
    monkeypatch.setattr(
        "evals.execution_accuracy.compare_result_sets",
        lambda generated, reference, database_url=None: {
            "status": "FAIL",
            "generated_row_count": 1,
            "reference_row_count": 0,
        },
    )
    scenario = {"id": "HLP-COUNT-1", "reference_sql": "SELECT 0"}

    result = grade_turn(scenario, "SELECT COUNT(*) FROM clean_jobs")

    assert result["status"] == "FAIL"


def test_exemption_preserves_reason() -> None:
    result = grade_turn(
        {"id": "SAF-REFUSAL-1", "execution_accuracy_exempt": {"reason": "No query is expected."}},
        None,
    )

    assert result == {"status": "EXEMPT", "reason": "No query is expected."}


def test_conversational_turns_can_use_turn_specific_references(monkeypatch) -> None:
    from evals.execution_accuracy import grade_run

    run = {
        "manifest": {"run_id": "run-1"},
        "scenarios": {
            "HLP-CONTEXT-1": {
                "repeats": [{"repeat": 1, "turns": [{"seams": {"sql_text": "one"}}, {"seams": {"sql_text": "two"}}]}]
            }
        },
    }
    scenario = {"id": "HLP-CONTEXT-1", "reference_sql": ["one", "two"]}

    import evals.execution_accuracy as accuracy

    monkeypatch.setattr(accuracy, "load_scenarios", lambda: [scenario])
    monkeypatch.setattr(
        accuracy,
        "compare_result_sets",
        lambda generated, reference, database_url=None: {"status": "PASS"},
    )
    result = grade_run(run)

    assert [turn["status"] for turn in result["scenarios"]["HLP-CONTEXT-1"][0]["turns"]] == ["PASS", "PASS"]


def test_cli_serializes_date_and_decimal_results(tmp_path, monkeypatch, capsys) -> None:
    import evals.execution_accuracy as accuracy

    run_path = tmp_path / "run.json"
    run_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        accuracy,
        "grade_run",
        lambda run, database_url=None: {
            "rows": [{"created_on": date(2026, 8, 13), "salary_max": Decimal("40000000")}]
        },
    )

    accuracy.main([str(run_path)])

    assert json.loads(capsys.readouterr().out) == {
        "rows": [{"created_on": "2026-08-13", "salary_max": "40000000"}]
    }


def test_cli_writes_a_utf8_report_the_grader_can_consume(tmp_path, monkeypatch, capsys) -> None:
    """Redirected stdout is cp1252 on Windows, so the report needs its own file."""
    import evals.execution_accuracy as accuracy

    run_path = tmp_path / "run.json"
    run_path.write_text("{}", encoding="utf-8")
    output_path = tmp_path / "accuracy.json"
    company = "NGÂN HÀNG TMCP QUÂN ĐỘI – MBBANK"
    monkeypatch.setattr(
        accuracy,
        "grade_run",
        lambda run, database_url=None: {
            "rows": [{"company": company, "created_on": date(2026, 8, 13)}]
        },
    )

    accuracy.main([str(run_path), "--output", str(output_path)])

    assert capsys.readouterr().out.strip() == str(output_path)
    assert json.loads(output_path.read_text(encoding="utf-8")) == {
        "rows": [{"company": company, "created_on": "2026-08-13"}]
    }
