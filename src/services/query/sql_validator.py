import re

from src.services.query.models import ValidationResult

ALLOWED_TABLE = "clean_jobs"

# Ingestion bookkeeping and lifecycle columns that exist on the physical table but
# are outside the agent-visible contract declared by `prompts.sql_generation`
# ("Reference only real columns"). The model is never told about them, so naming
# one is a silent contract break: the query executes and the answer looks fine.
# The test suite asserts this set plus the prompt's declared columns partition
# `src.api.schema_guard.EXPECTED_COLUMNS`.
HIDDEN_COLUMNS = frozenset(
    {"source", "external_id", "posted_date", "first_seen_at", "last_seen_at"}
)

# Write / DDL / procedure verbs that must never appear as a bare word (token) in a
# query. Matched case-insensitively against whole words only (see TOKEN_PATTERN), so
# `UPDATE` is caught but `updated_at` is not.
DENYLISTED_KEYWORDS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "CREATE",
    "TRUNCATE",
    "GRANT",
    "REVOKE",
    "REPLACE",
    "MERGE",
    "EXEC",
    "EXECUTE",
    "CALL",
    "INTO",
    "COPY",
}

# Blocks Postgres catalog/metadata tables: any identifier starting with `pg_`
# (pg_tables, pg_class, ...) or the literal `information_schema`. `\b` = word boundary.
SYSTEM_TABLE_PATTERN = re.compile(r"\bpg_\w*|\binformation_schema\b", re.IGNORECASE)

# One SQL identifier/word: a letter or underscore, then letters/digits/underscores.
# Used to split the statement into whole words for the denylist check.
TOKEN_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# SQL string literals: single-quoted strings (with escaped quotes) and PostgreSQL
# dollar-quoted strings. Their contents must not participate in safety checks.
SQL_LITERAL_OR_UNICODE_IDENTIFIER_PATTERN = re.compile(
    r"[Ee]'(?:[^'\\]|\\.|'')*'|'(?:[^']|'')*'|(?P<quoted_identifier>\"(?:[^\"]|\"\")*\")|"
    r"(?<![A-Za-z0-9_$\u0080-\U0010FFFF])(?P<delimiter>\$(?:[A-Za-z_\u0080-\U0010FFFF][A-Za-z0-9_\u0080-\U0010FFFF]*)?\$).*?(?P=delimiter)|"
    r"U&\"(?P<identifier>(?:[^\"]|\"\")*)\"(?:\s+UESCAPE\s+(?:E)?'(?P<escape>(?:[^']|'')*)')?",
    re.DOTALL | re.IGNORECASE,
)
DELIMITED_IDENTIFIER_PATTERN = re.compile(r'"(?:[^"]|"")*"')

# Server-side functions that can read files, connect to other services, or block a
# connection. Match function calls only, including double-quoted identifiers.
SERVER_SIDE_FUNCTION_PATTERN = re.compile(
    r'(?<![A-Za-z0-9_$\u0080-\U0010FFFF])(?:"(?:lo_\w+|pg_\w+|file_lo_\w+|dblink(?:_\w+)?|postgres_fdw_\w+)"|(?i:lo_\w+|pg_\w+|file_lo_\w+|dblink(?:_\w+)?|postgres_fdw_\w+))\s*\('
)

# The table name that immediately follows a FROM or JOIN keyword. Captures the
# identifier (group 1), which may be schema-qualified (letters/digits/underscore/dot).
# Every captured name must equal ALLOWED_TABLE.
TABLE_REF_PATTERN = re.compile(
    r'\b(?:FROM|JOIN)\s+(?:ONLY\s+)?("(?:[^"]|"")*"|[A-Za-z_][A-Za-z0-9_.]*)',
    re.IGNORECASE,
)

# A comma-separated table list in the FROM clause — `FROM clean_jobs, raw_jobs` — the
# old-style (implicit) join. Matches FROM, a table (optionally with an alias), then a
# comma. TABLE_REF_PATTERN alone can't catch the second table here, so this guards it.
FROM_CLAUSE_LIST_PATTERN = re.compile(
    r'\bFROM\s+(?:ONLY\s+)?(?:"(?:[^"]|"")*"|[A-Za-z_][A-Za-z0-9_.]*)(?:\s*\*)?(?:\s+(?:AS\s+)?(?:"(?:[^"]|"")*"|[A-Za-z_][A-Za-z0-9_]*)(?:\s*\((?:"(?:[^"]|"")*"|[^)])*\))?)?\s*,',
    re.IGNORECASE,
)

# One SQL identifier: unquoted (folded to lowercase) or double-quoted.
IDENTIFIER = r'(?:"(?:[^"]|"")*"|[A-Za-z_][A-Za-z0-9_]*)'

# One top-level sort key: a column reference, optionally table-qualified,
# followed by the direction/null/USING clauses PostgreSQL accepts. A computed
# expression is not matched: only the primary key's own value gives a total
# order for paging.
SORT_KEY_PATTERN = re.compile(
    rf"({IDENTIFIER})(?:\s*\.\s*({IDENTIFIER}))?"
    r"(?:\s+(?:ASC|DESC))?"
    r"(?:\s+NULLS\s+(?:FIRST|LAST))?"
    r"(?:\s+USING\s+[<>=]+)?",
    re.IGNORECASE,
)

# Clause keywords that end the ORDER BY list, so an ORDER BY is checked only
# up to the part of the statement it applies to.
ORDER_BY_END_KEYWORDS = frozenset(
    {"limit", "offset", "fetch", "for", "union", "intersect", "except"}
)


def _invalid(sql: str, reason: str) -> ValidationResult:
    return ValidationResult(valid=False, sql=sql, reason=reason)


def _decode_unicode_identifier(match: re.Match[str]) -> str:
    identifier = match.group("identifier")
    escape = match.group("escape")
    if escape is not None and len(escape) != 1:
        raise ValueError("Invalid Unicode escape character")

    escape_char = escape or "\\"
    decoded: list[str] = []
    index = 0
    while index < len(identifier):
        if identifier[index] != escape_char:
            decoded.append(identifier[index])
            index += 1
            continue

        if index + 1 < len(identifier) and identifier[index + 1] == escape_char:
            decoded.append(escape_char)
            index += 2
            continue

        hex_digits = identifier[index + 1 : index + 5]
        if len(hex_digits) == 4 and all(char in "0123456789abcdefABCDEF" for char in hex_digits):
            code_point = int(hex_digits, 16)
            index += 5
        elif identifier[index + 1 : index + 2] == "+":
            hex_digits = identifier[index + 2 : index + 8]
            if len(hex_digits) != 6 or not all(
                char in "0123456789abcdefABCDEF" for char in hex_digits
            ):
                decoded.append(escape_char)
                index += 1
                continue
            code_point = int(hex_digits, 16)
            index += 8
        else:
            decoded.append(escape_char)
            index += 1
            continue

        if code_point == 0 or 0xD800 <= code_point <= 0xDFFF or code_point > 0x10FFFF:
            raise ValueError("Invalid Unicode code point")
        decoded.append(chr(code_point))

    normalized_identifier = "".join(decoded).replace('"', '""')
    return f'"{normalized_identifier}"'


def _mask_literal_or_normalize_identifier(match: re.Match[str]) -> str:
    quoted_identifier = match.group("quoted_identifier")
    if quoted_identifier is not None:
        return quoted_identifier
    if match.group("identifier") is None:
        return "''"
    return _decode_unicode_identifier(match)


def validate_sql(sql: str) -> ValidationResult:
    """Deterministically vet an LLM-generated SQL string before it is executed.

    This is the trust boundary: the query only runs if every check below passes.
    Returns a ValidationResult (valid + cleaned sql, or invalid + a reason). The
    checks run in order and reject on the first failure:

      1. Not empty.
      2. Single statement only (no `;` separating statements).
      3. Read-only: must begin with SELECT.
      4. No SQL comment sequences (`--`, `/* */`) — a common injection vector.
      5. No write/DDL/procedure verbs (DENYLISTED_KEYWORDS).
      6. No server-side file, network, or blocking function calls.
      7. No Postgres system/catalog tables (SYSTEM_TABLE_PATTERN).
      8. No hidden ingestion/lifecycle columns (HIDDEN_COLUMNS).
      9. Single-table allowlist: every table referenced must be `clean_jobs`.

    Read-only enforcement at execution time is handled separately by the executor's
    `SET TRANSACTION READ ONLY`; this layer restricts *scope* (which statements and
    which tables the agent may reach).
    """
    # Normalize: drop surrounding whitespace and a single trailing semicolon.
    statement = sql.strip().rstrip(";").strip()

    if not statement:
        return _invalid(statement, "Empty SQL is not allowed")

    # A `;` still present after stripping one trailing `;` means multiple statements.
    if ";" in statement:
        return _invalid(statement, "Multiple statements are not allowed")

    # Read-only gate: only SELECT queries are permitted.
    if not statement.upper().startswith("SELECT"):
        return _invalid(statement, "Only SELECT statements are allowed")

    # Comments can hide a second statement or smuggle keywords past the token scan.
    if "--" in statement or "/*" in statement or "*/" in statement:
        return _invalid(statement, "Comment sequences are not allowed")

    # Blank out string-literal contents so a literal that happens to contain a denylisted
    # word or a table name (e.g. WHERE description ILIKE '%replace%') isn't mistaken for
    # a real keyword or table reference by the checks below.
    try:
        masked = SQL_LITERAL_OR_UNICODE_IDENTIFIER_PATTERN.sub(
            _mask_literal_or_normalize_identifier, statement
        )
    except ValueError:
        return _invalid(statement, "Invalid Unicode identifier")

    # Block functions that can access server files, connect to remote services, or sleep.
    if SERVER_SIDE_FUNCTION_PATTERN.search(masked):
        return _invalid(statement, "Server-side function calls are not allowed")

    # Split into whole words and reject any that is a denylisted verb (case-insensitive).
    token_masked = DELIMITED_IDENTIFIER_PATTERN.sub('""', masked)
    tokens = {token.upper() for token in TOKEN_PATTERN.findall(token_masked)}
    forbidden = sorted(DENYLISTED_KEYWORDS & tokens)
    if forbidden:
        return _invalid(statement, f"Unsafe keyword(s) detected: {', '.join(forbidden)}")

    # Block access to Postgres catalog/metadata tables.
    if SYSTEM_TABLE_PATTERN.search(masked):
        return _invalid(statement, "Access to system tables is not allowed")

    # Block the physical-but-hidden ingestion/lifecycle columns. Tokens come from
    # `masked` (not the delimited-identifier-flattened copy), so a quoted identifier
    # such as "external_id" is caught as well, while string-literal contents are
    # already blanked.
    hidden = sorted({token.lower() for token in TOKEN_PATTERN.findall(masked)} & HIDDEN_COLUMNS)
    if hidden:
        return _invalid(
            statement, f"Hidden column(s) are not allowed: {', '.join(hidden)}"
        )

    # Reject old-style comma joins (`FROM clean_jobs, raw_jobs`).
    if FROM_CLAUSE_LIST_PATTERN.search(masked):
        return _invalid(statement, "Query may only reference the clean_jobs table")

    # Reject if any FROM/JOIN target is a table other than clean_jobs (e.g. JOIN raw_jobs).
    table_refs = TABLE_REF_PATTERN.findall(masked)
    if any(
        ref[1:-1].replace('""', '"') != ALLOWED_TABLE
        if ref.startswith('"')
        else ref.lower() != ALLOWED_TABLE
        for ref in table_refs
    ):
        return _invalid(statement, "Query may only reference the clean_jobs table")

    return ValidationResult(valid=True, sql=statement)


def has_id_tiebreak(sql: str) -> bool:
    """Whether a SELECT's top-level ORDER BY includes ``id`` as a sort key.

    A page boundary is only stable when the order is total. PostgreSQL promises
    no row order for a query without ORDER BY, and an order on a non-unique
    column such as ``created_on`` can swap tied rows between two calls, so an
    OFFSET page can repeat or skip rows even though the OFFSET is correct.
    ``id`` is the primary key, so a top-level ORDER BY that includes it as a
    sort key orders every row uniquely (#727).

    Only the outermost ORDER BY counts: an ORDER BY inside a subquery or a
    window function does not order the rows the page slices. The statement is
    assumed to have passed ``validate_sql``, which strips string-literal
    contents before this scan.
    """
    try:
        masked = SQL_LITERAL_OR_UNICODE_IDENTIFIER_PATTERN.sub(
            _mask_literal_or_normalize_identifier, sql
        )
    except ValueError:
        # An invalid Unicode identifier is rejected by validate_sql. Treat it
        # as unordered here so a caller cannot reach execution with it.
        return False

    order_by = _top_level_order_by(masked)
    if order_by is None:
        return False
    return any(_is_id_sort_key(key) for key in _split_sort_keys(order_by))


def _top_level_order_by(sql: str) -> str | None:
    """Return the text after the outermost ORDER BY, up to its clause end."""
    tokens = _top_level_tokens(sql)
    for index, (_, token) in enumerate(tokens):
        if token.casefold() != "order":
            continue
        if index + 1 == len(tokens) or tokens[index + 1][1].casefold() != "by":
            continue
        body_start = tokens[index + 1][0] + len(tokens[index + 1][1])
        body_end = len(sql)
        for later_start, later_token in tokens[index + 2 :]:
            if later_token.casefold() in ORDER_BY_END_KEYWORDS:
                body_end = later_start
                break
        return sql[body_start:body_end]
    return None


def _top_level_tokens(sql: str) -> list[tuple[int, str]]:
    """Every unquoted word at parenthesis depth zero, with its start offset."""
    tokens: list[tuple[int, str]] = []
    depth = 0
    index = 0
    while index < len(sql):
        character = sql[index]
        if character == '"':
            index = _skip_delimited_identifier(sql, index)
        elif character == "(":
            depth += 1
            index += 1
        elif character == ")":
            depth = max(0, depth - 1)
            index += 1
        elif depth == 0 and (
            character.isascii() and (character.isalpha() or character == "_")
        ):
            end = index + 1
            while (
                end < len(sql)
                and sql[end].isascii()
                and (sql[end].isalnum() or sql[end] == "_")
            ):
                end += 1
            tokens.append((index, sql[index:end]))
            index = end
        else:
            index += 1
    return tokens


def _skip_delimited_identifier(sql: str, start: int) -> int:
    """Return the offset just past the double-quoted identifier at ``start``."""
    index = start + 1
    while index < len(sql):
        if sql[index] == '"':
            if index + 1 < len(sql) and sql[index + 1] == '"':
                index += 2
                continue
            return index + 1
        index += 1
    return index


def _split_sort_keys(order_by: str) -> list[str]:
    """Split an ORDER BY list on its top-level commas."""
    keys: list[str] = []
    depth = 0
    start = 0
    index = 0
    while index < len(order_by):
        character = order_by[index]
        if character == '"':
            index = _skip_delimited_identifier(order_by, index)
        elif character == "(":
            depth += 1
            index += 1
        elif character == ")":
            depth = max(0, depth - 1)
            index += 1
        elif character == "," and depth == 0:
            keys.append(order_by[start:index])
            start = index + 1
            index += 1
        else:
            index += 1
    keys.append(order_by[start:])
    return keys


def _is_id_sort_key(key: str) -> bool:
    match = SORT_KEY_PATTERN.fullmatch(key.strip())
    if match is None:
        return False
    return _is_id_identifier(match.group(2) or match.group(1))


def _is_id_identifier(identifier: str) -> bool:
    if identifier.startswith('"'):
        # A quoted identifier keeps its case, so only the exact stored name
        # matches the id column.
        return identifier[1:-1].replace('""', '"') == "id"
    # Unquoted PostgreSQL identifiers fold to lowercase.
    return identifier.casefold() == "id"
