"""Unit tests for how one validated SELECT's fetch window is decided (#702, #721, #742).

``resolve_bounds`` returns the statement without its own LIMIT/OFFSET/FETCH
clause plus the row count to fetch and the page offset; the executor appends
``LIMIT`` and ``OFFSET``. The count the model is told comes from the companion
count query over the base statement, not from a sentinel row or the page
length, so a later page still reports the whole match set.

The bound is read from PostgreSQL's parse tree, so ``FETCH FIRST`` and
``LIMIT ALL`` are bounds rather than text the executor appends a second
``LIMIT`` to, and a non-literal bound is refused with a named reason (#742).
"""

from __future__ import annotations

import unittest

from src.services.query.row_bound import FetchBounds, resolve_bounds
from src.services.query.statement import StatementError


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


class ParsedBoundTests(unittest.TestCase):
    """#742: bounds are read from the tree, not from the end of the text."""

    def test_fetch_first_rows_only_is_a_limit(self) -> None:
        result = resolve_bounds(
            "SELECT id FROM clean_jobs ORDER BY id FETCH FIRST 3 ROWS ONLY",
            max_rows=20,
        )

        self.assertEqual(
            result,
            FetchBounds(
                base_sql="SELECT id FROM clean_jobs ORDER BY id",
                limit=3,
                offset=0,
            ),
        )

    def test_fetch_first_with_offset_is_a_page(self) -> None:
        result = resolve_bounds(
            "SELECT id FROM clean_jobs ORDER BY id OFFSET 10 ROWS "
            "FETCH NEXT 3 ROWS ONLY",
            max_rows=20,
        )

        self.assertEqual(
            result,
            FetchBounds(
                base_sql="SELECT id FROM clean_jobs ORDER BY id",
                limit=3,
                offset=10,
            ),
        )

    def test_fetch_first_row_only_fetches_one(self) -> None:
        result = resolve_bounds(
            "SELECT id FROM clean_jobs ORDER BY id FETCH FIRST ROW ONLY",
            max_rows=20,
        )

        self.assertEqual(result.limit, 1)

    def test_limit_all_is_no_user_limit(self) -> None:
        result = resolve_bounds("SELECT id FROM clean_jobs LIMIT ALL", max_rows=20)

        self.assertEqual(
            result,
            FetchBounds(base_sql="SELECT id FROM clean_jobs", limit=20, offset=0),
        )

    def test_limit_all_after_an_order_is_stripped(self) -> None:
        result = resolve_bounds(
            "SELECT id FROM clean_jobs ORDER BY id LIMIT ALL", max_rows=20
        )

        self.assertEqual(
            result,
            FetchBounds(
                base_sql="SELECT id FROM clean_jobs ORDER BY id", limit=20, offset=0
            ),
        )

    def test_a_non_literal_limit_is_rejected_with_a_named_reason(self) -> None:
        with self.assertRaises(StatementError) as raised:
            resolve_bounds("SELECT id FROM clean_jobs LIMIT 2+1", max_rows=20)

        self.assertIn("LIMIT must be an integer literal", raised.exception.reason)

    def test_a_negative_limit_is_rejected(self) -> None:
        with self.assertRaises(StatementError) as raised:
            resolve_bounds("SELECT id FROM clean_jobs LIMIT -1", max_rows=20)

        self.assertIn("LIMIT must not be negative", raised.exception.reason)

    def test_a_fetch_with_ties_is_rejected(self) -> None:
        with self.assertRaises(StatementError) as raised:
            resolve_bounds(
                "SELECT id FROM clean_jobs ORDER BY id FETCH FIRST 3 ROWS WITH TIES",
                max_rows=20,
            )

        self.assertIn("WITH TIES", raised.exception.reason)

    def test_a_quoted_alias_named_limit_is_not_the_bound(self) -> None:
        sql = 'SELECT id AS "limit" FROM clean_jobs ORDER BY id LIMIT 2'

        result = resolve_bounds(sql, max_rows=20)

        self.assertEqual(
            result,
            FetchBounds(
                base_sql='SELECT id AS "limit" FROM clean_jobs ORDER BY id',
                limit=2,
                offset=0,
            ),
        )

    def test_a_cte_bound_is_part_of_the_cte_not_the_page(self) -> None:
        sql = (
            "WITH newest AS (SELECT id FROM clean_jobs ORDER BY id LIMIT 5) "
            "SELECT id FROM newest ORDER BY id"
        )

        result = resolve_bounds(sql, max_rows=20)

        self.assertEqual(result, FetchBounds(base_sql=sql, limit=20, offset=0))

    def test_the_page_bound_is_stripped_even_when_a_cte_has_its_own(self) -> None:
        sql = (
            "WITH newest AS (SELECT id FROM clean_jobs ORDER BY id LIMIT 5) "
            "SELECT id FROM newest ORDER BY id LIMIT 2 OFFSET 4"
        )

        result = resolve_bounds(sql, max_rows=20)

        self.assertEqual(
            result,
            FetchBounds(
                base_sql=(
                    "WITH newest AS (SELECT id FROM clean_jobs ORDER BY id LIMIT 5) "
                    "SELECT id FROM newest ORDER BY id"
                ),
                limit=2,
                offset=4,
            ),
        )

    def test_a_bound_inside_a_string_literal_is_not_a_bound(self) -> None:
        sql = "SELECT id FROM clean_jobs WHERE title = 'LIMIT 5'"

        result = resolve_bounds(sql, max_rows=20)

        self.assertEqual(result, FetchBounds(base_sql=sql, limit=20, offset=0))

    def test_a_parenthesised_statement_keeps_its_parentheses(self) -> None:
        # The bound is inside the parentheses; removing it must keep the
        # closing parenthesis so the executor appends its clause outside.
        sql = "(SELECT id FROM clean_jobs ORDER BY id LIMIT 2 OFFSET 1)"

        result = resolve_bounds(sql, max_rows=20)

        self.assertEqual(
            result,
            FetchBounds(
                base_sql="(SELECT id FROM clean_jobs ORDER BY id)",
                limit=2,
                offset=1,
            ),
        )

    def test_nested_parentheses_keep_their_balance(self) -> None:
        sql = "((SELECT id FROM clean_jobs ORDER BY id LIMIT 2))"

        result = resolve_bounds(sql, max_rows=20)

        self.assertEqual(
            result,
            FetchBounds(
                base_sql="((SELECT id FROM clean_jobs ORDER BY id))",
                limit=2,
                offset=0,
            ),
        )


if __name__ == "__main__":
    unittest.main()
