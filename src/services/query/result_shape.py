"""Classify what a validated SELECT's rows mean, so the interface can say.

`row_count` on the public `tool` event means "how many rows the tool actually
matched". A plain listing's table rows are those matches, so its row count is
the number to publish. An aggregate is different: `SELECT COUNT(*) AS count`
returns one row holding the number of matches, so publishing the table's row
count states "1 kết quả" for a count of 11 and contradicts the answer (#677).

This module owns that distinction. It reads the SQL rather than the result
table, because a table with one row and one integer cannot be told apart from
`SELECT id FROM clean_jobs LIMIT 1`; only the projection says which it is.

Detection is deliberately conservative. Only a count of every row in the
filtered set is a match count: `COUNT(<column>)` counts non-null values and
`COUNT(DISTINCT ...)` counts distinct values, so both are summaries. A shape
this module misreads costs a missing count on the card, never a wrong one.
"""

from __future__ import annotations

import re

from src.services.query.models import ResultShape, TableArtifact

# The select list of the outermost query: everything between its SELECT and its
# FROM. A nested SELECT inside the list leaves this capture unterminated, which
# fails the count match below and downgrades the shape to a summary.
_SELECT_LIST = re.compile(r"\bselect\s+(.*?)\s+from\b", re.IGNORECASE | re.DOTALL)

# A count of every row in the filtered set - the only projection whose single
# value is the number of matching records. `*` and `1` count rows the same way,
# and the alias is optional because the count prompt mandates `AS count` while
# a model may still omit or quote it.
_MATCH_COUNT = re.compile(
    r'count\s*\(\s*(?:\*|1)\s*\)(?:\s+(?:as\s+)?(?:"[^"]*"|[A-Za-z_][A-Za-z0-9_]*))?',
    re.IGNORECASE,
)

_AGGREGATE_FUNCTION = re.compile(r"\b(?:count|sum|avg|min|max)\s*\(", re.IGNORECASE)
_GROUPING = re.compile(r"\b(?:group\s+by|having)\b", re.IGNORECASE)


def classify_result_shape(sql: str) -> ResultShape:
    """Return what one validated SELECT's result rows represent."""
    select_list = _SELECT_LIST.search(sql)
    if select_list is None:
        # Nothing to enumerate and nothing counted: a statement without a FROM
        # has no match set to report a size for.
        return "summary"

    list_text = select_list.group(1).strip()
    if _MATCH_COUNT.fullmatch(list_text) and not _GROUPING.search(sql):
        # The grouping check is what keeps `COUNT(*) ... GROUP BY location` out:
        # with a GROUP BY the count is per group, not a total.
        return "match_count"

    if _AGGREGATE_FUNCTION.search(list_text) or _GROUPING.search(sql):
        return "summary"

    return "rows"


def counted_total(table: TableArtifact) -> int | None:
    """The number a match-count table holds, or None when it does not hold one."""
    if len(table.columns) != 1 or len(table.rows) != 1:
        return None

    value = table.rows[0][0]
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None

    return value
