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


def test_aggregate_count_accepts_an_id_projection_with_the_correct_cardinality(monkeypatch) -> None:
    """A count task is correct when the generated query returns the five matching rows."""
    monkeypatch.setattr(
        "evals.execution_accuracy.execute_query",
        lambda sql, database_url=None: (
            [{"id": index} for index in range(1, 6)] if sql == "generated" else [{"count": 5}]
        ),
    )

    result = compare_result_sets("generated", "reference", comparison_mode="aggregate_count")

    assert result["status"] == "PASS"
    assert result["difference"] == {
        "expected_count": 5,
        "observed_count": 5,
        "generated_count_source": "row_count",
    }


def test_limited_ids_rejects_an_extra_result_and_reports_it(monkeypatch) -> None:
    monkeypatch.setattr(
        "evals.execution_accuracy.execute_query",
        lambda sql, database_url=None: (
            [{"id": 1}, {"id": 2}, {"id": 3}]
            if sql.startswith("generated")
            else [{"id": 1}, {"id": 2}]
        ),
    )

    result = compare_result_sets("generated", "reference", comparison_mode="limited_ids")

    assert result["status"] == "FAIL"
    assert result["difference"] == {"missing_ids": [], "unexpected_ids": [3]}


def test_limited_ids_mirrors_the_product_twenty_row_display_cap(monkeypatch) -> None:
    monkeypatch.setattr(
        "evals.execution_accuracy.execute_query",
        lambda sql, database_url=None: (
            [{"id": index} for index in range(1, 22)]
            if sql.startswith("generated")
            else [{"id": index} for index in range(1, 21)]
        ),
    )

    result = compare_result_sets("generated", "reference", comparison_mode="limited_ids")

    assert result["status"] == "PASS"
    assert result["generated_row_count"] == 20
    assert result["generated_fetched_row_count"] == 21
    assert result["reference_row_count"] == 20
    assert result["generated_sql"] == "generated"
    assert result["executed_generated_sql"].endswith("LIMIT 21")


def test_destructive_compound_read_requires_all_python_job_ids(monkeypatch) -> None:
    reference = [{"id": number} for number in range(1, 13)]
    monkeypatch.setattr(
        "evals.execution_accuracy.execute_query",
        lambda sql, database_url=None: reference if sql == "reference" else list(reference),
    )

    assert compare_result_sets("generated", "reference", comparison_mode="ids_only")["status"] == "PASS"

    monkeypatch.setattr(
        "evals.execution_accuracy.execute_query",
        lambda sql, database_url=None: reference if sql == "reference" else reference[:-1],
    )

    result = compare_result_sets("generated", "reference", comparison_mode="ids_only")
    assert result["status"] == "FAIL"
    assert result["difference"]["missing_ids"] == [12]


def test_zero_results_requires_the_generated_query_to_return_no_rows(monkeypatch) -> None:
    monkeypatch.setattr(
        "evals.execution_accuracy.execute_query",
        lambda sql, database_url=None: ([{"id": 9}] if sql == "generated" else []),
    )

    result = compare_result_sets("generated", "reference", comparison_mode="zero_results")

    assert result["status"] == "FAIL"
    assert result["difference"] == {"expected_empty": True, "unexpected_rows": [{"id": 9}]}


def test_cross_currency_rejects_a_single_currency_ranking(monkeypatch) -> None:
    monkeypatch.setattr(
        "evals.execution_accuracy.execute_query",
        lambda sql, database_url=None: (
            [{"id": 7, "salary_currency": "VND"}]
            if sql == "generated"
            else [{"salary_currency": "USD"}, {"salary_currency": "VND"}]
        ),
    )

    result = compare_result_sets("generated", "reference", comparison_mode="cross_currency")

    assert result["status"] == "FAIL"
    assert result["difference"]["missing_currencies"] == ["USD"]


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


def test_ids_only_fails_a_generated_query_that_does_not_project_id(monkeypatch) -> None:
    """The mirror of the registry guard: an id-less *generated* query must not pass either.

    HON-ZERO-RESULTS-1 is the live case. Its reference finds no COBOL posting, so without this
    check a query that ignored the filter entirely compares an empty multiset against an empty one.
    """
    monkeypatch.setattr(
        "evals.execution_accuracy.execute_query",
        lambda sql, database_url=None: (
            [{"title": "Java Engineer"}, {"title": "Python Engineer"}] if sql == "generated" else []
        ),
    )

    result = compare_result_sets("generated", "reference", comparison_mode="ids_only")

    assert result["status"] == "FAIL"
    assert result["error"] == "Generated query does not project id, so row identity cannot be compared"
    assert result["generated_row_count"] == 2


def test_ids_only_names_the_projection_instead_of_a_row_mismatch(monkeypatch) -> None:
    """An id-less generated query reads as a projection defect, not as the wrong postings."""
    monkeypatch.setattr(
        "evals.execution_accuracy.execute_query",
        lambda sql, database_url=None: (
            [{"title": "AI Engineer"}] if sql == "generated" else [{"id": 3, "title": "AI Engineer"}]
        ),
    )

    result = compare_result_sets("generated", "reference", comparison_mode="ids_only")

    assert result["status"] == "FAIL"
    assert "does not project id" in result["error"]


def test_ids_only_passes_when_both_sides_are_legitimately_empty(monkeypatch) -> None:
    """An empty result has no projection to check, so HON-ZERO-RESULTS-1 still passes correctly."""
    monkeypatch.setattr("evals.execution_accuracy.execute_query", lambda sql, database_url=None: [])

    assert compare_result_sets("generated", "reference", comparison_mode="ids_only")["status"] == "PASS"


def test_ids_only_rejects_a_reference_whose_rows_carry_no_id(monkeypatch) -> None:
    """A registry mistake, not a model defect, so it raises rather than grading the turn."""
    monkeypatch.setattr(
        "evals.execution_accuracy.execute_query",
        lambda sql, database_url=None: [{"count": 5}],
    )

    with pytest.raises(ValueError, match="without an id column"):
        compare_result_sets("generated", "reference", comparison_mode="ids_only")


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


def test_missing_sql_is_not_evaluated_when_the_turn_completed() -> None:
    result = grade_turn(
        {"id": "HLP-COUNT-1", "reference_sql": "SELECT COUNT(*) FROM clean_jobs"},
        None,
    )

    assert result == {
        "status": "NOT_EVALUATED",
        "reason": "No generated SQL was persisted, so SQL execution cannot be compared.",
    }


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
