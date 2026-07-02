import re

from src.services.query.models import ValidationResult

ALLOWED_TABLE = "clean_jobs"

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
}

SYSTEM_TABLE_PATTERN = re.compile(r"\bpg_\w*|\binformation_schema\b", re.IGNORECASE)
TOKEN_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
STRING_LITERAL_PATTERN = re.compile(r"'(?:[^']|'')*'")
TABLE_REF_PATTERN = re.compile(r"\b(?:FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_.]*)", re.IGNORECASE)
FROM_CLAUSE_LIST_PATTERN = re.compile(
    r"\bFROM\s+[A-Za-z_][A-Za-z0-9_.]*(?:\s+[A-Za-z_][A-Za-z0-9_]*)?\s*,", re.IGNORECASE
)


def _invalid(sql: str, reason: str) -> ValidationResult:
    return ValidationResult(valid=False, sql=sql, reason=reason)


def validate_sql(sql: str) -> ValidationResult:
    statement = sql.strip().rstrip(";").strip()

    if not statement:
        return _invalid(statement, "Empty SQL is not allowed")

    if ";" in statement:
        return _invalid(statement, "Multiple statements are not allowed")

    if not statement.upper().startswith("SELECT"):
        return _invalid(statement, "Only SELECT statements are allowed")

    if "--" in statement or "/*" in statement or "*/" in statement:
        return _invalid(statement, "Comment sequences are not allowed")

    tokens = {token.upper() for token in TOKEN_PATTERN.findall(statement)}
    forbidden = sorted(DENYLISTED_KEYWORDS & tokens)
    if forbidden:
        return _invalid(statement, f"Unsafe keyword(s) detected: {', '.join(forbidden)}")

    if SYSTEM_TABLE_PATTERN.search(statement):
        return _invalid(statement, "Access to system tables is not allowed")

    # Masking is scoped to this table check only; it does not fix the denylist
    # keyword false-positives on string literals (bug 4, tracked separately).
    masked = STRING_LITERAL_PATTERN.sub("''", statement)

    if FROM_CLAUSE_LIST_PATTERN.search(masked):
        return _invalid(statement, "Query may only reference the clean_jobs table")

    table_refs = TABLE_REF_PATTERN.findall(masked)
    if any(ref.lower() != ALLOWED_TABLE for ref in table_refs):
        return _invalid(statement, "Query may only reference the clean_jobs table")

    return ValidationResult(valid=True, sql=statement)
