# Documentation Map

Each document below has one owner, tier, and intended reader.
Link to the owner instead of restating its facts elsewhere.

The living documentation surface is hand-maintained.
Historical ticket plans, completion records, checklists, and per-ticket entries are preserved under
[`archive/`](archive/).

| Doc | Owns | Tier | Reader |
|---|---|---:|---|
| [Documentation Map](README.md) | Document ownership and readers | T3 | All contributors |
| [MVP Spec](MVP_Spec.md) | Product capabilities and quality bar | T2 | Product and engineering |
| [Full Design](Full_Design_Document.md) | Permanent system laws and layer boundaries | T2 | Engineering |
| [Technical Design](MVP_Technical_Design.md) | Serving-path build blueprint | T2 | Engineering |
| [Offline Pipelines Design](Offline_Pipelines_Design.md) | Ingestion and evaluation build blueprint | T2 | Engineering |
| [Schema Contract](Schema_Contract.md) | Frozen v1 `clean_jobs` columns | T2 | Engineering and evaluation |
| [Agent Behavior Spec](Agent_Behavior_Spec.md) | Frozen agent behavior requirements | T2 | Agent and evaluation work |
| [Tech Stack](Tech_Stack.md) | Languages, services, versions, and dependencies | T1 | New contributors |
| [Decision Log](Decision_Log.md) | Durable decision rationale | T3 | Decision makers |
| [Documentation Conventions](Docs_Conventions.md) | Documentation rules and exemptions | T1 | Documentation authors |
| [Repository Current State](Repo_Current_State.md) | Current repository facts and next work | T3 | All contributors |
| [Known Issues](Known_Issues.md) | Open risks and follow-ups | T4 | Maintainers |
| [Operations](Operations.md) | Deployment, configuration, cron, and incident procedures | T3 | Operators |
| [Research index](../research/README.md) | Live pre-design research | T3 | Designers and maintainers |
| [Evaluation instrument](../evals/README.md) | `evals/` layout and pipeline order | T1 | Anyone touching `evals/` |
| [Evaluation operating manual](../evals/Operating_Manual.md) | Instrument seams, grading, and limits | T2 | Evaluation work |
| [Archives](archive/) | Historical plans, checklists, and snapshots | T4 | Project history |

## Fact Ledger

| Fact class | Sole owner |
|---|---|
| What the product must do | `MVP_Spec.md` |
| Permanent laws and layer boundaries | `Full_Design_Document.md` |
| How the serving path is built | `MVP_Technical_Design.md` |
| How the offline pipelines are built | `Offline_Pipelines_Design.md` |
| Languages, frameworks, versions, and services | `Tech_Stack.md` |
| `clean_jobs` column contract | `Schema_Contract.md` |
| Deploy topology, environment variables, runbooks, and cron | `Operations.md` |
| What is true right now | `Repo_Current_State.md` |
| Milestone identity and status | `roadmap.yaml` |
| Open risks | `Known_Issues.md` |
| Closed risks | `archive/Resolved_Issues.md` |
| Scenario definitions, inputs, expected behavior, and grading rules | `evals/scenarios_v1.yaml` |
| Agent behavior requirements and the probe protocol | `Agent_Behavior_Spec.md` |
| Graded outcomes of one dated evaluation run | The dated record under `evals/` |
| Why a durable choice was made | `Decision_Log.md` |
| Documentation rules and conventions | `Docs_Conventions.md` |
| Agent working rules | `AGENTS.md` and `CLAUDE.md` |

## Suggested reading order

1. [MVP Spec](MVP_Spec.md) - understand the product.
2. [Full Design](Full_Design_Document.md) - learn the permanent laws.
3. [Technical Design](MVP_Technical_Design.md) - see the serving-path blueprint.
4. [Offline Pipelines Design](Offline_Pipelines_Design.md) - see ingestion and evaluation.
5. [Repository Current State](Repo_Current_State.md) - find active work and verified facts.
6. [Known Issues](Known_Issues.md) - review open risks before changing behavior.
