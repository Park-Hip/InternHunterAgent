# Data Ingestion Stage — Deep Research

> **Status:** Research / pre-design. This document gathers the external facts needed
> before authoring the ingestion **design doc** and **technical doc**. It does not
> commit an implementation. It feeds `Full_Design_Document.md` / a future
> `Tickets.md` entry.
>
> **Scope:** how InternHunterAgent should acquire *real* internship-posting data from
> **Vietnamese job boards** and transform it into the `clean_jobs` table the existing
> SQL skill already queries. Current state: `clean_jobs` holds **7 hand-written rows**
> (id, title, company, description, tech_stack) loaded from
> `scripts/init_clean_jobs.sql`. There is no acquisition, no `raw_jobs`, no transform.

---

## 0. Decision — source market: **Vietnamese job boards**

The target market is **Vietnam**, so the source set is scoped to Vietnamese boards:
**TopCV, ITviec, TopDev, VietnamWorks, and LinkedIn** (LinkedIn included for its
Vietnam-localized postings). Global ATS-API aggregators (Greenhouse/Lever/Ashby,
USAJobs, Adzuna) are **out of scope** — they cover US/global companies, not the
Vietnamese internship market.

Consequences of staying in the Vietnamese market:

- **A scraping approach is required.** None of these boards offers a clean public
  JSON API; all are rate-limited and most sit behind Cloudflare-style anti-bot. So a
  scraper (free `cloudscraper`-style library first, managed Scrapfly as fallback) is
  **in scope** — see §3.
- **Language.** Postings are predominantly **Vietnamese** (ITviec is bilingual). The
  agent's prompts/persona are English. This raises a cross-cutting "what language does
  the agent answer in?" decision — see §2.6.
- **`tech_stack` is partially helped by the IT-specific boards.** ITviec and TopDev
  tag postings with **real technologies** (the right kind of `tech_stack` value),
  while general boards (TopCV, VietnamWorks) tag mostly **roles/categories** that are
  *not* technologies and must be filtered out — see §5 for the corrected definition.

**Target refinement (data scope, decided 06/2026).** The dataset is narrowed to
**IT jobs focused on AI/Data roles** — AI Engineer, Data Scientist, Data/ML Engineer,
Data Analyst. **All seniority levels are collected** (not internship-only); internship
postings are merely **flagged** (`is_internship`). This refinement is what selected the
source and method in §0.1.

---

## 0.1. Experiment — VietnamWorks AI/Data IT jobs (RESULT: ✅ reliable & schedulable)

A spike (`scripts/scrape_spike.py`, run `uv run python scripts/scrape_spike.py`) tested
the simplest reliable path to the refined target (IT / AI-Data, all levels, interns
flagged).

**Source choice (evidence-based).** Probed live: **ITviec returns 403 Cloudflare** on a
plain GET and **TopDev exposes no JSON API** — both need a managed/anti-bot scraper.
**VietnamWorks exposes a public JSON search API** —
`POST https://ms.vietnamworks.com/job-search/v1.0/search` (no auth, `userId: 0`) — so it
is the most reliable path. (Its SSR HTML carries only ~5 promoted jobs; the API has the
real results. The old Algolia keys in §0 are dead.) ITviec/TopDev's purer IT-only tag
quality remains a *future* cloudscraper experiment, traded away here for reliability.

**Method — keyword recall + structured precision.** Keyword search alone is noisy (a
`data scientist` query surfaces Marketing/Sales roles). So: query the API with several
**AI/Data role keywords** for recall, then keep only results whose structured
**`jobFunction`** is IT/Telecom (`parentId 5`) and tag the dedicated
**"Data Engineer/Data Analyst/AI"** category (`child id 27`) as the focus set — precision
comes from data already on every job, not an undocumented filter field. One `httpx` POST
per page, realistic User-Agent, ~0.6 s politeness delay. No HTML parser, no Cloudflare
bypass, no browser, no auth. Internships are **flagged** (`is_internship` from
`jobLevelVI`/`jobLevel`), never filtered out.

**Measured results (06/2026, 8 AI/Data keywords × 2 pages):**

| Metric | Result |
|--------|--------|
| Reliability | **5/5 runs OK (100%)**, zero 403/429/anti-bot |
| Latency | **~0.43 s median** (max 0.47 s) |
| Yield | **251 unique → 145 IT (func 5) → 112 AI/Data (child 27)** |
| Levels | all collected; **2 internships flagged** in the AI/Data set |
| Core fields (title+company+url) | **100%** |
| Description present | **100%** · structured `skills` | **98%** |
| Schedulable | **YES** — headless, deterministic, polite; daily cron is ample |

**Fields per job** (one call, no detail-page fetch): `jobId` (stable `external_id`),
`jobTitle`, `companyName`, `jobDescription` + `jobRequirement` (HTML → trivially
stripped), `prettySalary`/`salaryMin`/`salaryMax`, `address` + `workingLocations`,
`jobLevel`/`jobLevelVI` (level + internship flag), `jobFunction` (the IT/AI-Data
taxonomy used for precision), `industries`, and a structured **`skills`** array.

**Implications for the design:**
- **VietnamWorks is the MVP's lead source**, scoped to the AI/Data IT category via the
  `jobFunction` taxonomy — relevant *and* reliable.
- **`skills` is a strong but unfinished `tech_stack`:** for AI/Data IT roles it is mostly
  real technologies (`Python, ETL, Airflow, SQL, Machine Learning, Deep Learning,
  Computer Vision, AWS, Power BI`) but still mixes in soft/role terms, so §5 holds —
  **filter `skills` to known technologies**; the spike already dedupes the array.
- **Caveats / pre-build actions:** undocumented site API (shape can change) — pin the
  request shape behind the adapter interface and treat parse failures as a reliability
  signal. Some role keywords miss (`MLOps` → 0 hits) — the keyword list is tunable.
  Check `ms.vietnamworks.com/robots.txt` and VietnamWorks' ToS for the API host before
  production use; the spike stored only factual, non-personal fields. A captured sample
  lives at `research/experiments/vietnamworks_ai_data_sample.json`.

---

## 1. Headline finding

The Vietnamese internship market is served by a small number of boards, none with a
friendly API:

- **IT-specialist boards — ITviec, TopDev** — the highest-value sources for this
  project. Both are IT-only and tag each posting with explicit **technology skills**
  (Python, Java, ReactJS, Node.js, AWS, …) that map almost directly onto a *correct*
  `clean_jobs.tech_stack`. ITviec is bilingual (EN/VI), easing description handling.
- **General boards — TopCV, VietnamWorks** — large volume and a first-class
  internship filter (Vietnamese: *thực tập sinh*), but their tags are mostly **job
  roles/categories** (frontend, tester, devops) rather than technologies, so
  `tech_stack` must be derived from the description (§5).
- **LinkedIn** — global board with Vietnam-localized internship postings; JS-heavy,
  the strongest anti-bot, and the heaviest ToS/legal baggage (the board behind the
  well-known scraping lawsuits). Keep as a **last-resort/optional** source.

**Recommendation:** lead with **ITviec + TopDev** for clean technology tags, use
**TopCV/VietnamWorks** for internship volume, treat **LinkedIn** as optional and
defer it unless a product reason forces it.

---

## 2. Source landscape (Vietnamese boards)

| Source | Domain | Focus | Internship filter | Tag quality for `tech_stack` | Anti-bot |
|--------|--------|-------|-------------------|------------------------------|----------|
| **ITviec** | itviec.com | IT only, bilingual EN/VI | keyword / level (intern, fresher) | **High — real technology skill tags** | Cloudflare |
| **TopDev** | topdev.vn | IT/developer | keyword / level | **High — technology skill tags** | Cloudflare-style |
| **TopCV** | topcv.vn | General (largest) | first-class (*thực tập sinh*) | Mixed — role tags, techs in description | Rate-limit + Cloudflare |
| **VietnamWorks** | vietnamworks.com | General (Navigos) | category / keyword | Low — categories, techs in description | Rate-limit + anti-bot |
| **LinkedIn** | linkedin.com | Global, VN-localized | internship filter | Low — skills are noisy/optional | Strongest; JS render required |

**Implication:** the acquisition layer is a **scraper behind a provider-agnostic
`JobSource` interface**, with one adapter per board. Start with the IT-specialist
boards because their technology tags make the transform nearly trivial; add general
boards for volume; gate LinkedIn behind an explicit decision.

### 2.5. TopCV (topcv.vn) — detailed findings

**Coverage & volume.** One of Vietnam's largest boards (~3M+ monthly views). Dedicated
internship listing **`https://www.topcv.vn/tim-viec-lam-internship`** with thousands of
postings (low thousands as of 06/2026 — verify live). Internship is a first-class
filter.

**URL structure (the crawl surface).**
- **Internship listing:** `https://www.topcv.vn/tim-viec-lam-internship` (paginated).
- **Location-filtered:** `…/tim-viec-lam-internship-tai-ha-noi-kl1` (location code
  suffix `-klN`).
- **Job detail page:** `https://www.topcv.vn/viec-lam/{title-slug}/{job-id}.html`
  → the stable **`{job-id}`** is the natural `external_id` for dedup/upsert.
- Crawl shape: paginate the listing → collect detail URLs/ids → fetch each detail
  page. (Mirrors existing open-source TopCV crawlers.)

**Fields available on a detail page.** Rich — more than today's `clean_jobs`: title,
company, salary, location/address, experience level, deadline, description,
requirements, benefits, **tags**, working hours, plus company info.

**Tags ≠ tech_stack.** TopCV's tags are mostly **roles/categories** (devops, frontend,
tester, game developer, .net developer, it intern). Only the genuinely
*technology* terms among them (nodejs, .net, php, flutter, embedded) belong in
`tech_stack`; the role labels must be dropped. So for TopCV, `tech_stack` is derived
primarily from the **description** via the keyword dictionary (§5), with tags used only
where they name a real technology.

**Anti-bot.** TopCV rate-limits and presents Cloudflare-style challenges; naive
`requests` is throttled/blocked. Use `cloudscraper` first, Scrapfly fallback (§3).

### 2.6. Language consideration (applies to all VN boards)

Postings are in **Vietnamese** (ITviec is bilingual; tech terms are usually English,
which helps tag/keyword extraction). `clean_jobs.description`, `title`, `company` will
hold Vietnamese text, while the agent's persona/prompts (`config/prompts.yaml`) are
English.

**Recommendation:** store source text **as-is** (no translation at ingest — keeps
ingestion deterministic and lossless); handle language at the agent/prompt layer.
Whether the agent answers in Vietnamese, English, or mirrors the user is a
**cross-cutting decision** that belongs in the agent/prompt design, not the ingestion
doc.

---

## 3. Scraper assessment

All five boards need a scraper; the question is free vs managed.

- **Free — `cloudscraper`** (handles Cloudflare JS checks, returns raw HTML for
  BeautifulSoup/lxml): zero cost, but brittle when a board changes protections, and
  insufficient for fully JS-rendered boards (LinkedIn).
- **Managed — Scrapfly / ScrapingBee** with `anti_bot`/render enabled: costs credits
  but absorbs maintenance and handles JS render + anti-bot.
  - **Pricing:** free tier 1,000 credits (no card, no expiry); paid from **$30/mo**.
  - **Credit model:** simple HTTP scrape = **1 credit**; **+5** for JS render or
    anti-bot; **+25** for residential IPs. Benchmarked (June 2026) ~**$4.13 per 1,000
    requests** at high success.
  - **⚠️ Cost unpredictability:** the anti-scraping system can *dynamically upgrade* a
    request mid-flight (1 credit → up to 25), so budget caps must assume worst-case.

**Recommendation:** keep the acquisition adapter **provider-agnostic**. Start with
free `cloudscraper` for the Cloudflare boards (ITviec, TopDev, TopCV, VietnamWorks);
reach for Scrapfly only where the free path is defeated, and for LinkedIn if it is ever
pursued — without touching the transform/load layers.

---

## 4. Legality / ToS

- **Respect `robots.txt` + crawl-delay, rate-limit politely, store only factual
  posting fields, avoid any candidate/personal data.** Scraping public, non-personal,
  factual job data is generally defensible; risk concentrates at personal data, auth
  bypass, copyrighted content, server overload, and contract/ToS terms.
- **Positive signal for TopCV:** an academic dataset (**VietJobs**, arXiv) was built
  from "publicly accessible pages of TopCV.vn where web scraping is **permitted under
  its robots.txt policy**."
- **LinkedIn** carries the heaviest ToS/legal exposure (the board behind the
  well-known scraping lawsuits) — a managed scraper solves the *technical* difficulty
  but not the *legal* one. This is why LinkedIn is optional/last-resort.
- **Action required before implementation:** fetch and read each board's
  `https://<board>/robots.txt` directly to confirm the listing/detail paths are
  allowed and note any crawl-delay. Treat the VietJobs citation as encouraging, not as
  a substitute for checking the live `robots.txt` at build time.

---

## 5. The `tech_stack` field — corrected definition (architectural fork)

**Correction:** `clean_jobs.tech_stack` is a list of **technologies** — programming
languages, frameworks, libraries, and platforms (e.g. **Python, C++, Java, Node.js,
PyTorch, LangChain, Hugging Face, React, AWS**). It is **not** a list of job
roles/categories (devops, tester, frontend developer, game developer). Any pipeline
that populates `tech_stack` must yield *technology* terms only; role/category labels
are discarded.

This makes the IT-specialist boards uniquely valuable and the general boards weaker:

| Source signal | What it gives | Fit for `tech_stack` |
|---------------|---------------|----------------------|
| **ITviec / TopDev skill tags** | Curated **technology** tags per posting | **Direct** — use the tags as-is (filter to known techs) |
| **TopCV / VietnamWorks tags** | Mostly **roles/categories**, occasional tech | Partial — keep only the tech terms, derive the rest |
| **Free-text description (all boards)** | Technologies mentioned in prose | Derived via extraction (below) |

**Extraction options for the description (and general-board backfill):**

| Approach | Quality | Cost / complexity | Notes |
|----------|---------|-------------------|-------|
| **Keyword dictionary** (curated list of technologies, matched against description/tags) | Decent for common, explicit stacks; misses synonyms/context | Trivial, deterministic, no LLM, no external calls | **Strong MVP default.** Fully testable. |
| **NER models** | Limited for this domain | Medium | Research: traditional NER "ineffective for the semantically diverse, context-rich" nature of postings. |
| **LLM extraction** | Best — handles context/synonyms | Adds an LLM call into ingestion (cost, latency, nondeterminism) | Architecturally significant; ingestion would gain an LLM dependency. |

**Decision this forces:** does the ingestion pipeline contain an LLM step, or stay
purely deterministic? Recommended path: **technology tags first (ITviec/TopDev), a
curated keyword dictionary for derivation/backfill, LLM extraction deferred** as a
future enhancement. Keeps ingestion deterministic and testable, aligned with the
project's "don't over-engineer the MVP" rule. Make this an explicit decision in the
design doc.

---

## 6. Schema implications (raw + clean)

Two-table design:

- **`raw_jobs`** — store the source payload **verbatim**: raw HTML/JSON, `source`
  (board name), `source_url`, `external_id`, `fetched_at`, `content_hash`. Never lossy.
- **`clean_jobs`** — the agent-facing table the SQL skill already uses.

**Field availability across the Vietnamese boards (what the transform can populate):**

| Field | ITviec / TopDev | TopCV / VietnamWorks | LinkedIn | Currently in `clean_jobs`? |
|-------|-----------------|----------------------|----------|----------------------------|
| title | ✅ | ✅ | ✅ | ✅ |
| company | ✅ | ✅ | ✅ | ✅ |
| description | ✅ (HTML → text cleanup) | ✅ | ✅ | ✅ |
| **tech_stack** | ✅ **from skill tags** | ⚠️ derived (§5) | ⚠️ derived | ✅ (curated today) |
| location | ✅ | ✅ | ✅ | ❌ |
| salary/comp | partial | ✅ (TopCV) | partial | ❌ |
| posted_date / deadline | ✅ | ✅ | ✅ | ❌ |
| source_url | ✅ | ✅ | ✅ | ❌ |

**Implication:** real data offers *more* than today's 4 columns. Which get promoted
into `clean_jobs` is a product/schema decision — but each new column the agent can see
also requires updating `config/prompts.yaml` (`schema_context`, the SQL-generation
prompt, and the available-fields gate). Keep the *raw* table rich; keep the *clean*
table only as wide as the agent is prompted to use.

---

## 7. Internship filtering, identity, dedup (secondary findings)

- **Internship filter by source:** TopCV/VietnamWorks have explicit internship
  categories (*thực tập sinh*); ITviec/TopDev filter by level/keyword
  (intern/fresher); LinkedIn has an internship filter. For boards without a hard
  filter, **filter client-side on title/keywords** ("intern", "thực tập", "internship").
- **Identity / dedup key:** each board exposes a stable per-posting id (TopCV
  `{job-id}`; others similar) → combine with `source` for a natural key. A
  `content_hash` fallback covers reposts and edits. **Upsert on `(source, external_id)`.**
  Cross-board duplicates (same role on TopCV *and* ITviec) are possible — the
  `content_hash` and company+title heuristics can flag them if needed.
- **Description cleanup:** descriptions are **HTML** — the transform needs an HTML→text
  step before storing in `clean_jobs.description`.

---

## 8. Decisions

### Now decidable (no further research needed)

1. **Source market = Vietnamese boards.** Lead with **ITviec + TopDev** (clean
   technology tags), add **TopCV/VietnamWorks** for internship volume, **LinkedIn
   optional/deferred**.
2. **`tech_stack` = technology tags from ITviec/TopDev first, keyword-dictionary
   derivation/backfill from the description** (§5) — deterministic, no LLM. Role labels
   are filtered out.
3. **Store source text as-is** (no translation at ingest).
4. **Batch, re-runnable script**; no scheduler in MVP.
5. **Acquisition path = provider-agnostic adapter**, start with free `cloudscraper`,
   Scrapfly as drop-in fallback where protections defeat it.
6. **Dedup/identity key = `(source, external_id)` + `content_hash`.**

### Still genuinely needing a decision (product/risk, not research)

- **Board set for v1:** ITviec + TopDev only, or also TopCV/VietnamWorks? Include
  LinkedIn at all?
- **Crawl scope:** all internships, or filter to IT/tech internships only? (The
  IT-specialist boards are already tech-scoped; general boards are not.)
- **Final `clean_jobs` schema width** — which fields get promoted (drives
  `config/prompts.yaml` changes). Recommend at least `source_url` + `posted_date`;
  defer salary/location unless wanted now.
- **Language behaviour** — does the agent answer in Vietnamese / English / mirror the
  user? (Cross-cutting; surfaces because the data is Vietnamese — §2.6.)
- **Free vs managed scraper to start** — `cloudscraper` (free, more maintenance) vs
  Scrapfly (paid, robust). Recommendation: start free, keep Scrapfly as fallback.
- **Sample-size cap** — how many internships to ingest per board for the MVP.

---

## 9. Recommended shape for the design doc

The ingestion stage the design doc should describe:

1. **Acquisition layer** (`src/services/ingestion/`, isolated from API/agent per
   CLAUDE.md): a provider-agnostic `JobSource` interface with **one adapter per board**
   (ITviec, TopDev, TopCV, …), using `cloudscraper` first and a Scrapfly fallback
   behind the same interface.
2. **Raw landing:** `raw_jobs` table, verbatim payload + provenance, upsert on
   `(source, external_id)`.
3. **Transform:** HTML→text on the description; **`tech_stack` from technology tags
   (ITviec/TopDev) with keyword-dictionary derivation/backfill, role labels filtered
   out**; store Vietnamese text as-is; normalize into `clean_jobs`.
4. **Loader:** idempotent batch CLI; re-running refreshes without duplicating.
5. **Config:** per-board URLs, pagination/sample cap, rate-limit/crawl-delay, the
   technology keyword dictionary, scraper-provider toggle — all in
   `config/settings.yaml`; models in `models.py` (per CLAUDE.md).
6. **Schema decision:** promote `source_url` + `posted_date`/`deadline` into
   `clean_jobs`; update `config/prompts.yaml` accordingly; decide on salary/location.
7. **Pre-build gate:** verify each board's `robots.txt` allows the target paths and
   honor any crawl-delay (§4).

This keeps the MVP deterministic, dependency-light, and within the existing layered
architecture. The one cross-cutting decision that escapes ingestion is **answer
language** (§2.6), which belongs in the agent/prompt design.

---

## 10. Sources

- **ITviec:** [itviec.com](https://itviec.com) · IT-focused, bilingual, technology skill tags.
- **TopDev:** [topdev.vn](https://topdev.vn) · IT/developer board, technology tags.
- **TopCV:** [Internship listing (tim-viec-lam-internship)](https://www.topcv.vn/tim-viec-lam-internship) · [VietJobs dataset from TopCV (arXiv)](https://arxiv.org/html/2603.05262) · [IT-Jobs-TopCV-Crawler (GitHub)](https://github.com/tienlonghungson/IT-Jobs-TopCV-Crawler) · [scraping-topcv → PostgreSQL (GitHub)](https://github.com/minkminkk/scraping-topcv) · [TopCV-scraper (GitHub)](https://github.com/Eakan-Git/TopCV-scraper)
- **VietnamWorks:** [vietnamworks.com](https://www.vietnamworks.com) · general board (Navigos Group).
- **LinkedIn:** [linkedin.com/jobs](https://www.linkedin.com/jobs) · global, VN-localized; heaviest anti-bot + ToS exposure.
- **Skill/tech extraction research:** [Skill-LLM: Repurposing General-Purpose LLMs for Skill Extraction (arXiv)](https://arxiv.org/html/2410.12052v1) · [Rethinking Skill Extraction using LLMs (arXiv)](https://arxiv.org/pdf/2402.03832)
- **Anti-bot / scraping:** [Cloudscraper Python guide (ScrapingBee)](https://www.scrapingbee.com/blog/how-to-scrape-websites-with-cloudscraper-python-example/) · [Scrapfly Pricing](https://scrapfly.io/pricing) · [Scrapfly Billing docs](https://scrapfly.io/docs/scrape-api/billing) · [Scrapfly jobs scraping use-case](https://scrapfly.io/use-case/jobs-web-scraping)
- **Vietnamese boards context:** [Python web scraping for VN job sites (GitHub)](https://github.com/tcd93/python-web-scraping/)
- **Legality:** [Is Web Scraping Legal in 2026? (Browserless)](https://www.browserless.io/blog/is-web-scraping-legal) · [robots.txt Scraping Compliance (PromptCloud)](https://www.promptcloud.com/blog/robots-txt-scraping-compliance-guide/)
