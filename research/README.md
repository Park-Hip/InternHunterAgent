# Research Map

This is the index for InternHunterAgent's `research/` folder — pre-design research and
decision records, not implementation. Each document answers one question and gathers the
external facts, experiments, and trade-offs needed *before* a stage is designed, feeding
`docs/Full_Design_Document.md`, `docs/MVP_Technical_Design.md`, and `docs/Tickets.md`.
Nothing here is a commitment to build; it is the evidence behind the decisions the design
docs and tickets then formalize.

**Read the relevant document before designing, planning, or implementing any stage it
covers** — it captures decisions, live-tested facts, and dead-ends already ruled out, so
work is not re-derived or repeated.

## Where to find what

| Concern | Document | Status |
|---|---|---|
| Which Vietnamese job board(s) to scrape, and how | [`job-site-comparison.md`](job-site-comparison.md) | **Live-tested scorecard — current source of truth** for board choice |
| Broader ingestion architecture (raw/clean schema, scraper tooling, legality/ToS, dedup) | [`data-ingestion-stage.md`](data-ingestion-stage.md) | Decided; its own board-ranking sections are superseded by `job-site-comparison.md` (see the pointer notes in §1–§2) |
| What columns `clean_jobs` exposes to the agent, and why (`tech_stack`, `job_level`, `listing_expires_on`, `created_on`) | [`schema-enrichment-plan.md`](schema-enrichment-plan.md) | Decided (2026-07-09) — supersedes `data-ingestion-stage.md §5`'s `tech_stack` allowlist |
| How to architect DeepEval scoring for the SQL agent (layers, metrics, judge, topology) | [`deepeval-sql-agent-eval-planning.md`](deepeval-sql-agent-eval-planning.md) | Generic planner (§1–§10) + InternHunter-grounded (§11); §11.3/§11.4/§11.6 carry update notes where the shipped stack diverged |
| Judge/agent token cost and rate-limit budget for one eval-harness run | [`eval-cost-and-rate-limits.md`](eval-cost-and-rate-limits.md) | Measured snapshot (2026-07-07) — current source of truth for judge cost/RPD |
| What behavior the agent *should* have, scenario by scenario, feeding prompt-v2 | [`agent-behavior-question-bank.md`](agent-behavior-question-bank.md) | Catalog — `[Core]`/`[High]` tiers populated, `[Secondary]` open |
| Sequencing: freeze schema/metrics → baseline → prompt-tune → deploy-harden | [`pre-deploy-refinement-plan.md`](pre-deploy-refinement-plan.md) | Synthesis / roadmap — ties the ingestion and eval threads together |
| Where the API, DB, cron, and tracing should be hosted (cost, topology) | [`deployment-research-plan.md`](deployment-research-plan.md) | Skeleton — findings filled per section, final "Decision:" lines still blank |
| Captured spike outputs (raw samples backing the findings above) | [`experiments/`](experiments/) | Evidence, not prose |

## How the threads connect

Research here isn't layered by permanence the way `docs/` is (product → constitution →
blueprint) — it's organized by **investigation thread**, each one feeding a later
synthesis or decision doc:

- **Ingestion thread:** `data-ingestion-stage.md` (architecture) → `job-site-comparison.md`
  (which board, live-tested) → `schema-enrichment-plan.md` (what columns land in
  `clean_jobs`).
- **Eval thread:** `deepeval-sql-agent-eval-planning.md` (how to architect scoring) →
  `eval-cost-and-rate-limits.md` (what it costs to actually run) →
  `agent-behavior-question-bank.md` (what "correct" means, scenario by scenario).
- **Deploy thread:** `deployment-research-plan.md` — mostly independent of the other two;
  relevant once the eval baseline is trusted.
- **Synthesis:** `pre-deploy-refinement-plan.md` sits above both the ingestion and eval
  threads and sequences them into one pre-deploy path.

## The rule that keeps these separate

A research doc is a **point-in-time investigation**, not a living owner of a topic the way
a `docs/` file is. That means two things:

- **A later finding doesn't get silently folded into an earlier doc.** When a finding
  changes, the doc making the new claim should carry a dated `> **Update — superseded
  (see X)**` note, and the older doc gets a matching pointer back — never a silent rewrite
  that erases the "why we used to think X" trail. (See `data-ingestion-stage.md §1–§2` and
  `deepeval-sql-agent-eval-planning.md §11.3/§11.4/§11.6` for the pattern.)
- **Evidence over assumption.** Claims about external sites/services are **live-tested**
  (HTTP status, latency, field shape, measured cost) and the test is named, not assumed.
  Spikes are throwaway — experiment scripts live in `scripts/` (e.g. `scrape_spike.py`);
  their constants graduate to `config/settings.yaml` only if/when the spike becomes a real
  adapter. Captured samples go in `experiments/`.

## Suggested reading order

1. **`data-ingestion-stage.md`** — why the Vietnamese market, and the overall ingestion
   shape (raw/clean tables, scraper approach).
2. **`job-site-comparison.md`** — which board(s), backed by live tests.
3. **`schema-enrichment-plan.md`** — what that source data means for the `clean_jobs`
   columns the agent can see.
4. **`deepeval-sql-agent-eval-planning.md`** — how the agent is evaluated.
5. **`eval-cost-and-rate-limits.md`** — the budget constraints on actually running it.
6. **`agent-behavior-question-bank.md`** — the behavior catalog eval scores against.
7. **`pre-deploy-refinement-plan.md`** — the sequencing that ties 1–6 together before deploy.
8. **`deployment-research-plan.md`** — hosting/infra, read alongside or after 7.
