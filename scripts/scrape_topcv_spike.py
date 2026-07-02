"""Scraping spike — TopCV internship listings via cloudscraper.

A throwaway spike (NOT wired into the app, no database) that answers two questions:

  1. **Bypass success + reliability.** Does `cloudscraper` return real job HTML (200)
     rather than a 403/Cloudflare challenge page, and is it stable across repeated runs?
  2. **Field yield & quality.** From a small sample of detail pages, what fraction yield
     the core fields expected by the ingestion design?

Source: TopCV (topcv.vn) — selected job board for this project (see
research/data-ingestion-stage.md §0.1, §2.5, §3, §4). Plain requests/httpx gets
Cloudflare-blocked; `cloudscraper` is the free-path first attempt. If it cannot clear
Cloudflare, that is a valid, useful result — the design falls back to Scrapfly.

Legality: robots.txt is fetched and printed before any crawl. Paths are checked against
the disallow list; the run aborts if the listing or detail paths are disallowed. A
politeness delay is applied between every request. No CAPTCHA solving, no candidate data,
hard page and detail caps enforced.

Run:  uv run python scripts/scrape_topcv_spike.py

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
from urllib.parse import urlparse

import cloudscraper
from bs4 import BeautifulSoup

# --- spike parameters -------------------------------------------------------------
LISTING_URL = "https://www.topcv.vn/tim-viec-lam-internship"
ROBOTS_URL = "https://www.topcv.vn/robots.txt"
DETAIL_URL_RE = r"/viec-lam/[^/]+/(\d+)\.html"
RELIABILITY_RUNS = 5
MAX_PAGES = 2       # listing pages to paginate (keep small)
MAX_DETAILS = 15    # detail pages to fetch (hard cap — be polite)
DELAY_SECONDS = 1.5
TIMEOUT_SECONDS = 30
OUTPUT_PATH = (
    Path(__file__).resolve().parents[1]
    / "research"
    / "experiments"
    / "topcv_cloudscraper_sample.json"
)
# Strings that indicate a Cloudflare challenge page rather than real HTML
CHALLENGE_MARKERS = ["cf-challenge", "Just a moment", "cf_chl", "Enable JavaScript and cookies"]
# ----------------------------------------------------------------------------------

BROWSER_PROFILE = {
    "browser": "chrome",
    "platform": "windows",
    "mobile": False,
}


def make_scraper() -> cloudscraper.CloudScraper:
    return cloudscraper.create_scraper(browser=BROWSER_PROFILE)


def is_challenge(status: int, body: str) -> bool:
    if status in (403, 503):
        return True
    return any(marker.lower() in body.lower() for marker in CHALLENGE_MARKERS)


def pct(part: int, whole: int) -> float:
    return 100.0 * part / whole if whole else 0.0


# --- robots.txt -------------------------------------------------------------------

def fetch_and_check_robots(scraper: cloudscraper.CloudScraper) -> bool:
    """Fetch robots.txt, print it, and return True if listing/detail paths are allowed."""
    print(f"\n[robots.txt] GET {ROBOTS_URL}")
    try:
        resp = scraper.get(ROBOTS_URL, timeout=TIMEOUT_SECONDS)
        print(resp.text[:3000])
    except Exception as exc:
        print(f"  ! could not fetch robots.txt: {exc}")
        return True  # can't verify — continue cautiously

    body = resp.text.lower()
    # Simple check: scan for Disallow lines that would cover our paths
    listing_path = urlparse(LISTING_URL).path.lower()
    detail_prefix = "/viec-lam/"
    disallowed: list[str] = []
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("disallow:"):
            rule = line.split(":", 1)[1].strip()
            if rule and (listing_path.startswith(rule) or detail_prefix.startswith(rule) or rule == "/"):
                disallowed.append(rule)

    if disallowed:
        print(f"\n  BLOCKED by robots.txt — matching Disallow rules: {disallowed}")
        print("  Aborting spike to respect robots.txt.")
        return False

    print("  -> listing and detail paths not disallowed. Proceeding.")
    return True


# --- reliability harness ----------------------------------------------------------

def reliability_harness(scraper: cloudscraper.CloudScraper) -> list[dict]:
    print(f"\n[reliability] fetching listing page {RELIABILITY_RUNS}x ...")
    runs: list[dict] = []
    for i in range(RELIABILITY_RUNS):
        start = time.perf_counter()
        try:
            resp = scraper.get(LISTING_URL, timeout=TIMEOUT_SECONDS)
            latency = time.perf_counter() - start
            status = resp.status_code
            body = resp.text
            challenge = is_challenge(status, body)
            ok = status == 200 and not challenge
        except Exception as exc:
            latency = time.perf_counter() - start
            status = -1
            challenge = False
            ok = False
            body = ""
            print(f"  ! request error: {type(exc).__name__}: {exc}")

        runs.append({"status": status, "latency": latency, "ok": ok, "challenge": challenge})
        flag = "OK" if ok else ("CHALLENGE" if challenge else f"HTTP {status}")
        print(f"  run {i + 1}/{RELIABILITY_RUNS}: status={status} latency={latency:.2f}s ok={ok} [{flag}]")
        time.sleep(DELAY_SECONDS)
    return runs


# --- listing crawler --------------------------------------------------------------

def collect_detail_urls(scraper: cloudscraper.CloudScraper) -> list[tuple[str, str]]:
    """Paginate the listing and return deduped (url, job_id) pairs."""
    seen: dict[str, str] = {}  # job_id -> url
    pattern = re.compile(DETAIL_URL_RE)
    base = "https://www.topcv.vn"

    for page in range(1, MAX_PAGES + 1):
        url = LISTING_URL if page == 1 else f"{LISTING_URL}?page={page}"
        print(f"  listing page {page}/{MAX_PAGES}: {url}")
        try:
            resp = scraper.get(url, timeout=TIMEOUT_SECONDS)
        except Exception as exc:
            print(f"    ! error: {exc}")
            time.sleep(DELAY_SECONDS)
            continue

        if is_challenge(resp.status_code, resp.text):
            print(f"    ! Cloudflare challenge on listing page {page} (status={resp.status_code})")
            time.sleep(DELAY_SECONDS)
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        found = 0
        for a in soup.find_all("a", href=True):
            m = pattern.search(a["href"])
            if m:
                job_id = m.group(1)
                href = a["href"]
                full_url = href if href.startswith("http") else base + href
                if job_id not in seen:
                    seen[job_id] = full_url
                    found += 1

        print(f"    -> found {found} new detail URLs (total {len(seen)})")
        time.sleep(DELAY_SECONDS)

    return list(seen.items())  # (job_id, url)


# --- detail page parser -----------------------------------------------------------

def strip_tags(element) -> str:
    if element is None:
        return ""
    text = element.get_text(separator=" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def parse_detail(html_body: str, job_id: str, url: str) -> dict:
    soup = BeautifulSoup(html_body, "html.parser")

    # title — <h1> or meta og:title
    title_tag = soup.find("h1")
    if not title_tag:
        og = soup.find("meta", property="og:title")
        title = og["content"].strip() if og and og.get("content") else ""
    else:
        title = strip_tags(title_tag)

    # company — common TopCV selectors
    company = ""
    for sel in [
        ".company-name-label", ".employer-name", ".company-name",
        "[class*='company-name']", "[class*='employer']",
    ]:
        el = soup.select_one(sel)
        if el:
            company = strip_tags(el)
            break
    if not company:
        og_site = soup.find("meta", property="og:site_name")
        if og_site and og_site.get("content"):
            company = og_site["content"].strip()

    # salary
    salary = ""
    for sel in [".salary-text", "[class*='salary']", ".job-salary"]:
        el = soup.select_one(sel)
        if el:
            salary = strip_tags(el)
            break

    # location
    location = ""
    for sel in [".job-address", "[class*='address']", "[class*='location']"]:
        el = soup.select_one(sel)
        if el:
            location = strip_tags(el)
            break

    # deadline
    deadline = ""
    for sel in ["[class*='deadline']", "[class*='expire']", ".job-deadline"]:
        el = soup.select_one(sel)
        if el:
            deadline = strip_tags(el)
            break

    # description — the main job content block
    description = ""
    for sel in [
        ".job-description", "[class*='job-description']",
        ".content-tab", ".job-detail-content", "[class*='description']",
    ]:
        el = soup.select_one(sel)
        if el:
            description = strip_tags(el)
            break
    if not description:
        # fallback: largest text block on the page
        for div in soup.find_all("div"):
            text = strip_tags(div)
            if len(text) > len(description):
                description = text

    # tech_stack_candidate — raw tags/categories (TopCV tags are mostly roles, not tech)
    tags: list[str] = []
    for sel in [".tag-item", "[class*='tag']", ".job-tag", "[class*='skill']", ".label-item"]:
        for el in soup.select(sel):
            t = strip_tags(el)
            if t and t not in tags:
                tags.append(t)
    if not tags:
        # try meta keywords
        meta_kw = soup.find("meta", attrs={"name": "keywords"})
        if meta_kw and meta_kw.get("content"):
            tags = [k.strip() for k in meta_kw["content"].split(",") if k.strip()]

    return {
        "external_id": job_id,
        "title": title,
        "company": company,
        "location": location,
        "salary": salary,
        "deadline": deadline,
        "description": description[:2000],  # cap for the JSON sample
        "tech_stack_candidate": tags,
        "url": url,
        "source": "topcv",
    }


# --- main -------------------------------------------------------------------------

def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    print("=" * 74)
    print("TopCV internship listing — cloudscraper Cloudflare bypass spike")
    print(f"  listing  : {LISTING_URL}")
    print(f"  detail re: {DETAIL_URL_RE}")
    print(f"  caps     : {MAX_PAGES} listing pages / {MAX_DETAILS} detail pages")
    print(f"  politeness delay: {DELAY_SECONDS}s between requests")
    print("=" * 74)

    scraper = make_scraper()

    # 1. robots.txt gate
    if not fetch_and_check_robots(scraper):
        return

    # 2. reliability harness
    print("\n[reliability harness]")
    runs = reliability_harness(scraper)

    # 3. collect detail URLs from listing pages
    print(f"\n[collect] paginating listing (max {MAX_PAGES} pages) ...")
    detail_pairs = collect_detail_urls(scraper)  # list of (job_id, url)
    print(f"  -> {len(detail_pairs)} unique detail URLs collected")

    # 4. fetch detail pages (capped)
    records: list[dict] = []
    detail_anomalies: list[str] = []
    to_fetch = detail_pairs[:MAX_DETAILS]
    print(f"\n[details] fetching {len(to_fetch)} detail pages (cap={MAX_DETAILS}) ...")

    for idx, (job_id, url) in enumerate(to_fetch, 1):
        print(f"  {idx}/{len(to_fetch)}: {url}")
        try:
            resp = scraper.get(url, timeout=TIMEOUT_SECONDS)
        except Exception as exc:
            print(f"    ! error: {exc}")
            detail_anomalies.append(f"error:{url}")
            time.sleep(DELAY_SECONDS)
            continue

        if is_challenge(resp.status_code, resp.text):
            note = f"challenge:{resp.status_code}:{url}"
            print(f"    ! challenge/blocked (status={resp.status_code})")
            detail_anomalies.append(note)
            time.sleep(DELAY_SECONDS)
            continue

        if resp.status_code != 200:
            detail_anomalies.append(f"http{resp.status_code}:{url}")
            print(f"    ! HTTP {resp.status_code}")
            time.sleep(DELAY_SECONDS)
            continue

        rec = parse_detail(resp.text, job_id, url)
        records.append(rec)
        print(f"    title={rec['title'][:60]!r}  company={rec['company'][:30]!r}  tags={len(rec['tech_stack_candidate'])}")
        time.sleep(DELAY_SECONDS)

    # 5. write JSON sample
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[output] wrote {len(records)} records -> {OUTPUT_PATH}")

    # 6. verdict block
    ok_runs = sum(1 for r in runs if r["ok"])
    challenge_runs = sum(1 for r in runs if r["challenge"])
    latencies = [r["latency"] for r in runs]
    reliability_anomalies = [r["status"] for r in runs if not r["ok"]]

    n = len(records)
    f_external_id = sum(1 for r in records if r["external_id"]) if n else 0
    f_title = sum(1 for r in records if r["title"]) if n else 0
    f_company = sum(1 for r in records if r["company"]) if n else 0
    f_description = sum(1 for r in records if r["description"]) if n else 0
    f_tags = sum(1 for r in records if r["tech_stack_candidate"]) if n else 0

    listing_pages_crawled = min(MAX_PAGES, MAX_PAGES)  # we tried all pages

    print("\n" + "=" * 74)
    print("VERDICT")
    print("=" * 74)
    print(f"  bypass           : {ok_runs}/{RELIABILITY_RUNS} runs returned real HTML "
          f"({challenge_runs} challenge{'s' if challenge_runs != 1 else ''})")
    if latencies:
        print(f"  latency          : median={statistics.median(latencies):.2f}s  max={max(latencies):.2f}s")
    print(f"  collected        : {MAX_PAGES} listing page(s) crawled -> "
          f"{len(detail_pairs)} detail URLs found -> {n} records parsed")
    if n > 0:
        print(f"  field complete   : external_id={pct(f_external_id, n):.0f}%  "
              f"title={pct(f_title, n):.0f}%  company={pct(f_company, n):.0f}%  "
              f"description={pct(f_description, n):.0f}%  "
              f"tech_stack_candidate={pct(f_tags, n):.0f}%")
    else:
        print("  field complete   : N/A (no records parsed)")
    print(f"  reliability anomalies : {reliability_anomalies or 'none'}")
    print(f"  detail anomalies      : {detail_anomalies or 'none'}")

    bypass_ok = ok_runs >= (RELIABILITY_RUNS * 0.8)
    fields_ok = n > 0 and pct(f_title, n) >= 80 and pct(f_company, n) >= 80
    viable = bypass_ok and fields_ok

    if viable:
        verdict = (
            "FREE CLOUDSCRAPER PATH IS VIABLE — cleared Cloudflare reliably and "
            "yielded usable core fields. Schedule as daily crawler."
        )
    elif ok_runs == 0:
        verdict = (
            "CLOUDSCRAPER FAILED TO CLEAR CLOUDFLARE — all runs were blocked/challenged. "
            "Design must plan for the Scrapfly fallback."
        )
    elif not bypass_ok:
        verdict = (
            f"CLOUDSCRAPER UNRELIABLE — only {ok_runs}/{RELIABILITY_RUNS} bypass runs succeeded. "
            "Too flaky for a scheduled crawler; consider Scrapfly fallback."
        )
    else:
        verdict = (
            f"PARTIAL — bypass ok ({ok_runs}/{RELIABILITY_RUNS}) but field yield is low "
            f"({n} records, title={pct(f_title, n):.0f}%, company={pct(f_company, n):.0f}%). "
            "Review selectors or consider Scrapfly fallback."
        )

    print(f"\n  >> {verdict}")
    print("=" * 74)


if __name__ == "__main__":
    main()
