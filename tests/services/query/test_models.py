"""Unit tests for the typed tool-result models (#702).

The exact key sets matter beyond the unit tests: FastMCP publishes them as each
tool's ``outputSchema``, and the system prompt names them to the model.
"""

from __future__ import annotations

import unittest

from src.services.query.models import (
    BoundedRows,
    JobDetailsResult,
    QueryResult,
    ValidationResult,
)


class BoundedRowsTests(unittest.TestCase):
    def test_bounded_rows_serializes(self) -> None:
        bounded = BoundedRows(
            columns=["id", "title"], rows=[[1, "ML Intern"]], total_rows=161
        )

        self.assertEqual(
            bounded.model_dump(),
            {
                "columns": ["id", "title"],
                "rows": [[1, "ML Intern"]],
                "total_rows": 161,
            },
        )


class QueryResultTests(unittest.TestCase):
    def test_query_result_serializes_the_facts_and_the_sql_that_ran(self) -> None:
        result = QueryResult(
            sql="SELECT id, title FROM clean_jobs LIMIT 20",
            columns=["id", "title"],
            rows=[[1, "ML Intern"]],
            row_count=1,
            total_rows=161,
        )

        self.assertEqual(
            result.model_dump(),
            {
                "sql": "SELECT id, title FROM clean_jobs LIMIT 20",
                "columns": ["id", "title"],
                "rows": [[1, "ML Intern"]],
                "row_count": 1,
                "total_rows": 161,
            },
        )

    def test_query_result_carries_no_user_facing_sentence(self) -> None:
        result = QueryResult(
            sql="SELECT count(*) AS count FROM clean_jobs",
            columns=["count"],
            rows=[[0]],
            row_count=1,
            total_rows=1,
        )

        self.assertEqual(
            set(result.model_dump()),
            {"sql", "columns", "rows", "row_count", "total_rows"},
        )


class JobDetailsResultTests(unittest.TestCase):
    def test_job_details_result_serializes(self) -> None:
        result = JobDetailsResult(
            jobs=[{"id": 1, "title": "ML Intern", "description": "A role."}],
            not_found=[2],
            not_fetched=[3, 4],
        )

        self.assertEqual(
            result.model_dump(),
            {
                "jobs": [{"id": 1, "title": "ML Intern", "description": "A role."}],
                "not_found": [2],
                "not_fetched": [3, 4],
            },
        )


class ValidationResultTests(unittest.TestCase):
    def test_a_valid_result_needs_no_reason(self) -> None:
        result = ValidationResult(valid=True, sql="SELECT id FROM clean_jobs")

        self.assertEqual(result.reason, "")


if __name__ == "__main__":
    unittest.main()
