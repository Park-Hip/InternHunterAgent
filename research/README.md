# `research/` - Pre-Design Research

> **Eviction:** A live research record leaves when its decision is harvested into the decision log
> or its open question is retired.

This folder holds live research and pre-design evidence for work that has not yet shipped.
Read the relevant record before designing, planning, or implementing a covered stage.

Durable choices harvested from completed research belong in the
[Decision Log](../docs/Decision_Log.md).
Completed research is historical evidence, not current implementation guidance, and lives in
[archive](archive/).

## Live research documents

| Document | Purpose |
|---|---|
| [Evaluation and prompt-refinement strategy](evaluation-strategy.md) | How agent behavior is measured and prompts are refined: failure taxonomy, the production evaluation loop and our phased roadmap onto it, release bars, and the consolidation map for every evaluation record. |
| [v1 release readiness plan](v1-release-readiness-plan.md) | Defines the remaining release path, blockers, and maintainer decisions for the M20-M23 sequence. |
| [Documentation hygiene and system plan](docs-hygiene-and-system-plan.md) | Evidence and decisions behind M22 documentation hygiene, including the Fact Ledger and enforcement model. |
| [Documentation prune and structure plan](docs-prune-and-structure-plan.md) | Measured file-level prune and per-file restructuring plan for M22 phase 2 (T0022.10-.14). |
| [Prompt refinement methods](prompt-refinement-methods.md) | How production teams refine prompts, the tradeoffs of prompt length and instruction count, and the decision on where the `behavior_glossary` belongs. |
| [Honesty enforcement design](honesty-enforcement-design.md) | Unimplemented design for keeping generated job-search answers faithful to available evidence. |
| [Evaluation cost and rate limits](eval-cost-and-rate-limits.md) | Current quota and cost analysis for the Groq serving path and Gemini evaluation judge. |
| [Job-site comparison](job-site-comparison.md) | Source-market scorecard. VietnamWorks is decided; competing sources remain candidates for future spikes. |

## Evidence captures

The dated prompts, robots records, and response samples in [experiments](experiments/) preserve
the evidence behind research conclusions.
They are not implementation instructions.

## Conventions

- Each research document opens with a status banner that states what it feeds.
- Claims about external services name the live test or evidence that supports them.
- Spikes remain throwaway scripts until their configuration is promoted to `config/settings.yaml`.
- Update a live record when its finding changes instead of creating a competing version.
