"""Shared, source-agnostic transform functions for the ingestion pipeline.

All functions are pure (no DB, no network) and read deterministic config from
settings at call time. Safe to import without side effects.
"""
from __future__ import annotations

import html
import re
from datetime import date, datetime

from src.core.config import settings


def html_to_text(value: str | None) -> str:
    """Strip HTML tags, unescape entities, and collapse whitespace.

    Mirrors the spike's strip_html logic. Returns "" for None/empty input.
    """
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def to_date(value: str | None) -> date | None:
    """Parse an ISO-8601 datetime/date string to a date; None on missing/unparseable."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except (TypeError, ValueError):
        return None


def derive_is_internship(job_level: str | None, job_level_vi: str | None) -> bool:
    """Return True if either level string indicates an internship.

    Checks for "intern" (EN) or "thực tập" (VI), case-insensitive.
    Mirrors the spike's is_internship logic.
    """
    blob = f"{job_level or ''}|{job_level_vi or ''}".lower()
    return "intern" in blob or "thực tập" in blob


def _tech_alias_pattern(alias: str) -> re.Pattern[str]:
    """Compile the match pattern for one tech-vocabulary alias.

    Every alias is pinned on both sides to a non-word boundary, so short names
    are never matched inside larger words ("R" inside "Keras", "Go" inside
    "MongoDB"). Short alphabetic names get two extra guards because they are
    ambiguous in free text:

    * one-letter names match case-sensitively and are rejected when joined to
      a neighbour by "&" (so "R" and "D" inside "R&D" are not read as
      languages);
    * two-letter alphabetic names match case-sensitively (so the verb "go" is
      not read as the Go language).

    Longer names and names carrying punctuation (C#, C++, Node.js) keep the
    default case-insensitive matching.
    """
    boundary = r"(?<!\w)" + re.escape(alias) + r"(?!\w)"
    short_alpha = len(alias) <= 2 and alias.isascii() and alias.isalpha()
    if len(alias) == 1 and short_alpha:
        return re.compile(r"(?<![\w&])" + re.escape(alias) + r"(?![\w&])")
    if short_alpha:
        return re.compile(boundary)
    return re.compile(boundary, re.IGNORECASE)


def find_tech_stack(*text_sources: str) -> str | None:
    """Extract canonical technologies from source tags and description text."""
    combined = " ".join(text_sources)
    vocabulary = settings.tech_vocabulary_yaml
    canonical_terms = vocabulary.get("canonical_terms", [])
    aliases = vocabulary.get("aliases", {})
    denylist = {str(term).casefold() for term in vocabulary.get("denylist", [])}

    alias_to_canonical: dict[str, str] = {}
    for term in canonical_terms:
        if isinstance(term, str) and term.casefold() not in denylist:
            alias_to_canonical[term] = term

    if isinstance(aliases, dict):
        for alias, canonical in aliases.items():
            if not isinstance(alias, str) or not isinstance(canonical, str):
                continue
            if alias.casefold() in denylist or canonical.casefold() in denylist:
                continue
            alias_to_canonical[alias] = canonical

    found: list[str] = []
    seen: set[str] = set()
    for alias, canonical in sorted(
        alias_to_canonical.items(),
        key=lambda item: (len(item[0]), item[0].casefold()),
        reverse=True,
    ):
        pattern = _tech_alias_pattern(alias)
        canonical_key = canonical.casefold()
        if canonical_key not in seen and pattern.search(combined):
            found.append(canonical)
            seen.add(canonical_key)
    return ", ".join(found) if found else None


def classify_role(title: str, job_function_children: list[dict] | None) -> str:
    """Map a raw job title to a canonical role label using the ingestion_yaml taxonomy.

    Iterates role_taxonomy in YAML order; the first matching keyword wins.
    Keywords are matched as whole, case-insensitive phrases against the
    lowercased title, never raw substrings, so "ml engineer" does not match
    inside "html engineer". Unmatched titles return "Other".

    job_function_children is not consulted: the role is derived from the title
    alone. The parameter remains only to keep the VietnamWorks normalizer's call
    shape.
    """
    title_lower = title.lower()
    taxonomy: dict[str, dict] = settings.ingestion_yaml["role_taxonomy"]
    for role, config in taxonomy.items():
        for keyword in config["keywords"]:
            pattern = r"(?<!\w)" + re.escape(keyword.lower()) + r"(?!\w)"
            if re.search(pattern, title_lower):
                return role
    return "Other"


def normalize_location(*address_sources: str) -> str:
    """Normalise one or more raw address strings to canonical city names.

    Each alias key in ingestion_yaml["city_alias_map"] is matched against each
    source as a whole word / bounded phrase (case-insensitive, via a
    \\b-anchored regex per key), not merely as an exact full-string match or a
    raw substring. This lets a known city be recognised inside a free-form
    address (e.g. "12 Nguyen Hue, District 1, Ho Chi Minh City") while still
    preventing short aliases like "hn" or "hcm" from matching inside unrelated
    words (e.g. "john", "technology").

    Multiple distinct canonical cities are returned comma-separated, ordered
    by first appearance: sources are scanned in the order given, and within a
    source, matches are ordered by the position they start at (leftmost
    first), with city_alias_map's YAML declaration order used as a stable
    tiebreak for two keys that start at the same position (e.g. "ho chi minh"
    vs. "ho chi minh city" both starting at index 0).
    Unknown or empty sources are skipped; returns "Other" when no source maps
    to a known city.
    """
    city_alias_map: dict[str, str] = settings.ingestion_yaml["city_alias_map"]
    canonical_cities: list[str] = []
    seen: set[str] = set()
    for source in address_sources:
        if not source or not source.strip():
            continue
        matches: list[tuple[int, int, str]] = []
        for key_order, (key, canonical) in enumerate(city_alias_map.items()):
            pattern = r"\b" + re.escape(key) + r"\b"
            match = re.search(pattern, source, re.IGNORECASE)
            if match:
                matches.append((match.start(), key_order, canonical))
        for _, _, canonical in sorted(matches):
            if canonical not in seen:
                seen.add(canonical)
                canonical_cities.append(canonical)
    return ", ".join(canonical_cities) if canonical_cities else "Other"
