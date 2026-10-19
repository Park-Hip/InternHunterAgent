"""Unit tests for how one validated SELECT's fetch window is decided (#702).

``resolve_bounds`` returns the statement without a trailing LIMIT/OFFSET plus
the row count to fetch; the executor appends ``LIMIT <limit>``. The count the
model is told comes from the companion count query, not from a sentinel row,
so nothing here produces ``LIMIT 21`` any more.
"""

from __future__ import annotations

import unittest

from src.services.query.row_bound import FetchBounds, resolve_bounds


class ResolveBoundsTests(unittest.TestCase):
    def test_no_limit_fetches_the_cap(self) -> None:
        sql = "SELECT title FROM clean_jobs WHERE company = 'Acme'"

        result = resolve_bounds(sql, max_rows=20)

        self.assertEqual(result, FetchBounds(base_sql=sql, limit=20))

    def test_explicit_in_bounds_limit_is_honored(self) -> None:
        result = resolve_bounds("SELECT title FROM clean_jobs LIMIT 3", max_rows=20)

        self.assertEqual(
            result, FetchBounds(base_sql="SELECT title FROM clean_jobs", limit=3)
        )

    def test_limit_equal_to_max_is_honored(self) -> None:
        result = resolve_bounds("SELECT title FROM clean_jobs LIMIT 20", max_rows=20)

        self.assertEqual(result.limit, 20)

    def test_limit_above_max_fetches_the_cap(self) -> None:
        result = resolve_bounds("SELECT title FROM clean_jobs LIMIT 50", max_rows=20)

        self.assertEqual(
            result, FetchBounds(base_sql="SELECT title FROM clean_jobs", limit=20)
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
            ),
        )

    def test_limit_with_offset_keeps_the_limit_and_drops_the_offset(self) -> None:
        # The dropped OFFSET is a known bug, kept as-is on purpose: #721 ("a
        # trailing OFFSET is dropped, so the next page returns page 1 again")
        # owns the fix. This test pins today's behavior, so the fix has to
        # change it deliberately rather than quietly.
        result = resolve_bounds(
            "SELECT title FROM clean_jobs LIMIT 5 OFFSET 10", max_rows=20
        )

        self.assertEqual(result, FetchBounds(base_sql="SELECT title FROM clean_jobs", limit=5))
        self.assertNotIn("OFFSET", result.base_sql.upper())
        # What the executor would run: the second page asks for OFFSET 10 and
        # gets the first five rows again.
        self.assertEqual(f"{result.base_sql} LIMIT {result.limit}", "SELECT title FROM clean_jobs LIMIT 5")


if __name__ == "__main__":
    unittest.main()
