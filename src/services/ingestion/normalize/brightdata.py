"""Bright Data normalizer for LinkedIn-shaped job records.

A record here is provider-delivered evidence about a listing that claims to come
from LinkedIn. It is not verified LinkedIn truth, and the origin is a claim
supported only by the host of the returned `url`.

Three rules from the measured provider boundary are encoded in this module, and
each of them exists because the opposite was observed or is untested.

* `country_code` is never read, never inferred, and never back-filled from the
  submitted `country` filter.
  It was explicitly null in every observed record of the bounded observation
  even though the provider echoed that filter back exactly, so a value here
  would be a fabrication. The location comes from `job_location` alone.
* `job_seniority_level` is copied verbatim as a source level.
  It is not technical seniority and not leadership scope, and neither of those
  is populated here.
* `apply_link` and `application_availability` are never mapped to an application
  destination or to listing availability.
  The provider reported availability true beside an explicitly null apply link in
  every observed record, and a null link is an assertion that no value exists,
  not a closed listing.

Only fields the plan requests may be read at all: a value whose lineage names an
unrequested field is quarantined by the evidence writer rather than projected.
"""
from __future__ import annotations

from typing import Any

from src.services.ingestion.evidence_store import ProvenancePaths
from src.services.ingestion.models import NormalizedJob
from src.services.ingestion.transform import (
    classify_role,
    derive_is_internship,
    normalize_location,
)

# The declared source namespace. Bright Data is the acquisition provider and
# LinkedIn is the claimed origin platform; neither alone is the source, and this
# name is the one the plan is filed under.
SOURCE_ID = "linkedin_via_brightdata"

# The version of this rule set, recorded against every field it populates.
NORMALIZATION_VERSION = "brightdata-normalize-v1"

# Field lineage for every output field. Only `url`, `job_posting_id`,
# `job_title`, `company_name`, `job_location` and `job_seniority_level` are
# requested by the plan; everything else is `unavailable` on purpose, including
# the two provider fields that would be tempting: `discovery_input`, which is an
# acquisition echo rather than a listing fact, and `country_code`, which carried
# no evidence at all in the observed records.
PROVENANCE_PATHS: ProvenancePaths = {
    "source": ("@plan.source_id", "copy"),
    "external_id": ("job_posting_id", "copy"),
    "source_url": ("url", "copy"),
    "title": ("job_title", "copy"),
    "company": ("company_name", "copy"),
    "role": ("job_title", "derive"),
    "description": ("unavailable", "unavailable"),
    "tech_stack": ("unavailable", "unavailable"),
    "job_level": ("job_seniority_level", "copy"),
    "location": ("job_location", "normalize"),
    # `job_posted_date` is an ISO timestamp and `job_posted_time` is a relative
    # "ago" string, both undeclared in meaning by the provider. Neither is
    # promoted to a posted date, and there is no listing expiry to read.
    "posted_date": ("unavailable", "unavailable"),
    "listing_expires_on": ("unavailable", "unavailable"),
    "created_on": ("unavailable", "unavailable"),
    "is_internship": ("job_seniority_level", "derive"),
    # The dataset's salary fields are documented but were never requested, so no
    # salary value is available. `is_salary_negotiable` is a required boolean in
    # the canonical shape, so it is recorded as `unavailable` rather than as an
    # answer: false here means "the source asserts nothing", not "not negotiable".
    "salary_min": ("unavailable", "unavailable"),
    "salary_max": ("unavailable", "unavailable"),
    "salary_currency": ("unavailable", "unavailable"),
    "is_salary_negotiable": ("unavailable", "unavailable"),
    "technical_seniority": ("unavailable", "unavailable"),
    "leadership_scope": ("unavailable", "unavailable"),
}


def listing_key(record: dict) -> str:
    """The source listing key of one record, or "" when the record carries none.

    Shared with the adapter so the key an observation is filed under and the key a
    normalizer reads can never disagree. An empty key is not an identity: the
    observation is still retained so the evidence is not lost, and the evidence
    writer quarantines its normalization as a missing listing key rather than
    projecting it under a placeholder.
    """
    value = record.get("job_posting_id")
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return ""
    return str(value).strip()


def _text(record: dict, field: str) -> str:
    value: Any = record.get(field)
    return value.strip() if isinstance(value, str) else ""


def to_normalized_job(payload: dict) -> NormalizedJob:
    """Map one Bright Data record to the canonical shape.

    Reads only the fields the plan requests. The record is a candidate, so this
    never asserts that the listing exists, is open, is in any country, or is
    reachable at the URL it carries.
    """
    title = _text(payload, "job_title")
    company = _text(payload, "company_name")
    source_url = payload.get("url")
    return NormalizedJob(
        source=SOURCE_ID,
        external_id=listing_key(payload),
        source_url=source_url if isinstance(source_url, str) and source_url else None,
        title=title,
        company=company,
        role=classify_role(title, None),
        description=None,
        tech_stack=None,
        job_level=_text(payload, "job_seniority_level") or None,
        location=normalize_location(_text(payload, "job_location")),
        posted_date=None,
        listing_expires_on=None,
        created_on=None,
        is_internship=derive_is_internship(_text(payload, "job_seniority_level"), None),
        salary_min=None,
        salary_max=None,
        salary_currency=None,
        is_salary_negotiable=False,
    )
