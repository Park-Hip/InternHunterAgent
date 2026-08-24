# Decision Log

> **Last verified:** 2026-08-20.
> This is the compact index of durable project decisions harvested from executed research.
> It records the choice and points to the preserved reasoning.
> Current operational facts belong in the document that owns them.

> **Eviction:** A decision entry leaves when it is revoked or superseded, with its historical record
> retained in the decision archive.

## Decision index

| ID | Decision | Status |
|---|---|---|
| D-048 | The ticket-era verification queue is resolved, not archived open | Active |
| D-047 | Retire the ticket workflow in favor of reviewable plans and derived state | Active |
| D-046 | Frozen replays retain evidence, not per-turn telemetry | Active |
| D-045 | DeepSeek serves the agent, on measured throughput | Active |
| D-044 | Temperature 0 is rejected for the ReAct seam | Active |
| D-043 | Keep the DeepEval harness, discard its HTTP transport | Active |
| D-042 | Grader authority passes from human to grader at calibration | Active |
| D-041 | The scenario registry is the single source of truth for evaluation cases | Active |
| D-040 | M25 closes on instrument acceptance, not behavior quality | Active |
| D-039 | Evaluation scenario identifiers are class-first and self-describing | Active |
| D-038 | Scheduled ingestion is a required MVP capability, not an optional refresh | Active |
| D-037 | Evaluation baselines freeze fixture data with the agent-visible contract | Active |
| D-036 | The source market is Vietnamese job boards, not global ATS aggregators | Active |
| D-035 | The tracked `skills/` copy is canonical | Active |
| D-034 | VietnamWorks automation passed the robots.txt and terms gate | Active |
| D-033 | Render hosts the portfolio demo | Active |
| D-032 | Production uses a slim, non-root Python Docker image | Active |
| D-031 | Production Postgres uses Neon directly, not the pooler | Active |
| D-030 | Production secrets are Render runtime environment variables | Active |
| D-029 | Langfuse Cloud Hobby in Japan provides tracing | Active |
| D-028 | The demo uses the Render subdomain and same-origin serving | Active |
| D-027 | Render auto-deploys pushes to main | Active |
| D-026 | Liveness and readiness are separate endpoints | Active |
| D-025 | The demo has a 10 USD monthly cost ceiling | Active |
| D-024 | Ingestion runs externally through GitHub Actions | Active |
| D-023 | Schema changes use Alembic migrations | Active |
| D-022 | Ingestion accumulates records instead of truncating clean jobs | Active |
| D-021 | Lifecycle data is hidden until honesty behavior is measured | Active |
| D-020 | Production ingestion needs a yield floor, rollback path, and schema assertion | Active |
| D-019 | Keep-alive is windowed and must be measured against Neon compute use | Active |
| D-018 | Offline evaluation precedes online monitoring | Active |
| D-017 | The judge runs on a provider that does not serve the agent | Active |
| D-016 | Evaluation covers outcome, trajectory, and component layers | Active |
| D-015 | V1 schema changes are decided before the schema freeze | Active |
| D-014 | Tech stack uses an external vocabulary, not a hardcoded allowlist | Active |
| D-013 | Tech stack includes AI and data techniques as well as technologies | Active |
| D-012 | Job level is agent-visible in v1 | Active |
| D-011 | Listing expiry comes from the truthful source expiry field | Active |
| D-010 | Created-on is preserved, while posted date is never synthesized | Active |
| D-009 | Stream extraction tries event v3 and keeps a message fallback | Active |
| D-008 | Streaming uses a two-gate filter to prevent internal token leakage | Active |
| D-007 | Streaming uses FastAPI's native SSE response | Active |
| D-006 | The stream has typed terminal events | Active |
| D-005 | Mid-stream failures are in-band error events | Active |
| D-004 | The demo is an editorial vanilla front end | Active |
| D-003 | The demo UI is static and same-origin with FastAPI | Active |
| D-002 | Browser SSE over POST uses fetch and ReadableStream | Active |
| D-001 | The behavior question bank is exploratory, not a product commitment | Active |

## Active decisions

### D-048 - The ticket-era verification queue is resolved, not archived open

- **Decided:** 2026-08-20 - **Status:** Active. Completes the mitigation D-047 owed.
- Retiring the ticket workflow archived `Manual_Verification_Guide.md` with fourteen entry
  checklists still at `verified: no`. Burying an open queue is not the same as closing it, so each
  was swept and given a disposition. The archived entries keep their original `verified: no`, since
  an archived record is not edited to reflect a later outcome; this entry is the living owner of
  what happened to them.
- **Five were run and passed** against the merged tree on 2026-08-20. T0030.3 (replay telemetry
  exclusion) verified by reading D-046, the `replays/` row in [`evals/README.md`](../evals/README.md),
  and the replay files themselves; all three carry no trace identifier, latency, token usage,
  finish reason, or tool output. T0030.1 step 4 and T0035.1's schema and prompt-version assertions
  verified the same way. T0032.2 (model-facing string inventory) passed as
  `tests/test_prompt_surface.py`. T0031.3 steps 1 and 5 passed as `docs_build.py --check`, which
  still exits 0 clean and still refuses to verify the clone-local snapshot region.
- **Four are superseded by automated coverage** that runs in CI on every pull request, which is a
  stronger gate than a hand-run checklist. The freeze, sanitization, registry-drift, and
  prompt-version steps of T0030.1, T0030.2, and T0035.1 are covered by twenty-five tests under
  `tests/evals/`. The tool-surface half of T0024.2, T0024.3, T0032.1, and T0033.5 - glossary token
  coverage, absent-field wording, the truncation notice, the mandatory-caveat block, and the
  cross-currency rule - is covered under `tests/agents/` and `tests/evals/test_grader.py`.
- **The model-behavior half of those four belongs to the scenario registry, not to a checklist.**
  Whether the final answer preserves a caveat or declines to relabel listing expiry is exactly what
  the twenty-nine honesty scenarios in `evals/scenarios_v1.yaml` measure, under D-041. A hand-run
  question was the wrong instrument for it, and re-running one would not produce evidence anyone
  could compare.
- **Five are obsolete**, because the machinery they verify was deleted by D-047. T0031.1, T0031.2,
  T0031.4, and T0036.1 test the `size-cap`, `orphan`, `generated`, `scope`, `frozen`, and
  `registry` lint checks, the entry-fed generated regions, and the ticket-prompt skill - none of
  which exist. T0036.1's entire subject was the `scope` check. T0031.3 steps 2, 4, and 6 fall the
  same way, which is why only its steps 1 and 5 were run above.
- **The sweep found one live defect**, filed as `KI-2026-08-20-stale-replays` in
  [the issue tracker](https://github.com/Park-Hip/InternHunterAgent/issues). Running T0030.2's checklist as written fails: two of the three
  committed replays no longer validate against the scenario registry, and the CI gate replays only
  the third. That is the return on doing the sweep rather than archiving the queue silently.
- **Full record:** [`docs/archive/Manual_Verification_Guide.md`](archive/Manual_Verification_Guide.md)
  holds the fourteen checklists as written, and the entries under
  [`docs/archive/entries/`](archive/entries/README.md) hold their originating context.

### D-047 - Retire the ticket workflow in favor of reviewable plans and derived state

- **Decided:** 2026-08-20 - **Status:** Active.
- Reviewed pull-request bodies, a tiered planning workflow, branch protection, and a small set of
  derived state checks replace ticket allocation, numbered ticket scopes, entry-fed registers, and
  frozen-document ownership rules.
- The scenario registry, roadmap milestones, documentation map, and generated agent instructions
  remain explicit sources of truth where they provide durable value.
- **Full record:** [workflow retirement research](../research/archive/workflow-retirement.md).

### D-046 - Frozen replays retain evidence, not per-turn telemetry

- **Decided:** 2026-08-17 - **Status:** Active. Settled by T0030.3.
- A committed replay keeps the source artifact name and run id, questions, answers, called tools,
  generated SQL, and expected deterministic outcomes. It excludes per-turn latency, token usage,
  finish reasons, tool output, and every trace identifier.
- A future reader needs the retained fields to reproduce the fixture-bound verdict. Aggregate cost
  and latency belong in the dated arm record, where they explain the finding without making each
  replayed turn a broader sanitization obligation.
- **Full record:** [T0030.2 acceptance replay](../evals/replays/t0025.7-acceptance.json) and
  [T0027.3 DeepSeek arm](../evals/t0027_deepseek_arm.md).

### D-045 - DeepSeek serves the agent, on measured throughput

- **Decided:** 2026-08-15 - **Status:** Active. Narrows the serving half of D-017 below.
- The measured basis is throughput, not answer quality: the 29-scenario registry captured in
  5 minutes 20 seconds, 77 of 77 turns, zero retries, for about $0.04. The Groq free tier reached
  13 turns in 21 minutes before quota stopped it. Steps 1 to 3 of the pre-registered rule - safety,
  honesty, task and tool quality - found no difference this evidence can resolve, so the decision
  was taken at step 4.
- The evidence is one arm, not a bake-off. The Groq arm was dropped because running it costs
  roughly four days of rationed free-tier quota, which is the constraint this decision removes.
- Two consequences follow. `eval.driver.turn_pacing_seconds` moves to 0, because it existed only to
  survive a per-minute token ceiling DeepSeek does not publish. No provider key is required at
  boot: each branch validates its own, so a checkout holding only the selected provider's key runs.
- The Groq branch stays selectable. Two working branches are what keep the provider seam honest,
  and DeepSeek has no free tier to fall back on.
- **Full record:** [T0027.3 DeepSeek arm](../evals/t0027_deepseek_arm.md) and
  [DeepSeek provider evaluation](../research/deepseek-provider-evaluation.md).

### D-044 - Temperature 0 is rejected for the ReAct seam

- **Decided:** 2026-08-12 - **Status:** Active. Harvested at M25 close from settled decision D-6.
- Greedy decoding degrades the tool-choice loop for this model family, so the ReAct seam keeps its
  tuned sampling values. SQL generation stays at 0.0, where determinism is wanted.
- The earlier "0.0 fallback" plan is withdrawn. Any sampling experiment changes one variable at a
  time and belongs to M24, per D-040 below.
- **Full record:** [evaluation strategy](../research/evaluation-strategy.md), section 5c.

### D-043 - Keep the DeepEval harness, discard its HTTP transport

- **Decided:** 2026-08-12 - **Status:** Active. Harvested at M25 close from settled decision D-4.
- The instrumentation half is the valuable one: DeepEval's LangChain callback and trace manager are
  what make the three seams observable at all.
- The archived HTTP runner contributes orchestration logic as a pattern only; the driver runs the
  agent in-process.
- **Full record:** [evaluation strategy](../research/evaluation-strategy.md), section 2a.

### D-042 - Grader authority passes from human to grader at calibration

- **Decided:** 2026-08-12 - **Status:** Active. Harvested at M25 close from settled decisions D-2
  and D-3.
- During calibration the human label wins and the assertion is amended. After calibration the
  grader wins, and each disagreement becomes a new labeled case.
- Where a structural check and the judge disagree, the structural check wins.
- A six-scenario holdout spanning all three classes has assertions authored without reference to
  recorded answers. It proves contracts, never empirical calibration.
- **Full record:** [evaluation strategy](../research/evaluation-strategy.md), section 6a, and
  [`evals/Instrument_Report.md`](../evals/Instrument_Report.md).

### D-041 - The scenario registry is the single source of truth for evaluation cases

- **Decided:** 2026-08-12 - **Status:** Active. Harvested at M25 close from settled decisions D-1
  and D-5.
- `evals/scenarios_v1.yaml` owns the cases, their probe flags, reference SQL, and tool
  expectations. Goldens are generated from it, ending probe-flag drift structurally.
- The 29-scenario set is kept as authored: it matches the frozen schema and is requirement-seeded.
  Coverage is audited, not re-authored.
- **Full record:** [evaluation strategy](../research/evaluation-strategy.md), sections 2b and 3b.

### D-040 - M25 closes on instrument acceptance, not behavior quality

- **Decided:** 2026-08-13 - **Status:** Active.
- M25 closes when the clean current configuration produces a provenance-complete three-seam
  artifact that a human can inspect and CI can replay without a model call.
- M24 owns behavior fixes and production sampling selection.
  Judge calibration and release thresholds remain separate release-gate work.
- The bundled sampling A/B is withdrawn because it changes multiple variables and cannot identify
  a cause.
  A later experiment changes one variable at a time only if instrumented evidence supports it.
- **Full record:** [evaluation strategy](../research/evaluation-strategy.md), sections 5c, 6, and 8.

### D-039 - Evaluation scenario identifiers are class-first and self-describing

- **Decided:** 2026-08-13 - **Status:** Active.
- Scenario ids use `<CLASS>-<BEHAVIOR>-<n>`, with `SAF`, `HON`, and `HLP` marking the release-bar
  class and behavior tokens taken from the frozen behavior specification.
- Requirements, settled-decision traceability, and the display name are fields, not encoded into an
  authoring-batch label.
- This replaces D-5 in the evaluation strategy only for labels; the scenario set remains unchanged.
- **Full record:** [evaluation strategy](../research/evaluation-strategy.md), settled decision D-5.

### D-038 - Scheduled ingestion is a required MVP capability, not an optional refresh

- **Decided:** 2026-08-12 - **Status:** Active.
- A hand-loaded static corpus does not satisfy the MVP, so the nightly VietnamWorks schedule must be
  active and observed before the `v1.0.0` tag is cut.
- This settles D10 in the cron runbook and makes every activation gate release-blocking, including
  the terms posture that gates rearming the schedule.
- **Full record:** [architecture.md](architecture.md), product and MVP bar.

### D-037 - Evaluation baselines freeze fixture data with the agent-visible contract

- **Decided:** 2026-07-03 - **Status:** Active.
- Baseline evaluation uses the frozen agent-visible schema and seeded fixture data together so
  prompt changes can be measured independently of corpus churn.
- **Full record:** [pre-deployment refinement](../research/archive/pre-deploy-refinement-plan.md),
  section 1.

### D-036 - The source market is Vietnamese job boards, not global ATS aggregators

- **Decided:** 2026-06 - **Status:** Active.
- The product targets Vietnam AI/Data roles, so global ATS APIs are out of scope; VietnamWorks is
  the selected initial source under D-034.
- **Full record:** [data ingestion stage §0](../research/archive/data-ingestion-stage.md).

### D-035 - The tracked `skills/` copy is canonical

- **Decided:** 2026-08-11 - **Status:** Active.
- `.claude/` is gitignored, so the tracked `skills/` copy of a skill is the only
  version-controlled one and must remain tracked. The rule was settled against
  `skills/generate-ticket-prompt/`, retired by D-047; it now governs `skills/plan/` and
  `skills/integrate/`.
- CI on PR #41 exposed the invalid deletion premise when the ignored local copy was absent.
- **Full record:** [documentation prune plan §3.1.1](../research/docs-prune-and-structure-plan.md).

### D-034 - VietnamWorks automation passed the robots.txt and terms gate

- **Decided:** 2026-07-16 - **Status:** Active. **Ratified:** 2026-08-13.
- The scheduled VietnamWorks path is permitted under the recorded, dated review. The maintainer
  ratified the favorable verdict on 2026-08-13, clearing gate D2 of the cron activation runbook.
- Scope: automated *access*. The separate ToS §7 *republishing* restriction concerns what the
  public demo displays and stays open on the issue tracker; it does not gate the cron.
- **Full record:** [deployment research §11](../research/archive/deployment-research-plan.md).

### D-033 - Render hosts the portfolio demo

- **Decided:** 2026-07-16 - **Status:** Active.
- Render Free deploys the Docker image from GitHub in Singapore; cold starts are accepted.
- **Full record:** [deployment research §1](../research/archive/deployment-research-plan.md).

### D-032 - Production uses a slim, non-root Python Docker image

- **Decided:** 2026-07-16 - **Status:** Active.
- Use `python:3.12-slim`, `uv sync --frozen --no-dev`, and a non-root application user.
- **Full record:** [deployment research §2](../research/archive/deployment-research-plan.md).

### D-031 - Production Postgres uses Neon directly, not the pooler

- **Decided:** 2026-07-16 - **Status:** Active.
- Low request volume does not justify the pooler's prepared-statement trade-off.
- **Full record:** [deployment research §3](../research/archive/deployment-research-plan.md).

### D-030 - Production secrets are Render runtime environment variables

- **Decided:** 2026-07-16 - **Status:** Active.
- Secrets never enter the image or repository.
- Eval-only Google credentials stay off the request path.
- **Full record:** [deployment research §5](../research/archive/deployment-research-plan.md).

### D-029 - Langfuse Cloud Hobby in Japan provides tracing

- **Decided:** 2026-07-16 - **Status:** Active.
- Cloud hosting avoids a fourth workload and ClickHouse maintenance for a small demo.
- **Full record:** [deployment research §6](../research/archive/deployment-research-plan.md).

### D-028 - The demo uses the Render subdomain and same-origin serving

- **Decided:** 2026-07-16 - **Status:** Active.
- Render TLS is sufficient; a custom domain and CORS configuration are deferred.
- **Full record:** [deployment research §7](../research/archive/deployment-research-plan.md).

### D-027 - Render auto-deploys pushes to main

- **Decided:** 2026-07-16 - **Status:** Active.
- The free deployment path has no preview environments or pytest merge gate.
- **Full record:** [deployment research §8](../research/archive/deployment-research-plan.md).

### D-026 - Liveness and readiness are separate endpoints

- **Decided:** 2026-07-16 - **Status:** Active.
- `/health` is the Render target, while DB-gated `/ready` must not keep Neon awake.
- **Full record:** [deployment research §9](../research/archive/deployment-research-plan.md).

### D-025 - The demo has a 10 USD monthly cost ceiling

- **Decided:** 2026-07-16 - **Status:** Active.
- The expected cost is zero; Render Starter is the first cold-start upgrade if needed.
- **Full record:** [deployment research §10](../research/archive/deployment-research-plan.md).

### D-024 - Ingestion runs externally through GitHub Actions

- **Decided:** 2026-07-16 - **Status:** Active.
- Scheduling is out of band and applies only after legal and unattended-run safety gates pass.
- **Full record:** [ingestion milestone §3](../research/archive/ingestion-milestone-plan.md).

### D-023 - Schema changes use Alembic migrations

- **Decided:** 2026-07-03 - **Status:** Active.
- A baseline migration replaces reset scripts as the production schema-change mechanism.
- **Full record:** [deployment research §4.2](../research/archive/deployment-research-plan.md).

### D-022 - Ingestion accumulates records instead of truncating clean jobs

- **Decided:** 2026-07-03 - **Status:** Active.
- Upserts and time-based expiry make a partial run unable to shrink the served corpus.
- **Full record:** [deployment research §4.2](../research/archive/deployment-research-plan.md).

### D-021 - Lifecycle data is hidden until honesty behavior is measured

- **Decided:** 2026-07-16 - **Status:** Active.
- `is_active` mechanics ship in the data layer.
- Agent exposure waits for evaluation and recalibration.
- **Full record:** [ingestion milestone §1B](../research/archive/ingestion-milestone-plan.md).

### D-020 - Production ingestion needs a yield floor, rollback path, and schema assertion

- **Decided:** 2026-07-16 - **Status:** Active.
- These safeguards protect a live corpus without adding a staging database or a second serving path.
- **Full record:** [ingestion milestone](../research/archive/ingestion-milestone-plan.md),
  sections 1A and 1D.

### D-019 - Keep-alive is windowed and must be measured against Neon compute use

- **Decided:** 2026-07-16 - **Status:** Active.
- If idle pools prevent suspension, shed connections, reduce the window, or use Render Starter.
- **Full record:** [ingestion milestone §1C](../research/archive/ingestion-milestone-plan.md).

### D-018 - Offline evaluation precedes online monitoring

- **Decided:** 2026-07-03 - **Status:** Active.
- Establish the offline baseline before adding score writeback, alerts, and judge infrastructure.
- **Full record:** [DeepEval planning §4](../research/archive/deepeval-sql-agent-eval-planning.md).

### D-017 - The judge runs on a provider that does not serve the agent

- **Decided:** 2026-07-03 - **Status:** Active.
- Separating judge and serving load avoids double pressure on the serving provider's free quota.
- Gemini judges. The serving side was Groq when this was decided and is DeepSeek since D-045; the
  separation holds either way, and it is also what keeps a provider out of judging its own arm.
- **Full record:** [DeepEval planning](../research/archive/deepeval-sql-agent-eval-planning.md),
  sections 5 and 11.4.

### D-016 - Evaluation covers outcome, trajectory, and component layers

- **Decided:** 2026-07-03 - **Status:** Active.
- The three layers distinguish task failure, unsafe reasoning, and component regressions.
- **Full record:** [DeepEval planning §2](../research/archive/deepeval-sql-agent-eval-planning.md).

### D-015 - V1 schema changes are decided before the schema freeze

- **Decided:** 2026-07-09 - **Status:** Active.
- Enrichment work was sequenced before the v1 contract freeze, not after it.
- **Full record:** [schema enrichment §1](../research/archive/schema-enrichment-plan.md).

### D-014 - Tech stack uses an external vocabulary, not a hardcoded allowlist

- **Decided:** 2026-07-09 - **Status:** Active.
- Source tags are noisy; a large, refreshable vocabulary retains coverage without an LLM.
- **Full record:** [schema enrichment §2](../research/archive/schema-enrichment-plan.md).

### D-013 - Tech stack includes AI and data techniques as well as technologies

- **Decided:** 2026-07-09 - **Status:** Active.
- Users search for techniques such as machine learning, which dominate the observed source tags.
- **Full record:** [schema enrichment §2.4](../research/archive/schema-enrichment-plan.md).

### D-012 - Job level is agent-visible in v1

- **Decided:** 2026-07-09 - **Status:** Active.
- The populated field is more useful than preserving an artificial absent-field evaluation case.
- **Full record:** [schema enrichment §3](../research/archive/schema-enrichment-plan.md).

### D-011 - Listing expiry comes from the truthful source expiry field

- **Decided:** 2026-07-09 - **Status:** Active.
- `listing_expires_on` makes open-status questions answerable without inventing recency.
- **Full record:** [schema enrichment §4.2](../research/archive/schema-enrichment-plan.md).

### D-010 - Created-on is preserved, while posted date is never synthesized

- **Decided:** 2026-07-09 - **Status:** Active.
- Use stable source `createdOn`; do not mistake churny source timestamps for a posting date.
- **Full record:** [schema enrichment §4](../research/archive/schema-enrichment-plan.md).

### D-009 - Stream extraction tries event v3 and keeps a message fallback

- **Decided:** 2026-07-13 - **Status:** Active.
- The implementation validates the event path in this graph and retains the compatible fallback.
- **Full record:**
  [streaming implementation](../research/archive/streaming-implementation-plan.md), section 2.

### D-008 - Streaming uses a two-gate filter to prevent internal token leakage

- **Decided:** 2026-07-13 - **Status:** Active.
- Filter by the final agent node and non-empty content before sending browser tokens.
- **Full record:**
  [streaming implementation](../research/archive/streaming-implementation-plan.md), section 3.

### D-007 - Streaming uses FastAPI's native SSE response

- **Decided:** 2026-07-13 - **Status:** Active.
- `EventSourceResponse` provides the required transport without another SSE dependency.
- **Full record:**
  [streaming implementation](../research/archive/streaming-implementation-plan.md), section 4.

### D-006 - The stream has typed terminal events

- **Decided:** 2026-07-13 - **Status:** Active.
- Session, token, metadata, error, and done events reflect when each field becomes available.
- **Full record:**
  [streaming implementation](../research/archive/streaming-implementation-plan.md), section 5.

### D-005 - Mid-stream failures are in-band error events

- **Decided:** 2026-07-13 - **Status:** Active.
- Once the response starts, the generator emits a friendly error event and closes cleanly.
- **Full record:**
  [streaming implementation](../research/archive/streaming-implementation-plan.md), section 6.

### D-004 - The demo is an editorial vanilla front end

- **Decided:** 2026-07-14 - **Status:** Active.
- A single hand-written page keeps the demo readable and avoids a client build toolchain.
- **Full record:** [demo UI plan §0a and §4](../research/archive/demo-ui-and-golive-plan.md).

### D-003 - The demo UI is static and same-origin with FastAPI

- **Decided:** 2026-07-14 - **Status:** Active.
- One deployment unit removes CORS configuration and a second cold-start surface.
- **Full record:** [demo UI plan §2](../research/archive/demo-ui-and-golive-plan.md).

### D-002 - Browser SSE over POST uses fetch and ReadableStream

- **Decided:** 2026-07-14 - **Status:** Active.
- Native EventSource is GET-only and auto-reconnects, which could repeat an agent run.
- **Full record:** [demo UI plan §3](../research/archive/demo-ui-and-golive-plan.md).

### D-001 - The behavior question bank is exploratory, not a product commitment

- **Decided:** 2026-07-09 - **Status:** Archived pending a restarted behavior-design track.
- Its scenario prompts inform future work only.
- Current behavior is owned by the active specifications.
- **Full record:** [behavior question bank](../research/archive/agent-behavior-question-bank.md).
