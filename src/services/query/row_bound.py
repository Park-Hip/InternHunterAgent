import re
from typing import NamedTuple

# Trailing bounds at statement end, case-insensitive. The SQL generator writes
# either `LIMIT n`, `LIMIT n OFFSET m`, or `OFFSET m` alone. Postgres also
# accepts `OFFSET m LIMIT n`, so that order is recognized too. A trailing
# integer-literal OFFSET is a page start; an OFFSET inside a subquery is part
# of the query and is left alone.
_TRAILING_BOUNDS = re.compile(
    r"\s+(?:"
    r"OFFSET\s+(?P<offset_first>\d+)\s+LIMIT\s+(?P<limit_first>\d+)"
    r"|"
    r"LIMIT\s+(?P<limit>\d+)(?:\s+OFFSET\s+(?P<offset>\d+))?"
    r")\s*$",
    re.IGNORECASE,
)
_TRAILING_OFFSET = re.compile(r"\s+OFFSET\s+(?P<offset>\d+)\s*$", re.IGNORECASE)


class FetchBounds(NamedTuple):
    base_sql: str  # validated SELECT with any trailing LIMIT/OFFSET removed
    limit: int     # rows to fetch; the user's count when at most max_rows
    offset: int = 0  # rows to skip before the fetch; a page start


def resolve_bounds(sql: str, max_rows: int) -> FetchBounds:
    """Decide how many rows one validated SELECT may fetch, and from where.

    A trailing LIMIT is treated as an explicit user-requested count: if it is
    within the safety cap (<= max_rows) it is honored exactly, otherwise the
    system fetches ``max_rows``. A trailing OFFSET is never capped because it
    is a position, not a row count. ``OFFSET m`` without a LIMIT starts at row
    ``m`` and fetches up to ``max_rows``, matching PostgreSQL's own semantics.

    The caller states the real match total separately
    (``execute_bounded_select`` counts the base query without LIMIT or OFFSET),
    so a short or empty later page can still report the whole match set and no
    sentinel row or display cap is needed.
    """
    text = sql.rstrip()
    offset = 0
    user_limit: int | None = None

    match = _TRAILING_BOUNDS.search(text)
    if match is not None:
        user_limit = int(match.group("limit") or match.group("limit_first"))
        offset = int(match.group("offset") or match.group("offset_first") or 0)
        stripped = text[: match.start()].rstrip()
    else:
        offset_match = _TRAILING_OFFSET.search(text)
        if offset_match is not None:
            offset = int(offset_match.group("offset"))
            stripped = text[: offset_match.start()].rstrip()
        else:
            stripped = text

    if user_limit is not None and user_limit <= max_rows:
        return FetchBounds(base_sql=stripped, limit=user_limit, offset=offset)
    return FetchBounds(base_sql=stripped, limit=max_rows, offset=offset)
