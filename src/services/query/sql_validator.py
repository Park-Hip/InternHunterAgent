import re

from src.services.query.models import ValidationResult

ALLOWED_TABLE = "clean_jobs"

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
    r'(?<![A-Za-z0-9_])(?:"(?:lo_\w+|pg_\w+|file_lo_\w+|dblink(?:_\w+)?|postgres_fdw_\w+)"|(?:lo_\w+|pg_\w+|file_lo_\w+|dblink(?:_\w+)?|postgres_fdw_\w+))\s*\(',
    re.IGNORECASE,
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
    r'\bFROM\s+(?:ONLY\s+)?(?:"(?:[^"]|"")*"|[A-Za-z_][A-Za-z0-9_.]*)(?:\s+(?:AS\s+)?(?:"(?:[^"]|"")*"|[A-Za-z_][A-Za-z0-9_]*))?\s*,',
    re.IGNORECASE,
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
      8. Single-table allowlist: every table referenced must be `clean_jobs`.

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
