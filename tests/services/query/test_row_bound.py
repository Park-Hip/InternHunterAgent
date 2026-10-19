"""Unit tests for how one validated SELECT's fetch window is decided (#702, #721).

``resolve_bounds`` returns the statement without a trailing LIMIT/OFFSET plus
the row count to fetch and the page offset; the executor appends ``LIMIT`` and
``OFFSET``. The count the model is told comes from the companion count query
over the base statement, not from a sentinel row or the page length, so a later
page still reports the whole match set.
"""

from __future__ import annotations

import unittest

from src.services.query.row_bound import FetchBounds, resolve_bounds


class ResolveBoundsTests(unittest.TestCase):
    def test_no_limit_fetches_the_cap(self) -> None:
        sql = "SELECT title FROM clean_jobs WHERE company = 'Acme'"

        result = resolve_bounds(sql, max_rows=20)

        self.assertEqual(result, FetchBounds(base_sql=sql, limit=20, offset=0))

    def test_explicit_in_bounds_limit_is_honored(self) -> None:
        result = resolve_bounds("SELECT title FROM clean_jobs LIMIT 3", max_rows=20)

        self.assertEqual(
            result,
            FetchBounds(base_sql="SELECT title FROM clean_jobs", limit=3, offset=0),
        )

    def test_limit_equal_to_max_is_honored(self) -> None:
        result = resolve_bounds("SELECT title FROM clean_jobs LIMIT 20", max_rows=20)

        self.assertEqual(result.limit, 20)

    def test_limit_above_max_fetches_the_cap(self) -> None:
        result = resolve_bounds("SELECT title FROM clean_jobs LIMIT 50", max_rows=20)

        self.assertEqual(
            result,
            FetchBounds(base_sql="SELECT title FROM clean_jobs", limit=20, offset=0),
        )

    def test_order_by_is_preserved_with_a_honored_limit(self) -> None:
        result = resolve_bounds(
            "SELECT title FROM clean_jobs ORDER BY salary_max DESC LIMIT 3",
            max_rows=20,
        )

        self.assertEqual(
            result,
            FetchBounds(
                base_sql="SELECT title FROM clean_jobs ORDER BY salary_max DESC",
                limit=3,
                offset=0,
            ),
        )

    def test_limit_with_offset_preserves_the_offset(self) -> None:
        # #721: the second page must not be dropped and served as page 1.
        result = resolve_bounds(
            "SELECT title FROM clean_jobs LIMIT 5 OFFSET 10", max_rows=20
        )

        self.assertEqual(
            result,
            FetchBounds(
                base_sql="SELECT title FROM clean_jobs", limit=5, offset=10
            ),
        )
        # What the executor runs: the page starts after the first ten rows.
        self.assertEqual(
            f"{result.base_sql} LIMIT {result.limit} OFFSET {result.offset}",
            "SELECT title FROM clean_jobs LIMIT 5 OFFSET 10",
        )

    def test_offset_without_limit_fetches_the_cap_from_the_offset(self) -> None:
        # #721: Postgres allows OFFSET without LIMIT. It is a page start, not
        # a clause that survives into the base query and breaks the total.
        result = resolve_bounds("SELECT title FROM clean_jobs OFFSET 10", max_rows=20)

        self.assertEqual(
            result,
            FetchBounds(
                base_sql="SELECT title FROM clean_jobs", limit=20, offset=10
            ),
        )

    def test_limit_above_max_keeps_the_offset(self) -> None:
        result = resolve_bounds(
            "SELECT title FROM clean_jobs LIMIT 50 OFFSET 10", max_rows=20
        )

        self.assertEqual(
            result,
            FetchBounds(
                base_sql="SELECT title FROM clean_jobs", limit=20, offset=10
            ),
        )

    def test_offset_zero_is_no_offset(self) -> None:
        result = resolve_bounds("SELECT title FROM clean_jobs OFFSET 0", max_rows=20)

        self.assertEqual(
            result,
            FetchBounds(base_sql="SELECT title FROM clean_jobs", limit=20, offset=0),
        )

    def test_offset_before_limit_is_preserved(self) -> None:
        result = resolve_bounds(
            "SELECT title FROM clean_jobs OFFSET 10 LIMIT 5", max_rows=20
        )

        self.assertEqual(
            result,
            FetchBounds(
                base_sql="SELECT title FROM clean_jobs", limit=5, offset=10
            ),
        )

    def test_offset_inside_a_subquery_is_not_a_page(self) -> None:
        sql = "SELECT id FROM (SELECT id FROM clean_jobs OFFSET 5) AS q"

        result = resolve_bounds(sql, max_rows=20)

        self.assertEqual(result, FetchBounds(base_sql=sql, limit=20, offset=0))


if __name__ == "__main__":
    unittest.main()
