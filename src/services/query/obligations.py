import re

from src.core.config import settings
from src.services.query.models import HedgeObligation, TableArtifact


_RULE_TOKENS = {
    "zero_results": "ZERO_RESULTS",
    "created_on": "CREATED_ON_CAVEAT",
    "free_text": "FREE_TEXT_HEDGE",
    "cross_currency": "CROSS_CURRENCY",
    "negotiable_salary": "NEGOTIABLE_SALARY",
    "listing_expiry": "LISTING_EXPIRY_NOT_DEADLINE",
}

_SELECT_LIST = re.compile(r"\bselect\s+(.*?)\s+from\b", re.IGNORECASE | re.DOTALL)


def _projects(sql: str, *columns: str) -> bool:
    match = _SELECT_LIST.search(sql)
    if match is None:
        return False
    select_list = match.group(1)
    return any(re.search(rf"\b{re.escape(column)}\b", select_list) for column in columns)


def _uses_for_filter_or_order(sql: str, column: str) -> bool:
    return bool(
        re.search(rf"\bwhere\b.*\b{re.escape(column)}\b", sql, re.DOTALL)
        or re.search(rf"\border\s+by\b.*\b{re.escape(column)}\b", sql, re.DOTALL)
    )


def detect_obligations(sql: str, table: TableArtifact) -> list[HedgeObligation]:
    """Return deterministic caveats implied by validated SQL and its result table."""
    normalized_sql = sql.lower()
    tokens: list[str] = []

    if table.row_count == 0:
        tokens.append(_RULE_TOKENS["zero_results"])
    if _uses_for_filter_or_order(normalized_sql, "created_on"):
        tokens.append(_RULE_TOKENS["created_on"])
    if re.search(r"\bdescription\s+(?:not\s+)?ilike\b", normalized_sql):
        tokens.append(_RULE_TOKENS["free_text"])
    if re.search(r"\b(?:order\s+by\s+|max\s*\(|min\s*\()salary_(?:min|max)\b", normalized_sql):
        tokens.append(_RULE_TOKENS["cross_currency"])
    if _uses_for_filter_or_order(normalized_sql, "listing_expires_on"):
        tokens.append(_RULE_TOKENS["listing_expiry"])
    if _projects(normalized_sql, "salary_min", "salary_max", "salary_currency", "is_salary_negotiable") and _has_negotiable_salary(table):
        tokens.append(_RULE_TOKENS["negotiable_salary"])

    return [HedgeObligation(glossary_token=token) for token in tokens]


def filter_enabled_obligations(obligations: list[HedgeObligation]) -> list[HedgeObligation]:
    agent_cfg = settings.config_yaml.get("agent")
    query_cfg = agent_cfg.get("query") if isinstance(agent_cfg, dict) else None
    config = query_cfg.get("obligations") if isinstance(query_cfg, dict) else None
    if not isinstance(config, dict) or config.get("enabled") is not True:
        return []

    token_to_rule = {token: rule for rule, token in _RULE_TOKENS.items()}
    return [
        obligation
        for obligation in obligations
        if config.get(token_to_rule[obligation.glossary_token]) is True
    ]


def detect_row_obligations(table: TableArtifact) -> list[HedgeObligation]:
    if _has_negotiable_salary(table):
        return [HedgeObligation(glossary_token=_RULE_TOKENS["negotiable_salary"])]
    return []


def _has_negotiable_salary(table: TableArtifact) -> bool:
    positions = {column: index for index, column in enumerate(table.columns)}
    negotiable_index = positions.get("is_salary_negotiable")
    min_index = positions.get("salary_min")
    max_index = positions.get("salary_max")

    for row in table.rows:
        if negotiable_index is not None and row[negotiable_index] is True:
            return True
        if min_index is not None and max_index is not None:
            if row[min_index] is None and row[max_index] is None:
                return True
    return False
