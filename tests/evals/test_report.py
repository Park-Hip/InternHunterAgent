"""Offline tests for evals.report — grouping and table formatting.

No network calls, no provider credentials, no database required.
"""

from __future__ import annotations

import pytest

from evals.report import group_by_metric, print_table, to_table_rows


class TestGroupByMetric:
    def test_empty(self) -> None:
        assert group_by_metric([]) == {}

    def test_groups_by_name(self) -> None:
        results = [
            {"scenario_id": "A", "metric": "tool_correctness", "score": 1.0},
            {"scenario_id": "A", "metric": "sql_accuracy", "score": 0.0},
            {"scenario_id": "B", "metric": "tool_correctness", "score": 1.0},
        ]
        grouped = group_by_metric(results)
        assert set(grouped.keys()) == {"tool_correctness", "sql_accuracy"}
        assert len(grouped["tool_correctness"]) == 2
        assert len(grouped["sql_accuracy"]) == 1

    def test_preserves_order(self) -> None:
        results = [
            {"scenario_id": "B", "metric": "z", "score": 1.0},
            {"scenario_id": "A", "metric": "a", "score": 0.0},
        ]
        grouped = group_by_metric(results)
        assert list(grouped.keys()) == ["z", "a"]


class TestToTableRows:
    def test_empty(self) -> None:
        assert to_table_rows({}) == []

    def test_single_scenario(self) -> None:
        grouped = {"m1": [{"scenario_id": "X", "metric": "m1", "score": 1.0}]}
        rows = to_table_rows(grouped)
        assert len(rows) == 1
        assert rows[0]["scenario_id"] == "X"
        assert rows[0]["m1"] == 1.0

    def test_status_pass(self) -> None:
        grouped = {
            "m1": [{"scenario_id": "X", "metric": "m1", "score": 1.0}],
            "m2": [{"scenario_id": "X", "metric": "m2", "score": 1.0}],
        }
        rows = to_table_rows(grouped)
        assert rows[0]["status"] == "PASS"

    def test_status_fail(self) -> None:
        grouped = {
            "m1": [{"scenario_id": "X", "metric": "m1", "score": 0.0}],
        }
        rows = to_table_rows(grouped)
        assert rows[0]["status"] == "FAIL"

    def test_status_unrun(self) -> None:
        grouped = {}
        rows = to_table_rows(grouped)
        assert rows == []

    def test_missing_metric_columns(self) -> None:
        grouped = {
            "a": [{"scenario_id": "X", "metric": "a", "score": 1.0}],
        }
        rows = to_table_rows(grouped)
        assert "b" not in rows[0] or rows[0].get("b") is None


class TestPrintTable:
    def test_empty_output(self, capsys: pytest.CaptureFixture) -> None:
        print_table([])
        captured = capsys.readouterr()
        assert "No results" in captured.out

    def test_header_and_rows(self, capsys: pytest.CaptureFixture) -> None:
        rows = [{"scenario_id": "A", "m": 1.0, "status": "PASS"}]
        print_table(rows)
        captured = capsys.readouterr()
        assert "scenario_id" in captured.out
        assert "A" in captured.out
