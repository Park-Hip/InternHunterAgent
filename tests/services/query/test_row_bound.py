from __future__ import annotations

import unittest

from src.services.query.row_bound import enforce_fetch_limit


class EnforceFetchLimitTests(unittest.TestCase):
    def test_trailing_limit_is_replaced(self) -> None:
        sql = "SELECT title FROM clean_jobs LIMIT 5"

        result = enforce_fetch_limit(sql, 21)

        self.assertTrue(result.endswith("LIMIT 21"))
        self.assertEqual(result.upper().count("LIMIT"), 1)

    def test_limit_with_offset_is_stripped_and_replaced(self) -> None:
        sql = "SELECT title FROM clean_jobs LIMIT 5 OFFSET 3"

        result = enforce_fetch_limit(sql, 21)

        self.assertTrue(result.endswith("LIMIT 21"))
        self.assertNotIn("OFFSET", result.upper())
        self.assertEqual(result.upper().count("LIMIT"), 1)

    def test_no_limit_appends_one(self) -> None:
        sql = "SELECT title FROM clean_jobs WHERE company = 'Acme'"

        result = enforce_fetch_limit(sql, 21)

        self.assertTrue(result.endswith("LIMIT 21"))
        self.assertEqual(result.upper().count("LIMIT"), 1)

    def test_order_by_is_preserved_and_limit_replaced(self) -> None:
        sql = "SELECT title FROM clean_jobs ORDER BY posted_at DESC LIMIT 5"

        result = enforce_fetch_limit(sql, 21)

        self.assertTrue(result.endswith("LIMIT 21"))
        self.assertIn("ORDER BY posted_at DESC", result)
        self.assertEqual(result.upper().count("LIMIT"), 1)


if __name__ == "__main__":
    unittest.main()
