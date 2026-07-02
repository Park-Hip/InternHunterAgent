import re

# Matches a trailing LIMIT (and optional OFFSET) at the very end of a statement,
# e.g. "... LIMIT 20", "... LIMIT 20 OFFSET 5". Case-insensitive.
_TRAILING_LIMIT = re.compile(r"\s+LIMIT\s+\d+(\s+OFFSET\s+\d+)?\s*$", re.IGNORECASE)


def enforce_fetch_limit(sql: str, fetch_limit: int) -> str:
    """Return `sql` bounded to at most `fetch_limit` rows, regardless of any LIMIT
    the model added. Strips a trailing LIMIT/OFFSET and appends the system's own
    LIMIT so the caller controls how many rows are fetched (enabling +1 truncation
    detection). Input is already-validated single-table SELECT SQL; appending a
    numeric LIMIT keeps it safe, so no re-validation is needed."""
    stripped = _TRAILING_LIMIT.sub("", sql.rstrip())
    return f"{stripped} LIMIT {fetch_limit}"
