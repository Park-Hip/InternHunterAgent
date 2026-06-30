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
| [`deepeval-sql-agent-eval-planning.md`](deepeval-sql-agent-eval-planning.md) | Planner research for evaluating the LangChain SQL agent with DeepEval. (Eval stage was deferred — see git history; kept as reference.) |
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
