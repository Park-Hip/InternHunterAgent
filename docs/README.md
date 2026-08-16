# Documentation Map

Each document below has one owner, tier, cap, and intended reader.
Link to the owner instead of restating its facts elsewhere.

Caps are per-document and set from the measured length plus headroom, never from an aspiration.
A document over its cap means either the cap or the document is wrong; decide which, and say so.

Two caps moved on 2026-08-13 when T0025.10 closed M25, both measured after the change:

- `Tickets.md` 500 → 300, measured at 248 on 2026-08-14 after M26's three completed blocks joined
  M25's ten in [the archive](archive/Tickets_Archive.md) and M27 was scoped into four ticket
  bodies. That eviction was not optional: naming M27 pushed the document to its cap exactly, and
  the cap is what surfaced the plans that had already earned their exit. The remaining headroom is
  for M23 and M24, indexed but not yet scoped.
- `Decision_Log.md` 350 → 450, measured at 368. Harvesting is what this document is for, so it
  grows by design each time a milestone closes; M25 contributed D-041 through D-044. Evicting a
  decision requires revoking it, so the cap is the only lever that moves.

> **Eviction:** A map entry leaves when its owned document is retired or ownership moves elsewhere.

T0026.1 registered five `evals/` documents that this map had never listed. The two dated
measurement records are `T4 · Uncapped` like every other historical artifact here: they record what
was true on 2026-07-14 and will be replaced by a re-measurement rather than edited, so a line
budget on them would measure nothing. The three living ones carry caps set from their measured
length.

`Known_Issues.md` moved 250 → 275 on 2026-08-14, measured at 258. It sat exactly at its cap while
T0025.9, T0025.10, and T0026.1 each found something real, so the next true entry had nowhere to go.
Eviction is the cheaper fix when this binds again: several `LOW · OPEN` entries say in substance
"address only if this recurs", which is a deferred preference rather than an open risk.

T0031.1 split this map into a write surface and a read surface. Every document listed below is now
read-mostly for a ticket agent: the ones named in the `frozen:` list in
[`roadmap.yaml`](roadmap.yaml) are written only by the integration step, and a ticket routes what
it has to say into its own file under [`entries/`](entries/README.md). Caps therefore measure
integration decisions rather than ticket traffic, which is what makes them meaningful again -
`Repo_Current_State.md` absorbed 91 of the preceding 200 commits and was still a merge behind
itself on `main`.

`entries/` is indexed here as a directory, the same way `archive/` is. A per-ticket file cannot
take a per-file cap row without recreating the shared-table edit the directory exists to remove.

<!-- caps:begin -->
| Doc | Owns | Tier | Cap | Reader |
|---|---|---:|---:|---|
| [Documentation Map](README.md) | Document ownership, caps, and readers | T3 | 150 | All contributors |
| [MVP Spec](MVP_Spec.md) | Product capabilities and quality bar | T2 | 650 | Product and engineering |
| [Full Design](Full_Design_Document.md) | Permanent system laws and layer boundaries | T2 | 650 | Engineering |
| [Technical Design](MVP_Technical_Design.md) | Serving-path build blueprint | T2 | 750 | Engineering |
| [Offline Pipelines Design](Offline_Pipelines_Design.md) | Ingestion and evaluation build blueprint | T2 | 650 | Engineering |
| [Schema Contract](Schema_Contract.md) | Frozen v1 `clean_jobs` columns | T2 | 650 | Engineering and evaluation |
| [Agent Behavior Spec](Agent_Behavior_Spec.md) | Frozen agent behavior requirements | T2 | 650 | Agent and evaluation work |
| [Tech Stack](Tech_Stack.md) | Languages, services, versions, and dependencies | T1 | 150 | New contributors |
| [Decision Log](Decision_Log.md) | Durable decision rationale | T3 | 450 | Decision makers |
| [Documentation Conventions](Docs_Conventions.md) | Documentation rules and exemptions | T1 | 150 | Documentation authors |
| [Repository Current State](Repo_Current_State.md) | Current repository facts and next ticket | T3 | 150 | All contributors |
| [Known Issues](Known_Issues.md) | Open risks and follow-ups | T3 | 275 | Maintainers |
| [Tickets](Tickets.md) | Active ticket plans and delivery sequence | T3 | 300 | Delivery planning |
| [Operations](Operations.md) | Deployment, configuration, cron, and incident procedures | T3 | 175 | Operators |
| [Manual Verification Guide](Manual_Verification_Guide.md) | Re-runnable developer checks | T3 | 150 | Developers |
| [T0020.4 Cron Activation Runbook](T0020.4_Cron_Activation_Runbook.md) | Pending cron activation gates | T3 | 600 | Maintainers |
| [Streaming and SSE Explained](../guides/Streaming_And_SSE_Explained.md) | Streaming learning walkthrough | T4 | Uncapped | New contributors |
| [Research index](../research/README.md) | Live pre-design research | T3 | 250 | Designers and maintainers |
| [Evaluation instrument](../evals/README.md) | `evals/` layout, pipeline order, and which commands spend quota | T1 | 150 | Anyone touching `evals/` |
| [Evaluation operating manual](../evals/Operating_Manual.md) | Why the instrument exists, the seams, grading, and its stated limits | T2 | 400 | Evaluation work |
| [Instrument report](../evals/Instrument_Report.md) | The grader audit and the holdout calibration, merged | T3 | 250 | Evaluation work |
| [v1 scenario matrix](../evals/archive/v1_scenario_matrix.md) | The 2026-07-14 measurement, sealed as dated evidence | T4 | Uncapped | Project history |
| [v1 error analysis](../evals/archive/v1_error_analysis.md) | Open-coded failure modes from the recovered answers, sealed | T4 | Uncapped | Project history |
| [T0027.3 DeepSeek arm](../evals/t0027_deepseek_arm.md) | The 2026-08-14 measured arm and the provider decision taken from it | T4 | Uncapped | Project history |
| [Completion Reports](Completion_Reports.md) | Completed-ticket outcomes | T4 | Uncapped | Project history |
| [Resolved Issues](Resolved_Issues.md) | Closed risk and fix records | T4 | Uncapped | Project history |
| [Ticket entries](entries/README.md) | Per-ticket write surface, one file per ticket | T4 | Uncapped | Ticket agents |
| [Archives](archive/) | Historical plans, checklists, and snapshots | T4 | Uncapped | Project history |
<!-- caps:end -->

## Fact Ledger

T0028.1 added the three evaluation rows. The ledger assigned an owner to fourteen fact classes and
to no evaluation fact, which is how the 29-scenario matrix came to be hand-written in five files
with nothing able to detect drift between the copies. The `scenario-id` lint check enforces the
first row: a scenario ID named anywhere in documentation must exist in the registry.

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
| Ticket and milestone number allocation | `roadmap.yaml` |
| Which paths a milestone may change | `roadmap.yaml` |
| Which registers a ticket agent may not write | `roadmap.yaml` (`frozen:`) |
| What a ticket should do | `Tickets.md` or `archive/Tickets_Archive.md` |
| What one ticket planned, did, and found | `entries/T####.md`, written by its own agent |
| What a ticket did | `Completion_Reports.md` |
| Open risks | `Known_Issues.md` |
| Closed risks | `Resolved_Issues.md` |
| Scenario definitions, inputs, expected behavior, and grading rules | `evals/scenarios_v1.yaml` |
| Agent behavior requirements and the probe protocol | `Agent_Behavior_Spec.md` |
| Graded outcomes of one dated evaluation run | The dated record under `evals/` |
| Why a durable choice was made | `Decision_Log.md` |
| Documentation rules and conventions | `Docs_Conventions.md` |
| Agent working rules | `AGENTS.md` and `CLAUDE.md` |

## Suggested reading order

1. [MVP Spec](MVP_Spec.md) - understand the product.
2. [Full Design](Full_Design_Document.md) - learn the permanent laws and boundaries.
3. [Technical Design](MVP_Technical_Design.md) - see the serving-path blueprint.
4. [Offline Pipelines Design](Offline_Pipelines_Design.md) - see ingestion and evaluation.
5. [Repository Current State](Repo_Current_State.md) - find the active state and next work.
6. [Tickets](Tickets.md) - select an active ticket.
