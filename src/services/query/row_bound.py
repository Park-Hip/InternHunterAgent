import re
from typing import NamedTuple

# Trailing LIMIT (value captured) + optional OFFSET at statement end, case-insensitive.
_TRAILING_LIMIT = re.compile(r"\s+LIMIT\s+(\d+)(?:\s+OFFSET\s+\d+)?\s*$", re.IGNORECASE)


class FetchBounds(NamedTuple):
    sql: str          # SQL to execute — always ends in a LIMIT (TPM/display ceiling)
    display_cap: int  # max rows format_rows should display


def resolve_bounds(sql: str, max_rows: int) -> FetchBounds:
    """Decide how many rows to fetch/display for a validated SELECT.

    A trailing LIMIT is treated as an explicit user-requested count: if it is within
    the safety cap (<= max_rows) it is honored exactly. Otherwise (no LIMIT, or a LIMIT
    above the cap) the system fetches max_rows+1 as a truncation sentinel and displays
    max_rows, so an over-cap or unbounded result is reported honestly ("there are more").
    The returned SQL always ends in a LIMIT, so the executor never runs unbounded.
    """
    text = sql.rstrip()
    match = _TRAILING_LIMIT.search(text)
    user_limit = int(match.group(1)) if match else None
    stripped = _TRAILING_LIMIT.sub("", text)

    if user_limit is not None and user_limit <= max_rows:
        return FetchBounds(sql=f"{stripped} LIMIT {user_limit}", display_cap=user_limit)
    return FetchBounds(sql=f"{stripped} LIMIT {max_rows + 1}", display_cap=max_rows)
