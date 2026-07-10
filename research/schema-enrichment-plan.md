# Schema Enrichment & Tech-Stack Plan — InternHunterAgent

> **Status:** Research / pre-design decision record (2026-07-09). Not an implementation plan.
> It captures four enrichment decisions taken while reviewing the `clean_jobs` schema for the
> first deploy: (1) how `tech_stack` should be populated **from the source and an external
> vocabulary instead of a hardcoded allowlist**, (2) **exposing `job_level`** to the agent,
> (3) adding a **truthful time column** (`listing_expires_on`) and (4) what to do about the
> permanently-`NULL` `posted_date`. It feeds `docs/Tickets.md` (the T0013 Pre-Deploy Refinement
> freeze and the T0014 Ingestion Deploy Readiness milestone) and should be read alongside
> [`data-ingestion-stage.md`](data-ingestion-stage.md) §5–§6, [`job-site-comparison.md`](job-site-comparison.md)
> §120–§123, [`pre-deploy-refinement-plan.md`](pre-deploy-refinement-plan.md) §1, and
> `docs/Known_Issues.md`. Evidence for source-field claims is the live VietnamWorks spike
> (`data-ingestion-stage.md §0.1`) and the captured sample in `experiments/`.

---

## 0. TL;DR — decisions (2026-07-09)

1. **`tech_stack` — extract against a *large external vocabulary*.** A 2026-07-09 audit (§2.2,
   n=112) showed the source tags are **noisy** — only 24/288 distinct tags are known techs, 85%
   are techniques/roles/soft-skills/VI-duplicates/messy-phrases — so "trust the tags + denylist"
   is the wrong model. Instead **keep an extract-against-vocabulary model but make the vocabulary
   large and technique-inclusive** (GitHub Linguist + devicon + a curated AI/Data skills seed,
   from a committed data file), **extract from both tags and description**, and **normalize
   casing/synonyms** (`PowerBI`→`Power BI`). Deterministic, no LLM, "many techs without
   hardcoding" via external lists. **Decoupled from the schema freeze and the goldens.**
2. **Expose `job_level` in v1** (before the T0013 freeze). It is already populated (VietnamWorks
   5-value taxonomy); hiding real data purely to satisfy golden C6 is backwards. Rewrite C6.
3. **Add `listing_expires_on` in v1** — map the source's real `expiredOn` date to a new,
   truthful column enabling "is this still open?" questions. A genuine schema addition (DDL +
   pipeline + fixture), heavier than #2. **✅ verified 2026-07-09: `expiredOn` is 100% present,
   ISO-8601, and 100% future-dated** — viable.
4. **`posted_date`: don't synthesize — add `created_on` from the source's stable `createdOn`.**
   A live probe (2026-07-09) found **`createdOn`** is a *stable* source creation date (§4.3), so a
   truthful `created_on` is populated in v1 **directly from it** — making "recently posted"
   answerable and **retiring golden C1**. **✅ User-approved 2026-07-09, gated on a stability
   re-check** (confirm `createdOn` doesn't reset on re-list before it ships; if it fails, the column
   is dropped and C1's refusal stands). The fully-owned `first_seen_at`/`last_seen_at` (needs
   accumulate-upsert) stays a **T0014** fallback for "recently *added to our corpus*." Never
   fabricate a date from prose or the churny `onlineOn`. `posted_date` itself stays NULL.

**Net v1 agent-visible schema after this pass: 13 → 16 columns** (add `job_level`,
`listing_expires_on`, `created_on`). Ticketed as **T0013.1–T0013.4** (enrichments) then
**T0013.5** (the freeze) — see §5.

---

## 1. Context — the collision with the schema freeze (now resolved by the enrichment tickets)

The freeze (`docs/Tickets.md` T0013.5, formerly T0013.1) would, as originally written, have frozen
the **current 13-column** agent schema with `job_level`/`posted_date` hidden. Three of the four
decisions here **change that frozen surface**, so they were sequenced as tickets T0013.1–T0013.4 to
land **before** the freeze rather than becoming a post-v1 re-calibration delta (the pattern already
used for `is_active`). The exception is `tech_stack`, which changes only *data quality*, not the
*contract* — it floats free of the freeze entirely.

| Enrichment | Schema change? | Touches goldens/fixture? | v1 (pre-freeze) or T0014 |
|---|---|---|---|
| `tech_stack` redesign | **No** (column exists) | No (goldens pin to the hand-built fixture) | **Standalone, anytime** |
| Expose `job_level` | Yes (un-hide, prompt-only) | Yes — **rewrite C6** | **v1, before freeze** |
| Add `listing_expires_on` | Yes (**new** DDL column + pipeline) | Yes — fixture gains the column | **v1, before freeze** |
| `first_seen_at`/`last_seen_at` recency | Yes (internal + lifecycle) | Later | **T0014** (needs accumulate-upsert) |
| Synthesize `posted_date` | — | — | **Never** |

---

## 2. `tech_stack` — from a hardcoded allowlist to source-tags + external vocabulary

### 2.1 Current state — we discard the source's own tags
`normalize/vietnamworks.py:70-76` fetches `skills[].skillName` (live-tested present on **~98%**
of postings, `data-ingestion-stage.md §0.1`) and passes it to `find_tech_stack`
(`transform.py:35`), which keeps a term **only if it appears in the ~70-entry `tech_dictionary`**
in `config/ingestion.yaml`. Consequence: a source-tagged skill outside our list —
`ETL`, `Machine Learning`, `Data Visualization`, `NLP`, `Rust`, `Ruby`, `Solidity`, … — is
**silently dropped**. The allowlist is the bottleneck and the "hardcoding" to remove.

### 2.2 Field audit (2026-07-09, live sample n=112) — the raw tags are noisy

Auditing the captured spike sample (`experiments/vietnamworks_ai_data_sample.json`, 112 AI/Data
postings; `tech_stack_candidate` = the deduped source `skills[]`) **overturns the "tags are
mostly real technologies" assumption** (`scripts/audit_fields.py`, run 2026-07-09):

- **505 tag instances, 288 distinct, ~4.5/posting, 98% of postings carry ≥1 tag.**
- **Only 24 of 288 distinct tags are exact hits** in the current 70-term `tech_dictionary`; 18
  more *contain* a known tech buried in a phrase; **246 (85%) contain no known tech at all.**
- The most frequent "unknown" tags are **high-value techniques, not junk**: `Data Analysis`
  (18), `Machine Learning` (15), `Business Intelligence` (8), `Deep Learning` (7), `ETL` (6),
  `Big Data` (6), `Data Warehouse` (5), plus `NLP`, `LLM`, `Data Visualization`, `A/B Testing`…
- Genuine noise to exclude: roles (`Data Engineer` ×5, `Data Analyst`), soft skills
  (`Analytical Skills` ×6, `Communication` ×5, `Problem-solving`, `Teamwork`, `Leadership`),
  and **32 distinct Vietnamese tags** duplicating English techniques (`Phân Tích Dữ Liệu` =
  Data Analysis).
- **Casing/format drift** in real techs: `PowerBI` (vs our `Power BI`), `Sql`, and techs buried
  in messy phrases — `"Data Visualization & Analysis (Power BI; SQL – basic; Python – basic)"`
  hides Power BI + SQL + Python.
- With the *current* dictionary, tags **alone** yield ≥1 tech for only **58%** of postings.

**Consequence — "trust the tags + denylist" is the wrong model.** With 85% of distinct tags
outside any tech vocabulary and dominated by techniques + VI duplicates + messy phrases, a
denylist would have to enumerate hundreds of noise terms. The data points the other way:
**extraction against a *large* vocabulary**, not tag-trusting.

### 2.3 Revised approach — large external vocabulary + extraction (deterministic, no LLM)

Keep the **extract-against-a-vocabulary** model, but fix the two things wrong with today's: the
vocabulary is **too small** (~70 terms) and **too narrow** (languages/frameworks only, no
techniques).

1. **Build a large canonical vocabulary from external sources**, loaded from a committed data
   file (not hand-typed): **GitHub Linguist** (languages), **devicon/simple-icons**
   (frameworks/tools/platforms), plus a **curated AI/Data skills seed** for the technique terms
   the audit shows dominate (`Machine Learning`, `Deep Learning`, `NLP`, `Computer Vision`,
   `ETL`, `Big Data`, `Data Warehouse`, `Data Lake`, `LLM`, `RAG`, `MLOps`, `Data Visualization`,
   `A/B Testing`, …). Hundreds of terms, maintained upstream, refreshable. *(Optional breadth:
   StackOverflow tags dump or ESCO/O*NET for canonical skill IDs.)*
2. **Extract vocabulary terms from BOTH the source tags and the description** (word-boundary,
   case-insensitive) — this recovers techs buried in messy phrases (`PowerBI`, the parenthetical
   above) that tag-trusting or exact-matching would miss.
3. **Normalize to canonical form** (`PowerBI`→`Power BI`, `Sql`→`SQL`, `node`→`Node.js`) via an
   alias map in the vocabulary file; optionally a small **VI→EN alias** set for the frequent
   Vietnamese technique tags.
4. **Denylist is now small/optional** — extraction emits *only* vocabulary terms, so roles and
   soft-skills are excluded *by omission*, not by a maintained blocklist. A short denylist only
   resolves genuine ambiguities (a tech name that is also a common English word).

This stays deterministic and LLM-free, removes the allowlist **size** bottleneck (the vocabulary
is external + refreshable, satisfying "many tech names without hardcoding"), and is the only
approach that captures the technique-dominated reality the audit found.

### 2.4 The definitional call — resolved by the audit: **include techniques**
`data-ingestion-stage.md §5` defined `tech_stack` narrowly (languages/frameworks/libraries/
platforms). The audit forces the wider definition: the **most frequent real tags are techniques**
(`Machine Learning`, `Data Analysis`, `Deep Learning`), and they are what users search
("machine learning jobs"). Excluding them would gut `tech_stack`. **Decision: `tech_stack` =
technologies *and* core AI/Data techniques/skills.** Record this in `data-ingestion-stage.md §5`.

### 2.5 Why this is safe to do now
It changes **production data quality only** — not the `clean_jobs` schema, not the API, and not
the eval goldens (which assert against the hand-engineered `internhunter_eval` fixture, whose
`tech_stack` values are fixed by hand). So it can ship as a **standalone ingestion-transform
ticket** independent of the T0013 freeze. Verify on a live pull that source tags materially
increase per-posting tech coverage vs today before/after.

---

### 2.6 External vocabulary sources — concrete (verified 2026-07-09)

The vocabulary that drives extraction (§2.3) is assembled from maintained open lists, vendored as
a committed snapshot and refreshed by a build script — never hand-typed inline:

| Source | License | Size | Data file / shape | Best for | Notes |
|---|---|---|---|---|---|
| **GitHub Linguist** | MIT | ~600 languages | `lib/linguist/languages.yml` — keyed by canonical name; per entry `type` (programming/markup/data), `aliases`, `extensions`, `color` | **Languages** + aliases | De-facto language list; filter to `type: programming`/`markup` |
| **Devicon** | MIT | 150+ | `devicon.json` — `name`, `altnames`, `tags`, `versions` | **Frameworks / tools / platforms** (dev-focused, clean) | Primary framework source; `tags` help classify |
| **Simple Icons** | **CC0-1.0** (public domain) | 3,400+ | `data/` + `slugs.md` — `title`, `slug`, aliases | Broad **product/brand** names | Broad but **noisy** (many non-dev brands) — use to *validate/normalize*, not as source-of-truth |
| **Curated technique seed** | ours (bounded) | ~50 | a committed YAML list | **AI/Data techniques** the audit showed dominate (ML, DL, NLP, CV, ETL, Big Data, Data Warehouse/Lake, LLM, RAG, MLOps, A/B Testing, Data Viz/Modeling/Mining, BI) | Neither Linguist nor the icon sets cover techniques; this layer is a *finite, slow-moving* set, so a small curated list is acceptable — it's the languages/frameworks that are unbounded |
| **ESCO / O*NET** (optional) | free / gov | large | CSV / RDF | Formal skills incl. digital, multilingual | Only if canonical skill IDs or a VI layer are wanted later — heavier |

**Assembly & use (deterministic, no LLM):**
1. A build script merges the sources into **one canonical vocabulary + alias→canonical map** (e.g.
   `config/tech_vocabulary.yaml` or `data/`), adding hand aliases for the drift the audit found
   (`PowerBI`→`Power BI`, `Sql`→`SQL`, `Node`→`Node.js`) and, optionally, a small VI→EN map
   (`Phân Tích Dữ Liệu`→`Data Analysis`).
2. At ingest, **extract** vocabulary terms from the source tags **and** the description
   (word-boundary, case-insensitive), emit **canonical** forms, dedup.
3. Refresh = re-run the build script (upstream lists are maintained), so the vocabulary scales
   without hand-editing — satisfying "many tech names without hardcoding."

**Licensing:** all permissive — MIT (Linguist, Devicon) needs only the license notice kept in the
vendored snapshot; Simple Icons is CC0 (no attribution). No blockers to vendoring a snapshot.

## 3. `job_level` — expose it (v1)

### 3.1 Current state — real data hidden to pass a test
`job_level` is **populated** in production and in the fixture (VietnamWorks 5-value taxonomy:
`Experienced (non-manager)`, `Manager`, `Fresher/Entry level`, `Intern/Student`,
`Director and above` — `normalize/vietnamworks.py:97`). It is omitted from `schema_context`
**only** so golden **C6** ("what seniority are the Data Engineer roles?" → "not available")
passes. That inverts the honesty goal: C6 is testing honesty about data that *does exist*.

> **Audit (2026-07-09, n=112, `scripts/audit_fields.py`):** `job_level` is **100% populated**,
> all clean **English** 5-value taxonomy — Experienced (non-manager) 89, Manager 11,
> Fresher/Entry level 8, Intern/Student 2, Director and above 2 — **zero NULLs, zero Vietnamese
> values**. The `jobLevel`/`jobLevelVI` VI-EN mixing risk raised earlier is **disproven** for the
> AI/Data corpus (`jobLevel` EN is always present). Clean and safe to expose.

### 3.2 Decision — expose, and repoint C6
- **Prompt-only change** (cheap — the column and data already exist): add `job_level` to
  `config/prompts.yaml` `schema_context`, the `system_prompt` "Available fields" line, and the
  `sql_generation` real-columns list (canonical values, matched with `ILIKE`).
- **Rewrite golden C6** from an "absent-field" honesty probe into a normal retrieval case
  ("which Data Engineer roles are senior?"). To preserve honesty coverage, move the "genuinely
  absent" probe onto an attribute that is *actually* absent (e.g. applicant count or application
  deadline — neither is a column).
- **Overlap note:** `is_internship` is derived from the `Intern/Student` level; keep both —
  `is_internship` is a convenience boolean, `job_level` is the full ladder.
- **Freeze-guard flip:** the T0013.5 guard (§ Tickets) must now assert `job_level` **present**
  and drop it from the hidden-column assertions (which then cover only `source`, `external_id`,
  `posted_date`, plus `remote`).

Seniority is a top-tier user filter; this is clean, populated, low-effort — it belongs in v1.

---

## 4. Time column — `listing_expires_on` (v1) and real recency (T0014)

### 4.1 Why `posted_date` is permanently NULL
`posted_date` is hardcoded `None` (`normalize/vietnamworks.py:99-121`). The source's three
timestamps (`job-site-comparison.md §122`) each mean something **other than** "first posted":
`onlineOn` **churns on every employer re-list** (a recency trap), `approvedOn` is an admin
approval time, `expiredOn` is a **future** expiry. So "which was posted most recently?" cannot be
answered from data — the agent must decline (golden C1). Synthesizing a date from `onlineOn` or
from title/description prose is exactly the fabrication C1 guards against.

### 4.2 v1 quick win — `listing_expires_on` (from `expiredOn`)
`expiredOn` is a **real, forward-looking** date the source already sends (used for
"drop expired" per `job-site-comparison.md §148`). Exposing it as `listing_expires_on` is
truthful and answers a genuinely useful question — *"is this still open / expiring soon?"* — with
no pretence of being a posting date. This is a **new column**, so heavier than §3:
- **DDL** (`scripts/init_db.sql`): add `listing_expires_on DATE` (nullable).
- **Pipeline**: `models.py` field; `normalize/vietnamworks.py` parses `expiredOn`
  (epoch/ISO → date); `clean_store.py` insert + on-conflict set.
- **Prompts**: add to `schema_context`/`system_prompt`/`sql_generation` with an honest
  description ("the source's stated listing-expiry date; may be missing").
- **Fixture/goldens**: `evals/fixtures/seed_eval_db.sql` gains the column (some future dates,
  some NULL); existing goldens are unaffected; optionally add a "still open?" golden.
- **✅ VERIFIED (2026-07-09, live probe n=75):** `expiredOn` is **100% present**, clean
  **ISO-8601 with tz** (`2026-07-30T23:59:59+07:00` → trivially parsed to `DATE`), and **100%
  future-dated** (postings expire ~15–22 days out; `durationDays` is a flat **30**). The earlier
  sparsity risk is **disproven** — `listing_expires_on` is **well-supported**. robots.txt permits
  the pull: the API host `ms.vietnamworks.com` has **no robots.txt** (404 = no restrictions) and
  `www.vietnamworks.com/robots.txt` disallows only profile/auth/apply/AJAX paths — **not
  `/job-search`, no blanket disallow**. (Evidence: `scripts/scrape_spike.py` now captures the
  timestamps; the probe is the two scratch scripts run this date.)

### 4.3 New finding (2026-07-09) — `createdOn` is a plausible *stable* posting date
The prior research (`job-site-comparison.md §122`) considered only `onlineOn`/`approvedOn`/
`expiredOn` and concluded no source field means "first posted." The live probe surfaced a field
those notes missed — **`createdOn`** (100% present, clean ISO) — and it behaves like a **stable
original-creation date**, unlike the churny `onlineOn`:
- `createdOn` spreads over **~2 months** (2026-05-12 … 07-10, 31 distinct days); only **2/75** are
  today. `onlineOn` clusters recent (14 distinct days, **11/75 today**).
- For **56/75 (75%)** postings `createdOn` is **older** than `onlineOn` (median 21 days, max 54) —
  `onlineOn` is a re-list of an older creation. Where equal (19/75) the post is simply fresh. A
  field that *churned* would always equal `onlineOn`, so `createdOn` appears **not to churn**.

**Implication:** a truthful **`created_on`** (or `posted_date`) column could be populated
**directly from `createdOn`** — a real recency signal, **in v1**, **without** the accumulate-upsert
/ ingestion-owned `first_seen_at` machinery (§4.4). It would also largely **answer golden C1**
(freshness becomes truthfully answerable) rather than forcing a refusal.

**Caveats before trusting it:** (1) temporal **stability** across daily re-fetches is not proven
by a single pull — the distribution strongly implies it, but confirm `createdOn` doesn't reset on
an employer edit/re-list; (2) it is VietnamWorks' *record-creation* time — describe it honestly
("created on VietnamWorks", not "the role opened"). **This is a new user decision** (see §5).
*(Aside: `numOfApplications` reads **0** for all search results — genuinely unanswerable from the
API, so it's a good replacement honesty probe for the retired C6.)*

### 4.4 The still-owned recency answer — ingestion-owned timestamps (T0014)
*(Lower priority if `createdOn` (§4.3) proves stable — that may cover v1 recency on its own.)*
For "recently added" honestly, add ingestion-owned `first_seen_at`/`last_seen_at` (internal
bookkeeping; a derived "new" flag could surface). This **requires accumulate-upsert** — today's
`TRUNCATE`-and-rebuild resets any owned timestamp to "this run" (`Known_Issues.md`;
`deployment-research-plan.md §4.2`). It is therefore **T0014**, bundled with `is_active` and the
lifecycle load. Do **not** attempt it in v1.

---

## 5. Sequencing & ticket implications

**Ticketed 2026-07-09 (user-approved).** The freeze — formerly T0013.1 — is **renumbered T0013.5**
and now freezes an **enriched 16-column** schema; four enrichment sub-tickets land first:

1. **T0013.1 — `tech_stack` redesign** (external-vocabulary extraction from tags + description +
   normalization, §2). *Standalone; no schema/golden change; can run in parallel or ship
   independently.*
2. **T0013.2 — expose `job_level`** — prompt-only + rewrite golden C6 (§3).
3. **T0013.3 — add `listing_expires_on`** — DDL + pipeline + prompts + fixture (§4.2).
4. **T0013.4 — add `created_on`** — same shape as #3, **gated on a stability re-check** of
   `createdOn`; retires golden C1 (§4.3). If the re-check fails, the column is dropped and C1 stands.
5. **T0013.5 — freeze** the resulting **16-column** contract, with the guard asserting
   `job_level`/`listing_expires_on`/`created_on` **present** and only `source`/`external_id`/
   `posted_date` hidden.

Deferred to **T0014** (unchanged): recency (`first_seen_at`/`last_seen_at`), `is_active`,
accumulate-upsert, Alembic. `posted_date` stays NULL and unreferenced — never synthesized.

> **Update 2026-07-09 (scope confirmed + ticketed):** the user **approved the 16-column schema
> change** — all four enrichments, including `created_on` (gated on the §4.3 stability re-check).
> `docs/Tickets.md` T0013 now carries **T0013.1–T0013.4** (enrichments) and **T0013.5** (the
> freeze, renumbered from the old T0013.1). Cross-refs updated in `docs/Known_Issues.md`,
> `docs/Repo_Current_State.md`, and `research/agent-behavior-question-bank.md`. The former "open
> follow-up" (T0013.1 still described the narrow 13-column freeze) is **resolved**.

---

## 6. Cross-references

- `research/data-ingestion-stage.md` §5 (tech_stack definition — this supersedes the allowlist
  default), §6 (schema width), §0.1 (source fields, live-tested).
- `research/job-site-comparison.md` §120–§123, §148 (VietnamWorks fields, `onlineOn`/`approvedOn`/
  `expiredOn` semantics, drop-expired).
- `research/pre-deploy-refinement-plan.md` §1 (the schema-freeze surfaces).
- `docs/Known_Issues.md` (`posted_date` intentionally absent; reliable-time-column design note).
- `docs/Tickets.md` T0013.1–T0013.4 (the four enrichments), T0013.5 (the 16-column freeze), T0014
  (ingestion lifecycle / `is_active`).
- `config/ingestion.yaml` (`tech_dictionary` → to be demoted to backfill), `config/prompts.yaml`
  (`schema_context`/`system_prompt`/`sql_generation` — the three enumeration sites).
- Code: `src/services/ingestion/normalize/vietnamworks.py`, `transform.py`, `clean_store.py`,
  `models.py`; `scripts/init_db.sql`; `evals/fixtures/seed_eval_db.sql`.
