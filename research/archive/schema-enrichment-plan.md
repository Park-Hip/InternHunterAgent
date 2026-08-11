# Schema Enrichment & Tech-Stack Plan: Decision Record (archived)

> Archived 2026-08-11. M13 shipped. Outcome owned by
> `docs/Schema_Contract.md` and D-010 through D-015.
> Preserved for the reasoning and rejected alternatives; not implementation guidance.

## Decisions taken

- D-010: Created-on is preserved, while posted date is never synthesized.
- D-011: Listing expiry comes from the truthful source expiry field.
- D-012: Job level is agent-visible in v1.
- D-013: Tech stack includes AI and data techniques as well as technologies.
- D-014: Tech stack uses an external vocabulary, not a hardcoded allowlist.
- D-015: V1 schema changes are decided before the schema freeze.

## 1. Context - the collision with the schema freeze (now resolved by the enrichment tickets)

The freeze would, as originally written, have frozen the **current 13-column** agent schema with
`job_level`/`posted_date` hidden.
Three of the four decisions here **change that frozen surface**, so they were sequenced as tickets
T0013.1-T0013.4 to land **before** the freeze rather than becoming a post-v1 re-calibration delta.
The exception is `tech_stack`, which changes only *data quality*, not the *contract*.

## 2. `tech_stack` - from a hardcoded allowlist to source-tags + external vocabulary

### 2.1 Current state - we discard the source's own tags

The source returns `skills[].skillName` for most postings and passes it to `find_tech_stack`.
The existing transform keeps a term only when it appears in the small `tech_dictionary`.
As a result, source-tagged skills such as `ETL`, `Machine Learning`, `Data Visualization`,
`NLP`, `Rust`, `Ruby`, and `Solidity` are silently dropped.
The allowlist is the bottleneck and the hardcoding to remove.

### 2.2 Field audit (2026-07-09, live sample n=112) - the raw tags are noisy

- **505 tag instances, 288 distinct, ~4.5/posting, 98% of postings carry at least one tag.**
- **Only 24 of 288 distinct tags are exact hits** in the current 70-term `tech_dictionary`.
  **246 (85%) contain no known tech at all.**
- The most frequent unknown tags are high-value techniques, not junk: `Data Analysis`,
  `Machine Learning`, `Business Intelligence`, `Deep Learning`, `ETL`, `Big Data`,
  `Data Warehouse`, `NLP`, `LLM`, `Data Visualization`, and `A/B Testing`.
- Genuine noise includes roles, soft skills, and Vietnamese tags duplicating English techniques.
- Casing and format drift occurs in real techs such as `PowerBI` versus `Power BI` and `Sql`.
- With the *current* dictionary, tags **alone** yield at least one tech for only **58%** of
  postings.

**Consequence - "trust the tags + denylist" is the wrong model.**
With 85% of distinct tags outside any tech vocabulary and dominated by techniques, Vietnamese
duplicates, and messy phrases, a denylist would have to enumerate hundreds of noise terms.
The data points the other way: **extraction against a *large* vocabulary**, not tag-trusting.

### 2.3 Revised approach - large external vocabulary + extraction (deterministic, no LLM)

Keep the **extract-against-a-vocabulary** model, but fix the two things wrong with today's: the
vocabulary is **too small** (~70 terms) and **too narrow** (languages/frameworks only, no
techniques).

1. **Build a large canonical vocabulary from external sources**, loaded from a committed data
   file (not hand-typed).
2. **Extract vocabulary terms from BOTH the source tags and the description**.
3. **Normalize to canonical form** via an alias map in the vocabulary file.
4. **Denylist is now small/optional** - extraction emits *only* vocabulary terms, so roles and
   soft-skills are excluded *by omission*, not by a maintained blocklist.

The approach remains deterministic and LLM-free.
It removes the allowlist size bottleneck while capturing the technique-dominated reality observed
in the field audit.

### 2.4 The definitional call - resolved by the audit: **include techniques**

The audit forces the wider definition: the **most frequent real tags are techniques**
(`Machine Learning`, `Data Analysis`, `Deep Learning`), and they are what users search.
Excluding them would gut `tech_stack`.
**Decision: `tech_stack` = technologies *and* core AI/Data techniques/skills.**

### 2.6 External vocabulary sources - concrete (verified 2026-07-09)

The vocabulary that drives extraction (section 2.3) is assembled from maintained open lists,
vendored as a committed snapshot and refreshed by a build script - never hand-typed inline.

| Source | Best for |
|---|---|
| **GitHub Linguist** | Languages and aliases |
| **Devicon** | Frameworks, tools, and platforms |
| **Curated technique seed** | AI/Data techniques the audit showed dominate |

The external lists are a committed snapshot and can be refreshed by a build script.
GitHub Linguist supplies language aliases, Devicon supplies framework and platform names, and a
small curated technique seed covers the AI and data skills absent from those lists.

At ingestion, the system extracts terms from source tags and the job description, emits canonical
forms, and deduplicates them.
Refreshing the vocabulary means rerunning the build script against maintained upstream lists.

## 3. `job_level` - expose it (v1)

`job_level` is **populated** in production and in the fixture.
It is omitted from `schema_context` **only** so golden **C6** passes.
That inverts the honesty goal: C6 is testing honesty about data that *does exist*.

> **Audit (2026-07-09, n=112):** `job_level` is **100% populated**, all clean **English**
> 5-value taxonomy, with **zero NULLs, zero Vietnamese values**.

The v1 change is prompt-only: add `job_level` to `schema_context`, the system prompt's available
fields, and the SQL-generation real-columns list.
The former absent-field golden moves to an attribute that is genuinely absent.

`is_internship` remains as a convenience boolean while `job_level` exposes the full ladder.
The freeze guard asserts that `job_level` is present rather than hidden.

### 3.2 Decision - expose, and repoint C6

The prompt adds `job_level` to the schema context, the available-fields line, and the SQL
generation column list.
The canonical values are matched with `ILIKE`.
The normal retrieval golden replaces the previous absent-field test, and the honesty test moves to
an attribute that is actually unavailable.
This preserves honesty coverage without hiding populated production data.

## 4. Time column - `listing_expires_on` (v1) and real recency (T0014)

### 4.1 Why `posted_date` is permanently NULL

The source timestamps each mean something other than a truthful first-posted date.
`onlineOn` churns when an employer re-lists, `approvedOn` is an administrative approval time, and
`expiredOn` is a future expiry.
The agent must decline a question about the most recently posted role rather than synthesize a
date from those fields or job-description prose.

### 4.2 v1 quick win - `listing_expires_on` (from `expiredOn`)

`expiredOn` is a **real, forward-looking** date the source already sends.
Exposing it as `listing_expires_on` is truthful and answers a genuinely useful question -
*"is this still open / expiring soon?"* - with no pretence of being a posting date.

**VERIFIED (2026-07-09, live probe n=75):** `expiredOn` is **100% present**, clean
**ISO-8601 with tz**, and **100% future-dated**.
The earlier sparsity risk is disproven - `listing_expires_on` is **well-supported**.

The column needs DDL, pipeline parsing, prompt documentation, and fixture support.
It must be described as the source's stated listing-expiry date, not as a posting date.

The source's `onlineOn` timestamp churns on employer re-listing, and `approvedOn` is an
administrative timestamp.
Neither is a truthful substitute for a first-posted date.

### 4.3 New finding (2026-07-09) - `createdOn` is a plausible *stable* posting date

The live probe surfaced **`createdOn`** (100% present, clean ISO) and it behaves like a **stable
original-creation date**, unlike the churny `onlineOn`.

**Caveats before trusting it:** temporal **stability** across daily re-fetches is not proven by a
single pull, and it is VietnamWorks' *record-creation* time - describe it honestly
("created on VietnamWorks", not "the role opened").

`createdOn` spans about two months in the sample and is older than `onlineOn` for most postings.
The stability re-check is the gate before treating it as a truthful v1 recency signal.

### 4.4 The still-owned recency answer - ingestion-owned timestamps (T0014)

For "recently added" honestly, the ingestion pipeline records `first_seen_at` and `last_seen_at`.
This requires accumulation semantics because truncating and rebuilding resets an owned timestamp
to the current run.
The work belongs with lifecycle loading rather than this schema-enrichment pass.

Ingestion-owned `first_seen_at` and `last_seen_at` remain the fallback answer for "recently
added" and require accumulate-upsert semantics.
They are not a substitute for a source-provided, stable creation date.

## 5. Sequencing & ticket implications

The freeze is **renumbered T0013.5** and now freezes an **enriched 16-column** schema;
four enrichment sub-tickets land first.

1. **T0013.1 - `tech_stack` redesign**.
2. **T0013.2 - expose `job_level`**.
3. **T0013.3 - add `listing_expires_on`**.
4. **T0013.4 - add `created_on`**, gated on a stability re-check of `createdOn`.
5. **T0013.5 - freeze** the resulting **16-column** contract.

The later ingestion work retains recency bookkeeping, `is_active`, accumulate-upsert, and
Alembic work outside this v1 enrichment sequence.
`posted_date` stays NULL and unreferenced - never synthesized.

The freeze follows the enrichment work so prompts, fixtures, schema, and evaluation data all
agree on the same agent-visible contract.
The later lifecycle columns remain hidden and do not reopen the frozen v1 prompt surface.

## Sources

- `research/job-site-comparison.md`.
- `research/archive/data-ingestion-stage.md`.
- Live VietnamWorks field audit, 2026-07-09.
