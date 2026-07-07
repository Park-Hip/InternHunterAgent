"""VietnamWorks-specific normalizer: maps a raw payload dict → NormalizedJob.

All source-specific field name knowledge lives here. The reusable transforms
(html_to_text, classify_role, etc.) are imported from transform.py.
"""
from __future__ import annotations

from src.services.ingestion.models import NormalizedJob
from src.services.ingestion.transform import (
    classify_role,
    derive_is_internship,
    find_tech_stack,
    html_to_text,
    normalize_location,
)


def _extract_benefits(payload: dict) -> list[str]:
    """Pull benefit text from the payload's benefits array.

    Expected shape: [{"benefitName": str, "benefitValue": str}]
    T0009.8 should confirm this shape against a live pull before production.
    Tolerates: key absent, list of plain strings, or dicts missing either key.
    """
    benefits = payload.get("benefits") or []
    texts: list[str] = []
    for item in benefits:
        if isinstance(item, dict):
            raw = item.get("benefitValue") or item.get("benefitName") or ""
        elif isinstance(item, str):
            raw = item
        else:
            raw = ""
        text = html_to_text(raw)
        if text:
            texts.append(text)
    return texts


def to_normalized_job(payload: dict) -> NormalizedJob:
    """Map a raw VietnamWorks job dict to a canonical NormalizedJob.

    Raises pydantic ValidationError if required fields (jobId, jobTitle,
    companyName) are absent or the wrong type — no source-specific exceptions.
    """
    title: str = payload.get("jobTitle") or ""
    company: str = payload.get("companyName") or ""

    # --- description: merge jobDescription + jobRequirement + benefits ---
    desc_parts: list[str] = []
    for raw_html in (payload.get("jobDescription"), payload.get("jobRequirement")):
        text = html_to_text(raw_html)
        if text:
            desc_parts.append(text)
    desc_parts.extend(_extract_benefits(payload))
    description: str | None = "\n\n".join(desc_parts) if desc_parts else None

    # --- salary: structured fields, not display string ---
    is_salary_visible: bool = payload.get("isSalaryVisible", False)
    is_salary_negotiable: bool = not is_salary_visible
    if is_salary_visible:
        salary_min: float | None = payload.get("salaryMin")
        salary_max: float | None = payload.get("salaryMax")
        salary_currency: str | None = payload.get("salaryCurrency")
    else:
        salary_min = None
        salary_max = None
        salary_currency = None

    # --- tech_stack: skills array + merged description text ---
    skill_names: list[str] = [
        s["skillName"]
        for s in (payload.get("skills") or [])
        if s.get("skillName")
    ]
    tech_stack: str | None = find_tech_stack(*skill_names, description or "")

    # --- role: canonical label via taxonomy ---
    job_function_children: list[dict] | None = (
        payload.get("jobFunction", {}).get("children")
    )
    role: str = classify_role(title, job_function_children)

    # --- location: primary address + workingLocations city names ---
    address: str = payload.get("address") or ""
    working_location_names: list[str] = [
        loc["cityName"]
        for loc in (payload.get("workingLocations") or [])
        if loc.get("cityName")
    ]
    location: str = normalize_location(address, *working_location_names)

    # --- internship flag and raw level ---
    is_internship: bool = derive_is_internship(
        payload.get("jobLevel"), payload.get("jobLevelVI")
    )
    job_level: str | None = payload.get("jobLevel") or payload.get("jobLevelVI")

    # posted_date = None by decision, not because a parse step is merely pending:
    # VietnamWorks surfaces no *reliable* published date. The timestamps it does expose
    # (onlineOn/approvedOn/expiredOn) each mean something other than "first posted" —
    # onlineOn churns on every employer re-list, approvedOn is an admin approval time,
    # expiredOn is a future expiry — so none is a trustworthy posting date. The reliable
    # path is an ingestion-owned first_seen_at / an honestly-renamed listed_on column,
    # both of which depend on the accumulate-upsert persistence planned for T0013 (today
    # clean_jobs is TRUNCATE'd and rebuilt each run). See Known_Issues.md ("posted_date
    # intentionally absent from agent schema") and research/job-site-comparison.md §122.
    # The column is nullable so this is safe to leave until that work lands.

    return NormalizedJob(
        source="vietnamworks",
        external_id=str(payload["jobId"]),
        source_url=payload.get("jobUrl"),
        title=title,
        company=company,
        role=role,
        description=description,
        tech_stack=tech_stack,
        job_level=job_level,
        location=location,
        posted_date=None,
        is_internship=is_internship,
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency=salary_currency,
        is_salary_negotiable=is_salary_negotiable,
    )
