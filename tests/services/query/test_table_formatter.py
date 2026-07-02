from __future__ import annotations

import unittest

from src.services.query.table_formatter import format_rows


class FormatRowsTests(unittest.TestCase):
    def test_empty_input_returns_empty_table_artifact(self) -> None:
        table = format_rows([], max_rows=20)

        self.assertEqual(table.columns, [])
        self.assertEqual(table.rows, [])
        self.assertEqual(table.row_count, 0)

    def test_single_row_formats_columns_and_row(self) -> None:
        table = format_rows([{"title": "Data Analyst", "company": "Acme"}], max_rows=20)

        self.assertEqual(table.columns, ["title", "company"])
        self.assertEqual(table.rows, [["Data Analyst", "Acme"]])
        self.assertEqual(table.row_count, 1)

    def test_multi_row_preserves_column_order_from_first_row(self) -> None:
        rows = [
            {"title": "Data Analyst", "company": "Acme"},
            {"title": "ML Intern", "company": "Globex"},
        ]

        table = format_rows(rows, max_rows=20)

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

        table = format_rows(rows, max_rows=20)

        self.assertEqual(table.columns, ["title", "company"])
        self.assertEqual(
            table.rows,
            [["Data Analyst", "Acme"], ["ML Intern", None]],
        )
        self.assertEqual(table.row_count, 2)

    def test_description_column_is_dropped_even_when_present(self) -> None:
        rows = [
            {"title": "Data Analyst", "company": "Acme", "description": "a very long blob"},
        ]

        table = format_rows(rows, max_rows=20)

        self.assertEqual(table.columns, ["title", "company"])
        self.assertEqual(table.rows, [["Data Analyst", "Acme"]])
        self.assertEqual(table.row_count, 1)

    def test_wide_result_is_capped_but_true_total_is_preserved(self) -> None:
        rows = [{"title": f"Intern {i}", "company": "Acme"} for i in range(25)]

        table = format_rows(rows, max_rows=20)

        self.assertEqual(len(table.rows), 20)
        self.assertEqual(table.row_count, 25)
