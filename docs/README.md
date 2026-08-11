# Documentation Map

This index assigns one owner to each class of project fact.
Link to that owner instead of restating its facts elsewhere.

## Canonical docs

| Concern | Owner | Altitude |
|---|---|---|
| What the MVP must do | [MVP Spec](MVP_Spec.md) | Product capability |
| Permanent system laws and layer boundaries | [Full Design](Full_Design_Document.md) | Constitution |
| How the MVP realizes those laws | [Technical Design](MVP_Technical_Design.md) | Build blueprint |
| Frozen v1 `clean_jobs` columns | [Schema Contract](Schema_Contract.md) | Data contract |
| Agent behavior requirements | [Agent Behavior Spec](Agent_Behavior_Spec.md) | Behavior contract |

## Living and operational docs

| Concern | Owner |
|---|---|
| Current branch, completed work, and next ticket | [Repository Current State](Repo_Current_State.md) |
| Open risks and follow-ups | [Known Issues](Known_Issues.md) |
| Active ticket plans and delivery sequence | [Tickets](Tickets.md) |
| Deployment, configuration, cron, and incident procedures | [Operations](Operations.md) |
| Re-runnable developer checks | [Manual Verification Guide](Manual_Verification_Guide.md) |

## Reference and documentation-system docs

| Concern | Owner |
|---|---|
| Languages, frameworks, services, and versions | [Tech Stack](Tech_Stack.md) |
| Prompt design and conventions | [Prompt Playbook](Prompt_Playbook.md) |
| Durable decision rationale | [Decision Log](Decision_Log.md) |
| Documentation rules and lint exemptions | [Documentation Conventions](Docs_Conventions.md) |
| Cron activation gates while activation remains pending | [T0020.4 Cron Activation Runbook](T0020.4_Cron_Activation_Runbook.md) |

## Archives

The append-only record of completed work is [Completion Reports](Completion_Reports.md).
Closed risks are in [Resolved Issues](Resolved_Issues.md).
Historical ticket plans, checklists, reviews, and state snapshots live in [archive](archive/).

## Fact Ledger

| Fact class | Sole owner |
|---|---|
| What the product must do | `MVP_Spec.md` |
| Permanent laws and layer boundaries | `Full_Design_Document.md` |
| How a capability is built | `MVP_Technical_Design.md` |
| Languages, frameworks, versions, and services | `Tech_Stack.md` |
| `clean_jobs` column contract | `Schema_Contract.md` |
| Deploy topology, environment variables, runbooks, and cron | `Operations.md` |
| What is true right now | `Repo_Current_State.md` |
| What a ticket should do | `Tickets.md` or `archive/Tickets_Archive.md` |
| What a ticket did | `Completion_Reports.md` |
| Open risks | `Known_Issues.md` |
| Closed risks | `Resolved_Issues.md` |
| Why a durable choice was made | `Decision_Log.md` |
| Documentation rules and conventions | `Docs_Conventions.md` |
| Agent working rules | `AGENTS.md` and `CLAUDE.md` |

## Suggested reading order

1. [MVP Spec](MVP_Spec.md) - understand the product.
2. [Full Design](Full_Design_Document.md) - learn the permanent laws and boundaries.
3. [Technical Design](MVP_Technical_Design.md) - see the implementation blueprint.
4. [Repository Current State](Repo_Current_State.md) - find the active state and next work.
5. [Tickets](Tickets.md) - select an active ticket.
