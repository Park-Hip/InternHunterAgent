# Prompt — TopDev scraping spike (discovery + measurement)

> **What this is:** a self-contained instruction for a coding agent to (1) **discover how
> TopDev is reachable at all** and (2) build a *throwaway measurement spike* that tests
> whether the free path can acquire real **AI/Data IT** job data from **TopDev
> (`topdev.vn`)**. It is the IT-board counterpart to the existing VietnamWorks JSON-API
> spike (`scripts/scrape_spike.py`), the TopCV spike (`scripts/scrape_topcv_spike.py`),
> and the ITviec spike (`scripts/scrape_itviec_spike.py`). Background:
> `research/archive/data-ingestion-stage.md` (TopDev noted at §0.1 lines 53/57/132 — *"exposes no
> JSON API", "Cloudflare-style", "technology skill tags"*) and the running comparison
> `research/job-site-comparison.md` (Candidate 3 — TopDev, currently a stub).
>
> **Why TopDev is different from the earlier spikes:** for TopCV and ITviec the access
> method was known up front (`cloudscraper` over SSR HTML). For **TopDev the access method
> itself is unknown** — it may expose a hidden JSON/GraphQL API the page calls, or be
> server-rendered HTML, or be a JS-rendered SPA whose listing cards are absent from static
> HTML (as ITviec's `/it-jobs/<skill>` category pages turned out to be). So this spike has
> an explicit **Phase 0 discovery** step before any measurement.
>
> **Copy everything below the line into the agent.**

---

## Task

First **discover TopDev's reachable data path**, then write a throwaway scraping spike at
**`scripts/scrape_topdev_spike.py`** that measures whether the free path (plain
`requests`/`httpx` → falling back to `cloudscraper`, **never** a paid scraper) can reliably
get real **AI/Data IT** job data from TopDev and extract usable fields. This is a *spike*,
**not** a production adapter: no database, no app wiring, no `JobSource` interface, no
config — constants live at the top of the file, exactly like the existing spikes. Read
`scripts/scrape_itviec_spike.py` and `scripts/scrape_topcv_spike.py` first and **mirror
their structure, tone, docstring style, robots.txt gate, reliability harness, and
VERDICT-block format**.

Run command must be: `uv run python scripts/scrape_topdev_spike.py`

## Context you must respect (from the research docs)

- **Source:** TopDev (`topdev.vn`) — an **IT/developer-only** board. Expected upside
  (same as ITviec): postings tagged with **real technologies**, so `tech_stack` can be
  taken close to as-is. Expected friction: **no public JSON API was found in prior
  research** and the site is behind **Cloudflare-style anti-bot**, so the free path likely
  needs `cloudscraper` (Scrapfly is the paid fallback, **out of scope here**).
- **Project focus:** IT jobs centered on **AI/Data** roles (AI Engineer, Data Scientist,
  Data/ML Engineer, Data Analyst), **all seniority levels**, internships only *flagged*.
  The spike must scope to AI/Data, not scrape the whole board.
- **`external_id`:** find the stable per-job id (likely embedded in the detail URL or an
  API record) and use it as `external_id` for dedup — mirror how the other spikes do it.
- **`tech_stack` caveat:** keep the raw technology tags as `tech_stack_candidate`; do **not**
  build a tech filter here. If TopDev (like ITviec) separates technology tags from
  role/category labels, capture them in **separate fields** and note it — that separation
  is exactly what makes a board valuable for `tech_stack`.
- **Legality:** before fetching detail pages, **GET `https://topdev.vn/robots.txt`**, print
  it, and confirm the listing/detail/API paths are allowed; honor any crawl-delay. Be
  polite (realistic UA, delay between requests, hard page/detail caps). Store only factual
  posting fields — no personal/candidate data. Never solve/transmit a CAPTCHA.

## Phase 0 — discovery (do this FIRST, in throwaway scratchpad probes)

Do **not** commit Phase-0 probe scripts; keep them in the session scratchpad. The goal is
to answer five questions and write the answers as constants into the real spike.

1. **Anti-bot floor.** Try a plain `httpx.get("https://topdev.vn/...")`. Does it 200, or
   403/Cloudflare-challenge? If blocked, retry with `cloudscraper.create_scraper(...)`
   (realistic Chrome profile). Record which client is the minimum that works.
2. **Access method — is there a hidden JSON/GraphQL API?** This is the highest-value
   question (a JSON API would make TopDev as clean as VietnamWorks). Investigate:
   - Fetch a listing page and **grep the HTML/JS for API endpoints** — look for
     `api.topdev.vn`, `/api/`, `graphql`, `/jobs?`, `__NEXT_DATA__` /
     `application/json` script blobs, or a Next.js/Nuxt data payload embedded in the page.
   - If you find an embedded JSON blob (e.g. `__NEXT_DATA__`), it often already contains
     the listing records — prefer that over HTML scraping.
   - If you find an XHR/JSON endpoint, test it directly (note required headers/params).
   - **If a JSON API exists and is reachable, use it** (record the URL + payload shape).
     **If not, confirm SSR vs JS-rendered HTML** (is the job data in the static HTML, or
     only injected by JS? — check whether detail links/cards appear in `resp.text`).
3. **AI/Data scoping surface.** Find how to narrow to AI/Data IT roles. Probe candidates:
   a curated category/segment (like ITviec's `/segments/viec-lam-ai-data`), a
   keyword/skill URL (e.g. `…/viec-lam-it/python`, `…/ai`, `…/data`), or an API filter
   param. Pick the surface that yields **on-target AI/Data jobs with the least noise**.
4. **Detail-record shape.** Identify the detail URL (or API record) and the **stable
   `external_id`** (trailing numeric id in the slug, a `jobId` field, etc.). Confirm the
   crawl shape: listing/API → collect ids/urls → fetch each detail (or read inline).
5. **Field locations.** On a real AI/Data detail record, locate: `title`, `company`,
   `tech_stack_candidate` (technology tags), and ideally `salary`, `location`, `deadline`,
   `description`, plus any role/category labels kept separate from tech tags. Note the
   exact selectors / JSON paths so the spike's parser isn't guesswork.

Write a 4–6 line **Phase-0 findings note** (access method chosen, scoping surface,
detail/id shape, tag location, anti-bot floor) into your report and into the spike's module
docstring, so the next reader knows *why* the spike is built the way it is.

## What the spike must measure (two questions)

1. **Acquisition success + reliability.** Does the chosen path return **real AI/Data job
   data** (200 / valid JSON) rather than a **403 / Cloudflare challenge / empty JS shell**?
   Is it **stable across repeated runs**? Reuse the reliability harness from the other
   spikes: repeat one listing/API fetch `RELIABILITY_RUNS` times, record status + latency,
   and classify a run OK only if it returns real records (not a challenge/empty page).
   Detect challenge pages (`cf-challenge`, `Just a moment`, `cf_chl`, status 403/503/429)
   even when the status looks like 200.
2. **Field yield & quality.** From a small sample of detail records, what fraction yield
   the core fields? Report completeness for: `external_id`, `title`, `company`,
   `description`, and `tech_stack_candidate` (raw technology tags). If tech tags are
   separated from role labels, report tags/job and a sample of the tech vocabulary (mirror
   the ITviec spike's `tech tags/job` + `tech vocabulary` verdict lines).

## Method (mirror the existing spikes)

1. Put the Phase-0 answers into top-of-file constants (listing/API URL, scoping surface,
   detail/id regex or JSON path, the minimum working client). Add any missing dep via
   `uv add` (`cloudscraper`, `beautifulsoup4`, `lxml` are already in the project from the
   TopCV/ITviec spikes — reuse them; only `uv add` something genuinely new).
2. Fetch + print `robots.txt`; gate the run on the target paths being allowed.
3. **Reliability harness:** fetch the listing/API `RELIABILITY_RUNS` times, classifying each
   OK only if it returns real AI/Data records. Print status/latency/ok per run.
4. **Collect:** read the AI/Data listing/API (paginate up to `MAX_PAGES` only if needed),
   parse out detail ids/urls, dedup by `external_id`, then fetch up to `MAX_DETAILS` detail
   records with a politeness delay. (If the listing/API already carries full records inline,
   you may not need separate detail fetches — note that and still cap the sample.)
5. **Parse** each record into a normalized dict mirroring the other spikes' `normalize()` /
   `parse_detail()`: `external_id`, `title`, `company`, `location`, `salary`, `deadline`,
   `description` (HTML→text), `tech_stack_candidate` (raw tech tags), any separated
   `role/category` field, `url`, `source="topdev"`. If a selector/path misses, count it as
   a missing field rather than crashing.
6. **Write** the sample to `research/experiments/topdev_ai_data_sample.json` (UTF-8,
   `ensure_ascii=False` — Vietnamese text), next to the other samples.
7. Print a **VERDICT block** in the same style as the other spikes:
   - acquisition: `{ok}/{RELIABILITY_RUNS}` runs returned real data (challenge count)
   - latency: median / max
   - AI/Data scoping: surface → detail ids found → records parsed
   - field completeness: external_id / title / company / description / tech_stack (each %)
   - tech tags/job + a sample tech vocabulary (if tags are real technologies)
   - anomalies: any 403/503/429/challenge/empty-shell responses
   - **verdict line:** does the free path clear TopDev's anti-bot reliably and yield clean
     AI/Data tech tags, **or** does it need the Scrapfly fallback / is it JS-only?

## Suggested top-of-file parameters (tune after Phase 0)

```
BASE_URL          = "https://topdev.vn"
LISTING_OR_API    = "<set from Phase 0 — JSON API URL or AI/Data listing/segment URL>"
DETAIL_URL_RE     = r"<set from Phase 0 — capture group = external_id>"
SCOPING           = "<curated segment | keyword/skill url | api filter — note which>"
RELIABILITY_RUNS  = 5
MAX_PAGES         = 2      # only if pagination is needed (keep small)
MAX_DETAILS       = 15     # detail records to fetch (hard cap — be polite)
DELAY_SECONDS     = 2.0    # politeness gap (>= the ITviec/TopCV spikes; TopDev is anti-bot)
TIMEOUT_SECONDS   = 30
```

## Constraints

- **One committed file only** (`scripts/scrape_topdev_spike.py`) plus the JSON sample it
  writes and any `uv add` dependency change. Phase-0 probes stay in scratchpad (throwaway).
  Do not touch `src/`, `config/`, or any app layer — this spike stays outside the
  architecture (per `CLAUDE.md`).
- Handle Windows console UTF-8 like the existing spikes
  (`sys.stdout.reconfigure(encoding="utf-8")`).
- Never solve/transmit a CAPTCHA, never use real candidate data, never remove the
  politeness delay or the page/detail caps.
- **A negative result is a valid, useful result.** If the free path **cannot** clear
  TopDev's anti-bot, or TopDev is JS-only with no reachable API/SSR data, report it honestly
  in the verdict — it tells the design to fall back to Scrapfly (or drop TopDev from v1).
  **Do not** escalate to a headless browser or paid scraper to force a pass.

## Deliverable

1. `scripts/scrape_topdev_spike.py` (runnable via the command above).
2. `research/experiments/topdev_ai_data_sample.json` (the captured sample).
3. A short report: the **Phase-0 findings note** + the printed **VERDICT block** + a 3–5
   line plain-language conclusion on whether the **free path is viable for TopDev** (and how
   its tech-tag quality / AI-Data scoping compares to ITviec and VietnamWorks), or whether
   the design should plan for the Scrapfly fallback.
4. **Update `research/job-site-comparison.md`** — replace the *Candidate 3 — TopDev* stub
   with a full write-up at the same depth as the VietnamWorks / ITviec / TopCV sections
   (access method, anti-bot, AI/Data scoping, `tech_stack` quality, fields, measured
   results, strengths, weaknesses, evidence, net call) and update its scorecard row. If a
   broader finding emerges, append a sub-section to `research/archive/data-ingestion-stage.md`
   (mirroring §0.1) — but **ask before editing that doc**.
