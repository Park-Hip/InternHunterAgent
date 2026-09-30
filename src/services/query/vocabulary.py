"""User vocabulary for the governed query core.

Pure normalization: a user term in, a canonical stored value or a whole
technology token out. No database, no agent, no prompt.

Three vocabularies exist and only three:

- Cities come from ``config/ingestion.yaml``'s ``city_alias_map``, which already
  carries both the accented and the unaccented spelling of every city, plus the
  user-side synonyms in ``agent.query.user_city_synonyms``.
- Roles come from ``config/ingestion.yaml``'s ``role_taxonomy`` keywords, which
  are already the phrases a user would type, Vietnamese included.
- Technologies come from ``config/tech_vocabulary.yaml``, the same table the
  ingestion extractor used to write ``tech_stack``, so ``ML`` resolves to
  ``Machine Learning`` and never to the rows whose only similar token is
  ``MLOps``.

Nothing here folds diacritics. There is no ``unaccent`` extension in any
migration, so a claim of diacritic-insensitive matching would be a lie. What the
tables do provide is an explicit alias for each spelling a user is likely to
type, and a term that matches none of them is reported as unknown rather than
guessed.
"""

from __future__ import annotations

from typing import Final

from src.core.config import settings

CANONICAL_OTHER: Final = "Other"
"""The catch-all value ingestion writes when nothing else matched."""


def _query_config() -> dict:
    agent = settings.config_yaml.get("agent")
    if not isinstance(agent, dict):
        raise ValueError("Missing 'agent' section in config/settings.yaml")
    query = agent.get("query")
    if not isinstance(query, dict):
        raise ValueError("Missing 'agent.query' section in config/settings.yaml")
    return query


def city_aliases() -> dict[str, str]:
    """Lowercased user term to canonical city name.

    The ingestion map first, so a spelling it already knows always wins over a
    query-side synonym.
    """
    ingestion = settings.ingestion_yaml
    base = ingestion.get("city_alias_map") if isinstance(ingestion, dict) else None
    if not isinstance(base, dict) or not base:
        raise ValueError("Missing or empty 'city_alias_map' in config/ingestion.yaml")
    aliases = {str(key).strip().casefold(): str(value) for key, value in base.items()}
    synonyms = _query_config().get("user_city_synonyms")
    if isinstance(synonyms, dict):
        for key, value in synonyms.items():
            aliases.setdefault(str(key).strip().casefold(), str(value))
    return aliases


def canonical_cities() -> list[str]:
    """Every canonical city the alias map can produce, sorted and deduplicated."""
    return sorted(set(city_aliases().values()))


def normalize_city(term: str) -> str | None:
    """Resolve a user city term to its canonical name, or None when unknown.

    An unknown city is not silently ignored. Returning None lets the caller
    answer ``UNSUPPORTED`` with the list of cities the data actually holds,
    which is the only honest answer when the term cannot be resolved.
    """
    cleaned = _clean(term)
    if not cleaned:
        return None
    return city_aliases().get(cleaned)


def role_aliases() -> dict[str, str]:
    """Lowercased user phrase to canonical role category."""
    taxonomy = settings.ingestion_yaml.get("role_taxonomy")
    if not isinstance(taxonomy, dict) or not taxonomy:
        raise ValueError("Missing or empty 'role_taxonomy' in config/ingestion.yaml")
    aliases: dict[str, str] = {}
    for role, config in taxonomy.items():
        keywords = config.get("keywords") if isinstance(config, dict) else None
        if not isinstance(keywords, list):
            continue
        for keyword in keywords:
            aliases.setdefault(str(keyword).strip().casefold(), str(role))
    return aliases


def canonical_roles() -> list[str]:
    """Every canonical role category, sorted, with the catch-all included."""
    taxonomy = settings.ingestion_yaml.get("role_taxonomy")
    roles = sorted(str(role) for role in taxonomy) if isinstance(taxonomy, dict) else []
    return [*roles, CANONICAL_OTHER]


def normalize_role(term: str) -> str | None:
    """Resolve a user role term to its canonical category, or None.

    None means the term has no canonical category, which the contract handles
    as a disclosed free-text fallback onto title and description rather than as
    a category filter.
    """
    cleaned = _clean(term)
    if not cleaned:
        return None
    return role_aliases().get(cleaned)


def technology_aliases() -> dict[str, str]:
    """Lowercased user term to the canonical token ingestion stores."""
    vocabulary = settings.tech_vocabulary_yaml
    if not isinstance(vocabulary, dict):
        raise ValueError("Missing 'config/tech_vocabulary.yaml'")
    denylist = {str(term).casefold() for term in vocabulary.get("denylist", [])}
    expansion: dict[str, str] = {}
    canonical = vocabulary.get("canonical_terms", [])
    if isinstance(canonical, list):
        for term in canonical:
            key = str(term).strip().casefold()
            if key and key not in denylist:
                expansion.setdefault(key, str(term))
    aliases = vocabulary.get("aliases")
    if isinstance(aliases, dict):
        for alias, term in aliases.items():
            key = str(alias).strip().casefold()
            if key and key not in denylist:
                expansion.setdefault(key, str(term))
    return expansion


def expand_technology(term: str) -> str | None:
    """Resolve a user technology term to the canonical token, or None.

    An unknown term is returned as the user wrote it rather than dropped,
    because an absent vocabulary entry is not evidence that the technology does
    not exist. The caller matches it as a whole token either way, so an unknown
    term can never widen a result through a substring.
    """
    cleaned = " ".join(str(term).split()).strip()
    if not cleaned:
        return None
    return technology_aliases().get(cleaned.casefold(), cleaned)


def is_canonical_technology(term: str) -> bool:
    """Whether the term is already the canonical token the extractor writes."""
    cleaned = _clean(term)
    if not cleaned:
        return False
    return cleaned in {value.casefold() for value in technology_aliases().values()}


def max_free_text_terms() -> int:
    value = _query_config().get("max_free_text_terms")
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("agent.query.max_free_text_terms must be a positive integer")
    return value


def _clean(term: str) -> str:
    return " ".join(str(term).split()).strip().casefold()
