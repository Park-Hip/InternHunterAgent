"""Unit tests for the JSON shaping boundary the tools return (#702)."""

from __future__ import annotations

import datetime as dt
import decimal
import unittest

from src.services.query.table_formatter import json_value, shape_rows


class JsonValueTests(unittest.TestCase):
    def test_json_native_values_pass_through(self) -> None:
        for value in (None, True, False, 7, -3, 1.5, 0.0, "Data Analyst", ""):
            with self.subTest(value=value):
                self.assertIs(json_value(value), value)

    def test_an_integral_decimal_becomes_an_int(self) -> None:
        self.assertEqual(json_value(decimal.Decimal("17500625")), 17500625)
        self.assertIsInstance(json_value(decimal.Decimal("17500625")), int)

    def test_a_fractional_decimal_becomes_a_float(self) -> None:
        self.assertEqual(json_value(decimal.Decimal("17500625.5")), 17500625.5)
        self.assertIsInstance(json_value(decimal.Decimal("17500625.5")), float)

    def test_dates_and_times_become_iso_strings(self) -> None:
        self.assertEqual(json_value(dt.date(2026, 10, 18)), "2026-10-18")
        self.assertEqual(
            json_value(dt.datetime(2026, 10, 18, 9, 30, 15)),
            "2026-10-18T09:30:15",
        )
        self.assertEqual(json_value(dt.time(9, 30, 15)), "09:30:15")

    def test_anything_else_becomes_its_string_form(self) -> None:
        self.assertEqual(json_value(b"bytes"), "b'bytes'")


class ShapeRowsTests(unittest.TestCase):
    def test_keeps_the_columns_and_rows_it_is_given(self) -> None:
        columns, rows = shape_rows(
            ["id", "title"], [[1, "Data Analyst"], [2, "ML Intern"]]
        )

        self.assertEqual(columns, ["id", "title"])
        self.assertEqual(rows, [[1, "Data Analyst"], [2, "ML Intern"]])

    def test_drops_the_description_column_case_insensitively(self) -> None:
        for column in ("description", "Description", "DESCRIPTION"):
            with self.subTest(column=column):
                columns, rows = shape_rows(
                    ["id", column, "title"], [[1, "a very long blob", "Data Analyst"]]
                )

                self.assertEqual(columns, ["id", "title"])
                self.assertEqual(rows, [[1, "Data Analyst"]])

    def test_shapes_every_kept_value(self) -> None:
        columns, rows = shape_rows(
            ["posted", "salary_min", "unused"],
            [[dt.date(2026, 10, 18), decimal.Decimal("17500625"), "x"]],
        )

        self.assertEqual(columns, ["posted", "salary_min", "unused"])
        self.assertEqual(rows, [["2026-10-18", 17500625, "x"]])

    def test_empty_input_stays_empty(self) -> None:
        self.assertEqual(shape_rows([], []), ([], []))


if __name__ == "__main__":
    unittest.main()
