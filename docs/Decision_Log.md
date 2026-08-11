# Decision Log

> **Last verified:** 2026-08-11.
> This is the compact index of durable project decisions harvested from executed research.
> It records the choice and points to the preserved reasoning.
> Current operational facts belong in the document that owns them.

## Active decisions

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
- `.claude/` is gitignored, so `skills/generate-ticket-prompt/` is the only version-controlled
  copy and must remain tracked.
- CI on PR #41 exposed the invalid deletion premise when the ignored local copy was absent.
- **Full record:** [documentation prune plan §3.1.1](../research/docs-prune-and-structure-plan.md).

### D-034 - VietnamWorks automation passed the robots.txt and terms gate

- **Decided:** 2026-07-16 - **Status:** Active.
- The scheduled VietnamWorks path is permitted under the recorded, dated review.
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

### D-017 - Gemini judges evaluation while Groq serves the agent

- **Decided:** 2026-07-03 - **Status:** Active.
- Separating judge and serving load avoids double pressure on the serving provider's free quota.
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
