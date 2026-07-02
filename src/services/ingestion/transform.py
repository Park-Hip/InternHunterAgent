"""Shared, source-agnostic transform functions for the ingestion pipeline.

All functions are pure (no DB, no network) and read dictionaries from
settings.ingestion_yaml at call time. Safe to import without side effects.
"""
from __future__ import annotations

import html
import re

from src.core.config import settings


def html_to_text(value: str | None) -> str:
    """Strip HTML tags, unescape entities, and collapse whitespace.

    Mirrors the spike's strip_html logic. Returns "" for None/empty input.
    """
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def derive_is_internship(job_level: str | None, job_level_vi: str | None) -> bool:
    """Return True if either level string indicates an internship.

    Checks for "intern" (EN) or "thực tập" (VI), case-insensitive.
    Mirrors the spike's is_internship logic.
    """
    blob = f"{job_level or ''}|{job_level_vi or ''}".lower()
    return "intern" in blob or "thực tập" in blob


def find_tech_stack(*text_sources: str) -> str | None:
    """Scan combined text for technologies listed in ingestion_yaml["tech_dictionary"].

    Matching is case-insensitive with word-boundary guards to prevent
    false positives (e.g. "R" inside "Keras", "Go" inside "MongoDB").
    Returns dictionary-cased, deduped, YAML-order terms joined with ", ",
    or None when nothing matches.
    """
    combined = " ".join(text_sources)
    tech_dict: list[str] = settings.ingestion_yaml["tech_dictionary"]
    found: list[str] = []
    seen: set[str] = set()
    for tech in tech_dict:
        # Use negative lookbehind/lookahead instead of \b so that non-word
        # characters in tech names (e.g. C#, C++, Node.js) are handled correctly.
        pattern = r"(?<!\w)" + re.escape(tech) + r"(?!\w)"
        if re.search(pattern, combined, re.IGNORECASE) and tech.lower() not in seen:
            found.append(tech)
            seen.add(tech.lower())
    return ", ".join(found) if found else None


def classify_role(title: str, job_function_children: list[dict] | None) -> str:
    """Map a raw job title to a canonical role label using the ingestion_yaml taxonomy.

    Iterates role_taxonomy in YAML order; first keyword match wins (case-insensitive
    substring of the lowercased title). jobFunction child id 27 (AI/Data cluster) is
    available as a tiebreaker for ambiguous titles, though first-match-wins covers
    the current keyword set. Unmatched titles return "Other".
    """
    title_lower = title.lower()
    taxonomy: dict[str, dict] = settings.ingestion_yaml["role_taxonomy"]
    for role, config in taxonomy.items():
        for keyword in config["keywords"]:
            if keyword in title_lower:
                return role
    return "Other"


def normalize_location(*address_sources: str) -> str:
    """Normalise one or more raw address strings to canonical city names.

    Each source is lowercased and looked up in ingestion_yaml["city_alias_map"].
    Multiple distinct canonical cities are returned comma-separated in stable
    (encounter) order. Unknown or empty sources are skipped; returns "Other"
    when no source maps to a known city.
    """
    city_alias_map: dict[str, str] = settings.ingestion_yaml["city_alias_map"]
    canonical_cities: list[str] = []
    seen: set[str] = set()
    for source in address_sources:
        if not source or not source.strip():
            continue
        lower = source.lower().strip()
        canonical = city_alias_map.get(lower)
        if canonical and canonical not in seen:
            seen.add(canonical)
            canonical_cities.append(canonical)
    return ", ".join(canonical_cities) if canonical_cities else "Other"
