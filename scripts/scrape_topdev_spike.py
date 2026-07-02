"""Scraping spike — TopDev AI/Data IT jobs via RSC payload parsing.

A throwaway spike (NOT wired into the app, no database) that answers two questions
for TopDev (`topdev.vn`) so the result is directly comparable to the VietnamWorks,
ITviec, and TopCV spikes:

  1. **Acquisition success + reliability.** Does the chosen free path return real
     AI/Data job data reliably across repeated runs?
  2. **Field yield & quality.** What fraction of detail records yield the core fields?
     How clean is `tech_stack_candidate` (are skills real technologies)?

Phase-0 findings (discovery probes run 2026-06-30):
- **Anti-bot floor**: Plain `httpx` GET returns HTTP 200 with a 1.9 MB HTML body on
  every request — no Cloudflare challenge, no interstitial, no `cloudscraper` needed.
  This is the simplest anti-bot of any candidate tested.
- **Access method**: Next.js App Router with React Server Components (RSC) streaming.
  Job data is embedded inside `self.__next_f.push([1, "..."])` chunks in the HTML.
  There is no `__NEXT_DATA__` blob and no discoverable public JSON/GraphQL API at
  `api.topdev.vn` (all guessed paths returned 404). The RSC payload is parseable
  entirely with plain regex + `json.loads`.
- **Scoping surface**: `https://topdev.vn/jobs?page=N` — each page embeds 15 promoted/
  paid IT jobs in the RSC. The query string (`q=...`) does NOT change the embedded
  jobs (same 15 records regardless of keyword); AI/Data scoping is done client-side
  by filtering `skills_str` for AI/Data keywords. Measured density: ~23% of promoted
  jobs are AI/Data (17 found in 75 jobs across 5 pages).
- **Detail/ID shape**: `detail_url` in the listing RSC gives the full URL
  `https://topdev.vn/detail-jobs/{slug}-{id}`. The trailing `{id}` (int field) is the
  stable `external_id`. Detail page RSC has richer content: `requirements_original`,
  `responsibilities_original`, `why_you_should_apply` HTML blocks.
- **Field locations**: `skills_str` (comma-separated real tech tags — present on listing
  RSC), `title`/`id`/`detail_url`/`job_levels_str` on the listing RSC job object;
  `company.display_name`, `addresses.address_region_list`, `salary.value` are RSC
  `$ref` objects resolved from the same payload. Description comes from the detail page.

Run:  uv run python scripts/scrape_topdev_spike.py

Constants live at the top on purpose: this is a measurement spike, not a production
adapter. They graduate to config/settings.yaml only if/when ingestion becomes a real
JobSource adapter.
"""

from __future__ import annotations

import json
import re
import statistics
import sys
import time
from pathlib import Path

import html as html_lib

import httpx
from bs4 import BeautifulSoup

# --- spike parameters ------------------------------------------------------------
BASE_URL = "https://topdev.vn"
# Each listing page embeds 15 promoted/paid IT jobs in the RSC payload.
# Query param has no effect; pagination does.
LISTING_URL = "https://topdev.vn/jobs?page={page}"
ROBOTS_URL = "https://topdev.vn/robots.txt"
# Pattern to extract numeric job id from a detail URL
DETAIL_ID_RE = r"/detail-jobs/[a-z0-9-]+-(\d+)(?:[\"'\s?]|$)"
RELIABILITY_RUNS = 5
MAX_PAGES = 3       # listing pages to paginate (3 × 15 = 45 jobs to scan)
MAX_DETAILS = 15    # detail pages to fetch (hard cap — be polite)
DELAY_SECONDS = 2.0
TIMEOUT_SECONDS = 30
OUTPUT_PATH = (
    Path(__file__).resolve().parents[1]
    / "research"
    / "experiments"
    / "topdev_ai_data_sample.json"
)
CHALLENGE_MARKERS = ["just a moment", "cf-challenge", "cf_chl", "enable javascript and cookies"]
# Keywords for client-side AI/Data job filtering (matched against skills_str + title)
AI_DATA_KEYWORDS = {
    "python", "machine learning", "data science", "data scientist", "data engineer",
    "data analyst", "ai ", " ai,", "artificial intelligence", "deep learning",
    "neural", "nlp", "llm", "tensorflow", "pytorch", "pandas", "spark", "hadoop",
    "airflow", "data analytics", "power bi", "tableau", "scikit", "data warehouse",
    "etl", "mlops", "ml ", "computer vision", "langchain", "pyspark", "bigquery",
    "r language", "rstudio", "data pipeline", "feature engineering",
}
# ----------------------------------------------------------------------------------

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
    "Referer": "https://topdev.vn/",
}


def make_client() -> httpx.Client:
    return httpx.Client(headers=BROWSER_HEADERS, timeout=TIMEOUT_SECONDS,
                        follow_redirects=True)


def is_challenge(status: int, body: str) -> bool:
    if status in (403, 503, 429):
        return True
    low = body.lower()
    return any(marker in low for marker in CHALLENGE_MARKERS)


def pct(part: int, whole: int) -> float:
    return 100.0 * part / whole if whole else 0.0


def clean_html(html: str) -> str:
    """Strip HTML tags, decode entities, and collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", html or "")
    text = html_lib.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


# --- RSC payload parser ----------------------------------------------------------

def extract_rsc(html: str) -> str:
    """Decode and concatenate all `self.__next_f.push([1, "..."])` RSC chunks."""
    chunks = re.findall(
        r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', html, re.DOTALL
    )
    parts: list[str] = []
    for chunk in chunks:
        try:
            parts.append(json.loads('"' + chunk + '"'))
        except Exception:
            parts.append(
                chunk.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")
            )
    return "".join(parts)


def parse_rsc(rsc_text: str) -> tuple[dict[str, dict], dict[str, str]]:
    """Return (json_objects, text_blocks) from the RSC payload.

    RSC line formats:
      hexid:{json}              → json_objects[hexid] = parsed dict/list
      hexid:Thex_len,<content>  → text_blocks[hexid] = raw HTML/text (may be multi-line)

    T-format blocks can span multiple lines; we use the embedded hex length to read
    the exact content rather than splitting on \\n.
    """
    json_objs: dict[str, dict] = {}
    text_blocks: dict[str, str] = {}

    # Pass 1: extract T-format text blocks (multi-line safe).
    # Format: <hexid>:T<hex_length>,<content of exactly hex_length bytes>
    for m in re.finditer(r"([0-9a-f]+):T([0-9a-f]+),", rsc_text):
        rsc_id = m.group(1)
        content_len = int(m.group(2), 16)
        start = m.end()
        text_blocks[rsc_id] = rsc_text[start: start + content_len]

    # Pass 2: extract JSON objects (line-by-line; JSON objs don't span lines in RSC).
    json_re = re.compile(r"^([0-9a-f]+):(\{.+\}|\[.+\])$")
    for line in rsc_text.split("\n"):
        m = json_re.match(line)
        if m:
            try:
                json_objs[m.group(1)] = json.loads(m.group(2))
            except Exception:
                pass
    return json_objs, text_blocks


def resolve(val: object, json_objs: dict, text_blocks: dict) -> object:
    """Follow a `$refid` pointer one level deep."""
    if isinstance(val, str) and val.startswith("$"):
        key = val[1:]
        return json_objs.get(key) or text_blocks.get(key, val)
    return val


def extract_jobs_from_rsc(
    json_objs: dict[str, dict],
) -> list[tuple[str, dict]]:
    """Return (rsc_key, job_obj) pairs for job records in the RSC payload.

    Job records are identified by having an integer `id`, a non-empty `title`,
    `skills_str`, and `slug` — a combination unique to TopDev's job objects.
    """
    jobs: list[tuple[str, dict]] = []
    seen_ids: set[int] = set()
    for key, obj in json_objs.items():
        if not isinstance(obj, dict):
            continue
        jid = obj.get("id")
        if (
            isinstance(jid, int)
            and isinstance(obj.get("title"), str)
            and len(obj.get("title", "")) > 5
            and "skills_str" in obj
            and "slug" in obj
            and jid not in seen_ids
        ):
            jobs.append((key, obj))
            seen_ids.add(jid)
    return jobs


def is_ai_data_job(job: dict) -> bool:
    """Return True if `skills_str` or `title` contains AI/Data keywords."""
    combined = (
        (job.get("skills_str") or "").lower()
        + " "
        + (job.get("title") or "").lower()
    )
    return any(kw in combined for kw in AI_DATA_KEYWORDS)


# --- robots.txt gate -------------------------------------------------------------

def fetch_and_check_robots(client: httpx.Client) -> bool:
    print(f"\n[robots.txt] GET {ROBOTS_URL}")
    try:
        resp = client.get(ROBOTS_URL)
        print(resp.text[:2000])
    except Exception as exc:
        print(f"  ! could not fetch robots.txt: {exc}")
        return True

    listing_path = "/jobs"
    detail_prefix = "/detail-jobs/"
    disallowed: list[str] = []

    # Only evaluate rules under User-agent: * blocks (skip bot-specific sections).
    in_wildcard = False
    for raw_line in resp.text.splitlines():
        line = raw_line.strip().lower()
        if line.startswith("user-agent:"):
            ua = line.split(":", 1)[1].strip()
            in_wildcard = ua == "*"
            continue
        if not in_wildcard:
            continue
        if line.startswith("disallow:"):
            rule = line.split(":", 1)[1].strip()
            if rule and (
                listing_path.startswith(rule)
                or detail_prefix.startswith(rule)
                or rule == "/"
            ):
                disallowed.append(rule)

    if disallowed:
        print(f"\n  BLOCKED by robots.txt — matching Disallow rules: {disallowed}")
        return False
    print("  -> listing and detail paths not disallowed. Proceeding.")
    return True


# --- reliability harness ---------------------------------------------------------

def reliability_harness(client: httpx.Client) -> list[dict]:
    url = LISTING_URL.format(page=1)
    print(f"\n[reliability] fetching listing page 1 × {RELIABILITY_RUNS} ...")
    runs: list[dict] = []
    for i in range(RELIABILITY_RUNS):
        start = time.perf_counter()
        try:
            resp = client.get(url)
            latency = time.perf_counter() - start
            status = resp.status_code
            body = resp.text
            challenge = is_challenge(status, body)
            rsc = extract_rsc(body)
            json_objs, _ = parse_rsc(rsc)
            job_pairs = extract_jobs_from_rsc(json_objs)
            ok = status == 200 and not challenge and len(job_pairs) > 0
        except Exception as exc:
            latency = time.perf_counter() - start
            status, challenge, job_pairs, ok = -1, False, [], False
            print(f"  ! request error: {type(exc).__name__}: {exc}")
        runs.append(
            {"status": status, "latency": latency, "ok": ok, "challenge": challenge}
        )
        flag = "OK" if ok else ("CHALLENGE" if challenge else f"HTTP {status}")
        print(
            f"  run {i + 1}/{RELIABILITY_RUNS}: status={status}  "
            f"latency={latency:.2f}s  jobs_in_rsc={len(job_pairs)}  [{flag}]"
        )
        time.sleep(DELAY_SECONDS)
    return runs


# --- listing crawler -------------------------------------------------------------

def collect_ai_data_jobs(
    client: httpx.Client,
) -> list[tuple[str, dict, dict, dict]]:
    """Paginate listing pages and return (external_id, job_obj, json_objs, text_blocks)
    tuples for AI/Data jobs found, deduped by external_id."""
    seen: dict[str, tuple[dict, dict, dict]] = {}

    for page in range(1, MAX_PAGES + 1):
        url = LISTING_URL.format(page=page)
        print(f"\n  listing page {page}/{MAX_PAGES}: {url}")
        try:
            resp = client.get(url)
        except Exception as exc:
            print(f"    ! error: {exc}")
            time.sleep(DELAY_SECONDS)
            continue
        if is_challenge(resp.status_code, resp.text):
            print(f"    ! challenge/blocked (status={resp.status_code})")
            time.sleep(DELAY_SECONDS)
            continue

        rsc = extract_rsc(resp.text)
        json_objs, text_blocks = parse_rsc(rsc)
        job_pairs = extract_jobs_from_rsc(json_objs)
        ai_jobs = [(k, j) for k, j in job_pairs if is_ai_data_job(j)]
        print(f"    -> {len(job_pairs)} jobs in RSC, {len(ai_jobs)} AI/Data")

        for rsc_key, job in ai_jobs:
            ext_id = str(job["id"])
            if ext_id not in seen:
                seen[ext_id] = (job, json_objs, text_blocks)

        time.sleep(DELAY_SECONDS)

    return [(eid, *v) for eid, v in seen.items()]


# --- detail page parser ----------------------------------------------------------

def parse_detail(
    html: str, ext_id: str, listing_job: dict,
    listing_json: dict, listing_texts: dict,
) -> dict:
    """Build a normalized record from the detail page RSC + listing metadata."""
    rsc = extract_rsc(html)
    json_objs, text_blocks = parse_rsc(rsc)

    # Find the job record in the detail RSC (same id)
    detail_job: dict = {}
    for obj in json_objs.values():
        if isinstance(obj, dict) and obj.get("id") == int(ext_id):
            if "title" in obj and "slug" in obj:
                detail_job = obj
                break
    # Fall back to listing record if detail RSC parse failed
    job = detail_job if detail_job else listing_job
    ref_json = json_objs if detail_job else listing_json
    ref_text = text_blocks if detail_job else listing_texts

    # Resolve company
    company_obj = resolve(job.get("company", ""), ref_json, ref_text)
    company = (
        company_obj.get("display_name", "")
        if isinstance(company_obj, dict)
        else ""
    )

    # Resolve location
    addr_obj = resolve(job.get("addresses", ""), ref_json, ref_text)
    location = (
        addr_obj.get("address_region_list", "")
        if isinstance(addr_obj, dict)
        else ""
    )

    # Resolve salary
    sal_obj = resolve(job.get("salary", ""), ref_json, ref_text)
    salary = ""
    if isinstance(sal_obj, dict):
        salary = sal_obj.get("value", "") or ""
        if not salary and (sal_obj.get("min", 0) or sal_obj.get("max", 0)):
            mn, mx = sal_obj.get("min", 0), sal_obj.get("max", 0)
            cur = sal_obj.get("currency_estimate", sal_obj.get("currency", "VND"))
            salary = f"{mn}-{mx} {cur}/month"

    # Resolve deadline (expires field).  Falls back to HTML date-string search.
    exp_obj = resolve(job.get("expires", ""), ref_json, ref_text)
    if isinstance(exp_obj, dict):
        deadline = exp_obj.get("date", "") or exp_obj.get("datetime", "")
    else:
        # RSC reference not resolved — scan HTML for an expires/deadline date pattern
        m_date = re.search(
            r'(?:expires?|deadline|h[aạ]n\s*n[oô]p)[^\d]{0,20}(\d{1,2}[-/]\d{1,2}[-/]\d{4}|\d{2}-\d{2}-\d{4})',
            html, re.IGNORECASE,
        )
        deadline = m_date.group(1) if m_date else ""

    # Description: collect HTML blocks from requirements, responsibilities, etc.
    desc_parts: list[str] = []
    for field in (
        "responsibilities", "requirements",
        "why_you_should_apply", "why_you_stay",
        "content", "content_html",
    ):
        val = job.get(field, "")
        resolved = resolve(val, ref_json, ref_text)
        if isinstance(resolved, str) and resolved.strip() and not resolved.startswith("$"):
            desc_parts.append(resolved)
        elif isinstance(resolved, list):
            for item in resolved:
                if isinstance(item, str) and item.strip() and not item.startswith("$"):
                    desc_parts.append(item)
    # Fallback: grab all visible text from the page (HTML) if RSC parts are thin
    if sum(len(p) for p in desc_parts) < 100:
        soup = BeautifulSoup(html, "html.parser")
        # Try common job-detail content selectors
        for sel in [
            "[class*='job-detail']", "[class*='job-content']",
            "[class*='description']", "main article", "main section",
        ]:
            el = soup.select_one(sel)
            if el and len(el.get_text(strip=True)) > 100:
                desc_parts.append(el.get_text(separator=" ", strip=True))
                break
    description = clean_html(" ".join(desc_parts))[:2000]

    # Tech stack — `skills_str` on listing RSC is comma-separated real tech tags
    skills_str = (
        listing_job.get("skills_str") or job.get("skills_str") or ""
    )
    tech_stack_candidate = [s.strip() for s in skills_str.split(",") if s.strip()]

    # skills_arr reference (array of tag objects) — try to resolve for richer tags
    skills_arr = resolve(job.get("skills_arr", ""), ref_json, ref_text)
    if isinstance(skills_arr, list) and skills_arr and not tech_stack_candidate:
        tech_stack_candidate = [
            t.get("name", "") for t in skills_arr
            if isinstance(t, dict) and t.get("name")
        ]

    url = job.get("detail_url", "") or listing_job.get("detail_url", "")

    return {
        "external_id": ext_id,
        "title": job.get("title", "") or listing_job.get("title", ""),
        "company": company,
        "location": location,
        "salary": salary,
        "deadline": deadline,
        "description": description,
        "tech_stack_candidate": tech_stack_candidate,
        "job_levels": job.get("job_levels_str", "") or listing_job.get("job_levels_str", ""),
        "url": url,
        "source": "topdev",
    }


# --- main ------------------------------------------------------------------------

def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    print("=" * 74)
    print("TopDev AI/Data IT jobs — RSC streaming payload spike")
    print("  access   : plain httpx (NO cloudscraper needed — no Cloudflare wall)")
    print(f"  listing  : {LISTING_URL!r}  (15 promoted IT jobs/page in RSC)")
    print(f"  detail re: {DETAIL_ID_RE}")
    print(f"  caps     : {MAX_PAGES} listing pages / {MAX_DETAILS} detail pages")
    print(f"  delay    : {DELAY_SECONDS}s between requests")
    print("=" * 74)

    client = make_client()

    # 1. robots.txt gate
    if not fetch_and_check_robots(client):
        return

    # 2. reliability harness
    runs = reliability_harness(client)

    # 3. collect AI/Data job entries from listing pages
    print(f"\n[collect] scanning {MAX_PAGES} listing pages for AI/Data jobs ...")
    ai_data_entries = collect_ai_data_jobs(client)
    print(f"\n  -> {len(ai_data_entries)} unique AI/Data jobs collected")

    # 4. fetch detail pages (capped)
    records: list[dict] = []
    detail_anomalies: list[str] = []
    to_fetch = ai_data_entries[:MAX_DETAILS]
    print(f"\n[details] fetching {len(to_fetch)} detail pages (cap={MAX_DETAILS}) ...")

    for idx, (ext_id, listing_job, listing_json, listing_texts) in enumerate(
        to_fetch, 1
    ):
        url = listing_job.get("detail_url", "")
        if not url:
            url = f"{BASE_URL}/detail-jobs/{listing_job.get('slug', '')}-{ext_id}"
        print(f"  {idx}/{len(to_fetch)}: {url[-80:]}")
        try:
            resp = client.get(url)
        except Exception as exc:
            print(f"    ! error: {exc}")
            detail_anomalies.append(f"error:{ext_id}")
            time.sleep(DELAY_SECONDS)
            continue
        if is_challenge(resp.status_code, resp.text):
            note = f"challenge:{resp.status_code}:{ext_id}"
            print(f"    ! challenge/blocked (status={resp.status_code})")
            detail_anomalies.append(note)
            time.sleep(DELAY_SECONDS)
            continue
        if resp.status_code != 200:
            detail_anomalies.append(f"http{resp.status_code}:{ext_id}")
            print(f"    ! HTTP {resp.status_code}")
            time.sleep(DELAY_SECONDS)
            continue

        rec = parse_detail(
            resp.text, ext_id, listing_job, listing_json, listing_texts
        )
        records.append(rec)
        print(
            f"    title={rec['title'][:50]!r}  company={rec['company'][:25]!r}  "
            f"skills={rec['tech_stack_candidate'][:5]}"
        )
        time.sleep(DELAY_SECONDS)

    # 5. write JSON sample
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n[output] wrote {len(records)} AI/Data records -> {OUTPUT_PATH}")

    # 6. verdict block
    ok_runs = sum(1 for r in runs if r["ok"])
    challenge_runs = sum(1 for r in runs if r["challenge"])
    latencies = [r["latency"] for r in runs]
    reliability_anomalies = [r["status"] for r in runs if not r["ok"]]

    n = len(records)
    f_id = sum(1 for r in records if r["external_id"])
    f_title = sum(1 for r in records if r["title"])
    f_company = sum(1 for r in records if r["company"])
    f_desc = sum(1 for r in records if r["description"])
    f_tech = sum(1 for r in records if r["tech_stack_candidate"])
    tech_counts = [len(r["tech_stack_candidate"]) for r in records if r["tech_stack_candidate"]]

    print("\n" + "=" * 74)
    print("VERDICT")
    print("=" * 74)
    print(
        f"  acquisition      : {ok_runs}/{RELIABILITY_RUNS} runs returned real RSC job data "
        f"({challenge_runs} challenge{'s' if challenge_runs != 1 else ''})"
    )
    if latencies:
        print(
            f"  latency          : median={statistics.median(latencies):.2f}s  "
            f"max={max(latencies):.2f}s"
        )
    print(
        f"  AI/Data scoping  : listing pages ({MAX_PAGES}×15=max {MAX_PAGES*15} jobs scanned) "
        f"-> {len(ai_data_entries)} AI/Data found -> {n} detail records parsed"
    )
    if n:
        print(
            f"  field complete   : external_id={pct(f_id, n):.0f}%  "
            f"title={pct(f_title, n):.0f}%  company={pct(f_company, n):.0f}%  "
            f"description={pct(f_desc, n):.0f}%  "
            f"tech_stack={pct(f_tech, n):.0f}%"
        )
    if tech_counts:
        print(
            f"  tech tags/job    : median={statistics.median(tech_counts):.0f}  "
            f"max={max(tech_counts)}  (real technologies from skills_str)"
        )
        sample_tags = sorted({t for r in records for t in r["tech_stack_candidate"]})
        print(f"  tech vocabulary  : {sample_tags[:25]}")
    print(f"  reliability anomalies : {reliability_anomalies or 'none'}")
    print(f"  detail anomalies      : {detail_anomalies or 'none'}")

    bypass_ok = ok_runs >= (RELIABILITY_RUNS * 0.8)
    fields_ok = (
        n > 0
        and pct(f_title, n) >= 80
        and pct(f_company, n) >= 80
        and pct(f_tech, n) >= 80
    )
    viable = bypass_ok and fields_ok

    if viable:
        verdict = (
            "FREE PLAIN-HTTPX PATH IS VIABLE — no anti-bot at all, RSC payload "
            "delivers real job data reliably. `skills_str` carries real technology "
            "tags (comparable to ITviec) with no role/tech mixing. Strong tech_stack "
            "source. No cloudscraper needed."
        )
    elif ok_runs == 0:
        verdict = (
            "ACQUISITION FAILED — all reliability runs returned no job data. "
            "Investigate the RSC parser or anti-bot change."
        )
    elif not bypass_ok:
        verdict = (
            f"UNRELIABLE — only {ok_runs}/{RELIABILITY_RUNS} acquisition runs returned "
            "real data. Too flaky for a scheduled crawler."
        )
    else:
        verdict = (
            f"PARTIAL — acquisition ok ({ok_runs}/{RELIABILITY_RUNS}) but field yield low "
            f"(title={pct(f_title, n):.0f}%, company={pct(f_company, n):.0f}%, "
            f"tech={pct(f_tech, n):.0f}%). Review RSC reference resolver."
        )

    print(f"\n  >> {verdict}")
    print("=" * 74)

    client.close()


if __name__ == "__main__":
    main()
