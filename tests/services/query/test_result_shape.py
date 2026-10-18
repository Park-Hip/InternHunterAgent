from __future__ import annotations

import unittest

from src.services.query.models import TableArtifact
from src.services.query.result_shape import classify_result_shape, counted_total


class ClassifyResultShapeTests(unittest.TestCase):
    def test_a_listing_is_rows(self) -> None:
        for sql in (
            "SELECT id, title FROM clean_jobs",
            "SELECT id FROM clean_jobs WHERE location ILIKE '%Hanoi%' ORDER BY id",
            "SELECT DISTINCT city FROM clean_jobs",
        ):
            with self.subTest(sql=sql):
                self.assertEqual(classify_result_shape(sql), "rows")

    def test_a_count_of_every_row_is_a_match_count(self) -> None:
        for sql in (
            "SELECT COUNT(*) AS count FROM clean_jobs",
            "select count ( * ) as \"count\" from clean_jobs where location ILIKE '%Hanoi%'",
            "SELECT COUNT(1) AS total FROM clean_jobs",
            "SELECT COUNT(*) FROM clean_jobs",
            "SELECT COUNT(*) AS count FROM (SELECT id FROM clean_jobs) AS matches",
        ):
            with self.subTest(sql=sql):
                self.assertEqual(classify_result_shape(sql), "match_count")

    def test_a_grouped_count_is_a_summary(self) -> None:
        for sql in (
            "SELECT COUNT(*) AS count FROM clean_jobs GROUP BY location",
            "SELECT location, COUNT(*) AS count FROM clean_jobs GROUP BY location",
            "SELECT COUNT(*) AS count FROM clean_jobs HAVING COUNT(*) > 1",
        ):
            with self.subTest(sql=sql):
                self.assertEqual(classify_result_shape(sql), "summary")

    def test_other_aggregates_are_summaries(self) -> None:
        for sql in (
            "SELECT AVG(salary_min) AS average FROM clean_jobs",
            "SELECT SUM(salary_max) FROM clean_jobs",
            "SELECT MIN(salary_min), MAX(salary_max) FROM clean_jobs",
            "SELECT COUNT(*) OVER () AS total, id FROM clean_jobs",
            "SELECT (SELECT COUNT(*) FROM clean_jobs) AS n FROM clean_jobs",
        ):
            with self.subTest(sql=sql):
                self.assertEqual(classify_result_shape(sql), "summary")

    def test_counts_of_values_rather_than_rows_are_summaries(self) -> None:
        for sql in (
            "SELECT COUNT(salary_min) AS count FROM clean_jobs",
            "SELECT COUNT(DISTINCT company) AS companies FROM clean_jobs",
        ):
            with self.subTest(sql=sql):
                self.assertEqual(classify_result_shape(sql), "summary")

    def test_a_statement_without_a_from_has_no_match_set(self) -> None:
        self.assertEqual(classify_result_shape("SELECT 1"), "summary")


class CountedTotalTests(unittest.TestCase):
    def test_a_single_count_column_holds_the_total(self) -> None:
        table = TableArtifact(columns=["count"], rows=[[11]], row_count=1)

        self.assertEqual(counted_total(table), 11)

    def test_a_counted_zero_is_a_total(self) -> None:
        table = TableArtifact(columns=["count"], rows=[[0]], row_count=1)

        self.assertEqual(counted_total(table), 0)

    def test_a_value_that_is_not_a_count_is_not_a_total(self) -> None:
        for columns, rows in (
            (["count"], [[True]]),
            (["average"], [[17500625.5]]),
            (["count"], [["11"]]),
            (["count"], [[-1]]),
            (["count", "extra"], [[11, 1]]),
            (["count"], [[11], [12]]),
            ([], []),
        ):
            with self.subTest(columns=columns, rows=rows):
                table = TableArtifact(columns=columns, rows=rows, row_count=len(rows))

                self.assertIsNone(counted_total(table))


if __name__ == "__main__":
    unittest.main()
