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

    if ALLOWED_TABLE not in statement.lower():
        return _invalid(statement, "Query must reference the clean_jobs table")

    return ValidationResult(valid=True, sql=statement)
