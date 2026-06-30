# Prompt — Fill the Deployment Research Plan (findings only)

Paste the text below to an agent with web access. It researches and fills the **Findings**
in `research/deployment-research-plan.md` while leaving every **Decision** for the human.

---

You are completing the research in `research/deployment-research-plan.md`. Read that file
and `research/README.md` first; also skim `research/data-ingestion-stage.md` and
`research/job-site-comparison.md` for context they reference.

## Your job
For **each numbered section (§1–§11)**, run the web searches listed under "Research / web
searches", then **write the `Findings:` content** with what you learn. That is the only
thing you fill.

## Hard rules
1. **Fill `Findings:` ONLY. Never write into a `Decision:` (or `Decision (...)`) line —
   leave every Decision blank exactly as-is.** The human makes the calls; you supply the
   evidence. Likewise leave §12 Synthesis and the §0 subjective placeholders
   (e.g. expected traffic) blank — they depend on decisions you are not making.
2. **Do not change the document's structure** — no new/removed/renamed sections, headings,
   or the order of anything. Only replace the `_____` after `Findings:` (and the
   "Findings: _(table: ...)_" hints) with real content.
3. **Current facts only.** The month is June 2026 — prefer 2026 sources. Free tiers change
   often; if a source is older than ~12 months, note the date and flag it as possibly
   stale rather than stating it as current truth.
4. **Evidence over assumption.** Every quantitative claim (free-tier limit, price, cold-
   start, storage cap) must trace to a source. Add a short `Sources:` list of markdown
   links at the end of each section's Findings. If you cannot verify a number, write
   "unverified — needs manual check" rather than guessing.
5. **Honor the standing constraint:** cost must be **free or minimal**. In each section,
   call out the binding free-tier limit and anything that risks a recurring bill.
6. **Answer for all three workloads** where relevant — the web API, the Postgres DB, and
   the scheduled ingestion cron (the doc's §0 framing). Don't answer only for the API.
7. **Stay in the doc.** Do not create new files, write code, add dependencies, or start
   implementing a deploy. This is research-fill only.
8. **Be concise and comparative.** Prefer small comparison tables (option · free limits ·
   caveat) over prose. Match the terse, table-first style already in the research docs.

## Where partial work already exists
§3 (Postgres) and §4 (cron) note prior findings (Neon's no-pause edge; GitHub Actions
~$0.002/min, UTC-only, 60-day idle disable). **Verify these against current sources** and
expand them — do not just copy the hint.

## When done
End with a brief summary (outside the file, in your reply) of: which sections you filled,
any numbers you could not verify, and which Decisions are now ready for the human to make.
Do not make those decisions.
