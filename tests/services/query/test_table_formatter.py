from __future__ import annotations

import unittest

from src.services.query.table_formatter import format_rows


class FormatRowsTests(unittest.TestCase):
    def test_empty_input_returns_empty_table_artifact(self) -> None:
        table = format_rows([])

        self.assertEqual(table.columns, [])
        self.assertEqual(table.rows, [])
        self.assertEqual(table.row_count, 0)

    def test_single_row_formats_columns_and_row(self) -> None:
        table = format_rows([{"title": "Data Analyst", "company": "Acme"}])

        self.assertEqual(table.columns, ["title", "company"])
        self.assertEqual(table.rows, [["Data Analyst", "Acme"]])
        self.assertEqual(table.row_count, 1)

    def test_multi_row_preserves_column_order_from_first_row(self) -> None:
        rows = [
            {"title": "Data Analyst", "company": "Acme"},
            {"title": "ML Intern", "company": "Globex"},
        ]

        table = format_rows(rows)

        self.assertEqual(table.columns, ["title", "company"])
        self.assertEqual(
            table.rows,
            [["Data Analyst", "Acme"], ["ML Intern", "Globex"]],
        )
        self.assertEqual(table.row_count, 2)

    def test_missing_key_in_later_row_renders_as_none(self) -> None:
        rows = [
            {"title": "Data Analyst", "company": "Acme"},
            {"title": "ML Intern"},
        ]

        table = format_rows(rows)

        self.assertEqual(table.columns, ["title", "company"])
        self.assertEqual(
            table.rows,
            [["Data Analyst", "Acme"], ["ML Intern", None]],
        )
        self.assertEqual(table.row_count, 2)
