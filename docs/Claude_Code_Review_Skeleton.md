# Claude Code Review Skeleton

> Status: skeleton only. Do not record findings here until the review pass begins.

## 1. Review Entry Criteria

- [ ] Current branch:
- [ ] Ticket or milestone being reviewed:
- [ ] Intended base branch or parent commit:
- [ ] Files changed by the ticket:
- [ ] Out-of-scope files already dirty before review:
- [ ] Commands already run by the implementer:
- [ ] Reviewer commands to run:

## 2. Source Documents To Read First

- [ ] `research/README.md`
- [ ] Relevant `research/` document for the ticket area:
- [ ] `docs/MVP_Spec.md`
- [ ] `docs/Full_Design_Document.md`
- [ ] `docs/MVP_Technical_Design.md`
- [ ] `docs/Tickets.md`
- [ ] `docs/Repo_Current_State.md`
- [ ] `docs/Known_Issues.md`
- [ ] Prior relevant completion report:

## 3. Review Priority Order

### 3.1 Scope And Intent

- [ ] Does the implementation match exactly one ticket?
- [ ] Are future-ticket features avoided?
- [ ] Are unrelated refactors avoided?
- [ ] Are new dependencies justified by the ticket?
- [ ] Are parameters kept in `config/settings.yaml` where required?
- [ ] Are models kept in `models.py` where required?

### 3.2 Architecture Boundaries

- [ ] API layer owns HTTP and validation only.
- [ ] FastAPI routes do not own LangChain logic.
- [ ] Service layer remains the sole request orchestrator.
- [ ] Agent runtime is the only agent-construction layer.
- [ ] Tools expose natural-language or bounded handles, not raw execution primitives.
- [ ] Tracing and Langfuse concerns stay inside the tracing layer.
- [ ] Ingestion and eval tooling stay out of the request path.
- [ ] Core remains cross-cutting primitives only.

### 3.3 Correctness And Failure Modes

- [ ] Main happy path:
- [ ] Empty or invalid input:
- [ ] External provider failure:
- [ ] Database failure:
- [ ] Config missing or malformed:
- [ ] Concurrency or lifecycle edge:
- [ ] Boundary or limit case:

### 3.4 Security And Abuse Resistance

- [ ] Public endpoint exposure:
- [ ] CORS behavior:
- [ ] Rate limiting behavior:
- [ ] Input size limits:
- [ ] SQL/read-only guarantees:
- [ ] Error-message leakage:
- [ ] Docs/OpenAPI exposure:
- [ ] Headers or UI-specific controls, if applicable:

### 3.5 Data, Schema, And Prompt Contracts

- [ ] Schema changes are reflected in DDL/ORM/models.
- [ ] Schema changes are reflected in prompts/schema context.
- [ ] Schema changes are reflected in fixtures/evals.
- [ ] Field semantics remain truthful.
- [ ] Date fields use date-aware guidance.
- [ ] Nullable/source-derived fields are not overstated.
- [ ] Prompt freeze or guard tests still cover the contract.

### 3.6 Tests And Verification

- [ ] Unit tests cover deterministic logic.
- [ ] API tests cover response shape and error behavior.
- [ ] Runtime/tool tests cover agent-facing seams.
- [ ] Ingestion tests cover transform/load behavior, if touched.
- [ ] Eval tests or fixture tests are updated, if touched.
- [ ] Manual verification checklist is present.
- [ ] Build/lint/type commands are appropriate for the changed area.

### 3.7 Documentation And State Updates

- [ ] `docs/Completion_Reports.md` updated, if this is a completed ticket.
- [ ] `docs/Manual_Verification_Guide.md` updated, if behavior changed.
- [ ] `docs/Repo_Current_State.md` updated, if ticket completion state changed.
- [ ] `docs/Known_Issues.md` updated for open follow-ups only.
- [ ] `docs/Resolved_Issues.md` updated for closed register items only.
- [ ] README or design docs updated only when their owned concern changed.

## 4. Per-Area Review Checklist

### 4.1 API Layer

- [ ] `src/api/app.py`
- [ ] `src/api/routes/`
- [ ] `src/api/schemas.py`
- [ ] API tests:

### 4.2 Application Service

- [ ] `src/agents/service.py`
- [ ] Service tests:

### 4.3 Agent Runtime

- [ ] `src/agents/runtime/factory.py`
- [ ] `src/agents/runtime/react_agent.py`
- [ ] `src/agents/runtime/provider.py`
- [ ] `src/agents/runtime/prompts.py`
- [ ] `src/agents/runtime/middleware.py`
- [ ] Runtime tests:

### 4.4 Tools And Query Services

- [ ] `src/agents/tools/`
- [ ] `src/services/query/`
- [ ] Tool/query tests:

### 4.5 Tracing

- [ ] `src/agents/tracing/langfuse.py`
- [ ] Trace metadata and no-op behavior:
- [ ] Tracing boundary checks:

### 4.6 Core

- [ ] `src/core/config.py`
- [ ] `src/core/db.py`
- [ ] `src/core/checkpointer.py`
- [ ] `src/core/errors.py`
- [ ] Core tests:

### 4.7 Ingestion

- [ ] `src/services/ingestion/models.py`
- [ ] `src/services/ingestion/sources/`
- [ ] `src/services/ingestion/normalize/`
- [ ] `src/services/ingestion/transform.py`
- [ ] `src/services/ingestion/raw_store.py`
- [ ] `src/services/ingestion/clean_store.py`
- [ ] Ingestion tests:

### 4.8 Evaluation Harness

- [ ] `evals/harness.py`
- [ ] `evals/judge.py`
- [ ] `evals/writeback.py`
- [ ] `evals/goldens/`
- [ ] `evals/fixtures/`
- [ ] Eval tests:

### 4.9 Configuration And Prompts

- [ ] `config/settings.yaml`
- [ ] `config/prompts.yaml`
- [ ] `config/ingestion.yaml`
- [ ] `config/tech_vocabulary.yaml`
- [ ] Config tests:

### 4.10 Scripts, Docker, And Infra

- [ ] `scripts/`
- [ ] `docker-compose.yml`
- [ ] `docker/Dockerfile`
- [ ] `infra/`
- [ ] Operational commands:

## 5. Finding Template

### Finding

- Severity:
- File and line:
- Category:
- What is wrong:
- Why it matters:
- Suggested fix:
- Test or verification needed:
- Follow-up ticket, if out of scope:

## 6. Review Exit Criteria

- [ ] Findings are ordered by severity.
- [ ] Each finding includes file and line evidence.
- [ ] False positives and assumptions are called out.
- [ ] Out-of-scope issues are separated from ticket-blocking issues.
- [ ] Commands run and results are recorded.
- [ ] Manual verification gaps are recorded.
- [ ] No unrelated fixes are made during review.
