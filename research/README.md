# `research/` — Pre-Design Research

This folder holds **research and pre-design notes**, not implementation. Each document
gathers the external facts, experiments, and trade-offs needed *before* a stage is
designed — feeding `docs/Full_Design_Document.md`, `docs/MVP_Technical_Design.md`, and
`docs/Tickets.md`. Nothing here is a commitment to build; it is the evidence behind the
decisions that the design docs and tickets then formalize.

**Read the relevant document here before designing, planning, or implementing any stage
it covers** — it captures decisions, live-tested facts, and dead-ends already ruled out,
so work is not re-derived or repeated.

## Contents

| Document | Purpose |
|---|---|
| [`data-ingestion-stage.md`](data-ingestion-stage.md) | Deep research on acquiring real Vietnamese AI/Data job postings into `clean_jobs`. Source-market decision, the VietnamWorks scraping experiment (✅ reliable & schedulable), and the corrected `tech_stack` definition. |
| [`job-site-comparison.md`](job-site-comparison.md) | Running scorecard comparing candidate job boards (VietnamWorks, ITviec, TopDev, TopCV, LinkedIn) on the same axes. VietnamWorks fully written; others are stubs to fill in when spiked. |
| [`deployment-research-plan.md`](deployment-research-plan.md) | **Skeleton** outline of what to research before deploying the app (hosting, Postgres, cron, secrets, Langfuse, CI/CD, cost ceiling). Sections list the web searches to run and the decision each drives — findings to be filled in. |
| [`deepeval-sql-agent-eval-planning.md`](deepeval-sql-agent-eval-planning.md) | Planner research for evaluating the agent with DeepEval — the grounding for the **T0011 Model Evaluation milestone** (now next). §§1–10 are the generic framework; **§11 is the InternHunter-specific, version-pinned grounding (2026-07-03)** — read §11 first. |
| [`pre-deploy-refinement-plan.md`](pre-deploy-refinement-plan.md) | Pre-first-deploy brainstorm: is the schema finalized, how to optimize prompts, which eval metrics/thresholds, and what else to harden. Sequences the schema freeze → v1 baseline → scenario/prompt v2 → deploy-harden path. |
| [`schema-enrichment-plan.md`](schema-enrichment-plan.md) | Decisions (2026-07-09) on enriching `clean_jobs` before the v1 freeze: `tech_stack` from source tags + external vocabulary (not a hardcoded allowlist), exposing `job_level`, adding a truthful `listing_expires_on`, and why `posted_date` recency is deferred to T0014. Supersedes the `tech_stack` allowlist default in `data-ingestion-stage.md §5`. |
| [`agent-behavior-question-bank.md`](agent-behavior-question-bank.md) | Skeleton for the scenario-driven prompt-optimization pass (feeds `pre-deploy-refinement-plan.md` §2). Enumerates ~48 **groups of behavioral questions** for the agent, to be populated later with scenarios, desired behavior, and prompt levers. |
| [`demo-ui-and-golive-plan.md`](demo-ui-and-golive-plan.md) | Pre-scoping for the **T0018 Clickable Demo** placeholder. Settles the UI-location fork (**same-origin static via FastAPI** — CORS stays unused), the browser SSE-over-POST mechanism (**`fetch()` + `ReadableStream`**, not GET-only `EventSource`), the "not too boring" UI shape + canned honesty prompts, and folds in the small go-live blockers (server-issued session IDs, data disclaimer, `SELECT 1` readiness probe, topology). Proposes a three-way sub-ticket split. Consumes the T0017 SSE contract; feeds T0018 tickets. Facts live-checked 2026-07-14. |
| [`streaming-implementation-plan.md`](streaming-implementation-plan.md) | How to implement the T0017 streaming phase. The three axes (runtime extraction / no-leak filter / transport), the repo-specific `generate_sql`-inside-a-tool leak subtlety, the two-gate filter, native FastAPI `EventSourceResponse` (0.136.3), and the `meta`/`token`/`done`/`error` event contract. All version/API facts live-checked 2026-07-13. Feeds T0017 sub-tickets and `MVP_Technical_Design.md` streaming sections. |
| [`v1-release-readiness-plan.md`](v1-release-readiness-plan.md) | Gap analysis (2026-07-19) between the live deploy and a **v1.0 release** of the existing MVP: bullet-by-bullet DoD audit (§4 bullet 6 refuted as "met"), release-blockers vs quality debt, the proposed **M20–M22** milestone shape (Release Integrity → Serving-Path Hardening & Honesty Baseline → v1.0 Release Cut), per-milestone post-1.0 deferrals, and the maintainer gates/decisions that block progress. |
| [`experiments/`](experiments/) | Captured outputs from research spikes (e.g. `vietnamworks_ai_data_sample.json`) — evidence for the findings above. |

## Conventions

- **Status banner.** Each doc opens with a `> **Status:**` blockquote stating it is
  research / pre-design and what it feeds.
- **Evidence over assumption.** Claims about external sites are **live-tested** (HTTP
  status, latency, field shape) and the test is named, not assumed.
- **Spikes are throwaway.** Experiment scripts live in `scripts/` (e.g.
  `scrape_spike.py`); their constants graduate to `config/settings.yaml` only if/when the
  spike becomes a real adapter. Captured samples go in `experiments/`.
- **Update, don't duplicate.** When a finding changes, update the existing doc rather than
  adding a parallel one; record decisions with their date.
