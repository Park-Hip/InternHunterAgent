"""Scraping spike — ITviec AI/Data IT jobs via cloudscraper.

A throwaway spike (NOT wired into the app, no database) that answers, for the project's
*actual* target — **IT jobs focused on AI/Data roles** — the same questions the
VietnamWorks and TopCV spikes asked, so the three are directly comparable:

  1. **Bypass + reliability.** A plain GET to ITviec returns 403 Cloudflare; does the free
     `cloudscraper` library clear it, and is it stable across repeated runs?
  2. **AI/Data scoping.** Can we precisely isolate AI/Data IT roles? ITviec curates a
     **"Việc làm AI, Data" segment** (`/segments/viec-lam-ai-data`) — a server-rendered
     listing of exactly those roles, no keyword-noise filtering needed.
  3. **`tech_stack` quality.** ITviec is the IT-only board expected to tag postings with
     **real technologies**. It goes further: each detail page separates **Skills:**
     (technologies) from **Job Expertise:** (roles) from **Job Domain:** (industry) — so
     `tech_stack_candidate` can be the Skills box *as-is*, no role/tech untangling.

Source facts (see research/data-ingestion-stage.md and research/job-site-comparison.md):
- Listing is SSR HTML reached via cloudscraper; the `/it-jobs/<skill>` category pages are
  JS-rendered (cards absent from static HTML), but the **AI/Data segment page is fully
  server-rendered** — that is the crawl surface we use.
- Detail URL shape: `https://itviec.com/it-jobs/{role-company-slug}-{job-id}` →
  the trailing **`{job-id}` is the natural `external_id`** for dedup.

Run:  uv run python scripts/scrape_itviec_spike.py

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
from urllib.parse import urljoin, urlparse

import cloudscraper
from bs4 import BeautifulSoup

# --- spike parameters -------------------------------------------------------------
BASE = "https://itviec.com"
# The curated AI/Data segment — server-rendered listing of exactly the roles we target.
SEGMENT_URL = "https://itviec.com/segments/viec-lam-ai-data"
ROBOTS_URL = "https://itviec.com/robots.txt"
DETAIL_RE = r"/it-jobs/([a-z0-9][a-z0-9-]*-\d+)(?=[\"'?])"  # capture group = slug; id = trailing \d+
RELIABILITY_RUNS = 5
MAX_DETAILS = 15        # detail pages to fetch (hard cap — be polite)
DELAY_SECONDS = 2.0     # politeness gap (>= TopCV; ITviec didn't rate-limit in probes)
TIMEOUT_SECONDS = 30
OUTPUT_PATH = (
    Path(__file__).resolve().parents[1]
    / "research"
    / "experiments"
    / "itviec_ai_data_sample.json"
)
CHALLENGE_MARKERS = ["just a moment", "cf-challenge", "cf_chl", "enable javascript and cookies"]
# ----------------------------------------------------------------------------------

BROWSER_PROFILE = {"browser": "chrome", "platform": "windows", "mobile": False}


def make_scraper() -> cloudscraper.CloudScraper:
    return cloudscraper.create_scraper(browser=BROWSER_PROFILE)


def is_challenge(status: int, body: str) -> bool:
    if status in (403, 503, 429):
        return True
    low = body.lower()
    return any(marker in low for marker in CHALLENGE_MARKERS)


def pct(part: int, whole: int) -> float:
    return 100.0 * part / whole if whole else 0.0


# --- robots.txt -------------------------------------------------------------------

def fetch_and_check_robots(scraper: cloudscraper.CloudScraper) -> bool:
    """Fetch robots.txt, print it, return True if our segment/detail paths are allowed."""
    print(f"\n[robots.txt] GET {ROBOTS_URL}")
    try:
        resp = scraper.get(ROBOTS_URL, timeout=TIMEOUT_SECONDS)
        print(resp.text[:1500])
    except Exception as exc:
        print(f"  ! could not fetch robots.txt: {exc}")
        return True

    disallowed: list[str] = []
    paths = [urlparse(SEGMENT_URL).path.lower(), "/it-jobs/"]
    for line in resp.text.lower().splitlines():
        line = line.strip()
        if line.startswith("disallow:"):
            rule = line.split(":", 1)[1].strip()
            if rule and (rule == "/" or any(p.startswith(rule) for p in paths)):
                disallowed.append(rule)

    if disallowed:
        print(f"\n  BLOCKED by robots.txt — matching Disallow rules: {disallowed}")
        return False
    print("  -> segment and detail paths not disallowed. Proceeding.")
    return True


# --- reliability harness ----------------------------------------------------------

def reliability_harness(scraper: cloudscraper.CloudScraper) -> list[dict]:
    print(f"\n[reliability] fetching the AI/Data segment {RELIABILITY_RUNS}x ...")
    runs: list[dict] = []
    pattern = re.compile(DETAIL_RE)
    for i in range(RELIABILITY_RUNS):
        start = time.perf_counter()
        try:
            resp = scraper.get(SEGMENT_URL, timeout=TIMEOUT_SECONDS)
            latency = time.perf_counter() - start
            status = resp.status_code
            body = resp.text
            challenge = is_challenge(status, body)
            jobs = len(set(pattern.findall(body)))
            ok = status == 200 and not challenge and jobs > 0
        except Exception as exc:
            latency = time.perf_counter() - start
            status, challenge, jobs, ok = -1, False, 0, False
            print(f"  ! request error: {type(exc).__name__}: {exc}")

        runs.append({"status": status, "latency": latency, "ok": ok, "challenge": challenge})
        flag = "OK" if ok else ("CHALLENGE" if challenge else f"HTTP {status}")
        print(f"  run {i + 1}/{RELIABILITY_RUNS}: status={status} latency={latency:.2f}s "
              f"jobs={jobs} ok={ok} [{flag}]")
        time.sleep(DELAY_SECONDS)
    return runs


# --- listing crawler --------------------------------------------------------------

def collect_detail_urls(scraper: cloudscraper.CloudScraper) -> list[tuple[str, str]]:
    """Fetch the segment page, return deduped (job_id, url) pairs from detail slugs."""
    pattern = re.compile(DETAIL_RE)
    try:
        resp = scraper.get(SEGMENT_URL, timeout=TIMEOUT_SECONDS)
    except Exception as exc:
        print(f"  ! error fetching segment: {exc}")
        return []
    if is_challenge(resp.status_code, resp.text):
        print(f"  ! Cloudflare challenge on segment (status={resp.status_code})")
        return []

    seen: dict[str, str] = {}  # job_id -> url
    for slug in pattern.findall(resp.text):
        job_id = slug.rsplit("-", 1)[-1]
        if job_id not in seen:
            seen[job_id] = urljoin(BASE, f"/it-jobs/{slug}")
    return list(seen.items())


# --- detail page parser -----------------------------------------------------------

def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def labeled_box(soup: BeautifulSoup, label: str) -> list[str]:
    """Return the anchor texts in ITviec's `label:` row (Skills:/Job Expertise:/Job Domain:).

    Each row is `<div ...fw-600...>Label:</div><div ...>...<a>tag</a>...</div>`; we match the
    label div, walk to its row parent, and read the anchor texts (minus the label itself).
    """
    for div in soup.find_all("div"):
        if clean(div.get_text()) == label and "fw-600" in (div.get("class") or []):
            row = div.parent
            return [clean(a.get_text()) for a in row.find_all("a") if clean(a.get_text())]
    return []


def parse_detail(html_body: str, job_id: str, url: str) -> dict:
    soup = BeautifulSoup(html_body, "html.parser")

    h1 = soup.find("h1")
    title = clean(h1.get_text()) if h1 else ""

    emp = soup.select_one(".employer-name")
    company = clean(emp.get_text()) if emp else ""

    # salary — header `.salary` block, but often gated behind "Sign in to view salary"
    salary = ""
    sal = soup.select_one(".job-header-info .salary")
    if sal:
        txt = clean(sal.get_text())
        salary = "" if (not txt or "sign in" in txt.lower()) else txt

    # location / working model — labeled chips when present
    location = ""
    for label in ("Location:", "Work Type:", "Working Model:"):
        vals = labeled_box(soup, label)
        if vals:
            location = ", ".join(vals)
            break

    # freshness — "Last updated: ..." stamp
    last_updated = ""
    m = re.search(r"Last updated:\s*\"?([0-9 :+\-]+)", html_body)
    if m:
        last_updated = m.group(1).strip()

    # THE headline field: Skills box = real technologies, taken as-is
    tech_stack_candidate = labeled_box(soup, "Skills:")
    # bonus structured fields proving role/tech separation
    job_expertise = labeled_box(soup, "Job Expertise:")
    job_domain = labeled_box(soup, "Job Domain:")

    # description — the main content section
    description = ""
    content = soup.select_one("section.job-content") or soup.select_one("[class*='job-content']")
    if content:
        description = clean(content.get_text())

    return {
        "external_id": job_id,
        "title": title,
        "company": company,
        "location": location,
        "salary": salary,
        "last_updated": last_updated,
        "description": description[:2000],
        "tech_stack_candidate": tech_stack_candidate,  # technologies, no role-tag noise
        "job_expertise": job_expertise,                # roles (kept separate from tech)
        "job_domain": job_domain,                      # industry
        "url": url,
        "source": "itviec",
    }


# --- main -------------------------------------------------------------------------

def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    print("=" * 74)
    print("ITviec AI/Data IT jobs — cloudscraper Cloudflare bypass spike")
    print(f"  segment  : {SEGMENT_URL}  (curated AI/Data listing)")
    print(f"  detail re: {DETAIL_RE}")
    print(f"  cap      : {MAX_DETAILS} detail pages   politeness delay: {DELAY_SECONDS}s")
    print("=" * 74)

    scraper = make_scraper()

    # 1. robots.txt gate
    if not fetch_and_check_robots(scraper):
        return

    # 2. reliability harness
    runs = reliability_harness(scraper)

    # 3. collect detail URLs from the segment page
    print(f"\n[collect] reading AI/Data segment ...")
    detail_pairs = collect_detail_urls(scraper)
    print(f"  -> {len(detail_pairs)} unique AI/Data detail URLs found")

    # 4. fetch detail pages (capped)
    records: list[dict] = []
    detail_anomalies: list[str] = []
    to_fetch = detail_pairs[:MAX_DETAILS]
    print(f"\n[details] fetching {len(to_fetch)} detail pages (cap={MAX_DETAILS}) ...")
    for idx, (job_id, url) in enumerate(to_fetch, 1):
        try:
            resp = scraper.get(url, timeout=TIMEOUT_SECONDS)
        except Exception as exc:
            print(f"  {idx}/{len(to_fetch)} ! error: {exc}")
            detail_anomalies.append(f"error:{job_id}")
            time.sleep(DELAY_SECONDS)
            continue

        if is_challenge(resp.status_code, resp.text) or resp.status_code != 200:
            note = f"http{resp.status_code}:{job_id}"
            print(f"  {idx}/{len(to_fetch)} ! blocked/non-200 (status={resp.status_code})")
            detail_anomalies.append(note)
            time.sleep(DELAY_SECONDS)
            continue

        rec = parse_detail(resp.text, job_id, url)
        records.append(rec)
        print(f"  {idx}/{len(to_fetch)}: {rec['title'][:48]!r} @ {rec['company'][:26]!r}  "
              f"skills={rec['tech_stack_candidate'][:6]}")
        time.sleep(DELAY_SECONDS)

    # 5. write JSON sample
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
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
    print(f"  bypass           : {ok_runs}/{RELIABILITY_RUNS} runs returned real HTML "
          f"({challenge_runs} challenge{'s' if challenge_runs != 1 else ''})")
    if latencies:
        print(f"  latency          : median={statistics.median(latencies):.2f}s  max={max(latencies):.2f}s")
    print(f"  AI/Data scoping  : curated segment -> {len(detail_pairs)} detail URLs -> {n} parsed")
    if n:
        print(f"  field complete   : external_id={pct(f_id, n):.0f}%  title={pct(f_title, n):.0f}%  "
              f"company={pct(f_company, n):.0f}%  description={pct(f_desc, n):.0f}%  "
              f"tech_stack={pct(f_tech, n):.0f}%")
    if tech_counts:
        print(f"  tech tags/job    : median={statistics.median(tech_counts):.0f}  "
              f"max={max(tech_counts)}  (real technologies, role/domain kept separate)")
        sample_tags = sorted({t for r in records for t in r["tech_stack_candidate"]})
        print(f"  tech vocabulary  : {sample_tags[:20]}")
    print(f"  reliability anomalies : {reliability_anomalies or 'none'}")
    print(f"  detail anomalies      : {detail_anomalies or 'none'}")

    bypass_ok = ok_runs >= (RELIABILITY_RUNS * 0.8)
    fields_ok = n > 0 and pct(f_title, n) >= 80 and pct(f_company, n) >= 80 and pct(f_tech, n) >= 80
    viable = bypass_ok and fields_ok

    if viable:
        verdict = (
            "FREE CLOUDSCRAPER PATH IS VIABLE — cleared Cloudflare reliably, scoped AI/Data "
            "via the curated segment, and yielded clean technology tags as tech_stack. "
            "Strong tech_stack source; schedule as a daily crawler."
        )
    elif ok_runs == 0:
        verdict = ("CLOUDSCRAPER FAILED TO CLEAR CLOUDFLARE — all runs blocked. "
                   "Design must plan for the Scrapfly fallback.")
    elif not bypass_ok:
        verdict = (f"CLOUDSCRAPER UNRELIABLE — only {ok_runs}/{RELIABILITY_RUNS} bypass runs OK. "
                   "Too flaky for a scheduled crawler; consider Scrapfly fallback.")
    else:
        verdict = (f"PARTIAL — bypass ok ({ok_runs}/{RELIABILITY_RUNS}) but field yield low "
                   f"(title={pct(f_title, n):.0f}%, company={pct(f_company, n):.0f}%, "
                   f"tech={pct(f_tech, n):.0f}%). Review selectors.")

    print(f"\n  >> {verdict}")
    print("=" * 74)


if __name__ == "__main__":
    main()
