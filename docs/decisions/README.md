# Decision records

One immutable record per durable decision that constrains current architecture or operations.
A record changes only when a new record replaces it; the replaced record keeps its file with a
`Superseded by` status.
Decisions whose rationale already lives in an owning document, and ticket-era process decisions,
were not carried over - see the retirement list below.

Historical full records were deleted from the working tree on 2026-08-24 and remain browsable on
git tag `docs-history-pre-redesign`.

## Active records

| ADR | Decision | Theme |
|---|---|---|
| [ADR-0010](adr-0010-created-on-preserved-posted-date-never-synthesized.md) | Created-on is preserved; posted date is never synthesized | Data honesty |
| [ADR-0011](adr-0011-listing-expiry-from-truthful-source-field.md) | Listing expiry comes from the truthful source expiry field | Data honesty |
| [ADR-0016](adr-0016-evaluation-covers-three-layers.md) | Evaluation covers outcome, trajectory, and component layers | Evaluation |
| [ADR-0017](adr-0017-judge-provider-separate-from-serving.md) | The judge runs on a provider that does not serve the agent | Evaluation |
| [ADR-0018](adr-0018-offline-evaluation-precedes-online-monitoring.md) | Offline evaluation precedes online monitoring | Evaluation |
| [ADR-0021](adr-0021-lifecycle-data-hidden-until-measured.md) | Lifecycle data is hidden until honesty behavior is measured | Data honesty |
| [ADR-0025](adr-0025-demo-cost-ceiling.md) | The demo has a 10 USD monthly cost ceiling | Operations |
| [ADR-0029](adr-0029-langfuse-cloud-hobby-japan.md) | Langfuse Cloud Hobby in Japan provides tracing | Operations |
| [ADR-0031](adr-0031-neon-direct-not-pooler.md) | Production Postgres uses Neon directly, not the pooler | Operations |
| [ADR-0032](adr-0032-slim-non-root-docker-image.md) | Production uses a slim, non-root Python Docker image | Operations |
| [ADR-0034](adr-0034-vietnamworks-robots-and-terms-gate.md) | VietnamWorks automation passed the robots.txt and terms gate | Legal/source |
| [ADR-0036](adr-0036-source-market-vietnamese-job-boards.md) | The source market is Vietnamese job boards, not global ATS aggregators | Product scope |
| [ADR-0037](adr-0037-frozen-fixture-baselines.md) | Evaluation baselines freeze fixture data with the agent-visible contract | Evaluation |
| [ADR-0038](adr-0038-scheduled-ingestion-required.md) | Scheduled ingestion is a required MVP capability, not an optional refresh | Product scope |
| [ADR-0041](adr-0041-scenario-registry-single-source-of-truth.md) | The scenario registry is the single source of truth for evaluation cases | Evaluation |
| [ADR-0042](adr-0042-grader-authority-at-calibration.md) | Grader authority passes from human to grader at calibration | Evaluation |
| [ADR-0043](adr-0043-deepeval-harness-kept-http-discarded.md) | Keep the DeepEval harness, discard its HTTP transport | Evaluation |
| [ADR-0044](adr-0044-temperature-zero-rejected-for-react.md) | Temperature 0 is rejected for the ReAct seam | Agent runtime |
| [ADR-0045](adr-0045-deepseek-serves-the-agent.md) | DeepSeek serves the agent, on measured throughput | Agent runtime |
| [ADR-0046](adr-0046-replays-retain-evidence-not-telemetry.md) | Frozen replays retain evidence, not per-turn telemetry | Evaluation |

## Retired decisions, and why they were not carried over

- **Superseded by this redesign:** D-035 (tracked `skills/` copy canonical - the tracked skills were
  removed in favor of issue-based proposals and `.agents/skills/`), D-047 (retire the ticket
  workflow - realized and overtaken by the GitHub Issues workflow), D-048 (ticket-era verification
  queue sweep - completion record, not a standing constraint).
- **Owned by a living document:** D-002, D-003, D-004, D-005, D-006, D-007, D-008, D-009 (demo UI
  and streaming mechanics - architecture.md), D-012 (job level visibility - schema reference),
  D-013, D-014 (tech-stack vocabulary semantics - ingestion cleaning in the operate how-to),
  D-015 (pre-freeze enrichment sequencing - completed process), D-019 (windowed keep-alive -
  operate how-to plus its tracking issue), D-020 (ingestion safety trio - operate how-to),
  D-022 (accumulate, never wipe - operate how-to), D-023 (Alembic migrations - schema reference and
  `AGENTS.md` safety invariants), D-024 (external ingestion scheduling - architecture exclusions),
  D-026 (liveness/readiness split - architecture.md), D-027 (auto-deploy on main - operate how-to),
  D-028 (Render subdomain, same origin - architecture and configuration), D-030 (secrets are Render
  runtime variables - `AGENTS.md` safety invariants), D-033 (Render hosts the demo - operate
  topology), D-039 (scenario id scheme - registry-owned convention).
- **Milestone-era process, completed:** D-040 (M25 instrument acceptance gate).
- **Moot after deletion:** D-001 (behavior question bank exploratory status - the bank was deleted
  with the research history).
