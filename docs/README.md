# Documentation Map

Each document below has one owner, tier, and intended reader.
Link to the owner instead of restating its facts elsewhere.

The living documentation surface is hand-maintained.
Historical ticket plans, completion records, checklists, and per-ticket entries are preserved under
[`archive/`](archive/).

Five paths in this directory are redirects rather than documents: `MVP_Spec.md`,
`Full_Design_Document.md`, `MVP_Technical_Design.md`, `Offline_Pipelines_Design.md`, and
`Tech_Stack.md`.
Each merged into [Design](Design.md) and is retained only so the section citations in archived
research still resolve; each names the design section that now owns its content.
They own no facts and are not listed below.

| Doc | Owns | Tier | Reader |
|---|---|---:|---|
| [Documentation Map](README.md) | Document ownership and readers | T3 | All contributors |
| [Design](Design.md) | Product scope, architecture, serving, offline pipelines, and stack | T2 | Product and engineering |
| [Schema Contract](Schema_Contract.md) | Frozen v1 `clean_jobs` columns | T2 | Engineering and evaluation |
| [Agent Behavior Spec](Agent_Behavior_Spec.md) | Frozen agent behavior requirements | T2 | Agent and evaluation work |
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
| Product scope, architectural laws, serving, pipelines, and stack | `Design.md` |
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

1. [Design](Design.md) - understand product scope, architecture, and operating model.
2. [Schema Contract](Schema_Contract.md) - learn the frozen data surface.
3. [Agent Behavior Spec](Agent_Behavior_Spec.md) - learn the behavior requirements.
4. [Operations](Operations.md) - learn deployment and incident procedures.
5. [Repository Current State](Repo_Current_State.md) - find active work and verified facts.
6. [Known Issues](Known_Issues.md) - review open risks before changing behavior.
