"""Decide how many rows one validated SELECT may fetch, and from where.

The statement's own ``LIMIT``, ``OFFSET``, or ``FETCH FIRST`` clause is read
from the parse tree (:mod:`src.services.query.statement`), not from its text
(#742). A literal bound is a user-requested count; ``LIMIT ALL`` means the
statement asks for no bound; a non-literal bound is refused with a named
reason, where the old trailing regex left it in place and the executor turned
``LIMIT 2+1`` into a second ``LIMIT`` and a syntax error (#721).
"""

from typing import NamedTuple

from src.services.query.statement import parse_statement


class FetchBounds(NamedTuple):
    base_sql: str  # validated SELECT with its own bound clause removed
    limit: int     # rows to fetch; the user's count when at most max_rows
    offset: int = 0  # rows to skip before the fetch; a page start


def resolve_bounds(sql: str, max_rows: int) -> FetchBounds:
    """Decide how many rows one validated SELECT may fetch, and from where.

    A stated LIMIT is treated as an explicit user-requested count: if it is
    within the safety cap (<= max_rows) it is honored exactly, otherwise the
    system fetches ``max_rows``. An OFFSET is never capped because it is a
    position, not a row count; without a LIMIT the statement starts at that row
    and fetches up to ``max_rows``, matching PostgreSQL's own semantics.
    ``LIMIT ALL`` and no clause both mean the cap.

    The caller states the real match total separately
    (``execute_bounded_select`` counts the base query without LIMIT or OFFSET),
    so a short or empty later page can still report the whole match set and no
    sentinel row or display cap is needed.

    Raises:
        StatementError: the statement is outside the guard's contract, or its
            bound is not a literal the executor can honor.
    """
    parsed = parse_statement(sql)

    limit = max_rows
    if parsed.limit is not None and parsed.limit <= max_rows:
        limit = parsed.limit

    return FetchBounds(
        base_sql=parsed.base_sql, limit=limit, offset=parsed.offset or 0
    )
