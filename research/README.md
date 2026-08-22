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
| [Honesty enforcement design](honesty-enforcement-design.md) | M24's unimplemented design for keeping generated job-search answers faithful to available evidence. |
| [Grader correctness plan](grader-correctness-plan.md) | Why the deterministic grader disagreed with a human read on 10 of 18 turns at the M24 gate, the five decisions taken from it, and the three tickets that correct it before the Vietnamese milestone. |
| [DeepSeek as an agent provider](deepseek-provider-evaluation.md) | Feasibility evidence for swapping `agent.provider` from Groq to DeepSeek: pricing, the thinking-mode tool-calling landmines, the file-level change surface, and the spike that must pass first. |
| [The agentic workflow](agentic-workflow.md) | How work moves through this repository when agents do it: the pipeline as built, six measured bottlenecks, what the throughput and CI numbers say, and which parts to fix, automate, or encode as a skill. |
| [Workflow simplification](workflow-simplification.md) | How large the documentation system has grown against the product it documents, which lint checks are load-bearing and which are ceremony, and the sequenced prune that halves the live linted surface from 18,593 lines to about 9,350 without giving up a coordination guarantee. |
| [Production readiness plan](production-readiness-plan.md) | Design record feeding M27 serving reliability, M28 operational telemetry and the quality gate, and M29 the production evaluation loop; sequences around the M24 honesty design rather than restating it. |
| [Langfuse observability gaps](langfuse-observability-gaps.md) | Thirteen findings on what the Langfuse integration does not yet use: why streamed turns record no token usage or cost, why prompts are neither registered nor linked, the environment-and-tag taxonomy that separates eval traffic from production, and a sequenced remediation with the decisions it needs first. |
| [Evaluation readiness and Langfuse evaluators](eval-readiness-and-langfuse-evaluators.md) | Whether the instrument is ready for a full DeepSeek Vietnamese capture: five blockers found by running it, why execution accuracy fails correct answers, what an eval run does and does not send to Langfuse, and whether Langfuse's own evaluators should join or replace the DeepEval judge. |
| [The evaluation driver after DeepSeek](eval-driver-post-deepseek.md) | Which of the driver's mechanics were built for the Groq free-tier ceiling that D-045 removed: why pacing stays, why halting on a 429 is now wrong, and the measurement showing the bottleneck moved from capture to the throttled judge. |
| [Demo UI trust slice](demo-ui-trust-slice.md) | Which parts of the external `demo_UI/` report to adopt for the next demo UI pass: where its multi-source model diverges from this text-to-SQL agent, the seven adopted items, the four rejected, and the four open questions the pass needs answered first. |
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
