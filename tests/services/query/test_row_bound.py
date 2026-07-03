from __future__ import annotations

import unittest

from src.services.query.row_bound import resolve_bounds


class ResolveBoundsTests(unittest.TestCase):
    def test_explicit_in_bounds_limit_is_honored(self) -> None:
        sql = "SELECT title FROM clean_jobs LIMIT 3"

        result = resolve_bounds(sql, max_rows=20)

        self.assertTrue(result.sql.endswith("LIMIT 3"))
        self.assertEqual(result.display_cap, 3)
        self.assertEqual(result.sql.upper().count("LIMIT"), 1)

    def test_limit_above_max_falls_back_to_sentinel(self) -> None:
        sql = "SELECT title FROM clean_jobs LIMIT 50"

        result = resolve_bounds(sql, max_rows=20)

        self.assertTrue(result.sql.endswith("LIMIT 21"))
        self.assertEqual(result.display_cap, 20)
        self.assertEqual(result.sql.upper().count("LIMIT"), 1)

    def test_no_limit_falls_back_to_sentinel(self) -> None:
        sql = "SELECT title FROM clean_jobs WHERE company = 'Acme'"

        result = resolve_bounds(sql, max_rows=20)

        self.assertTrue(result.sql.endswith("LIMIT 21"))
        self.assertEqual(result.display_cap, 20)
        self.assertEqual(result.sql.upper().count("LIMIT"), 1)

    def test_limit_with_offset_is_stripped_and_honored(self) -> None:
        sql = "SELECT title FROM clean_jobs LIMIT 5 OFFSET 10"

        result = resolve_bounds(sql, max_rows=20)

        self.assertTrue(result.sql.endswith("LIMIT 5"))
        self.assertNotIn("OFFSET", result.sql.upper())
        self.assertEqual(result.display_cap, 5)
        self.assertEqual(result.sql.upper().count("LIMIT"), 1)

    def test_limit_equal_to_max_is_honored(self) -> None:
        sql = "SELECT title FROM clean_jobs LIMIT 20"

        result = resolve_bounds(sql, max_rows=20)

        self.assertTrue(result.sql.endswith("LIMIT 20"))
        self.assertEqual(result.display_cap, 20)

    def test_order_by_preserved_with_honored_limit(self) -> None:
        sql = "SELECT title FROM clean_jobs ORDER BY salary_max DESC LIMIT 3"

        result = resolve_bounds(sql, max_rows=20)

        self.assertIn("ORDER BY salary_max DESC", result.sql)
        self.assertTrue(result.sql.endswith("LIMIT 3"))
        self.assertEqual(result.display_cap, 3)
        self.assertEqual(result.sql.upper().count("LIMIT"), 1)


if __name__ == "__main__":
    unittest.main()
