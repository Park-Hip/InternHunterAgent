"""Report formatting: group scored scenarios by metric name.

Each scenario may be scored by multiple metrics. ``group_by_metric`` returns
an ordered dict mapping metric name to a list of per-scenario result rows.
That grouped structure is the one the CLI renders and the JSON artifact
persists, so both views read from a single deterministic grouping.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def group_by_metric(
    results: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Group a flat list of scenario-result dicts by their metric name.

    Each element in ``results`` is expected to carry at least ``scenario_id``
    and ``metric`` keys, plus the raw score data under ``score``.
    """
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in results:
        grouped[row["metric"]].append(row)
    return dict(grouped)


def to_table_rows(grouped: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Flatten the grouped output into a list of rows for tabular display.

    Columns are: scenario_id, then one column per metric name in sorted order,
    then ``status`` (overall PASS/FAIL across the metrics that scenario was
    actually scored on).
    """
    if not grouped:
        return []
    all_metrics = sorted({r["metric"] for rows in grouped.values() for r in rows})
    scenario_ids = sorted({r["scenario_id"] for rows in grouped.values() for r in rows})
    rows: list[dict[str, Any]] = []
    for sid in scenario_ids:
        row: dict[str, Any] = {"scenario_id": sid}
        scored: list[float | None] = []
        for m in all_metrics:
            scores = [r["score"] for r in grouped.get(m, []) if r["scenario_id"] == sid]
            row[m] = min(scores) if scores and all(score is not None for score in scores) else None
            if scores:
                scored.append(row[m])
        row["status"] = "UNRUN" if any(value is None for value in scored) else "PASS" if all(value == 1.0 for value in scored) else "FAIL"
        rows.append(row)
    return rows


def print_table(rows: list[dict[str, Any]]) -> None:
    if not rows:
        print("No results to display.")
        return
    columns = list(rows[0].keys())
    widths = {col: len(col) for col in columns}
    for row in rows:
        for col in columns:
            val = str(row[col]) if row[col] is not None else "-"
            widths[col] = max(widths[col], len(val))
    header = "  ".join(f"{col:<{widths[col]}}" for col in columns)
    sep = "  ".join("-" * widths[col] for col in columns)
    print(header)
    print(sep)
    for row in rows:
        parts = []
        for col in columns:
            val = str(row[col]) if row[col] is not None else "-"
            parts.append(f"{val:<{widths[col]}}")
        print("  ".join(parts))
