"""Read one agent-authored statement with PostgreSQL's own parser.

The guard and the row bound used to answer "what does this SQL do?" by scanning
its text: a keyword denylist, a regular expression for the relation after
``FROM``, and another for a trailing ``LIMIT``/``OFFSET``.  A text scan cannot
tell a comment from ``--`` inside a string literal, a CTE from a table, or
``LIMIT 2 + 1`` from no bound at all, and it refused valid statements with a
reason that was not the real one (#736).

This module parses the statement once with the grammar PostgreSQL itself uses:
``pglast`` bundles ``libpg_query``, the PostgreSQL parser compiled as a
library.  Every fact the callers need is read from the tree instead of the
text:

- which relations the statement reads, and whether a name is a CTE in scope;
- which functions it calls, checked against an explicit allowlist;
- which columns it names, so the five hidden ones are refused by name;
- its own bounds (``LIMIT``, ``OFFSET``, ``FETCH FIRST``), and whether its
  top-level ``ORDER BY`` includes ``id`` (ADR-0064).

The parser decides *shape* and *scope*.  It is not the column boundary: the
grant on the 16 declared columns stays the boundary (ADR-0063), so a star or a
whole-row read is still allowed here and refused by PostgreSQL.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from pglast import Error as PglastError
from pglast import parse_sql, scan
from pglast.ast import (
    A_Const,
    ColumnRef,
    CommonTableExpr,
    FuncCall,
    Integer,
    Node,
    RangeVar,
    SelectStmt,
    SortBy,
    SQLValueFunction,
    String,
)
from pglast.enums import LimitOption
from pglast.parser import Token

ALLOWED_TABLE = "clean_jobs"

#: Schemas a table reference may name explicitly.  ``clean_jobs`` lives in
#: ``public``; naming it changes nothing about which rows the agent reaches.
ALLOWED_SCHEMAS = frozenset({"public"})

#: Schemas whose relations are catalog metadata rather than posting data.
SYSTEM_SCHEMAS = frozenset({"pg_catalog", "information_schema"})

# Ingestion bookkeeping and lifecycle columns that exist on the physical table but
# are outside the agent-visible contract declared by `prompts.sql_generation`
# ("Reference only real columns"). The model is never told about them, so naming
# one is a silent contract break: the query executes and the answer looks fine.
# The test suite asserts this set plus the prompt's declared columns partition
# `src.api.schema_guard.EXPECTED_COLUMNS`.
HIDDEN_COLUMNS = frozenset(
    {"source", "external_id", "posted_date", "first_seen_at", "last_seen_at"}
)

# The functions the agent may call, grouped by what they are for. This is an
# allowlist, not a denylist: a name that is not here is refused, so a function
# added to PostgreSQL in a later release is unavailable until it is reviewed.
# Names are exact: an unquoted name reaches the tree folded to lowercase, so a
# quoted `"LOWER"` (which PostgreSQL would resolve case-sensitively) is not the
# `lower` that is allowlisted.
ALLOWED_FUNCTIONS = frozenset(
    {
        # Aggregates.
        "array_agg",
        "avg",
        "bool_and",
        "bool_or",
        "corr",
        "count",
        "covar_pop",
        "covar_samp",
        "every",
        "max",
        "min",
        "mode",
        "percentile_cont",
        "percentile_disc",
        "stddev",
        "stddev_pop",
        "stddev_samp",
        "string_agg",
        "sum",
        "var_pop",
        "var_samp",
        "variance",
        # Window functions.
        "cume_dist",
        "dense_rank",
        "first_value",
        "lag",
        "last_value",
        "lead",
        "nth_value",
        "ntile",
        "percent_rank",
        "rank",
        "row_number",
        # Strings.
        "btrim",
        "char_length",
        "character_length",
        "concat",
        "concat_ws",
        "format",
        "initcap",
        "left",
        "length",
        "lower",
        "lpad",
        "ltrim",
        "normalize",
        "octet_length",
        "overlay",
        "position",
        "repeat",
        "replace",
        "reverse",
        "right",
        "rpad",
        "rtrim",
        "split_part",
        "starts_with",
        "string_to_array",
        "string_to_table",
        "strpos",
        "substr",
        "substring",
        "to_char",
        "translate",
        "trim",
        "upper",
        # Regular expressions.
        "regexp_match",
        "regexp_matches",
        "regexp_replace",
        "regexp_split_to_array",
        "regexp_split_to_table",
        # Parser helpers. PostgreSQL rewrites `LIKE ... ESCAPE` and `SIMILAR TO`
        # into these calls, so the tree names them even though the model wrote a
        # comparison. They are pure string helpers, not a call to permit by name.
        "like_escape",
        "similar_to_escape",
        # Dates and times.
        "age",
        "date_bin",
        "date_part",
        "date_trunc",
        "extract",
        "make_date",
        "make_interval",
        "make_time",
        "make_timestamp",
        "make_timestamptz",
        "now",
        "overlaps",
        "timezone",
        "to_date",
        "to_timestamp",
        # Numbers.
        "abs",
        "cbrt",
        "ceil",
        "ceiling",
        "div",
        "exp",
        "floor",
        "gcd",
        "lcm",
        "ln",
        "log",
        "log10",
        "mod",
        "power",
        "round",
        "sign",
        "sqrt",
        "trunc",
        # Arrays and set-returning helpers.
        "array_append",
        "array_cat",
        "array_length",
        "array_lower",
        "array_position",
        "array_positions",
        "array_to_string",
        "array_upper",
        "cardinality",
        "unnest",
    }
)

# Server identity and configuration functions. They return the PostgreSQL build,
# the role, the database name, the server's address, or a server setting, and no
# grant governs them: a reader who dictates a statement can have them printed in
# an answer. They get their own reason because the fix is to remove the call,
# not to pick another function (#617 row 5, F4).
IDENTITY_FUNCTIONS = frozenset(
    {
        "current_catalog",
        "current_database",
        "current_query",
        "current_role",
        "current_schema",
        "current_setting",
        "current_user",
        "inet_client_addr",
        "inet_client_port",
        "inet_server_addr",
        "inet_server_port",
        "pg_backend_pid",
        "pg_conf_load_time",
        "pg_postmaster_start_time",
        "session_user",
        "set_config",
        "user",
        "version",
    }
)

# Functions that read server files, open large objects, connect elsewhere, block
# the connection, hold a lock, or serialize catalog state. The allowlist already
# refuses every one of them; naming this subset gives the honest reason, so a
# refusal says "this call is dangerous" rather than "this name is unknown".
SERVER_SIDE_FUNCTIONS = frozenset(
    {
        "cursor_to_xml",
        "cursor_to_xmlschema",
        "database_to_xml",
        "database_to_xmlschema",
        "dblink",
        "dblink_close",
        "dblink_connect",
        "dblink_connect_u",
        "dblink_disconnect",
        "dblink_exec",
        "dblink_fetch",
        "dblink_open",
        "lo_close",
        "lo_creat",
        "lo_create",
        "lo_export",
        "lo_from_bytea",
        "lo_get",
        "lo_import",
        "lo_lseek",
        "lo_lseek64",
        "lo_open",
        "lo_put",
        "lo_read",
        "lo_tell",
        "lo_truncate",
        "lo_truncate64",
        "lo_unlink",
        "lo_write",
        "pg_advisory_lock",
        "pg_advisory_lock_shared",
        "pg_advisory_unlock",
        "pg_advisory_unlock_all",
        "pg_advisory_unlock_shared",
        "pg_advisory_xact_lock",
        "pg_advisory_xact_lock_shared",
        "pg_cancel_backend",
        "pg_file_rename",
        "pg_file_sync",
        "pg_file_unlink",
        "pg_file_write",
        "pg_logical_emit_message",
        "pg_ls_archive_statusdir",
        "pg_ls_dir",
        "pg_ls_logdir",
        "pg_ls_tmpdir",
        "pg_ls_waldir",
        "pg_notify",
        "pg_read_binary_file",
        "pg_read_file",
        "pg_reload_conf",
        "pg_rotate_logfile",
        "pg_sleep",
        "pg_sleep_for",
        "pg_sleep_until",
        "pg_stat_file",
        "pg_switch_wal",
        "pg_terminate_backend",
        "pg_try_advisory_lock",
        "pg_try_advisory_lock_shared",
        "pg_try_advisory_xact_lock",
        "pg_try_advisory_xact_lock_shared",
        "query_to_xml",
        "query_to_xml_and_xmlschema",
        "query_to_xmlschema",
        "schema_to_xml",
        "schema_to_xml_and_xmlschema",
        "schema_to_xmlschema",
        "table_to_xml",
        "table_to_xml_and_xmlschema",
        "table_to_xmlschema",
    }
)

# Date and time keywords that PostgreSQL parses as a value, not a call. They are
# the clock the query is allowed to read; CURRENT_USER, CURRENT_CATALOG and the
# rest name the server or the role and are refused with the identity reason.
ALLOWED_VALUE_FUNCTIONS = frozenset(
    {
        "SVFOP_CURRENT_DATE",
        "SVFOP_CURRENT_TIME",
        "SVFOP_CURRENT_TIME_N",
        "SVFOP_CURRENT_TIMESTAMP",
        "SVFOP_CURRENT_TIMESTAMP_N",
        "SVFOP_LOCALTIME",
        "SVFOP_LOCALTIME_N",
        "SVFOP_LOCALTIMESTAMP",
        "SVFOP_LOCALTIMESTAMP_N",
    }
)

# Keywords that start the statement's own bound clause. The token scan below
# takes the shallowest one, because the top-level SELECT is the shallowest
# select in its text, so a LIMIT inside a subquery, a CTE, or a window frame is
# part of that query and is left alone.
BOUND_KEYWORDS = frozenset({"LIMIT", "OFFSET", "FETCH"})

# Tokens that may start a read-only statement: a SELECT, a WITH clause, or a
# parenthesised SELECT (PostgreSQL accepts `(SELECT ...)` as a statement).
STATEMENT_START_TOKENS = frozenset({"SELECT", "WITH", "ASCII_40"})

SEMICOLON_TOKEN = "ASCII_59"
OPEN_PAREN_TOKEN = "ASCII_40"
CLOSE_PAREN_TOKEN = "ASCII_41"
COMMENT_TOKENS = frozenset({"SQL_COMMENT", "C_COMMENT"})


class StatementError(Exception):
    """The statement is outside the shapes the agent may run.

    ``reason`` names the rule that refused it, in the words the model reads, so
    a rejection can be rewritten instead of guessed at. ``sql`` is the
    normalized statement that was checked.
    """

    def __init__(self, reason: str, sql: str = "") -> None:
        super().__init__(reason)
        self.reason = reason
        self.sql = sql


@dataclass(frozen=True)
class ParsedStatement:
    """The facts the guard and the row bound read from one parsed SELECT.

    ``sql`` is the normalized statement (surrounding whitespace and trailing
    semicolons removed). ``base_sql`` is the same statement without its own
    bound clause, so the executor can append its own ``LIMIT``/``OFFSET``.
    ``limit`` is the user's row count when the statement states one, and
    ``None`` for no clause and for ``LIMIT ALL``. ``offset`` is the page start
    when the statement states one.
    """

    sql: str
    base_sql: str
    limit: int | None
    offset: int | None
    orders_by_id: bool


@dataclass
class _Facts:
    """What one walk of the tree found, before the reasons are chosen."""

    system_tables: list[str] = field(default_factory=list)
    foreign_tables: list[str] = field(default_factory=list)
    identity_functions: list[str] = field(default_factory=list)
    server_side_functions: list[str] = field(default_factory=list)
    unknown_functions: list[str] = field(default_factory=list)
    identity_value_functions: list[str] = field(default_factory=list)
    hidden_columns: list[str] = field(default_factory=list)
    select_into: bool = False
    row_locking: bool = False
    modifying_cte: bool = False
    self_join: bool = False


def parse_statement(sql: str) -> ParsedStatement:
    """Parse one agent-authored statement and enforce the statement contract.

    The checks run in the order below and the first failure is the reason the
    caller reports:

      1. Not empty, one statement, and it starts with SELECT, WITH, or `(`.
      2. No SQL comments (`--`, `/* */`), detected as scanner tokens so a `--`
         inside a string literal is still data.
      3. PostgreSQL can parse it, and the top-level node is a SELECT. CTEs,
         subqueries, set operations, and set-returning functions in `FROM` are
         all part of a SELECT.
      4. The SELECT does not write: no `INTO`, no row locking, and no
         data-modifying statement in a `WITH` clause.
      5. Every relation is `clean_jobs` (optionally `public.clean_jobs`) or a
         CTE in scope, no system table is named, and `clean_jobs` appears once
         per `FROM` clause so a self-join cannot multiply the row set.
      6. Every function is on the allowlist, with the identity and server-side
         subsets named for what they are.
      7. No hidden column is named.
      8. The bounds are plain integer literals, and `FETCH ... WITH TIES` is
         refused because it needs a unique order to be a row count.

    Raises:
        StatementError: the statement is outside that contract.
    """
    statement = _strip_trailing_semicolons(sql)
    if not statement:
        raise StatementError("Empty SQL is not allowed", statement)

    tokens = _scan(statement)
    if any(token.name in COMMENT_TOKENS for token in tokens):
        raise StatementError("Comment sequences are not allowed", statement)

    if not tokens or tokens[0].name not in STATEMENT_START_TOKENS:
        if tokens and tokens[0].name == SEMICOLON_TOKEN:
            raise StatementError("Multiple statements are not allowed", statement)
        raise StatementError("Only SELECT statements are allowed", statement)

    try:
        parsed = parse_sql(statement)
    except PglastError as exc:
        # The parser's own message names the token that broke the statement,
        # which is exactly what the model needs to rewrite it.
        raise StatementError(f"SQL syntax error: {_parser_message(exc)}", statement) from exc

    if len(parsed) != 1:
        raise StatementError("Multiple statements are not allowed", statement)

    node = parsed[0].stmt
    if not isinstance(node, SelectStmt):
        raise StatementError("Only SELECT statements are allowed", statement)

    facts = _Facts()
    _walk(node, facts, frozenset())
    _raise_for_facts(facts, statement)

    limit = _bound_value(node.limitCount, "LIMIT", statement)
    offset = _bound_value(node.limitOffset, "OFFSET", statement)
    if node.limitOption == LimitOption.LIMIT_OPTION_WITH_TIES:
        raise StatementError(
            "FETCH FIRST ... WITH TIES is not allowed; use LIMIT", statement
        )

    base_sql = statement
    if node.limitCount is not None or node.limitOffset is not None:
        base_sql = _strip_own_bound(statement, tokens)

    return ParsedStatement(
        sql=statement,
        base_sql=base_sql,
        limit=limit,
        offset=offset,
        orders_by_id=_orders_by_id(node),
    )


def _strip_trailing_semicolons(sql: str) -> str:
    """Drop surrounding whitespace and every trailing `;`.

    PostgreSQL accepts `SELECT 1;;` as one statement, and so should the guard:
    the empty statement after the semicolons reads nothing. A leading `;` is
    still refused, because the statement is then preceded by one.
    """
    statement = sql.strip()
    while statement.endswith(";"):
        statement = statement[:-1].rstrip()
    return statement


def _scan(statement: str) -> list[Token]:
    """Tokenize the statement, naming an unterminated literal as a syntax error.

    The scanner raises on an unterminated string or block comment before the
    parser runs, so its failure needs the same named reason as a parse failure
    instead of escaping as an internal error.
    """
    try:
        return scan(statement)
    except PglastError as exc:
        raise StatementError(
            f"SQL syntax error: {_parser_message(exc)}", statement
        ) from exc


def _parser_message(exc: PglastError) -> str:
    """The parser's message without its byte offset.

    ``ParseError.args`` is ``(message, location)`` and its ``str`` appends
    ", at index N"; the model needs the token and the reason, not the offset.
    """
    return str(exc.args[0]) if exc.args else str(exc)


def _raise_for_facts(facts: _Facts, statement: str) -> None:
    """Turn the walk's findings into the first reason that applies."""
    if facts.modifying_cte:
        raise StatementError(
            "Data-modifying statements are not allowed in a WITH clause", statement
        )
    if facts.select_into:
        raise StatementError("SELECT INTO is not allowed", statement)
    if facts.row_locking:
        raise StatementError("Row locking clauses are not allowed", statement)
    if facts.system_tables:
        raise StatementError(
            f"Access to system tables is not allowed: {_names(facts.system_tables)}",
            statement,
        )
    if facts.foreign_tables:
        raise StatementError(
            "Query may only reference the clean_jobs table: "
            f"{_names(facts.foreign_tables)}",
            statement,
        )
    if facts.self_join:
        raise StatementError(
            "Query may only reference the clean_jobs table once; "
            "a self-join is not allowed",
            statement,
        )
    if facts.identity_functions:
        raise StatementError(
            "Server identity functions are not allowed: "
            f"{_names(facts.identity_functions)}",
            statement,
        )
    if facts.server_side_functions:
        raise StatementError(
            "Server-side function calls are not allowed: "
            f"{_names(facts.server_side_functions)}",
            statement,
        )
    if facts.unknown_functions:
        raise StatementError(
            f"Function is not allowed: {_names(facts.unknown_functions)}; "
            "only the documented function list may run",
            statement,
        )
    if facts.identity_value_functions:
        raise StatementError(
            "Server identity functions are not allowed: "
            f"{_names(facts.identity_value_functions)}",
            statement,
        )
    if facts.hidden_columns:
        raise StatementError(
            f"Hidden column(s) are not allowed: {_names(facts.hidden_columns)}",
            statement,
        )


def _names(values: list[str]) -> str:
    """The distinct names in first-seen order, for one refusal message."""
    return ", ".join(dict.fromkeys(values))


def _bound_token(tokens: list[Token]) -> tuple[int, int] | None:
    """The own-bound keyword's start offset and parenthesis depth.

    The statement's top-level SELECT is the shallowest select in its text, so
    its own ``LIMIT``/``OFFSET``/``FETCH`` keyword is the shallowest one. A
    bound inside a subquery, a CTE, or a window frame sits deeper and is part
    of that query. A quoted alias or a string literal is an ``IDENT`` or
    ``SCONST`` token, never a bound keyword.
    """
    depth = 0
    found: tuple[int, int] | None = None
    for token in tokens:
        if token.name == OPEN_PAREN_TOKEN:
            depth += 1
        elif token.name == CLOSE_PAREN_TOKEN:
            depth = max(0, depth - 1)
        elif token.name in BOUND_KEYWORDS and (found is None or depth < found[1]):
            found = (token.start, depth)
    return found


def _strip_own_bound(statement: str, tokens: list[Token]) -> str:
    """Remove the statement's own bound clause from its text.

    The clause runs from its keyword to the end of the statement, or to the
    parenthesis that closes the select it belongs to. Keeping that closing
    parenthesis is what makes a fully parenthesised ``(SELECT ... LIMIT 5)``
    become ``(SELECT ...)``: the executor then appends its own clause outside
    the parentheses and no second bound is inserted inside the query.
    """
    located = _bound_token(tokens)
    if located is None:
        # The tree says a bound exists, so its keyword is in the token stream.
        # Refusing is still safer than appending a second clause we cannot place.
        raise StatementError(
            "The statement's LIMIT or OFFSET clause could not be located",
            statement,
        )
    start, bound_depth = located

    end = len(statement)
    depth = bound_depth
    for token in tokens:
        if token.start <= start:
            continue
        if token.name == OPEN_PAREN_TOKEN:
            depth += 1
        elif token.name == CLOSE_PAREN_TOKEN:
            depth -= 1
            if depth < bound_depth:
                end = token.start
                break

    return (statement[:start].rstrip() + statement[end:]).strip()


def _bound_value(node: Node | None, clause: str, statement: str) -> int | None:
    """Read one bound as a row count, or name why it is not one.

    ``LIMIT ALL`` is an explicit "no bound" and returns ``None``. Anything that
    is not an integer literal - an arithmetic expression, a cast, a subquery, a
    parameter - is refused, because the executor cannot both honour it and
    guarantee the cap without rewriting the model's statement.
    """
    if node is None:
        return None
    if isinstance(node, A_Const) and node.isnull:
        return None
    if (
        isinstance(node, A_Const)
        and isinstance(node.val, Integer)
        and node.val.ival is not None
    ):
        if node.val.ival < 0:
            raise StatementError(f"{clause} must not be negative", statement)
        return node.val.ival
    raise StatementError(
        f"{clause} must be an integer literal, for example LIMIT 10", statement
    )


def _orders_by_id(select: SelectStmt) -> bool:
    """Whether the statement's own ORDER BY includes `id` as a sort key.

    Only the outermost ORDER BY counts: an ORDER BY inside a subquery or a
    window function does not order the rows a page slices. A computed key such
    as ``lower(id)`` and an ordinal such as ``ORDER BY 1`` are not the primary
    key's own value and are conservatively refused (ADR-0064).
    """
    for key in select.sortClause or ():
        if not isinstance(key, SortBy) or not isinstance(key.node, ColumnRef):
            continue
        fields = key.node.fields or ()
        if fields and isinstance(fields[-1], String) and fields[-1].sval == "id":
            return True
    return False


def _walk(node: Node, facts: _Facts, visible: frozenset[str]) -> None:
    """Collect facts from ``node``, with ``visible`` CTE names in scope."""
    if isinstance(node, SelectStmt):
        _walk_select(node, facts, visible)
        return
    if isinstance(node, CommonTableExpr):
        # A CTE is reached through the WITH clause that owns it, because that
        # clause decides which names are visible inside its query.
        return
    if isinstance(node, RangeVar):
        _note_table(node, facts, visible)
    elif isinstance(node, FuncCall):
        _note_function(node, facts)
    elif isinstance(node, SQLValueFunction):
        _note_value_function(node, facts)
    elif isinstance(node, ColumnRef):
        _note_column(node, facts)

    for child in _children(node):
        _walk(child, facts, visible)


def _walk_select(
    select: SelectStmt, facts: _Facts, visible: frozenset[str]
) -> None:
    """Check one SELECT's clauses in its own CTE scope."""
    body_visible = visible
    if select.withClause is not None:
        ctes = [
            cte
            for cte in select.withClause.ctes or ()
            if isinstance(cte, CommonTableExpr)
        ]
        names = frozenset(cte.ctename for cte in ctes if cte.ctename)
        if select.withClause.recursive:
            # With RECURSIVE every CTE may reference itself and the others.
            for cte in ctes:
                _walk_cte(cte, facts, visible | names)
        else:
            # Without RECURSIVE a CTE body sees only the CTEs before it; a
            # reference to its own name is the real table, so it must be
            # checked as one.
            earlier: set[str] = set()
            for cte in ctes:
                _walk_cte(cte, facts, visible | earlier)
                if cte.ctename:
                    earlier.add(cte.ctename)
        body_visible = visible | names

    if select.intoClause is not None:
        facts.select_into = True
    if select.lockingClause:
        facts.row_locking = True

    references = 0
    for item in select.fromClause or ():
        for range_var in _range_vars(item):
            if _is_allowed_table(range_var) and not _is_cte_reference(
                range_var, body_visible
            ):
                references += 1
    if references > 1:
        facts.self_join = True

    for field_name in select:
        if field_name == "withClause":
            continue
        for child in _nodes_in(getattr(select, field_name, None)):
            _walk(child, facts, body_visible)


def _walk_cte(
    cte: CommonTableExpr, facts: _Facts, visible: frozenset[str]
) -> None:
    query = cte.ctequery
    if not isinstance(query, SelectStmt):
        facts.modifying_cte = True
        return
    _walk(query, facts, visible)


def _note_table(
    range_var: RangeVar, facts: _Facts, visible: frozenset[str]
) -> None:
    if _is_cte_reference(range_var, visible):
        return
    name = range_var.relname or ""
    schema = range_var.schemaname
    qualified = f"{schema}.{name}" if schema else name
    if schema in SYSTEM_SCHEMAS or name.startswith("pg_"):
        facts.system_tables.append(qualified)
    elif not _is_allowed_table(range_var):
        facts.foreign_tables.append(qualified)


def _is_cte_reference(range_var: RangeVar, visible: frozenset[str]) -> bool:
    """Whether the reference names a CTE in scope rather than a table.

    A schema-qualified name always names a table: a CTE cannot be qualified.
    """
    return (
        range_var.schemaname is None
        and range_var.relname is not None
        and range_var.relname in visible
    )


def _is_allowed_table(range_var: RangeVar) -> bool:
    """Whether the reference names the one readable relation.

    Quoted identifiers keep their case in the tree, so `"CLEAN_JOBS"` does not
    match; it is a different relation name to PostgreSQL.
    """
    return (
        range_var.relname == ALLOWED_TABLE
        and (range_var.schemaname is None or range_var.schemaname in ALLOWED_SCHEMAS)
    )


def _note_function(call: FuncCall, facts: _Facts) -> None:
    if not call.funcname:
        return
    # A schema-qualified call such as pg_catalog.lower is the same function, so
    # only the last name is checked.
    name = call.funcname[-1].sval or ""
    if name in IDENTITY_FUNCTIONS:
        facts.identity_functions.append(name)
    elif name in SERVER_SIDE_FUNCTIONS:
        facts.server_side_functions.append(name)
    elif name not in ALLOWED_FUNCTIONS:
        facts.unknown_functions.append(name)


def _note_value_function(node: SQLValueFunction, facts: _Facts) -> None:
    op = node.op.name if node.op is not None else ""
    if op in ALLOWED_VALUE_FUNCTIONS:
        return
    facts.identity_value_functions.append(op.removeprefix("SVFOP_").lower() or op)


def _note_column(ref: ColumnRef, facts: _Facts) -> None:
    fields = ref.fields or ()
    if not fields:
        return
    # Only the last field is a column: `c.source` names `source`, while the
    # first field is a table alias or a CTE name. An unquoted name is already
    # folded to lowercase by the scanner, so this also catches EXTERNAL_ID.
    last = fields[-1]
    if isinstance(last, String) and last.sval in HIDDEN_COLUMNS:
        facts.hidden_columns.append(last.sval)


def _range_vars(node: Node) -> Iterator[RangeVar]:
    """Every relation in one FROM item, without entering a nested query."""
    if isinstance(node, RangeVar):
        yield node
        return
    if isinstance(node, SelectStmt):
        return
    for child in _children(node):
        yield from _range_vars(child)


def _children(node: Node) -> Iterator[Node]:
    for field_name in node:
        yield from _nodes_in(getattr(node, field_name, None))


def _nodes_in(value: object) -> Iterator[Node]:
    """Every node in one field's value, including tuples of tuples.

    ``RangeFunction.functions`` holds ``(FuncCall, coldeflist)`` pairs, so a
    single level of tuple unwrapping would miss the call.
    """
    if isinstance(value, Node):
        yield value
    elif isinstance(value, (tuple, list)):
        for item in value:
            yield from _nodes_in(item)
