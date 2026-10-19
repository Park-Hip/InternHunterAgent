import re
from typing import NamedTuple

# Trailing LIMIT (value captured) + optional OFFSET at statement end, case-insensitive.
_TRAILING_LIMIT = re.compile(r"\s+LIMIT\s+(\d+)(?:\s+OFFSET\s+\d+)?\s*$", re.IGNORECASE)


class FetchBounds(NamedTuple):
    base_sql: str  # validated SELECT with any trailing LIMIT/OFFSET removed
    limit: int     # rows to fetch; the user's count when at most max_rows


def resolve_bounds(sql: str, max_rows: int) -> FetchBounds:
    """Decide how many rows one validated SELECT may fetch.

    A trailing LIMIT is treated as an explicit user-requested count: if it is
    within the safety cap (<= max_rows) it is honored exactly, otherwise the
    system fetches ``max_rows``. The caller states the real match total
    separately (``execute_bounded_select`` counts the base query), so no
    sentinel row and no display cap are needed.
    """
    text = sql.rstrip()
    match = _TRAILING_LIMIT.search(text)
    user_limit = int(match.group(1)) if match else None
    stripped = _TRAILING_LIMIT.sub("", text)

    if user_limit is not None and user_limit <= max_rows:
        return FetchBounds(base_sql=stripped, limit=user_limit)
    return FetchBounds(base_sql=stripped, limit=max_rows)
