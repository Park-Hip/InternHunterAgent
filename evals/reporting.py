"""Result formatting shared by the two remaining evaluation tracks.

A run produces a flat list of metric rows. ``group_by_metric`` turns that list
into the mapping the JSON artifacts persist, and ``to_table_rows`` plus
``print_table`` render the same mapping for a terminal. Keeping the grouping in
one place means the gate and the baseline cannot drift in how they present a
pass or a failure.
"""

from __future__ import annotations

from typing import Any

PASS = 1.0


def group_by_metric(results: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Group a flat list of metric rows under their metric name."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in results:
        grouped.setdefault(row["metric"], []).append(row)
    return grouped


def to_table_rows(grouped: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Flatten the grouped output into one row per case for display."""
    if not grouped:
        return []
    all_metrics = sorted({row["metric"] for rows in grouped.values() for row in rows})
    scenario_ids = sorted({row["scenario_id"] for rows in grouped.values() for row in rows})
    rows: list[dict[str, Any]] = []
    for scenario_id in scenario_ids:
        row: dict[str, Any] = {"scenario_id": scenario_id}
        scored: list[float] = []
        for name in all_metrics:
            scores = [row["score"] for row in grouped.get(name, []) if row["scenario_id"] == scenario_id]
            row[name] = min(scores) if scores else None
            scored.extend(scores)
        row["status"] = "PASS" if all(score == PASS for score in scored) else "FAIL"
        rows.append(row)
    return rows


def print_table(rows: list[dict[str, Any]]) -> None:
    if not rows:
        print("No results to display.")
        return
    columns = list(rows[0])
    widths = {column: len(column) for column in columns}
    for row in rows:
        for column in columns:
            value = "-" if row[column] is None else str(row[column])
            widths[column] = max(widths[column], len(value))
    print("  ".join(f"{column:<{widths[column]}}" for column in columns))
    print("  ".join("-" * widths[column] for column in columns))
    for row in rows:
        values = ["-" if row[column] is None else str(row[column]) for column in columns]
        print("  ".join(f"{value:<{widths[column]}}" for value, column in zip(values, columns)))
