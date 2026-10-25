"""Deterministic shape filter for LLM-authored SQL, read from PostgreSQL's tree.

This is the trust boundary: the query only runs if the checks below pass. The
checks themselves live in :mod:`src.services.query.statement`, which parses the
statement once with the PostgreSQL grammar (``pglast``) and reads the facts from
the tree instead of the text. A statement passes when:

  1. It is not empty, it is one statement, and it starts with SELECT, WITH, or
     a parenthesised SELECT.
  2. It contains no SQL comments.
  3. PostgreSQL parses it and the top-level node is a SELECT, including CTEs,
     subqueries, set operations, and set-returning functions in FROM.
  4. It does not write: no SELECT INTO, no row locking, and no data-modifying
     statement in a WITH clause.
  5. Every relation is ``clean_jobs`` (optionally ``public.clean_jobs``) or a
     CTE in scope, no system table is named, and ``clean_jobs`` appears once
     per FROM clause.
  6. Every function is on the explicit allowlist, with server identity and
     server-side calls named for what they are.
  7. No hidden ingestion or lifecycle column is named.
  8. Its bounds are integer literals, and ``FETCH ... WITH TIES`` is refused.

Read-only enforcement at execution time is separate: the executor marks its
transaction ``READ ONLY``. This layer restricts *scope* (which statement shape,
which relations, which functions). It is deliberately not the column boundary:
the grant on the 16 declared columns is, so a star or a whole-row read passes
here and is refused by PostgreSQL (ADR-0063).
"""

from src.services.query.models import ValidationResult
from src.services.query.statement import (
    HIDDEN_COLUMNS,
    StatementError,
    parse_statement,
)

__all__ = ["HIDDEN_COLUMNS", "has_id_tiebreak", "validate_sql"]


def validate_sql(sql: str) -> ValidationResult:
    """Vet an agent-generated SQL string before it is executed.

    Returns the normalized statement when it is inside the contract, or a
    reason that names the rule that refused it. Parsing happens in
    :func:`src.services.query.statement.parse_statement`; this function only
    carries its answer into the tool's typed result.
    """
    try:
        parsed = parse_statement(sql)
    except StatementError as exc:
        return ValidationResult(valid=False, sql=exc.sql, reason=exc.reason)
    return ValidationResult(valid=True, sql=parsed.sql)


def has_id_tiebreak(sql: str) -> bool:
    """Whether a SELECT's top-level ORDER BY includes ``id`` as a sort key.

    A page boundary is only stable when the order is total. PostgreSQL promises
    no row order for a query without ORDER BY, and an order on a non-unique
    column such as ``created_on`` can swap tied rows between two calls, so an
    OFFSET page can repeat or skip rows even though the OFFSET is correct.
    ``id`` is the primary key, so a top-level ORDER BY that includes it as a
    sort key orders every row uniquely (#727, ADR-0064).

    Only the outermost ORDER BY counts: an ORDER BY inside a subquery or a
    window function does not order the rows the page slices. The statement is
    assumed to have passed ``validate_sql``; anything that fails the same
    contract has no order this function can vouch for, so it returns False.
    """
    try:
        return parse_statement(sql).orders_by_id
    except StatementError:
        return False
