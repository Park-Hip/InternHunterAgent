# Documentation

> **Single source of truth for the documentation map.** If you are lost, start here.
> The map is organised by Diátaxis quadrant — tutorial, how-to guide, reference, explanation —
> not by folder. Each entry routes to exactly one canonical destination.

## Tutorials (learning-oriented)

Guided experiences for readers who are encountering the system for the first time.
They assume no prior knowledge and take the reader through a complete scenario.

| Doc | What you will be able to do |
|---|---|
| [Quickstart](../README.md) | Install, configure, load data, and run the agent locally |
| *(empty — add as needed)* | |

## How-to guides (task-oriented)

Step-by-step procedures for readers who know what they want to do and need to do it now.

| Doc | Task |
|---|---|
| [Operate the service](how-to/operate.md) | Deploy, configure, manage the database, run ingestion, handle incidents |
| [Evaluate agent behavior](how-to/evaluate.md) | Run, grade, freeze, and inspect evaluations |
| [Release gate](how-to/release-gate.md) | Invoke and interpret the live semantic release gate |
| [Latency observability](how-to/latency-observability.md) | Read stream latency metrics and percentile publication gate |
| [Cron activation runbook](how-to/cron-activation-runbook.md) | Manage the scheduled ingestion cron |

## Reference (information-oriented)

Factual descriptions of the system's parts — schemas, configuration, behaviour contracts.
Numbers here are sourced from machine-readable files, not restated as prose.

| Doc | Contents |
|---|---|
| [Configuration](reference/configuration.md) | Stack, dependencies, tunables, hosted services, quotas |
| [Schema](reference/schema.md) | Frozen agent-visible `clean_jobs` columns and evolution path |
| [Agent behaviour](reference/agent-behavior.md) | Frozen agent behaviour requirements and probe protocol |
| [Evaluation instrument](../evals/README.md) | Navigation hub: role routing, decision tree, quick commands, full file map |
| [Evaluation pipeline](../evals/pipeline.md) | Five-step pipeline, result-term table, step-by-step commands |
| [Deterministic grading](../evals/deterministic/index.md) | Four-kind cascade, tier precedence, coverage map, known weaknesses |
| [Calibration](../evals/calibration/index.md) | Corpus composition; thresholds; provenance |
| [Semantic judge](../evals/semantic/index.md) | DeepEval wrapper, provider arms, throttle, rubric |
| [Authoring scenarios](../evals/authoring/index.md) | Grammar, id pattern, assertions, execution comparisons |
| [Replay](../evals/replay/index.md) | Freeze→sanitize→replay contract; CI gate |
| [Tests](../evals/README.md#test-to-module-mapping) | Test-to-module mapping; offline vs live split |
| [Disagreements](../evals/disagreements/index.md) | Grader-vs-judge-vs-human workflow |
| [Operating manual](../evals/Operating_Manual.md) | Maintainer review rules, authority boundary, outcome interpretation |

## Explanation (understanding-oriented)

Context and reasoning for readers who want to understand why the system is the way it is.

| Doc | Contents |
|---|---|
| [Architecture](architecture.md) | Product scope, architecture, layer laws, serving design |
| [Decision records](decisions/README.md) | Durable decision rationale, one record per decision |
| [Streaming & SSE explained](explanation/streaming-sse.md) | How streaming chat works, from browser to LLM |
| [Research records](../research/README.md) | Investigation-only reports; evidence for decisions |

## Role-based routing

| Role | Start here |
|---|---|
| **New reader** | [README.md](../README.md) → [Tutorials](#tutorials) |
| **Operator** | [Operate how-to](how-to/operate.md) → [Evaluation pipeline](../evals/pipeline.md) |
| **Maintainer** | [Operating manual](../evals/Operating_Manual.md) → [Calibration](../evals/calibration/index.md) |
| **Contributor** | [Authoring scenarios](../evals/authoring/index.md) → [How-to: evaluate](how-to/evaluate.md) |
| **Auditor** | [Deterministic grading](../evals/deterministic/index.md) → [Tests](../evals/README.md#test-to-module-mapping) |
| **Decision maker** | [Architecture](architecture.md) → [Decision records](decisions/README.md) |

## Related documentation

| Doc | What it answers |
|---|---|
| [Root README](../README.md) | Five-minute quickstart, project overview |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | Change workflow, issue discipline |
| [AGENTS.md](../AGENTS.md) | Cross-agent policy, safety invariants, change tiers |

## Evaluation instrument map

The evaluation documentation lives under [`evals/`](../evals/) and is reached from the single
map above. It is not a parallel hub — every role entry point routes through one of the tables
in this file.

```
evals/
├── README.md                     ← Role-routing hub (this file references it)
├── Operating_Manual.md           ← Maintainer review rules, authority boundary
├── pipeline.md                   ← Five-step pipeline, result-term table
├── scenarios_v1.yaml             ← Single source of truth: 50 scenarios (24 probe)
│
├── deterministic/index.md        ← Four-kind cascade, tier precedence, canonical description
├── semantic/                     ← Semantic judge tier
│   ├── index.md                  ← What the tier is for; authority; D-042 relationship
│   ├── judge.md                  ← DeepEval wrapper, provider arms, throttle
│   ├── rubric.md                 ← SAF/HON/HLP rubrics, failure modes
│   ├── exemplars.md              ← PASS/FAIL exemplar selection
│   └── not-evaluated.md          ← Two NOT_EVALUATED senses
├── calibration/                  ← Human-label corpus + threshold derivation
│   ├── index.md                  ← Why calibration exists; corpus composition; thresholds
│   ├── corpus.md                 ← Case schema; composition; id disjointness
│   └── thresholds.md             ← Recall-first rule; RELEASE_THRESHOLDS_BY_CLASS; Wilson intervals
├── replay/                       ← Frozen, sanitized evidence for CI
│   └── index.md                  ← Freeze→sanitize→replay contract
├── authoring/                    ← How to author and edit scenarios
│   └── index.md                  ← Grammar, id pattern, assertions
├── disagreements/                ← Grader-vs-judge-vs-human workflow
│   └── index.md                  ← Decision tree; live register pointer
│
├── Instrument_Report.md          ⚠ Dated snapshot (2026-09-04)
├── V6_Grader_Audit_2026-08-23.md ⚠ Dated snapshot
├── t0027_deepseek_arm.md         ⚠ Dated snapshot (2026-08-14)
├── IMPLEMENTATION_PLAN.md        ⚠ Dated plan
│
├── calibration_v7.yaml           ← 54 immutable human-labelled cases
├── calibration_v8.yaml           ← 12 immutable holdout cases
├── calibration_release_gate.yaml ← Enforced per-class thresholds
│
└── archive/                      ← Historical preserved evidence (readable history)
```

> **Drift guard:** Numeric facts (scenario count, corpus sizes, thresholds) are sourced from
> machine-readable files. `scripts/docs_lint.py` checks that prose does not drift from these
> sources. See [docs/lint](../scripts/docs_lint.py) for current checks.
