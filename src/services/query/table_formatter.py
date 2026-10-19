"""Shape database values into JSON-native facts for the tools.

The listing result drops the ``description`` blob (it is fetched only by
``get_job_details``), and every value becomes JSON-native: ``Decimal`` stays an
``int`` when integral and becomes a ``float`` otherwise, dates and datetimes
become ISO strings, and ``NULL`` stays ``null``.
"""

from __future__ import annotations

import datetime
import decimal
from typing import Any

from src.services.query.models import JsonValue


def json_value(value: Any) -> JsonValue:
    """Convert one database value to its JSON-native form."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, decimal.Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    return str(value)


def shape_rows(
    columns: list[str], rows: list[list[Any]]
) -> tuple[list[str], list[list[JsonValue]]]:
    """Return the listing columns and rows, without ``description``.

    ``description`` is never projected by the SQL rules, but a listing that
    asked for it explicitly is still dropped here: this is the boundary that
    guarantees the blob never reaches the model in bulk.
    """
    kept = [index for index, column in enumerate(columns) if column.lower() != "description"]
    shaped_columns = [columns[index] for index in kept]
    shaped_rows = [[json_value(row[index]) for index in kept] for row in rows]
    return shaped_columns, shaped_rows
