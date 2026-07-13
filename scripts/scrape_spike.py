"""Scraping experiment — VietnamWorks AI/Data IT jobs.

A throwaway spike (NOT wired into the app, no database) that answers three questions
for the project's *actual* target data — **IT jobs focused on AI/Data roles**
(AI Engineer, Data Scientist, Data/ML Engineer, Data Analyst), **all seniority levels**,
with internships merely *flagged*:

  1. Can we get *real, relevant* AI/Data IT results with the simplest client?
  2. Is it *reliable* (repeatable, low failure rate)?
  3. Can it be *scheduled* (headless, non-interactive, no anti-bot solving)?

Source choice (evidence-based, see research/data-ingestion-stage.md §0.1):
- ITviec (403 Cloudflare on a plain GET) and TopDev (no JSON API) need a managed/anti-bot
  scraper — lower reliability. **VietnamWorks exposes a public JSON search API**
  (`POST https://ms.vietnamworks.com/job-search/v1.0/search`, no auth) and a structured
  `jobFunction` taxonomy, so it is both the most reliable path *and* precisely scopable.

How relevance is enforced (keyword recall + structured precision):
- **Recall:** query the API with several AI/Data role keywords (keyword search alone is
  noisy — it matches description text, surfacing Sales/Marketing roles).
- **Precision:** keep only results whose structured `jobFunction` is IT/Telecom
  (parentId 5); tag those in the dedicated **"Data Engineer/Data Analyst/AI"** category
  (child id 27) as the AI/Data focus set. This uses data already on every job, so it does
  not depend on any undocumented filter field.

Run:  uv run python scripts/scrape_spike.py

Constants live at the top on purpose: this is a measurement spike, not a production
adapter. They graduate to config/settings.yaml only if/when ingestion becomes a real
JobSource adapter.
"""

from __future__ import annotations

import html
import json
import re
import statistics
import sys
import time
from pathlib import Path

import httpx

# --- spike parameters -------------------------------------------------------------
API_URL = "https://ms.vietnamworks.com/job-search/v1.0/search"
# AI/Data role keywords drive recall; precision is enforced by jobFunction below.
QUERIES = [
    "data scientist",
    "data engineer",
    "data analyst",
    "machine learning",
    "AI engineer",
    "MLOps",
    "computer vision",
    "deep learning",
]
IT_PARENT_FUNCTION_ID = 5            # "Information Technology/Telecommunications"
AI_DATA_CHILD_FUNCTION_IDS = {27}    # "Data Engineer/Data Analyst/AI"
HITS_PER_PAGE = 50
PAGES_PER_QUERY = 2                  # recall depth per keyword
RELIABILITY_RUNS = 5                 # repeats of one query to measure stability
DELAY_SECONDS = 0.6                  # politeness gap between requests
TIMEOUT_SECONDS = 30
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "research" / "experiments" / "vietnamworks_ai_data_sample.json"
# ----------------------------------------------------------------------------------


def headers() -> dict:
    return {
        "User-Agent": USER_AGENT,
        "Content-Type": "application/json",
        "Origin": "https://www.vietnamworks.com",
        "Referer": "https://www.vietnamworks.com/",
    }


def build_payload(query: str, page: int) -> dict:
    return {
        "userId": 0,
        "query": query,
        "filter": [],
        "ranges": [],
        "order": [],
        "hitsPerPage": HITS_PER_PAGE,
        "page": page,
    }


def strip_html(text: str | None) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def function_ids(job: dict) -> tuple[int | None, set[int]]:
    fn = job.get("jobFunction") or {}
    children = {c.get("id") for c in (fn.get("children") or []) if c.get("id") is not None}
    return fn.get("parentId"), children


def is_it(job: dict) -> bool:
    return function_ids(job)[0] == IT_PARENT_FUNCTION_ID


def is_ai_data(job: dict) -> bool:
    parent, children = function_ids(job)
    return parent == IT_PARENT_FUNCTION_ID and bool(AI_DATA_CHILD_FUNCTION_IDS & children)


def is_internship(job: dict) -> bool:
    blob = f"{job.get('jobLevelVI') or ''}|{job.get('jobLevel') or ''}".lower()
    return "thực tập" in blob or "intern" in blob


def dedup_skills(job: dict) -> list[str]:
    seen, out = set(), []
    for s in job.get("skills") or []:
        name = s.get("skillName")
        if name and name.lower() not in seen:
            seen.add(name.lower())
            out.append(name)
    return out


def normalize(job: dict) -> dict:
    """Map a raw API job onto the fields an ingestion transform would target.

    `tech_stack_candidate` is the deduped skills array — the spike only reports it to
    gauge feasibility; deriving the real tech_stack (filtering to technologies) is out
    of scope here.
    """
    fn = job.get("jobFunction") or {}
    return {
        "external_id": job.get("jobId"),
        "title": job.get("jobTitle"),
        "company": job.get("companyName"),
        "job_level": job.get("jobLevel") or job.get("jobLevelVI"),
        "is_internship": is_internship(job),
        "job_function": [c.get("name") for c in (fn.get("children") or []) if c.get("name")],
        "location": job.get("address"),
        "salary": job.get("prettySalary"),
        "url": job.get("jobUrl"),
        # Raw source timestamps — captured to audit a possible `listing_expires_on` column
        # (research/schema-enrichment-plan.md §4). None reliably means "first posted":
        # onlineOn churns on re-list, approvedOn is admin approval, expiredOn is a future expiry.
        "online_on": job.get("onlineOn"),
        "approved_on": job.get("approvedOn"),
        "expired_on": job.get("expiredOn"),
        "tech_stack_candidate": dedup_skills(job),
        "description": strip_html(job.get("jobDescription")),
        "requirement": strip_html(job.get("jobRequirement")),
        "source": "vietnamworks",
    }


def fetch(client: httpx.Client, query: str, page: int) -> tuple[int, float, list[dict]]:
    """Return (status_code, latency_seconds, jobs)."""
    start = time.perf_counter()
    try:
        resp = client.post(API_URL, json=build_payload(query, page), headers=headers(), timeout=TIMEOUT_SECONDS)
        latency = time.perf_counter() - start
        if resp.status_code != 200:
            return resp.status_code, latency, []
        return 200, latency, resp.json().get("data") or []
    except Exception as exc:  # noqa: BLE001 — spike: any failure is a reliability data point
        print(f"  ! request error ({query!r} p{page}): {type(exc).__name__}: {exc}")
        return -1, time.perf_counter() - start, []


def pct(part: int, whole: int) -> float:
    return 100.0 * part / whole if whole else 0.0


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # Vietnamese text on the Windows console
    except AttributeError:
        pass

    print("=" * 74)
    print("VietnamWorks AI/Data IT jobs scraping spike")
    print(f"  endpoint : POST {API_URL}")
    print(f"  queries  : {len(QUERIES)} AI/Data keywords x {PAGES_PER_QUERY} page(s)")
    print(f"  scope    : IT/Telecom (func {IT_PARENT_FUNCTION_ID}); focus child {AI_DATA_CHILD_FUNCTION_IDS}")
    print("=" * 74)

    with httpx.Client(follow_redirects=True) as client:
        # --- 1. reliability harness: repeat one query and measure stability ----------
        probe = QUERIES[0]
        print(f"\n[reliability] repeating query {probe!r} {RELIABILITY_RUNS}x ...")
        runs: list[dict] = []
        for i in range(RELIABILITY_RUNS):
            status, latency, jobs = fetch(client, probe, 0)
            ok = status == 200 and len(jobs) > 0
            runs.append({"status": status, "latency": latency, "ok": ok})
            print(f"  run {i + 1}/{RELIABILITY_RUNS}: status={status} latency={latency:.2f}s jobs={len(jobs)} ok={ok}")
            time.sleep(DELAY_SECONDS)

        # --- 2. recall + precision: collect AI/Data IT jobs across keywords ----------
        print(f"\n[collect] {len(QUERIES)} queries x {PAGES_PER_QUERY} pages ...")
        raw_by_id: dict[int, dict] = {}
        for query in QUERIES:
            got = 0
            for page in range(PAGES_PER_QUERY):
                status, _, jobs = fetch(client, query, page)
                for j in jobs:
                    if j.get("jobId") is not None:
                        raw_by_id[j["jobId"]] = j
                got += len(jobs)
                time.sleep(DELAY_SECONDS)
            print(f"  {query!r:22} -> {got} hits")

    unique = list(raw_by_id.values())
    it_jobs = [j for j in unique if is_it(j)]
    ai_data_jobs = [j for j in unique if is_ai_data(j)]
    records = [normalize(j) for j in ai_data_jobs]  # the focus dataset

    # --- 3. write the JSON sample (AI/Data focus set) -------------------------------
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[output] wrote {len(records)} AI/Data records -> {OUTPUT_PATH}")

    # --- 4. preview -----------------------------------------------------------------
    print("\n[preview] first 5 AI/Data records:")
    for rec in records[:5]:
        flag = " [INTERN]" if rec["is_internship"] else ""
        print(f"  - {rec['title']} @ {rec['company']}  ({rec['job_level']}){flag}")
        print(f"      function={rec['job_function']}")
        print(f"      skills={rec['tech_stack_candidate'][:8]}")

    # --- 5. verdict block -----------------------------------------------------------
    ok_runs = sum(1 for r in runs if r["ok"])
    latencies = [r["latency"] for r in runs]
    anomalies = [r["status"] for r in runs if r["status"] != 200]
    interns = sum(1 for r in records if r["is_internship"])
    with_skills = sum(1 for r in records if r["tech_stack_candidate"])
    with_core = sum(1 for r in records if r["title"] and r["company"] and r["url"])
    with_desc = sum(1 for r in records if r["description"])

    print("\n" + "=" * 74)
    print("VERDICT")
    print("=" * 74)
    print(f"  reliability      : {ok_runs}/{RELIABILITY_RUNS} runs OK ({pct(ok_runs, RELIABILITY_RUNS):.0f}%)")
    print(f"  latency          : median={statistics.median(latencies):.2f}s  max={max(latencies):.2f}s")
    print(f"  collected unique : {len(unique)}  ->  IT(func 5)={len(it_jobs)}  AI/Data(child 27)={len(records)}")
    print(f"  internships       : {interns} flagged (collected at all levels, not filtered out)")
    print(f"  field complete   : core(title+company+url)={pct(with_core, len(records)):.0f}%  "
          f"description={pct(with_desc, len(records)):.0f}%  skills={pct(with_skills, len(records)):.0f}%")
    print(f"  anomalies        : {anomalies or 'none (no 403/429/non-200)'}")

    schedulable = ok_runs == RELIABILITY_RUNS and bool(records) and with_core == len(records)
    print(f"  schedulable      : {'YES' if schedulable else 'NEEDS REVIEW'} — "
          f"{'headless JSON API, stable, structured AI/Data records' if schedulable else 'see runs above'}")
    if schedulable:
        print("  suggested cadence: daily (e.g. cron 06:00) — small, polite, no anti-bot path")
    print("=" * 74)


if __name__ == "__main__":
    main()
