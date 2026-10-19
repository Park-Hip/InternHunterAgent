from typing import Any, Literal

from pydantic import BaseModel

#: The values a tool result may carry: JSON-native scalars. Database values are
#: converted at the tool boundary (``Decimal`` to ``int``/``float``, dates to
#: ISO strings), so the model receives exactly what FastMCP can serialize.
JsonValue = bool | int | float | str | None

#: What a validated SELECT's result rows represent, as classified by
#: ``result_shape.classify_result_shape``. ``rows`` enumerates matching records,
#: ``match_count`` is a single count of them, and ``summary`` is any other
#: aggregation whose rows are figures rather than matches.
ResultShape = Literal["rows", "match_count", "summary"]


class BoundedRows(BaseModel):
    """One bounded read: the columns, the rows, and the unbounded total."""

    columns: list[str]
    rows: list[list[Any]]
    total_rows: int


class QueryResult(BaseModel):
    """The typed facts one ``query_clean_jobs`` call returns to the model.

    No user-facing sentence is built here (#702). ``sql`` is the statement that
    ran, after bounds; the system prompt owns what may be said about it.
    """

    sql: str
    columns: list[str]
    rows: list[list[JsonValue]]
    row_count: int
    total_rows: int


class JobDetailsResult(BaseModel):
    """The typed facts one ``get_job_details`` call returns to the model."""

    jobs: list[dict[str, JsonValue]]
    not_found: list[int]
    not_fetched: list[int]


class ValidationResult(BaseModel):
    valid: bool
    sql: str
    reason: str = ""
