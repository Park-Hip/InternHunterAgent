# Completion Reports

Per-ticket outcome records (`CLAUDE.md §5`). Append-only: each entry captures what changed,
files touched, test results, and follow-ups for one ticket. This is the durable record;
`Repo_Current_State.md` holds only the milestone-level snapshot and links here.

Entries are kept to the durable summary — full implementation detail lives in the code and
git. **Older milestones (M0–M14) are archived** in
[`archive/Completion_Reports_Archive.md`](archive/Completion_Reports_Archive.md); this file
holds the current deploy-era stack (M16+).

## Entry format
One entry per ticket: **Did** (what changed) · **Files** (key paths) · **Tests** (result) ·
**Follow-up** (where it went). Longer standalone entries may use the full `CLAUDE.md §5`
field list (Summary / Files / Commands / Build & test / Manual verification / Risks /
Follow-ups / Docs).

Every entry records the paths a ticket touched **on the day it shipped**. Later tickets move files,
so those paths are dated evidence rather than a live index, and the whole file is exempt from the
link-path check under the historical-audit rule in
[Documentation Conventions](Docs_Conventions.md).

<!-- lint-allow-link-path:begin -->

---

## T0025.4 follow-up fixes

- **Summary:** Hardened the local viewer against missing or corrupt run artifacts, browser storage
  failures, and unreadable row dumps.
  Added `--sample` so the viewer can be demonstrated and manually verified without serving-model
  quota.
- **Files:** `evals/viewer.py`, `evals/test_viewer.py`, `docs/Manual_Verification_Guide.md`,
  `docs/Completion_Reports.md`, and `docs/Repo_Current_State.md`.
- **Commands:** Ran Ruff, `git diff --check`, direct sample-generation assertions, and the
  missing-file CLI path with the available system Python.
- **Build/test:** Direct checks passed.
  The repository pytest environment remains unavailable because its uv-managed interpreter cannot
  be started.
- **Manual verification:** Run `uv run python -m evals.viewer --sample`, open the generated
- `trace-viewer-sample.html`, navigate between both turns, and verify the table rows and
  note-storage fallback behavior.
- **Risks:** Browser storage remains best-effort by design; notes cannot persist when site data is
  blocked, but navigation remains available and the page reports the limitation.
- **Follow-ups:** T0025.5 remains the next evaluation ticket.
- **Docs:** Updated the manual checklist and available-script snapshot.

## T0025.4 - Trace viewer and first-upstream-failure rule

- **Summary:** Added a dependency-free local HTML viewer for persisted scenario-driver records.
  It presents one turn at a time with routing, generated SQL, rows, final answer, trace id, and
  an operator note field whose contents persist in browser local storage.
  The viewer and manual checklist state the first-upstream-failure rule: annotate the earliest
  wrong seam only and stop.
- **Files:** `evals/viewer.py`, `evals/test_viewer.py`, `docs/Manual_Verification_Guide.md`,
  `docs/Completion_Reports.md`, and `docs/Repo_Current_State.md`.
- **Commands:** Ran the focused viewer test and Ruff checks through the repository Python tooling.
  A later repeat was blocked by the known local uv interpreter/cache process failure.
- **Build/test:** Three focused viewer tests passed before the uv environment failure was triggered.
  Ruff passed for `evals/viewer.py` and `evals/test_viewer.py`.
- **Manual verification:** Generate the viewer from a recorded run, open the HTML locally, inspect
  all three seams, annotate one turn, reload, and confirm the note survives.
- **Risks:** Browser local storage is scoped to the local file/browser profile.
  Clearing browser data
  removes notes.
  The viewer intentionally does not score or grade records.
- **Follow-ups:** T0025.5 owns deterministic reference-SQL execution accuracy.
- **Docs:** Added the T0025.4 checklist and updated the repository state snapshot.

## T0025.3 - Scenario driver over the existing harness

- **Summary:** Added an in-process scenario driver with frozen-registry loading, probe repeat
  counts, capture-only execution, per-turn three-seam persistence, manifests, retry events,
  checkpoint/resume, quota-safe partial runs, and comparable-run checks.
- **Files:** `evals/driver.py`, `evals/test_driver.py`, `.gitignore`, `docs/Repo_Current_State.md`,
  and this report.
- **Commands:** Ran `uv run pytest -q evals/test_driver.py`, `uv run ruff check
  evals/driver.py evals/test_driver.py`, and attempted `uv run python -m evals.driver --help`.
- **Build/test:** Four focused driver tests passed and Ruff passed.
  The CLI help attempt was blocked by a pre-existing local uv cache permission conflict.
- **Manual verification:** Run two selected scenarios with `uv run python -m evals.driver --ids
  SAF-...,... --output evals/runs/run.json` and confirm the manifest and `sql_text` fields.
  Interrupt a run, then use `--resume` and confirm completed records are skipped.
  Change `config/prompts.yaml`, create a second run, and confirm `diff` rejects it as
  incomparable.
- **Risks:** Live provider quota, fixture Postgres availability, and the existing local uv cache
  permission issue remain environmental risks.
- **Follow-ups:** T0025.4 should build the local viewer over these records.
- **Docs:** `Repo_Current_State.md` now points to the driver and the next ticket.


## T0022.7 - Rebuild repository state and true up registers

- **Summary:** Rebuilt `Repo_Current_State.md` as an 85-line current-facts sheet. It retains the
  recovery tags, unverified stash, and M15 behavior-track caveat while linking operational facts to
  `Operations.md`. Moved three closed items to `Resolved_Issues.md`, removed five duplicate stubs,
  and rebuilt the eight-category open-register index from the resulting entries.
- **Files:** `docs/Repo_Current_State.md`, `docs/Known_Issues.md`, `docs/Resolved_Issues.md`,
  `docs/Tickets.md`, and this report.
- **Commands:** inspected the ticket research, Git branch, tags, stash, registers, and documentation
  linter; counted entries from the final register; ran `uv run python scripts/docs_lint.py --check
  line-length` and `--check link-path`.
- **Build/test:** `uv run pytest -q tests/test_docs_lint.py` passed (15 tests), and `uv run ruff
  check .` passed. The rebuilt state file is 85 lines and has no non-table line-length findings.
  `Known_Issues.md` has three closed-state headlines, all intentionally partially or mostly closed.
  The full `uv run pytest -q` attempt timed out after 64 seconds without output. The full
  line-length
  and link-path checks still report findings in out-of-scope research and legacy documentation,
  including the two `docs/README.md` line-length findings owned by T0022.9.
- **Manual verification:** open `Repo_Current_State.md` and confirm the branch, head, live URL, and
  next ticket are visible immediately. Run `Select-String -Pattern 'RESOLVED' docs/Known_Issues.md`
  and confirm only the three partial-state headlines remain. Compare each index count with a fresh
  section count and locate the three moved entries in `Resolved_Issues.md`.
- **Risks:** archived resolution notes retain historic statements. This ticket relocates them and
  does not re-triage their factual claims.
- **Follow-up:** T0022.8 owns research pruning and broken research links. T0022.9 owns the remaining
  live index cleanup and blocking documentation CI enforcement.
- **Docs updated:** `Repo_Current_State.md`, both issue registers, `Tickets.md`, and this report.

## T0022.6 - History split

- **Summary:** Moved completed ticket specifications into `Tickets_Archive.md` and reusable
  completed checklists into `Manual_Verification_Archive.md`. The live roadmap retains its full
  index, open work, and the current verification checklist. Reconciled the stale keep-alive record:
  the ICT cron-job.org `/api/v1/health` job is running, and idle Neon pool connections do not keep
  compute awake.
- **Files:** `docs/Tickets.md`, `docs/archive/Tickets_Archive.md`,
  `docs/Manual_Verification_Guide.md`, `docs/archive/Manual_Verification_Archive.md`,
  `docs/Operations.md`, `docs/Known_Issues.md`, `docs/Repo_Current_State.md`, `docs/README.md`,
  `docs/Completion_Reports.md`, `scripts/docs_lint.py`, and textual-pointer references.
- **Commands:** ran focused documentation lint checks, automatic reflow, pointer audit, docs-lint
  tests, Ruff, and `git diff --check`.
- **Build/test:** Ruff and the `encoding`, `agent-parity`, and `stack` docs-lint checks passed.
  Focused docs-lint tests could not run because the checked-in virtualenv points to a missing uv
  Python installation. The full `link-path` check remains non-zero because of pre-existing stale
  paths outside this ticket's scope.
- **Manual verification:** open `Tickets.md` and find the current T0022 work in the first two
  screenfuls; open `Manual_Verification_Guide.md` and find T0021.1 immediately; follow one
  archive-index entry; and confirm the keep-alive facts in `Operations.md`.
- **Risks:** no browser session was available to inspect cron-job.org directly. The scheduled
  timezone and endpoint are recorded from maintainer-supplied facts in the ticket.
- **Follow-up:** T0022.7 owns the full state-sheet rebuild and resolved-issue eviction. T0022.8
  owns research pruning. T0022.9 owns the remaining index and CI enforcement work.
- **Docs updated:** `Tickets.md`, `Manual_Verification_Guide.md`, both new archive files,
  `Operations.md`, `Known_Issues.md`, `Repo_Current_State.md`, `README.md`, and this report.

## T0022.5 - Operations consolidation

- **Summary:** Added `Operations.md` as the sole operational reference for deployment, environment
  variables, database procedures, cron state, keep-alive constraints, and incident response.
  Moved the local database-reset procedure out of the root README and reduced duplicated live
  topology statements to links.
- **Files:** `docs/Operations.md`, `README.md`, `docs/Tech_Stack.md`, `docs/README.md`,
  `docs/T0020.4_Cron_Activation_Runbook.md`, `docs/Repo_Current_State.md`,
  `scripts/docs_lint.py`, this report, and `docs/Tickets.md`.
- **Commands:** ran docs-lint checks and reflow, focused documentation-lint tests, Ruff, and
  `git diff --check`.
- **Build/test:** 15 focused docs-lint tests passed; Ruff passed; `stack` and `encoding`
  checks passed. The runbook and new operations guide have no line-length findings.
- **Manual verification:** compare every runbook sign-off row with its pre-change state; confirm
  the env-var table against `render.yaml` and `.env.example`; use the local reset procedure with
  Docker; and confirm the cron's direct, non-pooled Neon host requirement can be found within
  `Operations.md`.
- **Risks:** cron activation gates and dashboard-managed secrets intentionally remain maintainer
  actions. The schedule remains disabled.
- **Follow-up:** T0022.6 owns the archive split. T0022.7 will rebuild the remaining state sheet.
- **Docs updated:** `README.md`, `docs/Operations.md`, `docs/Tech_Stack.md`, `docs/README.md`,
  `docs/T0020.4_Cron_Activation_Runbook.md`, `docs/Repo_Current_State.md`,
  `docs/Completion_Reports.md`, and `docs/Tickets.md`.

## T0022.3 - Structure-safe reflow of stable documentation

- **Summary:** Added prefix-aware Markdown reflow and YAML-frontmatter protection, then
  mechanically wrapped the ticket's stable documentation set. The one residual code-span
  ellipsis was repaired separately before reflow.
- **Files:** `scripts/docs_lint.py`, `tests/test_docs_lint.py`, both agent instruction files,
  eight stable docs under `docs/`, `evals/v1_scenario_matrix.md`, and two stable research docs.
- **Commands:** ran the focused docs-lint tests, Ruff, encoding and parity checks, `--fix`,
  line-length checks, word-diff review, and `git diff --check`.
- **Build/test:** 11 focused tests passed; Ruff passed; encoding and agent parity passed.
  The full suite was stopped after four minutes without output, so it is inconclusive.
- **Manual verification:** preview `MVP_Spec.md`, `Known_Issues.md`, and
  `Agent_Behavior_Spec.md`; run `uv run python scripts/docs_lint.py --check line-length`;
  confirm the remaining findings are outside this ticket's scope.
- **Risks:** no word-level content changes were found in the dedicated reflow commit. Remaining
  line-length findings belong to documents deferred to T0022.4-T0022.9.
- **Follow-up:** T0022.4 is the next recommended ticket; it owns the root README and
  `Tech_Stack.md`.
- **Docs updated:** `docs/Completion_Reports.md`, `docs/Repo_Current_State.md`, and
  `docs/Tickets.md`.

## T0022.2 - Encoding repair, agent-surface parity, and orphan cleanup

- **Summary:** Repaired the T0019.10 mojibake without reflowing prose, confirmed agent-file
  parity, synchronized the shared skill instructions while retaining Codex's manifest, removed
  the disposable milestone scratchpad after tagging it, and replaced the stale Langfuse README.
- **Files:** `docs/Completion_Reports.md`, `AGENTS.md`/`CLAUDE.md` (verified only),
  `skills/generate-ticket-prompt/SKILL.md`, `skills/generate-ticket-prompt/agents/openai.yaml`
  (retained), deleted `milestone/data-ingestion-stage.md`, `infra/langfuse/README.md`, <!-- archived-on-tag -->
  `scripts/docs_lint.py`, `tests/test_docs_lint.py`, `docs/Tickets.md`, and this report.
- **Commands:** verified exact repair counts before replacement; ran `uv run pytest
  tests/test_docs_lint.py -q`, `uv run ruff check scripts/docs_lint.py tests/test_docs_lint.py`,
  and the `encoding` and `agent-parity` checks.
- **Build/test:** 7 focused tests passed; Ruff passed; `encoding` and `agent-parity` both pass.
- **Manual verification:** confirm `git tag --list archive/milestone-scratchpad` lists the tag,
  `Test-Path milestone` is false, and the root skill still has `agents/openai.yaml`.
- **Risks:** 83 known `link-path` findings remain out of scope. The full suite was not rerun;
  its most recent attempt in T0022.1 exceeded the 120-second command limit.
- **Follow-up:** T0022.3 handles mechanical reflow; T0022.6 handles broader archive structure.
- **Docs updated:** `docs/Completion_Reports.md`, `docs/Repo_Current_State.md`,
  `docs/Tickets.md`, and `infra/langfuse/README.md`. <!-- archived-on-tag -->

## T0022.1 - Docs lint harness, conventions, and warn-only CI gate

- **Summary:** Added the dependency-free documentation linter with `line-length`, `link-path`,
  `encoding`, and `agent-parity` checks; documented the conventions; and added a non-blocking
  CI job. The encoding check was corrected before merge to match the actual `â€` and `â†`
  codepoints in the repository. Existing findings are intentionally not repaired in this ticket.
- **Files:** `scripts/docs_lint.py`, `tests/test_docs_lint.py`, `docs/Docs_Conventions.md`,
  `.github/workflows/ci.yml`, `docs/Repo_Current_State.md`, and this report.
- **Commands:** `uv run pytest tests/test_docs_lint.py -q`; `uv run ruff check
  scripts/docs_lint.py tests/test_docs_lint.py`; `uv run python scripts/docs_lint.py --check
  agent-parity`; `uv run python scripts/docs_lint.py --stat`.
- **Build/test:** 5 focused tests passed; Ruff passed; agent parity passed. The corrected
  encoding check exits 1 on 18 actionable existing findings; 11 further raw occurrences are
  exempt inside backticked code spans. Baseline: 48 tracked
  or unignored Markdown files, 1,490,851 bytes, 3,200 lines over 100 characters, and 1,564 over
  200 characters.
- **Manual verification:** run `uv run python scripts/docs_lint.py --stat`; run each individual
  `--check`; confirm the GitHub Actions `docs` job reports its findings without blocking a PR.
- **Risks:** the linter is warn-only by design until T0022.9; the existing documentation backlog
  still makes a bare run exit non-zero.
- **Follow-up:** T0022.2 repairs the current encoding/parity/orphan findings. T0022.3 handles
  mechanical reflow. T0022.9 turns the job into a blocking CI gate.
- **Docs updated:** `docs/Docs_Conventions.md`, `docs/Repo_Current_State.md`, and this report.

## Milestone 16 — Security Posture (Public-Endpoint Hardening)
- **T0016.1 — CORS middleware (config-driven, credential-less).**
  - **Did:** added an `api.cors` block to `config/settings.yaml` (credential-less defaults: empty
    `allowed_origins`, `allow_credentials: false`, methods `GET/POST/OPTIONS`); `src/api/app.py`
    registers `CORSMiddleware` before router includes; added `create_app(...)` so focused tests
    build a CORS app without opening the lifespan/runtime/DB.
  - **Files:** `config/settings.yaml`, `src/api/app.py`, `tests/api/test_cors.py`.
  - **Tests:** `tests/api/test_cors.py tests/api/test_query.py tests/api/test_startup_config.py`
    pass (allowed preflight returns CORS headers, disallowed omits them).
  - **Follow-up:** the deployed UI origin is still intentionally unset — fill it into
    `config/settings.yaml` when the demo host is known.
  - **Correction (2026-07-13):** no `T0016.5 Langfuse secrets hygiene` ticket exists; superseded
    when deploy moved to Langfuse Cloud Hobby and T0016 was scoped to CORS / rate-limit / input-cap
    / `/docs`.

- **T0016.2 — Per-IP rate limiting + graceful 429/quota degradation.**
  - **Did:** added `slowapi` + `api.rate_limit: "15/minute"`; `app.py` builds a per-app
    `Limiter(key_func=get_remote_address)` + friendly `RateLimitExceeded` handler, applied only to
    `POST /api/v1/agent/chat` (health not decorated). `errors.py` adds `ProviderBusyError` +
    `BUSY_MESSAGE` + a 429/quota/timeout classifier; `service.py` translates provider pressure to a
    friendly busy response, preserving the generic 500 for real bugs.
  - **Files:** `pyproject.toml`/`uv.lock`, `config/settings.yaml`, `src/api/app.py`,
    `src/core/errors.py`, `src/agents/service.py`, `src/api/routes/query.py`,
    `tests/api/test_rate_limit.py`, `tests/api/test_query.py`.
  - **Tests:** `16 passed` (focused API suite).
  - **Follow-up:** live provider-quota behavior not exercised — confirm the classifier with
    credentials when available.

- **T0016.3 — Request input hardening (length cap).**
  - **Did:** `api.max_query_chars: 2000` in config + matching static `DEFAULT_MAX_QUERY_CHARS =
    2000` `Field(max_length=...)` on `QueryRequest.query`. Oversized bodies fail with HTTP 422
    before the route runs (not logged, service not awaited); blank input keeps the existing 400
    path.
  - **Files:** `config/settings.yaml`, `src/api/schemas.py`, `tests/api/test_query.py`.
  - **Tests:** `18 passed`; ruff clean.
  - **Follow-up:** the cap is static in code and mirrored in config — if the value changes later,
    update both or add a validated config loader.

- **T0016.4 — `/docs` exposure decision + minimal security headers.**
  - **Did:** `api.docs_enabled: true` makes Swagger/ReDoc/OpenAPI an explicit config choice;
    `app.py` wires `docs_url`/`redoc_url`/`openapi_url` together (all three removed when disabled),
    flippable via `create_app(docs_enabled=...)`. No security-header middleware added by design
    (still API-only until a same-origin HTML UI is served).
  - **Files:** `config/settings.yaml`, `src/api/app.py`, `tests/api/test_docs_exposure.py`.
  - **Tests:** focused API suite passes (enabled→200, disabled→404 for all three).
  - **Follow-up:** when FastAPI later serves an HTML UI, add frame-protection headers in that ticket
    (done in T0018.2).

## Milestone 17 — Streaming Response Delivery
- **T0017.1 — Runtime streaming + no-leak filter.**
  - **Did:** added `AgentRuntime.astream(...)` beside `ainvoke` using the stable `agent.astream(...,
    stream_mode="messages")` surface; emits transport-agnostic `token` dicts then one trailing
    `metadata` dict after Langfuse flush. Two-gate no-leak filter: only `langgraph_node == "model"`
    survives, and chunks with empty/non-string content or any `tool_call_chunks` are dropped.
    Enabled `agent.groq.streaming: true` + a system-prompt line to not narrate before tool calls.
  - **Files:** `src/agents/runtime/react_agent.py`, `config/settings.yaml`, `config/prompts.yaml`,
    `tests/agents/runtime/test_react_agent.py`, `research/archive/streaming-implementation-plan.md`.
  - **Tests:** `9` focused stream tests pass; full suite `273 passed, 7 skipped, 19 deselected`.
  - **Follow-up:** live tool-using stream probe BLOCKED (no Groq creds / DB in sandbox) →
    `Known_Issues.md`.

- **T0017.2 — Streaming service + SSE endpoint.**
  - **Did:** `stream_agent_response(...)` in `service.py` — transport-agnostic async generator
    emitting `session` → `token`* → (`metadata` held until after the empty-answer fallback decision)
    / in-band `error` (carrying `BUSY_MESSAGE`, no `str(exc)` leak) → terminal `done`. `POST
    /api/v1/agent/chat/stream` reuses the chat limiter, keeps the pre-stream blank-query 400, and
    returns `EventSourceResponse` with explicit `json.dumps` framing + anti-buffering headers
    (`Cache-Control: no-cache`, `X-Accel-Buffering: no`). Verified FastAPI 0.136.3's
    `ServerSentEvent` isn't auto-encoded, hence the explicit framing.
  - **Files:** `src/agents/service.py`, `src/api/routes/query.py`, `src/api/schemas.py`,
    `tests/api/test_stream.py`.
  - **Tests:** `test_stream.py` `4 passed`; API suite `24 passed`; full suite `277 passed, 7
    skipped, 19 deselected`.
  - **Follow-up:** live `curl -N` check BLOCKED (needs Groq creds + seeded Postgres) →
    `Known_Issues.md`.

## Milestone 18 — Clickable Demo (UI + go-live)
- **T0018.1 — Go-live glue: server session IDs, data disclaimer, DB readiness probe.**
  - **Did:** UUID4 session ids minted when omitted in both one-shot and streaming paths (client ids
    kept as advisory); `api.demo.data_snapshot_date: "2026-07-14"` as the disclaimer source of
    truth; `GET /api/v1/ready` runs `session_factory()` + `text("SELECT 1")` and returns readiness +
    snapshot date (or 503), included outside the chat limiter so probes aren't rate-limited; fixed
    the `/health` `async def` typo.
  - **Files:** `config/settings.yaml`, `src/api/routes/health.py`, `src/api/schemas.py`,
    `tests/api/test_ready.py`, `tests/agents/test_service.py`, `tests/api/test_stream.py`.
  - **Tests:** focused `11 passed`; API suite `29 passed`; full suite `282 passed, 7 skipped, 19
    deselected`; ruff clean.
  - **Follow-up:** `data_snapshot_date` must be updated whenever the demo corpus changes; live
    `/ready` against a running Postgres not exercised in-sandbox.

- **T0018.2 — Same-origin static serving + frame protection.**
  - **Did:** `create_app()` registers a pure-ASGI frame guard injecting `X-Frame-Options: DENY`,
    includes API/docs routes first, then mounts `StaticFiles(directory=src/api/static, html=True)`
    at `/`. The root page is a deliberately minimal placeholder (no CSS/JS/UI behavior yet).
  - **Files:** `src/api/app.py`, `src/api/static/` (placeholder),
    `tests/api/test_static_serving.py`.
  - **Tests:** `test_static_serving.py` `4 passed`; `test_stream.py` `5 passed`; API suite `33
    passed`; full suite `286 passed, 7 skipped, 19 deselected`.
  - **Follow-up:** none.
  - *(Backfilled from `Repo_Current_State` during the 2026-07-15 docs-hygiene pass — this ticket
    originally had no completion entry.)*

- **T0018.3 — Editorial streaming chat UI (vanilla).**
  - **Did:** three static assets — `index.html` + `styles.css` + `app.js` — replace the placeholder
    with the vanilla Editorial demo page (system serif stack, hairline rules, restrained vermilion
    accent, light theme; no build step, no framework, no new dependency, CSP-clean). Consumes `POST
    /api/v1/agent/chat/stream` via `fetch()` + a `ReadableStream` reader + a ~30-line in-app SSE
    parser dispatching `session`/`token`/`metadata`/`error`/`done` (stops on `done`, no reconnect).
    Reads the disclaimer date from `GET /api/v1/ready`; ships 4 send-on-click honesty chips; pins +
    reuses the server session id; shows `view-trace` only when `trace_url` is non-null; degrades
    mid-stream `error` to a friendly bubble and pre-stream 400/429 to a toast. Preserves the
    `InternHunter` string `test_static_serving` asserts. No backend change.
  - **Files:** `src/api/static/index.html`, `src/api/static/styles.css`, `src/api/static/app.js`.
  - **Tests:** `test_static_serving.py` `4 passed`; API suite `33 passed`; full suite `286 passed, 7
    skipped, 19 deselected`. Rendered + screenshot-verified at 960px and 390px; the mid-stream
    `error` path is code-inspection-only.
  - **Follow-up:** mid-stream `error` bubble, SSE-parser assumptions, and no idle-timeout →
    `Known_Issues.md` § Demo UI (T0018.3).
  - *(Backfilled from `Repo_Current_State` during the 2026-07-15 docs-hygiene pass — this ticket
    originally had no completion entry.)*

## Backend hotfix — SQL-generation reasoning effort
- **Summary:** disabled qwen reasoning only for the hidden SQL-generation model build.
  `AgentProvider.build_model()` now accepts an optional per-call `reasoning_effort` kwarg (omitted
  by default, so the main ReAct agent path is unchanged); `query_clean_jobs.generate_sql()` reads
  `agent.query.sql_generation_reasoning_effort` and passes `"none"` only to the mechanical
  SQL-generation call. Fixes the `[HIGH]` empty-SQL-on-reasoning-heavy-queries issue.
- **Files:** `src/agents/runtime/provider.py`, `src/agents/tools/query_clean_jobs.py`,
  `config/settings.yaml`, `tests/agents/runtime/test_provider.py`,
  `tests/agents/tools/test_query_clean_jobs.py`, plus `docs/Known_Issues.md`,
  `docs/Resolved_Issues.md`, `docs/Repo_Current_State.md`.
- **Build & test:** focused provider/tool suite `15 passed`; ruff clean; full standard suite `296
  passed, 19 deselected, 4 subtests passed`.
- **Manual verification:** live Groq SQL probe, streaming curl, and DeepEval regression BLOCKED (no
  `GROQ_API_KEY`/`GOOGLE_API_KEY` in sandbox; local Postgres `127.0.0.1:5433` was reachable) →
  `Known_Issues.md`.
- **Risks:** covered offline at the construction boundary; live provider behavior still needs
  maintainer credentials.
- **Follow-ups:** salary-sort SQL may need single-currency prompt tuning if it appears in evals;
  maintainer live verification remains blocked on credentials.

## Backend hotfix — Split ReAct-agent and SQL-generation LLM configs
- **Summary:** replaced the shared `agent.groq` model profile plus per-call `reasoning_effort`
  override with two explicit profiles: `agent.react` for the outer ReAct agent and
  `agent.sql_generation` for the nested SQL-generation LLM call. Both profiles expose the same
  fields; only `agent.sql_generation.reasoning_effort: none` is forwarded for SQL generation.
- **Files:** `config/settings.yaml`, `src/agents/runtime/provider.py`,
  `src/agents/runtime/factory.py`, `src/agents/tools/query_clean_jobs.py`,
  `tests/agents/runtime/test_provider.py`, `tests/agents/tools/test_query_clean_jobs.py`, plus
  `docs/Repo_Current_State.md`, `docs/Known_Issues.md`, `docs/MVP_Technical_Design.md`,
  `docs/Completion_Reports.md`, `docs/Manual_Verification_Guide.md`.
- **Commands:** `uv run pytest tests/agents/runtime/test_provider.py
  tests/agents/tools/test_query_clean_jobs.py -q`; `uv run pytest -q`.
- **Build & test:** focused provider/tool suite `16 passed`; full standard suite `297 passed, 19
  deselected, 4 subtests passed`.
- **Manual verification:** confirm config has independent `agent.react` and `agent.sql_generation`
  blocks; confirm `agent_factory()` uses `build_model("react")`; confirm
  `query_clean_jobs.generate_sql()` uses `build_model("sql_generation")`; with maintainer
  credentials and seeded DB, run `generate_sql("List the AI Engineer jobs that require Python,
  sorted by salary descending.")`.
- **Risks:** live Groq behavior still requires maintainer credentials; no prompt, schema, eval
  fixture, API, or UI changes were made for this split.
- **Follow-ups:** none from the config split itself; existing salary-sort prompt-adherence and
  maintainer live-verification notes remain tracked in `Known_Issues.md`.

## T0018.4 — Deploy topology + first public deploy
- **Summary:** first public deploy of the same-origin app + DB + tracing. Confirmed and recorded the
  researched topology (all blank `Decision:` lines in `research/archive/deployment-research-plan.md`
  now
  filled), injected secrets via env vars, loaded a static corpus snapshot into Neon, and verified
  the streamed demo end-to-end at the public URL. **Live: https://internhunteragent.onrender.com**
  (verified 2026-07-16).
- **Topology:** API on **Render** (Docker `docker/Dockerfile`, Singapore, Free instance,
  `WEB_CONCURRENCY=1`, health check `/api/v1/health`, `PORT=8000`) · Postgres on **Neon** (PG17,
  direct `postgresql+psycopg://…` DSN, Singapore, Neon Auth off) · tracing on **Langfuse Cloud Hobby
  (JP)** · CI via **Render auto-deploy on push** to `main` (repointed from `feature/t0018.4-deploy`
  in T0020.2; `render.yaml` now pins the source). Cost: **$0/mo** (hard ceiling $10).
- **Branch prep:** built `feature/t0018.4-deploy` clean off `e4076b2` (kept ReAct/SQL config split)
  + the T0018.3 Editorial UI committed fresh as `7d4cfef`; the T0015.6/.7 provider-A/B phase was
  dumped (reversed + pruned) and parked recoverably at `45d333c` on `feature/t0015.6-provider-ab`.
- **Files/config:** `research/archive/deployment-research-plan.md` (§1–§12 Decision lines),
  `docs/Completion_Reports.md`, `docs/Manual_Verification_Guide.md`, `docs/Repo_Current_State.md`.
  No app-code change was needed — the fixed-port Dockerfile is handled by the `PORT=8000` env var.
  `config/settings.yaml` `api.demo.data_snapshot_date` kept at `2026-07-14` (reflects the corpus,
  not the copy date).
- **Secrets:** `GROQ_API_KEY`, `DATABASE_URL` (Neon), `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`,
  `LANGFUSE_BASE_URL` (code reads `LANGFUSE_BASE_URL`, **not** `LANGFUSE_HOST`) — Render dashboard
  env vars only, never in image/repo. `api.cors.allowed_origins` stays `[]` (same-origin; CORS never
  exercised) — rationale recorded in the deploy plan §7.
- **Data shipped:** static snapshot — Neon loaded with **50 `clean_jobs` + 50 `raw_jobs`** via
  `pg_dump | psql` (direct DSN). Checkpointer tables self-create on boot.
- **Build & verify (against the live public URL):** boot clean (`Application startup complete` →
  checkpointer connected to Neon); `GET /` + `/styles.css` 200 (Editorial UI); streamed a canned
  prompt → `session`→`token`*→`metadata`→`done`, answer *"There are 10 AI Engineer jobs that require
  Python."* (Groq + Neon query working); `trace_url` resolves to the Langfuse JP project;
  `/api/v1/health` + `/api/v1/ready` 20/20 when warm; `/docs` 200; `X-Frame-Options: DENY` present.
- **Risks:** free-tier compound cold start (Render spin-down + Neon suspend) → first request after
  idle can take 1–2 min, and the very first `/ready` during the wake window can 404 briefly (UI
  degrades to a dateless disclaimer; refresh fixes) — infra behavior, not a bug. Static snapshot
  goes stale until the ingestion milestone lands; the honest disclaimer covers this.
- **Follow-ups:** ingestion cron / `is_active` (separate milestone); CI merge-gate on `main`
  (`research/archive/pre-deploy-refinement-plan.md §6i`); external uptime + dead-man's-switch
  monitoring; optional
  custom domain; optional snapshot-date bump. _(Reconciliation update, T0020.1:)_ `main` is no
  longer stuck at T0009 — it was reconciled to `bcc81db` via PR #29, carrying the full M10–M19 chain
  (T0019.6/.8/.9/.10 + the M13/M15 doc rescues). Render's deploy branch is repointed to `main`
  separately in T0020.2.
- *(Annotated 2026-07-16, milestone-close pass.)* The cold start above was re-assessed and is
  **worse than this report models**: it is ~all Render (~60 s), not a Render+Neon compound — Neon
  resumes in ~300–500 ms — and because the UI is same-origin it blanks the *page*, not just the
  first answer. It is now registered as `[MED · OPEN]` in [`Known_Issues.md`](Known_Issues.md) §
  Config, startup & deployment, with a windowed `/health` keep-alive ping as the
  decided-but-unapplied mitigation and the Render-policy check recorded in
  `research/archive/deployment-research-plan.md` §1a. The companion `[HIGH · OPEN]`
  750-instance-hour cliff
  is registered alongside it. Also re-pointed: the `[HIGH · OPEN]` schema-drift issue this ticket
  was expected to absorb was **not** absorbed — `pg_dump | psql` sidestepped drift without adding an
  assertion or migration path — so it moves to the ingestion milestone.

## Milestone 19 — Ingestion Deploy Readiness (live-DB)

## T0019.1 — robots.txt / ToS verification for `ms.vietnamworks.com`
- **RECOMMENDED VERDICT: favorable — pending maintainer confirmation.** Neither trigger of the
  decision rule fires. **T0019.6 (nightly cron) unblocks once the maintainer confirms and .2–.5
  land.** The unfavorable branch (`research/archive/ingestion-milestone-plan.md` §1D) is not
  triggered.
- **Summary:** resolved the `research/archive/deployment-research-plan.md` §11 hard gate before any
  scheduled run exists. Fetched and archived both robots.txt files, located and read the
  VietnamWorks ToS (Vietnamese-only), and recorded a dated Decision in §11. **Doc-only and
  research-only: zero lines of code changed** — nothing under `src/`, `tests/`, `config/`,
  `alembic/`, or `.github/` was touched, and the ingestion pipeline was never run.
- **Findings:**
  - `ms.vietnamworks.com/robots.txt` → **HTTP 404**. The API host the pipeline actually fetches from
    **serves no robots.txt at all**; the 404 body is a JSON gateway error, not a robots file. **This
    is a third outcome the ticket's favorable/unfavorable framing did not enumerate** — it is
    *silence*: neither permission nor refusal, which throws the verdict onto the ToS alone. No
    `Crawl-delay`.
  - `www.vietnamworks.com/robots.txt` → **HTTP 200** (`Last-Modified: 11 May 2026`). One
    `User-agent: *` group, no `Disallow: /`, no rule matching `/job-search/`, no `Crawl-delay`.
    Disallows only profile/login/apply/print/AJAX/ad paths — the pipeline touches none. Context
    only; different host from the API.
  - **ToS** (https://www.vietnamworks.com/thoa-thuan-su-dung, Vietnamese only, **no last-updated
    date shown**): **no automated-access clause exists.** `robot`, `spider`, `crawler`, `crawl`,
    `scrape`, `API`, `giao diện lập trình`, `dịch ngược`, `trích xuất`, `hàng loạt` all return
    **zero matches**. The one "tự động" (automated) clause governs **bulk account registration**,
    not content access — and the pipeline registers no account (`userId: 0`). Sections read in full:
    §3, §4, §5, §7, §9.
- **Decision rule applied:** unfavorable requires robots.txt disallowing `/job-search/` for `*`
  **or** a ToS clause explicitly prohibiting automated access. Neither holds. Absence of robots.txt
  is not a disallow; absence of a ToS clause is not a prohibition. → **favorable**.
- **⚠️ The one caveat the maintainer must weigh** (registered `[MED · DECISION]` in
  `Known_Issues.md`; it does **not** change the verdict): ToS **§7** restricts what may be done with
  content *once obtained* — *"bạn không được quyền thay đổi, sao chép, … công bố, … hiển thị hoặc
  chuyển giao, hoặc khai thác nhằm mục đích thương mại bất kỳ phần nào của nội dung"* ("you are not
  entitled to modify, copy, … publish, … display or transfer, or commercially exploit any part of
  the content"), carving out copies *"để dùng nội bộ"* ("for internal use"). This is a
  **retention/display** constraint, not an **access** one, so it does not trigger the rule — but the
  pipeline stores postings in a DB and the demo displays them publicly. **Crucially it is not a
  reason to park the cron:** the already-deployed static snapshot raises this exact question
  **today**, independently of any schedule; T0019.6 changes refresh frequency, not whether the
  corpus is republished. Cheapest partial step (per §7's own wording): attribute VietnamWorks and
  link each posting's source URL.
- **Files created:** `research/experiments/vietnamworks_robots_2026-07-16.txt`,
  `research/experiments/vietnamworks_www_robots_2026-07-16.txt` (both verbatim bodies with source
  URL / fetch date / HTTP status / response headers in a `#` header),
  `research/experiments/vietnamworks_tos_excerpt_2026-07-16.md` (verbatim Vietnamese +
  explicitly-labeled English translations, negative-search record, section list).
- **Files changed:** `research/archive/deployment-research-plan.md` (§11 — new dated Decision
  appended; the
  prior `Decision (2026-07-16)` line left **intact**, its final sentence superseded; the stale "⚠️
  Unverified — needs manual check" bullet and the companion "Action required before production" line
  updated to point at the new record), `docs/Tickets.md` (T0019.6 blocked-on marker),
  `docs/Known_Issues.md` (2 entries + category count 7→9), `docs/Repo_Current_State.md`,
  `docs/Completion_Reports.md`.
- **Commands:** `curl -sS -D - https://ms.vietnamworks.com/robots.txt`; `curl -sS -D -
  https://www.vietnamworks.com/robots.txt`; `curl -sS
  https://www.vietnamworks.com/thoa-thuan-su-dung` (+ tag-strip and keyword search); byte-comparison
  of each archive against its live fetch; verbatim-verification of every quoted clause against the
  fetched page. **No pipeline run, no build, no test run.**
- **Build & test:** **not applicable — doc-only ticket; no build or test was run and none is
  claimed.** No code path, dependency, or config was touched, so the existing suite is unaffected.
  Verification performed instead: both archives confirmed **byte-identical** to their live fetches
  (BOM and CRLF preserved), and **every** Vietnamese clause quoted in the excerpt and §11 was
  confirmed present **verbatim** in the fetched page (elisions marked `[…]`; 475 chars elided in the
  §3 quote, order preserved).
- **Manual verification:** (1) `git diff --name-only` → only `research/**` and `docs/**`. (2) `ls
  research/experiments/*robots*` → both dated copies exist, non-empty. (3) `curl -sS -o - -w "\nHTTP
  %{http_code}\n" https://ms.vietnamworks.com/robots.txt` → 404 + JSON gateway body, matching the
  archive; same for the www host → 200 + matching body. (4)
  `research/archive/deployment-research-plan.md`
  §11 → new Decision present, marked *pending maintainer confirmation*, every claim traceable to an
  archived file. (5) Open https://www.vietnamworks.com/thoa-thuan-su-dung → loads; spot-check a
  quote by searching the page for `Hoạt động không đúng mục đích`. (6) `grep -n "T0019.1"
  docs/Tickets.md` → T0019.6's marker reflects the outcome.
- **Risks:** (a) **the verdict is a point-in-time fetch** — the API host has no robots.txt *now*,
  and the ToS shows no last-updated date, so neither can be diffed for change; an unattended nightly
  cron would keep fetching through a newly published `Disallow` (registered `[LOW · NOTE]`; the
  dated archives exist to make a re-check cheap). (b) The ToS §7 republishing caveat above
  (registered `[MED · DECISION]`). (c) Translations are mine, not official — the ToS is
  Vietnamese-only; the verbatim Vietnamese is authoritative and archived so the maintainer can
  verify independently. (d) **This is a recommended verdict, not a legal opinion**; the maintainer
  owns the call.
- **Follow-ups:** maintainer confirms the verdict (gates T0019.6 only — .2–.5, .7, .8 proceed
  regardless); decide the public demo's attribution/posture per the `[MED · DECISION]` entry (own
  ticket if actioned, **not** folded into T0019). Both registered in `Known_Issues.md`. **No
  conditions to implement:** no `Crawl-delay` exists on either host, so the pipeline's `0.6 s` delay
  and daily cadence stand unchanged — nothing for T0019.4/.6 to honor beyond keeping off the paths
  `www` disallows (it already does).
- **Docs updated:** `research/archive/deployment-research-plan.md` §11, `docs/Tickets.md`,
  `docs/Known_Issues.md`, `docs/Repo_Current_State.md`, this file.
  `research/archive/ingestion-milestone-plan.md` deliberately **not** touched (its §1D prescribes
  both
  branches; this ticket executes it). **Left stale on purpose — outside this ticket's allowed
  files:** `research/archive/data-ingestion-stage.md` §4's robots.txt bullet carries a *"Status
  2026-07-16 —
  still unverified for `ms.vietnamworks.com`, and now a hard gate"* line, which the §11 record now
  answers. Worth re-pointing at §11 when that file is next edited; flagged rather than fixed, per
  `CLAUDE.md` §1.
- **Working-tree note (not this ticket's work):** the branch was cut from `feature/t0018.4-deploy`
  with **pre-existing uncommitted changes** already present from the prior T0019-scoping session —
  `docs/Tickets.md` (the T0019.1–.8 scoping, ~137 lines), `docs/MVP_Technical_Design.md`,
  `research/archive/data-ingestion-stage.md`, and the untracked
  `research/archive/ingestion-milestone-plan.md`. Only
  the single T0019.6 marker line in `docs/Tickets.md` is mine; `MVP_Technical_Design.md` and
  `research/archive/data-ingestion-stage.md` were **not** touched by this ticket despite appearing
  in `git status`.
  Worth committing that scoping work separately from this gate.

## T0019.2 — Alembic adoption: baseline migration + env wiring
- **Summary:** adopted Alembic as the forward path for schema change. `scripts/reset_db.sql` (DROP +
  recreate) stops being the de-facto migration strategy — that was only acceptable while
  `raw_jobs`/`clean_jobs` were fully reproducible, which stops holding once T0019.3 lands
  accumulating, irreplaceable postings. Added Alembic scaffolding, a hand-written baseline migration
  that reproduces the exact current schema (cross-checked against `scripts/init_db.sql`), and
  aligned the ORM's `id` columns to the DB's actual `BIGINT GENERATED ALWAYS AS IDENTITY` (was
  `BIGSERIAL`-shaped metadata, a pre-existing metadata/reality mismatch this ticket had to fix so
  the baseline wouldn't diverge from the deployed schema).
- **Files created:** `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`, `alembic/README`,
  `alembic/versions/f3a1c9d2e7b4_baseline_schema.py`, `tests/migrations/test_baseline_roundtrip.py`.
- **Files changed:** `pyproject.toml` (added `alembic>=1.14` to `[project].dependencies`),
  `uv.lock`, `src/services/ingestion/models.py` (`RawJob.id`/`CleanJob.id` →
  `mapped_column(BigInteger, Identity(always=True), primary_key=True)`, dropped
  `autoincrement=True`; metadata-only, no DDL against existing data, no other columns touched),
  `scripts/reset_db.sql` (header comment only — now states destructive/local-dev-only, prod goes
  through Alembic, must never point at Neon), `docs/archive/Manual_Verification_Archive.md` (new
  `### T0019.2:
  Alembic adoption` entry with checklist A–F), `docs/Repo_Current_State.md` (§ Available scripts —
  `alembic current`/`alembic history`/`alembic upgrade head` added, `reset_db.sql` line annotated,
  `init_db.sql` line notes the eval-fixture-loader dependency), `docs/Known_Issues.md` (1 new entry
  + category count 9→10).
- **`alembic/env.py` details:** imports `settings` from `src.core.config` and `Base` from
  `src.services.ingestion.models`; `target_metadata = Base.metadata`; resolves the DSN as
  `os.environ.get("ALEMBIC_DATABASE_URL") or settings.DATABASE_URL` so migrations can be pointed at
  Neon's direct, non-pooled endpoint independently of the app's runtime DSN; `alembic.ini`'s
  `sqlalchemy.url` is commented out — never committed. `run_migrations_online()` sets
  `pool_pre_ping=True`. Repo root is prepended to `sys.path` so `from src...` resolves regardless of
  invocation cwd.
- **Baseline migration:** `f3a1c9d2e7b4_baseline_schema.py`, `down_revision = None`, hand-written
  (not autogenerate-derived — autogenerate against an already-matching DB produces an empty diff and
  wasn't trustworthy at this scale). Creates `raw_jobs` (6 columns + unique `(source, external_id)`)
  and `clean_jobs` (19 columns in `scripts/init_db.sql`'s exact order, including
  `tech_stack`/`job_level` which the ticket prose's column list dropped mid-transcription —
  cross-checked and confirmed against `init_db.sql` and `models.py` per the ticket's own instruction
  to treat `init_db.sql` as ground truth). `posted_date` stays in the schema, stays nullable, no
  backfill. `downgrade()` drops `clean_jobs` then `raw_jobs`.
- **Commands run:** `uv sync`; `uv run alembic init alembic`; `uv run pytest -q`; `uv run ruff check
  .`; `uv run mypy`; `docker compose exec -T postgres psql ... CREATE DATABASE
  internhunter_scratch`; `ALEMBIC_DATABASE_URL=... uv run alembic upgrade head`; `docker compose
  exec -T postgres psql ... "\d clean_jobs"`; `SCRATCH_DATABASE_URL=... uv run pytest
  tests/migrations -v`; `uv run alembic stamp head`; `uv run alembic current`; `uv run alembic
  upgrade head` (no-op check); `docker compose up -d --build api` (Linux app-boot check); `curl
  .../api/v1/ready`; `curl -X POST .../api/v1/agent/chat -d '{"query":"How many jobs are there?"}'`;
  `docker compose stop api`; `DROP DATABASE internhunter_scratch`.
- **Build & test:** `uv run pytest -q` → `297 passed, 1 skipped, 19 deselected, 4 subtests passed`
  in ~5s (the new round-trip test skips cleanly without `SCRATCH_DATABASE_URL`, confirmed both
  ways). `uv run ruff check .` → all checks passed. `uv run mypy` → `2 errors` — both
  **pre-existing**, in files this ticket does not touch (`src/core/checkpointer.py:25`,
  `src/agents/runtime/middleware.py:48`), already documented as benign in `Known_Issues.md` § Agent
  runtime & prompts.
- **Manual verification (actual results):**
  - **A — empty scratch DB:** `alembic upgrade head` against `internhunter_scratch` built the
    schema; `\d clean_jobs` showed all 19 columns in the documented order, `id` as `generated always
    as identity`, `UNIQUE (source, external_id)` present.
  - **B — round-trip test:** with `SCRATCH_DATABASE_URL` set, `tests/migrations` → `1 passed` (after
    fixing the test's type-name comparison — SQLAlchemy's reflected type is `BIGINT`, the
    ORM-declared type is `BigInteger`; added a small alias map rather than a brittle exact match,
    matching the spec's own guidance to compare at the name/nullability/type-family altitude). With
    the var unset → `1 skipped`.
  - **C — no-op on the real local DB:** `alembic stamp head` → stamped at `f3a1c9d2e7b4`; `alembic
    current` → `f3a1c9d2e7b4 (head)`; `alembic upgrade head` → no DDL emitted; `SELECT COUNT(*) FROM
    clean_jobs` → `50` both before and after, unchanged.
  - **D — app boots and answers a query:** native `uv run uvicorn ... --reload` on this Windows
    sandbox **never completed startup** — a pre-existing, ticket-unrelated issue (see Known Issues
    below), not caused by anything in this ticket's diff. Verified instead via `docker compose up -d
    --build api` (Linux): booted cleanly (`Application startup complete`), `GET /api/v1/ready` →
    `{"status":"ok","data_snapshot_date":"2026-07-14"}`, and `POST /api/v1/agent/chat` with `"How
    many jobs are there?"` → `"There are 50 jobs in the database."` — correct, matches the row
    count, proves the migrated/stamped schema serves live reads unchanged.
  - **E — full suite:** `uv run pytest && uv run ruff check . && uv run mypy` → pytest green, ruff
    clean, mypy shows only the two pre-existing benign errors noted above.
  - **F — Neon adoption:** documented only (not executed) in `docs/Manual_Verification_Guide.md` →
    T0019.2 § F, instructing the maintainer to run
    `ALEMBIC_DATABASE_URL="...<neon-DIRECT-non-pooled-host>...?sslmode=require" uv run alembic stamp
    head` once, deliberately, against Neon's direct endpoint (never the pooler).
- **Risks:**
  - Native Windows `uv run uvicorn` local dev is currently unusable end-to-end (async checkpointer
    pool loops forever under `ProactorEventLoop`) — pre-existing, not introduced here, but it means
    future tickets on this machine will need the same Docker workaround for boot-level manual
    checks. Registered `[LOW · NOTE]` in `Known_Issues.md`.
  - The Identity-alignment change in `models.py` is metadata-only and was verified to emit no DDL
    against the existing local DB (`alembic upgrade head` was a clean no-op after stamping) — low
    risk, but worth re-confirming against Neon specifically when the maintainer runs check F, since
    Neon's `id` columns were never independently inspected in this session (no Neon access).
  - The baseline migration was hand-written per the ticket's explicit sanction, not autogenerated;
    correctness rests on the manual cross-check against `scripts/init_db.sql` plus the passing
    round-trip test — both done, but a future column addition (T0019.3) is the first real test of
    whether the baseline truly matches production.
- **Follow-ups:** T0019.3 (lifecycle columns: `is_active`, `first_seen_at`, `last_seen_at`) is now
  unblocked. The native-Windows-uvicorn-boot issue is logged but not fixed (out of scope — requires
  touching `checkpointer.py`, which this ticket must not touch). Maintainer still needs to run the
  Neon `alembic stamp head` adoption command (§ F) deliberately, once, before any future migration
  targets Neon.
- **Docs updated:** `docs/Manual_Verification_Guide.md`, `docs/Repo_Current_State.md`,
  `docs/Known_Issues.md`, this file.

## T0019.3 — Accumulate load semantics + hidden lifecycle columns
- **Summary:** landed §4.2 #1/#2 — dropped the `TRUNCATE` in `clean_store.py` so the already-written
  `ON CONFLICT (source, external_id) DO UPDATE` upsert becomes the live load path, and added
  time-based `is_active` soft-expiry as three **hidden** `clean_jobs` columns (`is_active`,
  `first_seen_at`, `last_seen_at`) with zero agent-visible surface change. `raw_jobs`/`clean_jobs`
  now accumulate across ingestion runs instead of being rebuilt from whatever came through the
  latest run — the standing safety rule blocking ingestion against the production DSN (recorded in
  `Repo_Current_State.md` since T0019.2) is lifted by this ticket.
- **Files created:** `alembic/versions/b7e2f4a91c3d_lifecycle_columns.py`.
- **Files changed:** `config/ingestion.yaml` (new `lifecycle: { expire_after_days: 7 }` block near
  `max_jobs`), `src/services/ingestion/models.py` (`CleanJob` gains
  `is_active`/`first_seen_at`/`last_seen_at` mapped columns; `NormalizedJob` untouched per the
  ticket's non-goals), `src/services/ingestion/clean_store.py` (renamed `replace_clean_jobs` →
  `upsert_clean_jobs`, removed the `TRUNCATE`, `set_` gains `last_seen_at`/`is_active` refresh, new
  `expire_stale_clean_jobs(expire_after_days)`), `src/services/ingestion/loader.py`
  (import/call-site rename, calls `expire_stale_clean_jobs` after the upsert using
  `settings.ingestion_yaml["lifecycle"]["expire_after_days"]`, run summary gains `expired_count`,
  module docstring-style comment documents the rollback runbook),
  `tests/services/ingestion/test_clean_store.py` (renamed tests, removed the TRUNCATE assertion,
  added upsert-refresh and expiry-pass coverage), `tests/services/ingestion/test_loader.py` (updated
  all `@patch` targets for the rename, added ordering + `expired_count` coverage),
  `tests/agents/runtime/test_prompts.py` (hidden-column guard tuple extended with the three new
  columns), `docs/archive/Manual_Verification_Archive.md` (new `### T0019.3` checklist A–H),
  `docs/Repo_Current_State.md` (branch header, folder structure, milestone summary, build/test
  status, next-recommended-ticket section, safety-rule notice lifted), `docs/Known_Issues.md` (2 new
  entries + category count 10→12).
- **`clean_store.py` details:** `upsert_clean_jobs` is otherwise identical to the old
  `replace_clean_jobs` (same dedup-last-wins guard, same 16 payload columns in `set_`) — only the
  `TRUNCATE` line is gone and `set_` gains `"last_seen_at": text("now()")` and `"is_active":
  text("true")`. `first_seen_at` is deliberately absent from `set_` (insert-only; the column's own
  `server_default=now()` only fires on the initial `INSERT`, per Postgres `ON CONFLICT` semantics).
  `expire_stale_clean_jobs` executes exactly one time-based `UPDATE` — no `DELETE`, no "absent from
  this run" logic — and returns `result.rowcount` inside the same `(OperationalError, DBAPIError) →
  CleanStoreError` wrapping as the upsert.
- **Migration details:** `b7e2f4a91c3d_lifecycle_columns.py`, `down_revision = "f3a1c9d2e7b4"`.
  `upgrade()` adds the three columns with `sa.text(...)` server defaults (mirroring the baseline's
  style), then runs a single `UPDATE ... FROM raw_jobs` backfill matching `(source, external_id)`.
  `downgrade()` drops the three columns in reverse order. Not autogenerate-derived, consistent with
  T0019.2's baseline precedent at this migration count.
- **Commands run:** `uv run pytest tests/services/ingestion/test_clean_store.py
  tests/services/ingestion/test_loader.py tests/agents/runtime/test_prompts.py -q`; `uv run pytest
  -q`; `uv run ruff check <touched files>`; `uv run mypy <touched files>`; `docker compose ps`;
  `docker compose exec -T postgres psql ... CREATE DATABASE internhunter_scratch2`;
  `ALEMBIC_DATABASE_URL=... uv run alembic upgrade head`; `docker compose exec -T postgres psql ...
  "\d clean_jobs"`; `ALEMBIC_DATABASE_URL=... uv run alembic downgrade -1`; `docker compose exec -T
  postgres psql ... DROP DATABASE internhunter_scratch2`; `uv run alembic current`; `docker compose
  exec -T postgres psql -c "SELECT COUNT(*) ... WHERE NOT EXISTS (... raw_jobs join ...)"`
  (join-totality check); `uv run alembic upgrade head` (real local DB); `docker compose exec -T
  postgres psql -c "SELECT COUNT(*) FROM clean_jobs WHERE first_seen_at > now() - interval '1
  minute'"`; a scratch Python script exercising `upsert_clean_jobs`/`expire_stale_clean_jobs`
  directly against the local DB with a synthetic row (then deleted, and the real 50-row snapshot's
  `is_active`/`last_seen_at` restored — see Known Issues); `docker compose up -d --build api`; `curl
  .../api/v1/ready`; `curl -X POST .../api/v1/agent/chat -d '{"query":"How many AI Engineer jobs are
  there?"}'`; `docker compose stop api`.
- **Build & test:** `uv run pytest -q` → `303 passed, 1 skipped, 19 deselected, 4 subtests passed`
  in ~5s. `uv run ruff check .` (touched files) → all checks passed. `uv run mypy` (touched files) →
  no issues found.
- **Manual verification (actual results):**
  - **A — migrate + inspect schema:** empty-DB `alembic upgrade head` built the full schema through
    `b7e2f4a91c3d`; `\d clean_jobs` on the scratch DB showed 22 columns, with `is_active boolean not
    null default true`, `first_seen_at`/`last_seen_at timestamp with time zone not null default
    now()` appended after `is_salary_negotiable`.
  - **B — backfill join-totality (pre-flight check required by the ticket):** `SELECT COUNT(*) FROM
    clean_jobs c WHERE NOT EXISTS (SELECT 1 FROM raw_jobs r WHERE r.source=c.source AND
    r.external_id=c.external_id)` → **`0`** on the real local DB before migrating — the join is
    total, so no row was left defaulted to migration-run time. Confirmed after migrating: `SELECT
    COUNT(*) FROM clean_jobs WHERE first_seen_at > now() - interval '1 minute'` → **`0`**.
  - **C — downgrade:** `alembic downgrade -1` on the scratch DB cleanly dropped all three columns;
    `\d clean_jobs` afterward showed the original 19-column T0019.2 baseline shape.
  - **D — real local DB upgrade:** row count unchanged at `50` before and after `alembic upgrade
    head`; `0` rows flagged `is_active = false` immediately after.
  - **E — accumulate/expire/re-activate semantics:** exercised directly against the real Docker
    Postgres via a scratch script calling `upsert_clean_jobs`/`expire_stale_clean_jobs` with a
    synthetic `NormalizedJob` (not a live double-fetch — see `Known_Issues.md` for why). Two
    successive upserts of the same `(source, external_id)` kept `is_active=true`, advanced
    `last_seen_at`, and left `first_seen_at` unchanged. Aging that row's `last_seen_at` to 8 days
    ago and calling `expire_stale_clean_jobs(7)` flipped it (and, correctly per the real time-based
    logic, the real 50-row snapshot rows whose `last_seen_at` had been backfilled from weeks-old
    `fetched_at`) to `is_active=false` — none were deleted, all still selected normally.
    Re-upserting the synthetic row flipped its `is_active` back to `true`. The 50 real snapshot rows
    were restored afterward (`is_active=true`, `last_seen_at=fetched_at` re-applied) so local dev
    state was left as found — logged in `Known_Issues.md`.
  - **F — hidden-column guard:** `uv run pytest tests/agents/runtime/test_prompts.py -q` → green;
    `schema_context` never mentions `is_active`, `first_seen_at`, or `last_seen_at`.
  - **G — agent answers unchanged:** `docker compose up -d --build api` booted cleanly; `GET
    /api/v1/ready` → `{"status":"ok","data_snapshot_date":"2026-07-14"}`; `POST /api/v1/agent/chat`
    with `"How many AI Engineer jobs are there?"` → `"There are 13 AI Engineer jobs in the
    database."` — a plain count, no mention of any hidden column in the answer text.
  - **H — full suite:** `uv run pytest -q` green as above; `ruff`/`mypy` clean on touched files.
- **Risks:**
  - `scripts/init_db.sql` now diverges from the Alembic head (it does not create the three lifecycle
    columns) — deliberately left untouched per the ticket's "Do not touch" list, since the eval
    fixture loader depends on its exact current shape. A DB built purely from `init_db.sql` and
    never migrated would break `upsert_clean_jobs`/`expire_stale_clean_jobs` (both assume the
    columns exist), though the read-only `query_clean_jobs` agent tool is unaffected. Logged `[LOW ·
    OPEN]` in `Known_Issues.md` with a follow-up recommendation (point the eval fixture loader at
    `alembic upgrade head`, or accept the divergence permanently).
  - The manual "run ingestion twice" check was verified via direct
    `upsert_clean_jobs`/`expire_stale_clean_jobs` calls against a synthetic row rather than a
    genuine live double-fetch of VietnamWorks — a deliberate choice to avoid an unnecessary extra
    live crawl during dev; the SQL exercised is identical regardless of how the `NormalizedJob`
    batch was produced. Logged `[LOW · NOTE]` in `Known_Issues.md`.
  - `expire_stale_clean_jobs` is a blunt, single-statement time-based pass by design (per the
    ticket's explicit non-goals) — it will flip any row whose `last_seen_at` ages past the window
    even if the underlying posting is still live but the source happened to omit it from search
    transiently. Accepted as the intended MVP behavior; not a defect.
- **Follow-ups:** T0019.4 (source resilience: per-page try/continue + retry/backoff) is next in the
  milestone spine — T0019.5 (unattended-run safety) needs both this ticket (done) and T0019.4's
  `pages_failed` field before it unblocks. The `init_db.sql` ↔ Alembic-head divergence follow-up
  above is its own small future task, not scheduled as a numbered ticket.
- **Docs updated:** `docs/Manual_Verification_Guide.md`, `docs/Repo_Current_State.md`,
  `docs/Known_Issues.md`, this file.

## T0019.4 — Source resilience: per-page try/continue + retry/backoff
- **Summary:** a single transient failure used to kill an entire ingestion run — `_post`'s
  `resp.raise_for_status()` propagated straight out through `_collect` → `fetch()` →
  `run_ingestion`, and because `loader.py` does `list(source.fetch())`, one 429/5xx on any page
  discarded every posting already fetched from every earlier page. Now that T0019.3 made loading
  accumulate (soft, time-based expiry instead of `TRUNCATE`), a partial run is no longer a
  correctness problem, only a completeness one — a run that salvages 14 of 16 pages is strictly
  better than one that saves nothing, and the missing postings are simply re-seen on the next run,
  well inside the 7-day expiry window. This ticket adds retry-then-skip at the page level and
  surfaces a `pages_failed` count in the run summary for T0019.5 to consume.
- **Files changed:** `config/ingestion.yaml` (two new keys under `api:` — `retry_attempts: 2`,
  `retry_backoff_seconds: 2.0`, with inline comments documenting the "retries after the initial
  attempt" semantics), `src/services/ingestion/sources/base.py` (`JobSource` gains `pages_failed:
  int = 0` as a class-level default; no `__init__` added to the ABC),
  `src/services/ingestion/sources/vietnamworks.py` (new `_post_with_retry` wrapper; `_post` itself
  is byte-for-byte unchanged — the retry policy lives entirely in the wrapper; `_collect`'s page
  loop calls the wrapper and `continue`s past a `None` result; the politeness
  `time.sleep(self._delay)` moved into a `finally` so it still fires on a skipped page; `fetch()`
  resets `self.pages_failed = 0` at entry), `src/services/ingestion/loader.py` (`pages_failed =
  getattr(source, "pages_failed", 0)` read after `list(source.fetch())`, added to the returned
  summary dict — no other loader ordering changed), `tests/services/ingestion/test_vietnamworks.py`
  (new `VietnamWorksResilienceTests` class, 7 tests, plus
  `_http_error`/`_ok_response`/`_mock_client_sequence` helpers),
  `tests/services/ingestion/test_loader.py` (one new test asserting a stub source's `pages_failed`
  surfaces in the summary — no existing test needed editing), `docs/Manual_Verification_Guide.md`
  (new `### T0019.4` entry, checklist A–E), `docs/Repo_Current_State.md`, `docs/Known_Issues.md`,
  this file.
- **`_post_with_retry` details:** transient = `httpx.HTTPStatusError` with `.response.status_code`
  `== 429` or `>= 500`, plus `httpx.TimeoutException` and `httpx.TransportError` (checked in that
  order since `TimeoutException` is a subclass of `TransportError`). On a transient failure with
  retries remaining, sleeps `retry_backoff_seconds * 2**(attempt-1)` (2.0s, then 4.0s at the
  defaults) and retries. Permanent failures (any other 4xx) are not retried — give up immediately,
  since a retry cannot fix a 403 and burning delays on one would mask a block. On give-up (retries
  exhausted or permanent failure): increments `self.pages_failed`, logs a `structlog` warning
  `ingestion.page_failed` with `source`/`query`/`page`/`attempts`/`reason` (e.g. `"http_500"`,
  `"timeout"`, `"transport_error"`), and returns `None` — the exception never escapes the wrapper.
- **Commands run:** `git add -A && git commit` (T0019.1–.3, previously uncommitted WIP, committed
  first so this branch has a clean base); `uv run pytest
  tests/services/ingestion/test_vietnamworks.py tests/services/ingestion/test_loader.py -v`; `uv run
  pytest -q`; `uv run ruff check .`; `uv run mypy`; a throwaway scratch script (not committed)
  driving `VietnamWorksSource` with a mock client where page 0 fails 500 three times then page 1
  succeeds; `uv run python -c "..."` exercising `run_ingestion` end-to-end with a stub source
  exposing `pages_failed = 2`.
- **Build & test:** `uv run pytest -q` → `311 passed, 1 skipped, 19 deselected, 4 subtests passed`
  in ~5s (the skip is the pre-existing `SCRATCH_DATABASE_URL`-gated migration round-trip test;
  unrelated to this ticket). `uv run ruff check .` → all checks passed. `uv run mypy` → 2
  pre-existing errors in `src/core/checkpointer.py:25` and `src/agents/runtime/middleware.py:48`,
  both already logged in `Known_Issues.md` and untouched by this ticket's diff. **No pre-existing
  test was modified** — the new `test_pages_failed_surfaced_in_summary` case is additive, and
  `StubSource` already inherited the ABC's `pages_failed = 0` default so no existing assertion
  needed a change.
- **Manual verification (actual results):**
  - **A — full suite green:** `uv run pytest && uv run ruff check . && uv run mypy` → pytest and
    ruff green; mypy shows only the two pre-existing, unrelated errors noted above.
  - **B — resilience tests specifically:** `uv run pytest
    tests/services/ingestion/test_vietnamworks.py -v` → all 15 tests pass (8 pre-existing + 7 new
    `VietnamWorksResilienceTests`), finishing in well under a second — confirming `time.sleep` is
    patched and no real backoff delay fired.
  - **C — the summary line carries `pages_failed` (no network):** a mock client returned 500 three
    times for page 0 (query `"q"`, `pages_per_query=2`) then a real fixture response for page 1.
    Output: `posting_count: 1`, `pages_failed: 1`, and a JSON `ingestion.page_failed` warning on
    stderr showing `"query": "q", "page": 0, "attempts": 3, "reason": "http_500"`.
  - **D — end-to-end summary shape:** a stub `JobSource` with `pages_failed = 2` and an empty
    `fetch()`, run through `run_ingestion` with
    `upsert_raw_postings`/`upsert_clean_jobs`/`expire_stale_clean_jobs` patched, returned
    `{'fetched': 0, 'raw_upserted': 0, 'clean_loaded': 0, 'skipped': 0, 'expired_count': 0,
    'pages_failed': 2}` — `pages_failed` present alongside every other summary key, matching the
    ticket's expected shape exactly.
  - **E — real ingestion against the local DB:** not exercised this session (no live network call is
    part of this ticket's scope; the ticket's own non-goals exclude any live fetch against
    `ms.vietnamworks.com`). Deferred to whenever the pipeline is next run against local Docker
    Postgres.
- **Risks:**
  - A page that exhausts retries is skipped for that run only — there is no query-level retry or
    end-of-run re-queue, per the ticket's explicit non-goal. Logged `[LOW · NOTE]` in
    `Known_Issues.md`.
  - `pages_failed` is produced but nothing yet acts on it (no exit-code logic, no alerting) —
    intentional, since that is T0019.5's job. Logged `[LOW · NOTE]` in `Known_Issues.md`.
  - Working-tree note: this branch was cut from `feature/t0019.3-accumulate-lifecycle`, which had
    T0019.1–.3's completed-but-uncommitted work sitting in the working tree at the start of this
    session (30 files, matching each ticket's own completion-report narrative already drafted in
    `docs/`). That work was committed as `a74f462` before cutting
    `feature/t0019.4-source-resilience`, so this ticket's diff is clean and isolated on top of it.
- **Follow-ups:** T0019.5 (unattended-run safety) is next — it consumes `pages_failed` for its
  pre-flight/assertion logic. Both `[LOW · NOTE]` items above are recorded in `Known_Issues.md` and
  need no further action from this ticket.
- **Docs updated:** `docs/Manual_Verification_Guide.md`, `docs/Repo_Current_State.md`,
  `docs/Known_Issues.md`, this file.

## T0019.5 — Unattended-run safety: pre-flight assertion, yield floor, dead-man ping
- **Summary:** T0019.6 will run this pipeline nightly against the live Neon DB with nobody watching.
  Three preconditions had to be true first: the run must fail *before writing* when the schema looks
  wrong (T0019.2's Alembic closes the correction path but does not detect a DB someone changed by
  hand — that detection is this ticket); a near-empty fetch must not overwrite good rows under
  T0019.3's accumulate semantics (a `min_yield` pre-write floor); and a run that never happens must
  be noticeable (a dead-man ping to healthchecks.io that fires only on the fully-green path, so
  silence is the alert). A new `src/services/ingestion/safety.py` module implements all three as
  independently testable, `sys.exit`-free functions; `run_ingestion` calls them in the ordering the
  ticket specifies, and only `main()` owns the process exit contract.
- **Files changed:** `src/services/ingestion/safety.py` (new — `IngestionSafetyError`,
  `assert_clean_jobs_schema`, `assert_min_yield`, `send_dead_man_ping`),
  `tests/services/ingestion/test_safety.py` (new, 13 tests), `src/services/ingestion/loader.py`
  (calls the three safety functions in order; `main()` catches `IngestionSafetyError` and exits 1;
  sends the ping only after a successful run), `tests/services/ingestion/test_loader.py` (patched
  `assert_clean_jobs_schema` and added `safety.min_yield: 0` into all 9 pre-existing tests' mocked
  `ingestion_yaml`; 3 new tests for schema-abort, yield-floor-abort, and happy-path ordering),
  `config/ingestion.yaml` (new `safety.min_yield: 20` block), `src/core/config.py` (new optional
  `HEALTHCHECKS_URL: str | None = None`), `.env.example` (documents the new var, commented out),
  `docs/archive/Manual_Verification_Archive.md` (new `### T0019.5` entry, checklist A–E),
  `docs/Known_Issues.md` (updated the `[HIGH · OPEN]` schema-drift entry to `[HIGH · PARTIALLY
  RESOLVED]` — write-path detection closed, API-side read-path assertion flagged as the remaining
  gap; corrected the T0019.4 `pages_failed` note, which had wrongly predicted this ticket would
  consume it), `docs/Repo_Current_State.md`, this file.
- **`assert_clean_jobs_schema` details:** queries `information_schema.columns` for
  `clean_jobs`/`public` via `session_factory()` + `sqlalchemy.text`, wrapping `(OperationalError,
  DBAPIError)` into `IngestionSafetyError` the same way `clean_store.py` wraps into
  `CleanStoreError`. The expected column set is derived live from `{c.name for c in
  CleanJob.__table__.columns}` — never hand-maintained, so it can't itself become a drift source. An
  empty result (table doesn't exist) raises with its own "table not found" message rather than
  listing all 22 columns as "missing." On any mismatch it logs `ingestion.schema_drift` with both
  `missing` and `unexpected` (sorted lists) before raising; on match it logs `ingestion.schema_ok`.
- **`run_ingestion` ordering (as specified):** `assert_clean_jobs_schema()` first — before the
  source is constructed, before any fetch — then `fetch()` → `upsert_raw_postings` (raw landing
  always proceeds, preserving evidence of a bad run) → `assert_min_yield(len(postings), min_yield)`
  → normalize/skip loop → `upsert_clean_jobs` → `expire_stale_clean_jobs`. A yield-floor abort
  therefore happens before *both* the clean write and the expiry pass — getting the expiry-safety
  property (a skipped run can never wrongly expire healthy rows whose `last_seen_at` didn't get
  refreshed) for free, without a special case.
- **Commands run:** `git checkout -b feature/t0019.5-unattended-safety` (cut from
  `feature/t0019.4-source-resilience`, after committing that branch's own uncommitted T0019.4 work
  as `b0b3016`); `uv run pytest tests/services/ingestion/test_safety.py
  tests/services/ingestion/test_loader.py -q`; `uv run pytest -q`; `uv run ruff check .`; `uv run
  mypy`.
- **Build & test:** `uv run pytest -q` → `319 passed, 8 skipped, 19 deselected, 4 subtests passed`
  in ~268s (skips are all DB-dependent — no local Docker Postgres was running this session;
  unrelated to this ticket's diff). `uv run ruff check .` → all checks passed. `uv run mypy` (whole
  repo) → the same 2 pre-existing, unrelated errors as every prior ticket in this stack
  (`src/core/checkpointer.py:25`, `src/agents/runtime/middleware.py:48`); the three touched files
  are clean. **No pre-existing test's assertions were weakened** — all 9 pre-existing
  `test_loader.py` tests needed only a patch for the new schema-assertion call and a
  `safety.min_yield: 0` addition to their already-mocked config, per the ticket's explicit
  instruction.
- **Manual verification (actual results / what's deferred):**
  - **A — full suite green:** `uv run pytest && uv run ruff check . && uv run mypy` → pytest and
    ruff green; mypy shows only the two pre-existing, unrelated errors noted above.
  - **B/C/D/E — live-DB checks:** **not run this session — no local Docker Postgres was up.** These
    require `docker compose up -d`, a scratch `internhunter_drift` database for check C, and a
    temporary `min_yield` edit for check D, none of which are safe to fabricate results for. The
    full checklist is appended to `archive/Manual_Verification_Archive.md` → `### T0019.5` for the
    next person
    with the stack running, and is a **prerequisite gate before T0019.6** is trusted to run
    unattended.
- **Risks:**
  - **Unverified against a live DB this session** — the schema-drift detection (check C) and
    yield-floor abort (check D) are exercised only by mocked unit tests here, not against a real
    Postgres instance. Since this ticket exists specifically to protect an unattended live-DB
    writer, running checks B–D before T0019.6 ships is not optional. Logged as a follow-up below.
  - The dead-man ping is single-attempt, fire-and-forget by design (per the ticket's explicit
    non-goals — no retry, no `/start` ping, no alerting beyond healthchecks.io's own email). A
    transient network blip on the ping POST looks identical to a real failed run from
    healthchecks.io's perspective until the next scheduled run succeeds.
  - `pages_failed` remains produced but unconsumed — T0019.4's completion report predicted T0019.5
    would act on it; this ticket's explicit non-goals rule that out. Corrected in `Known_Issues.md`.
  - The API-side read path (`query_clean_jobs`, `get_job_details`) still has no schema-drift
    protection — only the ingestion write path is covered. Logged in `Known_Issues.md` as the
    remaining gap on the now-`[HIGH · PARTIALLY RESOLVED]` entry.
- **Follow-ups:**
  - Run manual checks B–D against local Docker Postgres before T0019.6 is built or merged — this is
    the actual proof the abort-before-write behavior works outside of mocks.
  - No ticket currently owns an API-side startup schema assertion (protecting the read path).
    Candidate: reuse or adapt `assert_clean_jobs_schema` at FastAPI startup.
  - No ticket currently owns turning `pages_failed` into a threshold/abort; revisit if observed
    non-zero on a recurring basis once T0019.6 is live.
  - T0019.6 (nightly cron) is next and was blocked on this ticket; it is now unblocked pending the
    maintainer's T0019.1 verdict confirmation (independent, pre-existing blocker, unaffected by this
    ticket).
- **Docs updated:** `docs/Manual_Verification_Guide.md`, `docs/Repo_Current_State.md`,
  `docs/Known_Issues.md`, this file.

## T0019.7 — Windowed keep-alive ping + Neon idle-pool verification (doc-only)
- **Summary:** applies the cold-start mitigation decided 2026-07-16
  (`research/archive/deployment-research-plan.md`
  §1a) but never executed: a windowed external ping of `GET /api/v1/health` to keep Render's free
  instance from spinning down. The ticket is deliberately doc-only — dashboard config and a ~24 h
  Neon observation are not things a coder session can perform — so the deliverable is a runbook
  precise enough to execute without re-deriving anything, a measurement template with the "expected
  if healthy" arithmetic worked out, and a pre-written, numerically-triggered decision rule for the
  one open question: whether the checkpointer's idle Postgres pool (`min_size=4` by psycopg_pool
  default, never overridden in `src/core/checkpointer.py`) alone keeps Neon awake regardless of
  which endpoint is pinged, which would blow Neon's 100 CU-h/month free cap.
- **Files changed (documentation only):** `docs/archive/Manual_Verification_Archive.md` (new `###
  T0019.7`
  entry — Part A setup runbook, Part B measurement template, Part C decision rule, Part D rollback),
  `research/archive/deployment-research-plan.md` (§1a status update + new empty **Verification
  outcome
  (T0019.7, date)** record), `docs/Known_Issues.md` (updated the cold-start entry's "To verify when
  applied" line and the 750-instance-hour entry's "latent today" line — both still `OPEN`, neither
  closed by this ticket), `docs/Repo_Current_State.md`, this file. **No file under `src/`, `tests/`,
  `config/`, `.github/`, or `alembic/` was touched.**
- **Runbook contents (Part A):** target `https://internhunteragent.onrender.com/api/v1/health`
  (never `/ready` — confirmed by reading `src/api/routes/health.py:13-21` vs `:40-46` that `/health`
  touches no database), 10–14 min interval (12 used as the concrete value) with an explicit "15 min
  is not safe" warning tied to Render's exact 15-min idle timer, the `07:00–23:00 ICT` /
  `00:00–16:00 UTC` window with a step telling the maintainer to check the cron-job.org account's
  configured timezone before entering hours (flagged as the easiest mistake in the ticket), the ~80
  requests/day sanity-check figure, and a note to record the enable timestamp since Part B's 24 h
  window starts there. Part A also carries forward the Render AUP tension from §1a's policy check
  (one clause has a foothold — "avoid payment or financial responsibility" — read as
  low-risk-not-prohibited) so it isn't quietly dropped, and points to decision-rule branch (c) as
  the clean way out of that tension if the maintainer would rather not sit in it.
- **Measurement template (Part B):** the five pre-written rows from the ticket, with "expected if
  healthy" values derived rather than left vague — well under ~4 CU-h/day if Neon suspends properly
  between pings vs. exactly 4 CU-h/day (16 h × 0.25 CU) → ≈122 CU-h/month if the idle pool holds it
  awake, against the 100 CU-h cap. Notes where each number is read from (Neon Console →
  Monitoring/Usage; Render Dashboard → Metrics/Billing) and that Neon's meter can lag, so the 24 h
  reading should be taken with slack.
- **Decision rule (Part C):** numeric trigger (≈4 CU-h/day, no suspension gaps → ≈122 CU-h/month
  projected) gating three ordered branches — (a) shed idle pool connections (`min_size=0`/idle
  lifetime in `config/settings.yaml`, explicitly flagged as its own future ticket, conditional on
  this ticket's measurement, with an instruction to re-run Part B afterward — **not implemented
  here**), (b) shrink the window (12 h/day ≈ 91 CU-h/month, arithmetic shown), (c) Render Starter
  $7/mo (inside the $10 ceiling, removes the problem at the root).
- **Commands run:** `git checkout feature/t0019.6-nightly-cron` / reconciliation of pre-existing
  uncommitted work found in the working tree at session start (see "Working-tree note" below), `git
  checkout -b feature/t0019.7-keepalive-verification`, `uv run ruff check .`, `uv run mypy`, `uv run
  pytest -q`, `curl -s -o /dev/null -w "%{http_code}\n" --max-time 90
  https://internhunteragent.onrender.com/api/v1/health`, `git status --short` / `git diff --stat`
  (before finalizing, to confirm the diff stayed documentation-only).
- **Build & test:** `uv run ruff check .` → all checks passed. `uv run mypy` → the same 2
  pre-existing, unrelated errors as every prior ticket in this stack (`src/core/checkpointer.py:25`,
  `src/agents/runtime/middleware.py:48`). `uv run pytest -q` → `319 passed, 8 skipped, 19
  deselected, 4 subtests passed` in ~266s — identical counts to the pre-ticket baseline; skips are
  all DB-dependent (no local Docker Postgres this session). None of these were expected to move,
  since no code changed; run anyway per the ticket's manual-verification requirement B.
- **Manual verification (actual results):**
  - **A — diff is documentation-only:** `git status --short` / `git diff --stat` → only `docs/*` and
    `research/*` changed (3 files, 73 insertions / 4 deletions); confirmed no `src/` file appears.
  - **B — suite unaffected:** confirmed above, byte-for-byte the same pass/skip counts as the
    untouched baseline.
  - **C — runbook executable cold:** re-read Part A assuming no prior context — every value is
    concrete (full URL, `*/12` minute value, both ICT and UTC hour ranges spelled out, exact
    dashboard paths for Part B's readings). No step points back to
    `research/archive/deployment-research-plan.md` to
    look something up; the checkpointer/pool detail that motivates the whole verification is inlined
    in the section's opening paragraph instead of cross-referenced.
  - **D — ping target live:** `curl` → `200`. Confirmed from reading `src/api/routes/health.py` that
    `/health` (lines 13–21) returns a static dict and runs no query, unlike `/ready` (lines 40–46),
    which calls `_select_one()` against Postgres. The service was warm at request time (T0019.7's
    own curl didn't need to wait out a cold start), so the ~60 s cold-start case named in the
    ticket's manual check D was not observed directly this session — noted, not fabricated.
  - **E — maintainer steps, not executed:** creating the cron-job.org job, recording the enable
    timestamp, taking before/after readings, waiting ~24 h, applying the decision rule, and filling
    in the §1a outcome record were **not** attempted. **No external service (cron-job.org or
    otherwise) was configured or signed into.**
- **Working-tree note (not this ticket's own work, but resolved before starting it):** this branch
  was cut from `feature/t0019.6-nightly-cron`, which itself sat at the same commit as
  `feature/t0019.5-unattended-safety` — T0019.6's actual work (`.github/workflows/ingestion.yml` +
  supporting docs) had been done in an earlier session but left uncommitted on the wrong branch.
  While reconciling that (maintainer-directed, see below), a **second, concurrent session** was
  found to be actively operating on the same working directory mid-reconciliation — causing a
  transient merge-conflict-like state and, confirmed after the fact, the loss of the uncommitted
  T0019.6 *documentation* (its completion report draft, Manual Verification Guide entry,
  Known_Issues updates) that was never `git add`ed before the collision. The concurrent session's
  own legitimate work (`ec063e7`, correcting stale `main`-divergence notes and logging a T0019.5
  live-DB verification gap) survived and was left as-is. Per maintainer direction: committed one
  small, self-contained, genuinely-orphaned T0019.5 doc addition (`docs/MVP_Technical_Design.md`
  §7.1, `24020b3`) that predated the collision; left `.github/workflows/ingestion.yml` (the
  surviving T0019.6 file, now undocumented) untouched and untracked for a future session to properly
  redo T0019.6's documentation. T0019.7's own branch and diff are unaffected by any of this —
  verified clean via requirement A above.
- **Risks:**
  - The core question — does the idle pool hold Neon awake — is still genuinely unmeasured; this
    ticket only makes it measurable. Logged as the load-bearing open item in both `Known_Issues.md`
    entries and the new §1a outcome slot, all left open by design.
  - Decision-rule branch (a) (pool `min_size=0`/idle lifetime) is explicitly not implemented here
    per the ticket's "Do not touch `checkpointer.py`" instruction — it is speculative work against
    an untested hypothesis until Part B's measurement says otherwise. Logged as a conditional future
    ticket in `Known_Issues.md`.
  - The Render AUP "avoid payment" clause tension is carried forward, not resolved — recorded in §1a
    and Part A step 9; branch (c) is the clean resolution if the maintainer wants to exit the
    tension rather than accept it.
  - `.github/workflows/ingestion.yml` now exists in the working tree with no corresponding
    documentation (completion report, Manual Verification Guide entry, Known_Issues entries) after
    the concurrent-session data loss described above — flagged here since it's adjacent to this
    session's work, even though redoing T0019.6's docs is out of scope for T0019.7.
- **Follow-ups:**
  - Maintainer executes Part A–E of the T0019.7 runbook (own action, not a ticket).
  - If Part C's trigger fires, decision-rule branch (a) (shed idle pool connections) becomes its own
    ticket, gated on the measurement — touches `src/core/checkpointer.py` and
    `config/settings.yaml`, explicitly out of scope here.
  - T0019.6's documentation (completion report, Manual Verification Guide entry,
    Known_Issues/Full_Design_Document/deployment-research-plan updates) needs to be redone from
    scratch in a future session — the workflow file survived, its docs did not.
- **Docs updated:** `docs/Manual_Verification_Guide.md`,
  `research/archive/deployment-research-plan.md`,
  `docs/Known_Issues.md`, `docs/Repo_Current_State.md`, this file.

## T0019.8 — Truthful refresh date on `/ready`
- **Summary:** the UI's corpus-age disclaimer was rendering a hand-maintained static config value
  (`api.demo.data_snapshot_date`). With T0019.3's accumulate semantics landed, the corpus can
  advance nightly while that string does not — making the disclaimer the one part of the UI able to
  silently lie, and release-blocker #7 in `research/v1-release-readiness-plan.md`. `/api/v1/ready`
  now derives the date from data state: `SELECT MAX(last_seen_at)::date FROM clean_jobs`, falling
  back to the configured value when the table is empty or the query fails. Response shape, field
  name, and the UI are all unchanged — only the value's source moved. This session also **verified
  and finished work already present uncommitted in the working tree** rather than reimplementing it,
  and (per maintainer decision D3) gave real ticket IDs to the T0019.9/T0019.10 references that an
  earlier uncommitted design-doc edit had cited without them existing anywhere.
- **Files created / changed:**
  - `src/api/routes/health.py` — split the old `get_data_snapshot_date` into
    `_configured_snapshot_date()` (the static fallback, unchanged defensive handling of a malformed
    `api.demo` block) and a new data-derived `get_data_snapshot_date()`; added
    `_select_max_last_seen()` running the plain SQL through the existing `session_factory`.
    `readiness_check` runs the date query via `asyncio.to_thread` *after* the `SELECT 1` probe.
  - `tests/api/test_ready.py` — 7 cases covering: MAX present, empty-table fallback, query-raises
    fallback, 503 short-circuit with `assert_not_called()` on the date query, and the
    not-rate-limited guarantee.
  - `docs/Tickets.md` — **new T0019.9 and T0019.10 ticket entries**; milestone sequencing line,
    roadmap row, and backlog pointer updated.
  - `docs/MVP_Technical_Design.md` — §11.3 rewritten; §7 status banner corrected (see "Doc
    corrections" below).
  - `docs/Manual_Verification_Guide.md`, `docs/Known_Issues.md`, `docs/Repo_Current_State.md`, this
    file.
- **Layer isolation:** holds. The readiness route reads a *table* with plain SQL; it does not import
  `src.services.ingestion` (the ticket's explicit constraint). No LangChain logic entered the route.
- **Doc corrections made (this ticket found three untrue statements in the working tree):**
  1. §11.3 named `SELECT MAX(fetched_at)` as the intended fix. That is wrong under T0019.3 —
     `fetched_at` lives on `raw_jobs`, while `last_seen_at` is the per-row freshness signal on
     `clean_jobs` that the upsert refreshes each run. The disclaimer describes the *served* corpus,
     so it must read the served table. Doc updated to match the implementation.
  2. The §7 banner asserted the T0019.1 robots/ToS verdict was "favorable and
     **maintainer-confirmed** 2026-07-19". **No committed document records that confirmation** — the
     T0019.1 completion report says "RECOMMENDED VERDICT: favorable — pending maintainer
     confirmation." Softened to state the gate is not yet cleared (decision D2 remains open).
  3. The same banner claimed T0019.6 was **built**, while `.github/workflows/ingestion.yml` is
     untracked and its docs were lost to the concurrent-session collision recorded in the T0019.7
     report. A committed doc must not assert a file the repo does not contain; the banner now marks
     T0019.6 open with the reason.
- **Commands run:** `uv run pytest tests/api/test_ready.py -v`, `uv run pytest -q`, `uv run ruff
  check .`, `uv run mypy`, `docker ps`, plus `git diff`/`git status` inspection and grep/read of
  `config/ingestion.yaml`, `src/services/query/job_details.py`,
  `src/services/ingestion/sources/vietnamworks.py`.
- **Build & test:** `uv run pytest tests/api/test_ready.py -v` → **7 passed** in 1.88s. `uv run ruff
  check .` → all checks passed. `uv run mypy` → the same **2 pre-existing, unrelated** errors as
  every prior ticket in this stack (`src/core/checkpointer.py:25`,
  `src/agents/runtime/middleware.py:48`) — no third error introduced.
- **Manual verification — NOT RUN. This is the ticket's main gap, stated plainly:**
  - **Docker Desktop was not running this session** (`docker ps` → `open
    //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified`), so **none** of
    checks A–E in the new `archive/Manual_Verification_Archive.md` T0019.8 entry were executed
    against a real
    database.
  - What this leaves unproven: the automated tests patch `_select_max_last_seen` and hand it a
    `datetime.date` object, so they exercise the fallback logic but **cannot** prove that
    PostgreSQL's `::date` cast actually arrives as a `datetime.date` through psycopg3, nor that
    against a populated table the real value wins rather than the fallback quietly firing. Check B
    (endpoint value vs. `psql` value must match) is the load-bearing one and is outstanding.
  - This is the **same class of gap** as T0019.5's unrun checks B–E. It is recorded rather than
    papered over; do not treat T0019.8 as end-to-end verified until check B passes.
- **Risks:**
  - **The live-DB behaviour is unverified** (above). Confidence in the SQL and the psycopg3 date
    mapping is from reading, not from running.
  - **Silent degradation by design.** Against an un-migrated DB the query raises, the fallback
    fires, and `/ready` still returns `200` with a stale-but-plausible date — no signal in the
    response body, only the `snapshot_date_query_failed_using_config_fallback` warning (with
    `exc_info`). Deliberate (a readiness probe must not flap on a cosmetic field) but logged as
    `[LOW · NOTE]` in `Known_Issues.md`.
  - **`/ready` now costs a second DB round trip** on the success path. Kept as two separate
    `asyncio.to_thread` calls on purpose: the 503 path short-circuits before the date query, so
    failure modes stay independently observable and a down-DB probe still costs exactly one query.
  - T0019.9/T0019.10 are **scoped only** — neither is implemented, and the design doc now points at
    ticket text rather than at nothing.
- **Follow-ups:**
  - **Run the T0019.8 manual checks A–E** against local Docker Postgres (needs Docker up). Check B
    specifically.
  - **T0019.10 before the cron is enabled** — the `get_job_details` `SELECT *` leak is cosmetic only
    while all rows are `is_active = true`; it becomes a real honesty defect the moment expiry starts
    flipping rows.
  - **T0019.9** after the D8 ToS-posture decision (it raises request volume against the same host).
  - **T0019.6 remains open** and is not this ticket's work: it needs its lost docs rewritten, its
    workflow committed, D2 (ToS verdict ratified in a tracked doc) and D5 (T0019.5 checks B–E)
    cleared.
  - **D11** — the 60-day Actions auto-disable has no mitigation; the action T0019.6 named is
    ToS-blocked by GitHub. Newly logged in `Known_Issues.md`.
- **Docs updated:** `docs/Tickets.md`, `docs/MVP_Technical_Design.md`,
  `docs/Manual_Verification_Guide.md`, `docs/Known_Issues.md`, `docs/Repo_Current_State.md`, this
  file.

## T0019.9 — Ingestion coverage: raise `max_jobs` + interleave query order
- **Summary:** the corpus the demo answers from was both **truncated** and **skewed**, and the two
  defects were independent. `config/ingestion.yaml` capped every run at `max_jobs: 50` while a
  06/2026 spike measured ~50–112 postings actually available across the 8 configured queries — so
  the cap bound at the low end of the real range, and a truncated run looked identical to a complete
  one. Worse, that global cap was spent in **fixed config order**: `_collect` iterated queries outer
  / pages inner and broke the outer loop once `kept >= max_jobs`, so if `"data scientist"` and
  `"data engineer"` alone filled the budget, the remaining six queries never issued a single request
  — `"MLOps"`, `"computer vision"` and `"deep learning"` were structurally starved. The corpus was
  not a sample of AI/Data roles; it was a prefix of the config file. Both fixes land: the cap rises
  to `150`, and `_collect` now interleaves **page outer / query inner**. Neither suffices alone —
  raising the cap does not fix order bias, interleaving does not fix a ceiling that is too low.
- **⚠️ The D8 gate held — no live API request was issued.** This ticket raises request *volume
  tolerance* against `ms.vietnamworks.com`, an undocumented API whose republishing posture (decision
  **D8**, `research/v1-release-readiness-plan.md` §4) is unsettled. Everything was implemented and
  tested against **canned responses only**. No live fetch was performed — not to measure, not once.
  This branch was **not** merged toward `main` and **not** merged into the nightly cron's path
  (`.github/workflows/ingestion.yml` is untouched and remains untracked). The re-measure §11 calls
  for is written as a runbook for the maintainer and was **not executed**.
- **Files changed:**
  - `config/ingestion.yaml` — `max_jobs: 50 → 150`, one value, plus a comment explaining it is a
    **safety ceiling, not a target**: it bounds a runaway run, now sits above the measured yield so
    the API's real output ends a run, and — the point that matters for D8 — **raising it does not
    increase per-run request volume**, since `pages_per_query x queries` (2 × 8 = 16) determines
    request count and neither moved.
  - `src/services/ingestion/sources/vietnamworks.py` — `_collect` only: loop nesting inverted to
    page-outer/query-inner; docstring rewritten to describe the interleave and why.
  - `tests/services/ingestion/test_vietnamworks.py` — new `_ai_job` / `_per_query_client` helpers
    (the existing mock returns one fixture for every call and therefore **cannot** show per-query
    coverage at all) and a new `VietnamWorksCoverageTests` class, 6 cases.
  - `research/archive/data-ingestion-stage.md` — new §11: re-measure runbook, results table with
    every cell
    `_TBD — pending D8_`, and a decision rule.
  - `docs/Known_Issues.md`, `docs/Manual_Verification_Guide.md`, `docs/Repo_Current_State.md`, this
    file.
- **Invariants verified explicitly (each one re-read against the final code):** `seen_ids` is still
  initialised **once before both loops**, so cross-query dedup holds — the interleave makes
  collisions surface *earlier*, not differently. `kept` is still a single global counter and **all
  three cap checks remain** (outer loop, inner loop, inner-most job loop), so the run stops at
  exactly `max_jobs`, never one more. `_is_ai_data` is applied per job, unchanged.
  `time.sleep(self._delay)` is still in the `finally`, unmoved and unconditional, with its comment
  intact — it runs for every page attempt including skipped ones. T0019.4's `_post_with_retry`
  semantics are untouched: `None` still means `continue`, `pages_failed` still increments, nothing
  raises.
- **Commands run:** `git checkout -b feature/t0019.9-ingestion-coverage`, `uv run pytest
  tests/services/ingestion/test_vietnamworks.py -q/-v`, `uv run pytest -q`, `uv run ruff check .`,
  `uv run mypy`, `git diff config/ingestion.yaml`, `git diff --stat`, and a throwaway distribution
  script run from scratch space (not committed).
- **Build & test:** `uv run pytest -q` → **328 passed, 8 skipped**, 19 deselected, 4 subtests passed
  (~526s) — **+6 over T0019.8's 322**, exactly the six new cases. `uv run ruff check .` → all checks
  passed. `uv run mypy` → the same **2 pre-existing, unrelated** errors as every prior ticket in
  this stack; no third introduced. **No existing test broke, was loosened, or was removed** — all 21
  prior cases in the file pass unchanged, `test_max_jobs_cap_is_honoured` included.
- **Manual verification — A–C run and passing, D skipped, E confirmed:**
  - **A — diff is tight.** `git diff config/ingestion.yaml` shows exactly one changed value plus its
    comment; `queries`, `pages_per_query`, `delay_seconds`, `hits_per_page` and the retry settings
    are untouched. `git diff --stat` → 5 files, all inside the allowed areas.
  - **B — the anti-skew test genuinely discriminates (the load-bearing check).** With the
    interleave: `27 passed`. With `_collect`'s loops **temporarily reverted** to query-outer: `2
    failed, 25 passed` — `test_cap_truncates_evenly_across_queries_not_alphabetically` fails with
    `AssertionError: Items in the second set but not the first: 'q7', 'q6', 'q8' : some queries were
    starved by the cap`, and `test_request_order_is_page_major` fails with `[0,1,0,1,…] !=
    [0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1]`. The interleave was then restored and green re-confirmed. A
    test that passed both before and after would prove nothing; this one names the exact starved
    queries.
  - **C — per-query distribution, end to end, no network.** 8 queries × 2 pages × 2 jobs, `max_jobs
    = 20` → `total postings: 20`, `requests issued: 10`, `pages_failed: 0`, distribution `q1:4 q2:4
    q3:2 q4:2 q5:2 q6:2 q7:2 q8:2`, **queries represented: 8/8**. Under the old loop this is
    `4,4,4,4,4,0,0,0`.
  - **D — local pipeline: SKIPPED, stated plainly.** Running the loader end-to-end could not be done
    without either a live fetch or scaffolding beyond this ticket's scope, so it was not attempted.
    The gate outranks the check. Nothing about the local pipeline is claimed as verified.
  - **E — gate confirmed.** No request to `ms.vietnamworks.com`; branch not merged toward `main` or
    the cron workflow.
- **Deviation from the ticket, with reasoning (please review):** the ticket specified the anti-skew
  test use **8 queries each yielding 10 AI/Data jobs with `max_jobs = 20`**, expecting an even
  spread across all 8 and predicting the old code prints `10,10,0,0,0,0,0,0`. **That shape cannot
  produce the assertion.** The interleave's granularity is a **page**, not a job — `_collect` drains
  an entire page before moving to the next query — so with 10 jobs on each query's page 0 the budget
  of 20 is spent on two queries *under page-major order too*, and the test would fail identically
  before and after the fix. Jobs-per-query-per-page must be `<= max_jobs / len(queries)` for a cap
  to reach every query at all. I used **2 jobs per page** (8 queries × 2 pages = 32 available, cap
  20), which discriminates exactly as intended — see check B's failure output. This constraint is
  documented in the test class docstring and in the Manual Verification Guide entry, because anyone
  re-deriving the check from the ticket text would hit the same wall.
- **Working-tree note (not my work, left untouched):** `docs/Known_Issues.md` acquired an unrelated
  `[LOW · OPEN]` Demo-UI entry (agent markdown rendered as raw text, dated 2026-07-20) **during this
  session** — `git status` at session start showed only `?? .github/`. This is consistent with the
  concurrent-session activity recorded in the T0019.7 report. I left the entry and its index-count
  bump exactly as found, edited only my own entries around it, and staged only this ticket's files.
  Flagging it so it is not mistaken for T0019.9's work or silently swept into this commit.
- **Risks:**
  - **The `150` figure is unverified against current reality.** It clears the *06/2026* measurement,
    which may be stale. If the API's yield has grown past ~150 the cap is binding again and the
    original defect has silently returned — with, per the follow-up below, still no signal. This is
    the reason the `Known_Issues` entry is `PARTIALLY RESOLVED` rather than closed.
  - **The interleave changes request *order* against the live host** (`q1p0, q2p0, …, q8p0, q1p1, …`
    instead of `q1p0, q1p1, q2p0, …`). Count and per-request delay are identical, but the traffic
    *shape* differs, and this has never been exercised live. Worth a sentence in the D8
    conversation.
  - **Fairness is page-granular, not job-granular.** If one query returns far more jobs per page
    than others, it still takes a larger share of the budget. The interleave bounds the skew; it
    does not eliminate it. Per-query quotas were explicitly out of scope.
  - **Raising the cap widens the budget but not the discovery ratio** — most of it is still spent
    re-confirming postings already in `clean_jobs` (logged below).
- **Follow-ups — all three appended to `docs/Known_Issues.md`:**
  - The `[MED]` coverage entry moved `OPEN → PARTIALLY RESOLVED` with an explicit Status paragraph:
    both fixes landed, closure requires the §11 re-measure, which requires D8. It also corrects one
    claim in its own old follow-up text — raising `max_jobs` alone does not increase request volume.
  - **New `[LOW · OPEN]`:** budget still spent re-confirming known postings (`seen_ids` is per-run;
    no "skip IDs already in `clean_jobs`"). Unowned — the fix needs a **DB read inside the source
    adapter**, which is a layer-isolation question, not just an optimisation. Deliberately not
    attempted here.
  - **New `[LOW · OPEN]`:** a truncated run surfaces no signal — hitting `max_jobs` logs nothing and
    leaves `pages_failed` at `0`, so an operator cannot distinguish a capped run from a complete
    one. Cheap to fix; would make the §11 re-measure partly self-reporting.
- **Docs updated:** `research/archive/data-ingestion-stage.md`, `docs/Known_Issues.md`,
  `docs/Manual_Verification_Guide.md`, `docs/Repo_Current_State.md`, this file.

## T0019.10 — `get_job_details` explicit column allowlist
- **Summary:** the two query tools disagreed about what the agent was allowed to see.
  `prompts.schema_context` defines a 16-column frozen contract and ends "Do not reference any column
  not listed above — unlisted columns do not exist in this schema"; the executor path behind
  `query_clean_jobs` respects it by projecting explicitly. `fetch_job_details` did not — it ran
  `SELECT * FROM clean_jobs` and returned every column as a dict, which `_build_answer` then
  rendered key-by-key via `row.items()` straight into the tool result. So one tool told the model
  those columns did not exist while the other handed them over. The fix is one statement: the
  wildcard becomes the 16 contract columns, named explicitly, in `schema_context`'s own order, under
  a comment binding the two together. Nothing downstream changed — `_build_answer` renders whatever
  it receives, so fixing the data source is the whole fix.
- **⚠️ The leak was six columns, not the three the ticket's objective named.** `clean_jobs` has 22
  columns; `schema_context` lists 16. Beyond the three T0019.3 lifecycle columns the ticket called
  out (`is_active`, `first_seen_at`, `last_seen_at`), the wildcard was also leaking **`source`** and
  **`external_id`** (ingestion bookkeeping, not in the agent's vocabulary) and — the one that
  matters most — **`posted_date`**, the always-NULL column this project has repeatedly refused to
  synthesize. The model was receiving `posted_date=None` on **every single detail lookup**: exactly
  the field a model narrates ("no posting date available") or quietly reasons about. The ticket's
  In-Scope line ("the 16-column frozen contract and nothing else") already covered all six, so this
  is a clarification rather than a scope change — but a reader following only the objective would
  have fixed three and left three, including the worst one.
- **Why now, not after:** the leak is cosmetic *today* only because every row is `is_active = true`,
  so the leaked value is uniform and tells the model nothing. The moment T0019.6's nightly cron
  starts expiring rows, the agent can read and describe stale-listing state through an unguarded
  path, using vocabulary it was never given and reasoning it was never calibrated for, while the
  sanctioned path still hides it. This ticket is sequenced ahead of enabling that cron.
- **Files changed (5 — all inside the ticket's allowed areas):**
  - `src/services/query/job_details.py` — the `SELECT` statement only, plus a 7-line sync comment
    naming `config/prompts.yaml → prompts.schema_context` as the counterpart this list mirrors and
    stating why they must change together. Everything else is byte-identical: the `if not ids:
    return []` early exit, `SET TRANSACTION READ ONLY`, the `:ids` bound parameter,
    `result.mappings().all()`, and the `(OperationalError, DBAPIError) → ExecutorError` wrapping.
  - `tests/services/query/test_job_details.py` — one new guard test plus two module-level column
    tuples and a `_selected_columns` parsing helper. All 6 pre-existing tests unchanged.
  - `docs/Manual_Verification_Guide.md`, `docs/Known_Issues.md`, `docs/Repo_Current_State.md`, this
    file.
- **Not touched, deliberately:** `config/prompts.yaml` (the contract is the reference, not the
  target), `src/agents/tools/get_job_details.py`, `src/services/query/executor.py` /
  `query_clean_jobs`, and every prompt, golden file, and eval fixture. No schema change — the six
  columns stay in the table, they just stop being selected.
- **`description` was kept in the allowlist.** `sql_generation`'s "never SELECT the description
  column" rule governs the *executor* path, where descriptions are large blobs that bloat multi-row
  results. `get_job_details` is precisely the tool whose job is to return the full description —
  that is what its docstring promises the model. Dropping it would have degraded the tool rather
  than narrowing it.
- **How the `source` / `source_url` substring trap was handled.** This was the ticket's flagged
  failure mode: `source` is a substring of the allowlisted `source_url`, and `external_id` of `id`,
  so `assertNotIn("source", statement)` fails against *correct* code — and the natural "fix" is to
  weaken the assertion until it passes, at which point it catches nothing. The guard does **no
  substring matching against raw SQL**. A helper, `_selected_columns`, regexes the `SELECT … FROM`
  clause out of the statement, splits it on commas, strips each token, and returns a `set` of
  **whole column names**; every allowed/forbidden assertion runs against that set. Proof it works is
  in check B scenario 2 below: the test reports `source` as leaked while `source_url` stays clean,
  and `external_id` while `id` stays clean — a distinction a substring version is structurally
  incapable of making.
- **Assertion order matters and was changed from the obvious layout.** The set-equality check
  (`selected == CONTRACT_COLUMNS`) is the strongest assertion, but placing it first makes it
  short-circuit so the per-column named assertions never run, and failures report an opaque set
  diff. The guard now asserts, in order: no `*` in the statement; each of the 16 contract columns
  present **by name**; each of the 6 out-of-contract columns absent **by name**; then set equality
  last, as a catch-all for columns in neither list (e.g. one added to the table later).
- **Commands run:** `git add -u && git commit` (T0019.9's uncommitted work, at the maintainer's
  direction, so this ticket's diff stays clean), `git checkout -b
  feature/t0019.10-job-details-allowlist`, `uv run pytest tests/services/query/test_job_details.py
  -v`, `uv run pytest`, `uv run ruff check .`, `uv run ruff check` on the two changed files, `uv run
  mypy`, plus the two deliberate-regression runs of check B and a live `fetch_job_details([1])`
  attempt.
- **Build & test:** `uv run pytest` (full standard suite) → **329 passed, 8 skipped**, 19 deselected
  in 526.10s — **+1 over T0019.9's 328**, exactly accounting for the single net-new guard case. `uv
  run pytest tests/services/query/test_job_details.py -v` → **7 passed** in 0.53s; the 6
  pre-existing cases pass **unchanged** — none was modified, weakened or removed,
  `test_returns_rows_as_dicts` / `test_maps_result_rows_to_list_of_dicts_incl_description` included
  (it hand-builds its own dict and does not care what was selected, so it needed no edit, as the
  ticket predicted). The 8 skips are the usual DB-dependent ones plus
  `tests/migrations/test_baseline_roundtrip.py` (needs `SCRATCH_DATABASE_URL`) — unchanged from
  prior tickets, not caused by this one. `uv run ruff check .` → all checks passed. `uv run mypy` →
  the same **2 pre-existing, unrelated** errors as every prior ticket in this stack
  (`src/core/checkpointer.py:25`, `src/agents/runtime/middleware.py:48`); no third introduced, and
  `src/services/query/job_details.py` is clean. The chained command's exit code 1 came from those
  two known mypy errors, not from pytest or ruff.
- **Manual verification — A and B run and passing; C, D and E NOT run:**
  - **A — suite green.** See Build & test above.
  - **B — the guard genuinely discriminates (the ticket's real deliverable). Two scenarios were
    needed, not one.**
    - *Scenario 1, the ticket's version:* reverting to `SELECT *` **fails** the guard — but it fails
      naming the 16 **missing** columns, not any leaked one, because with a wildcard the parsed
      token set is simply `{'*'}` and the forbidden-column assertions are never reached. The `*`
      assertion is what trips. This proves the wildcard-regression case and nothing more.
    - *Scenario 2, added because scenario 1 is insufficient:* keeping the allowlist but appending `,
      is_active, source, external_id, posted_date` fails with `AssertionError: Items in the first
      set but not the second: 'posted_date', 'is_active', 'external_id', 'source'` — naming all four
      leaks exactly. **This is the run that exercises the forbidden-column assertions, and the run
      that proves the substring trap was handled.** A report claiming check B passed on scenario 1
      alone would be overstating the coverage.
    - The allowlist was restored and green re-confirmed after each scenario.
  - **C, D, E — NOT RUN. Docker Desktop was not running this session.** `fetch_job_details([1])` was
    attempted and failed with `ExecutorError: Failed to execute query:
    (psycopg.errors.ConnectionTimeout) connection timeout expired` against `localhost:5433`. One
    incidental confirmation from that failure: the `(OperationalError, DBAPIError) → ExecutorError`
    wrapping demonstrably still works against a **real** driver error, not only against the mocked
    ones. But the substantive checks are outstanding, and **check D is the load-bearing one** — it
    prints the literal string the model receives, which is the only direct evidence the agent's
    actual view is clean. Do not treat T0019.10 as end-to-end verified until C and D pass. Same
    class of gap as T0019.8's and T0019.5's unrun checks; recorded rather than papered over.
- **Risks:**
  - **The 16-column list and `schema_context` are coupled by comment and test only, not by a shared
    constant.** A future schema change must update both or they drift apart again in exactly the
    direction this ticket just closed. The ticket explicitly ruled out the shared-constant refactor
    and I did not build it: `schema_context` is descriptive prose the model reads (per-column type +
    semantics), not a column list, so there is no clean common ancestor, and inventing one is
    architecture this ticket did not sanction. Logged in `Known_Issues.md`.
  - **The guard asserts against the SQL *string*, not the executed projection.** It parses statement
    text, so it catches a wildcard regression and any added/dropped column name, but it would not
    catch a column exposed by other means (a view change, dynamically-built SQL, a join). Adequate
    for one static statement; logged with a follow-up trigger.
  - **Unverified against live data** (C/D/E above). Confidence that the returned dict has exactly 16
    keys comes from reading the statement, not from running it.
  - **No behavioural change was measured on the agent.** Narrowing what the tool returns necessarily
    changes the tool-result string the model conditions on. Nothing in the eval suite was re-run
    (prompts, goldens and fixtures were out of scope), so the claim "narrowed, not degraded" rests
    on check E — which was also not run.
- **Follow-ups — all appended to `docs/Known_Issues.md`:**
  - **New `[MEDIUM Â· OPEN]`:** the column list — `schema_context` coupling is by comment and guard
    test, not mechanical. Revisit only if a third consumer of the contract appears; a
    machine-readable manifest that `schema_context` is *rendered from* would be the shape, and is
    not warranted at two consumers.
  - **New `[RESOLVED]`:** the leak was six columns, not three — recorded because the wildcard hid
    the miscount and the ticket's own objective understated it.
  - **New `[LOW Â· OPEN]`:** the guard is text analysis over a static statement; replace with a
    DB-backed assertion on real result keys if `fetch_job_details` ever builds SQL dynamically.
  - **Run manual checks C and D** against a local Docker Postgres. D specifically.
- **Docs updated:** `docs/Manual_Verification_Guide.md`, `docs/Known_Issues.md`,
  `docs/Repo_Current_State.md`, this file.

## T0019.6 — GitHub Actions nightly ingestion cron (recovery & finish)
- **Summary:** this is a recovery ticket, not a greenfield build. T0019.6's work was written
  2026-07-19 and then stranded — the workflow file (`.github/workflows/ingestion.yml`) survived
  untracked across several later tickets' sessions, but its supporting doc set sat in `stash@{0}`
  (`b7a291e`, "T0019.6 WIP: nightly cron workflow + docs"), based at `bb75d10`, five commits stale
  by the time this session started. This ticket hand-ports the stash's doc hunks onto the current
  tree (not a raw `git stash pop`, which would have conflicted destructively against `.7`–`.9`'s
  rewrites of the same files), fixes one real defect in the recovered workflow (the secrets block),
  and lands everything as a committed, still-dormant workflow.
- **Base branch deviation (per the ticket's own contingency clause):** the ticket says branch off
  `feature/t0019.10-job-details-allowlist` if it has been committed, otherwise off `b44aa20`
  (T0019.9). At session start, `feature/t0019.10-job-details-allowlist` was checked out but **its
  own tip was still `b44aa20`** — T0019.10's work (`src/services/query/job_details.py`, its test
  file, and doc drafts) sat uncommitted in the working tree. Per the contingency clause, this ticket
  branches off `b44aa20` directly. To do so without touching T0019.10's in-progress work, the seven
  affected tracked files were stashed (`git stash push -m "T0019.10 WIP..."`, a **new**, separate
  stash entry — `stash@{0}` after this operation, distinct from the pre-existing T0019.6 stash which
  shifted to `stash@{1}`), the branch was cut cleanly from `b44aa20`, and the T0019.10 stash was
  restored onto `feature/t0019.10-job-details-allowlist` afterward. Neither stash was dropped.
- **Files changed:** `.github/workflows/ingestion.yml` (now tracked, one edit — see below),
  `docs/Full_Design_Document.md` (§2 amendment, carried verbatim from the stash),
  `docs/archive/Manual_Verification_Archive.md` (new `### T0019.6` entry), `docs/Known_Issues.md` (2
  new
  entries + 1 new follow-up + category count), `docs/Repo_Current_State.md` (rewritten),
  `docs/Tickets.md` (1 marker line), `research/archive/deployment-research-plan.md` (§11
  confirmation line),
  `research/archive/ingestion-milestone-plan.md` (scope-addendum block), this file. **No file under
  `src/`,
  `tests/`, or `config/` touched.**
- **Carry-vs-skip table followed exactly:** `docs/Full_Design_Document.md` carried verbatim;
  `Manual_Verification_Guide.md` and `Completion_Reports.md` carried-and-edited; `Known_Issues.md`
  carried a reduced set (2 of the stash's 2 T0019.6-original entries — the third, the 60-day
  keepalive gap, had **already been carried forward for real** by a later ticket's session and
  exists in the current file; duplicating it would have been wrong, so it was left alone and only
  cross-checked); `Repo_Current_State.md` rewritten, not carried (the stash's version describes a
  branch state five tickets stale); `Tickets.md` carried only the one heading-status line
  (T0019.9/.10 ticket bodies already exist for real, committed by those tickets — the stash's
  versions of those sections were **not** reapplied, since they'd be a stale duplicate of
  already-landed work); both `research/` files carried their named blocks. `docs/Schema_Contract.md`
  was **skipped** per the ticket's explicit instruction (orphaned T0019.3 documentation work, not
  this ticket's) — logged as a new `[LOW · OPEN]` follow-up in `Known_Issues.md` instead of fixed
  inline. `docs/MVP_Technical_Design.md` was also skipped — its stashed hunk is already present in
  `HEAD` (verified by diff before touching it).
- **The one real fix, Step 2 (secrets block):** the ticket's own scope line says ingestion needs
  **no** `GROQ_API_KEY` — it is deterministic, no LLM. But `src/core/config.py`'s `Settings`
  declares `GROQ_API_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_PUBLIC_KEY` as required-no-default,
  validated at import — so the CLI cannot start without them regardless of whether ingestion logic
  reads them. The recovered stash workflow wired all three to real `secrets.*`, contradicting the
  ticket. Per this session's maintainer decision, the three lines were replaced with literal
  placeholders (`"unused-by-ingestion"`) instead — no real LLM or tracing credential ever reaches
  the ingestion runner. Only `DATABASE_URL` and `HEALTHCHECKS_URL` remain real GitHub secrets. The
  inline comment above the `env:` block was rewritten to match. Nothing else in the workflow
  changed: cron expression, concurrency, `timeout-minutes: 15`, `permissions: contents: read`, the
  SHA-pinned actions, the no-migrations note, and the keepalive-omission block (with its
  `TODO(maintainer)`) are all exactly as recovered.
- **Manual Verification Guide entry:** new `### T0019.6` placed between the existing `T0019.5` and
  `T0019.7` entries (ticket order). Checks A and B carried as-is (B's live-tested claim — "confirmed
  live 2026-07-19" — is preserved as historical fact, and B was **also re-run this session**, see
  below). Check C's stale prerequisite ("`feature/t0019.6-nightly-cron` does not exist yet ... cut
  it off `bb75d10`") was rewritten: push `feature/t0019.6-nightly-cron-finish`, then Actions →
  "Nightly ingestion" → Run workflow → select that branch; also notes C–E additionally require
  T0019.5's manual checks B–E to have been run against a live DB first (they have not, per
  `Known_Issues.md`). Checks D/E carried; E states plainly that the scheduled (as opposed to
  `workflow_dispatch`-triggered) run cannot fire until the T0019 chain merges to `main`.
- **Commands run:** `git branch -a`, `git stash list`, `git log --oneline` (several forms), `git
  show b7a291e:<path>` (per file, to read stash contents without popping), `git diff b7a291e^1
  b7a291e -- <path>` (per file, to see the stash's own diff), `git diff b44aa20:<path>` equivalents
  via reading current files, `git stash push -m "..." -- <7 tracked files>`, `git checkout -b
  feature/t0019.6-nightly-cron-finish b44aa20`, `uv run python -c "import yaml;
  yaml.safe_load(open('.github/workflows/ingestion.yml')); print('YAML OK')"`, `uv run pytest -q`,
  `uv run ruff check .`, `uv run mypy`, `grep -n "secrets\." .github/workflows/ingestion.yml`, `grep
  -n "No autonomous or background execution" docs/Full_Design_Document.md`, `grep -c "T0019.6"
  docs/Manual_Verification_Guide.md`, `git status --short`.
- **Build & test:** `uv run pytest -q` → `328 passed, 8 skipped, 19 deselected, 4 subtests passed`
  in ~8567s — identical to T0019.9's baseline, exactly as expected since no `src`/`tests` file was
  touched. `uv run ruff check .` → all checks passed. `uv run mypy` → the same 2 pre-existing,
  unrelated errors in `checkpointer.py:25` / `middleware.py:48`. `YAML OK` from the `yaml.safe_load`
  check.
- **Manual verification — actually run this session:**
  - **Check A** — YAML parse (`YAML OK`), `git status --short` (clean except intended files), full
    suite/ruff/mypy — all as expected above.
  - **Check B** — with `.env` moved aside, unsetting each of `GROQ_API_KEY`, `LANGFUSE_SECRET_KEY`,
    `LANGFUSE_PUBLIC_KEY` in turn and running `uv run python -m src.services.ingestion.loader`
    failed fast with `ConfigLoadError` and `exit=1`, before any DB connection, for all three. `.env`
    restored immediately after.
  - **Acceptance-criteria greps** — `grep -n "secrets\." .github/workflows/ingestion.yml` → exactly
    2 lines (`DATABASE_URL`, `HEALTHCHECKS_URL`); `grep -n "No autonomous or background execution"
    docs/Full_Design_Document.md` → no match (line replaced); `grep -c "T0019.6"
    docs/Manual_Verification_Guide.md` → `1` (the new heading; > 0, satisfying the criterion).
- **Checks C, D, and E were NOT run** — stated plainly, per the ticket's own instruction not to
  fabricate them. They require GitHub Actions secrets configured on the real repo (`DATABASE_URL`,
  `HEALTHCHECKS_URL`) and, for the schedule half of E, the T0019 chain merged to `main`. Both are
  maintainer-gated actions outside this ticket's scope. T0019.5's manual checks B–E (live-DB
  schema-drift/yield-floor proof) also remain unrun, as recorded in that ticket's own completion
  report and `Known_Issues.md` — this ticket does not run them either, per its explicit instruction
  not to.
- **Risks (all appended to `docs/Known_Issues.md`):**
  - The nightly cron stays fully dormant until the T0019 chain merges to `main` — a maintainer
    decision, out of scope here. `[MED · OPEN]`.
  - Three config-validation-only placeholders (`GROQ_API_KEY`, `LANGFUSE_SECRET_KEY`,
    `LANGFUSE_PUBLIC_KEY`) must stay in the workflow despite never being read by ingestion — logged
    so a future reader doesn't strip them and break the first run. `[LOW · NOTE]`.
  - No keepalive mechanism covers GitHub's 60-day scheduled-workflow auto-disable; the ticket's
    suggested action is itself 403'd for a ToS violation. **Already logged** by a prior ticket's
    session — not duplicated here, only cross-checked. `[MED · OPEN]`, pre-existing.
  - `docs/Schema_Contract.md` still describes `is_active`/`first_seen_at`/`last_seen_at` as a future
    T0014 addition; they have been live hidden columns since T0019.3. Newly logged here as orphaned
    doc drift, explicitly not fixed inline. `[LOW · OPEN]`.
- **Follow-ups:**
  - Merge the T0019 chain to `main` (maintainer decision) — activates the schedule.
  - Run T0019.5's manual checks B–E against a live Postgres at least once before trusting the cron
    unattended (pre-existing follow-up, restated).
  - Finish and commit T0019.10 (in progress on its own branch, stashed aside during this ticket) — a
    named release gate before the T0019.6 workflow may merge to `main`, alongside the already-landed
    T0019.9.
  - Reconcile `docs/Schema_Contract.md`'s stale "future `is_active`" framing against the T0019.3
    reality (own doc-only ticket).
- **Docs updated:** `docs/Full_Design_Document.md`, `docs/Manual_Verification_Guide.md`,
  `docs/Known_Issues.md`, `docs/Repo_Current_State.md`, `docs/Tickets.md`,
  `research/archive/deployment-research-plan.md`, `research/archive/ingestion-milestone-plan.md`,
  this file.

## Milestone 20 — Reconciliation & Activation
- **T0020.4 (docs slice) — cron-activation runbook committed + T0020 milestone authored; activation
  gates (D2/D6/activation/D10) remain maintainer-pending.**
  - **Summary:** a docs-only slice of T0020.4. It does **not** activate the nightly ingestion cron —
    the cron stays dormant. It (1) verifies and commits the maintainer-execution runbook, (2)
    authors the previously-missing `## T0020` milestone + `### T0020.1`–`.4` sub-ticket blocks in
    `Tickets.md`, and (3) wires the cross-references. The live activation steps (D2 ratification, D6
    Neon `alembic stamp head`, `workflow_dispatch` activation + first scheduled run, D10
    live-vs-parked decision) are the maintainer's, captured in the runbook; D5's local
    Docker-Postgres portion was signed in a prior 2026-07-22 coder session, the Neon portion
    remains.
  - **Runbook verification:** spot-checked every load-bearing claim against the repo as it stands —
    **no drift found, nothing rewritten.** Confirmed: `.github/workflows/ingestion.yml` is on
    `main`/`origin/main` (`git log origin/main -- …/ingestion.yml` → `8f8406f`), so activation is
    structurally possible; `config/ingestion.yaml` carries `safety.min_yield: 20` and
    `lifecycle.expire_after_days: 7`; `src/services/ingestion/loader.py` resolves;
    `docs/archive/Manual_Verification_Archive.md` has the `### T0019.2`, `### T0019.5`, `###
    T0019.6` anchors
    the runbook cites; the §2 "mypy now green" note matches `Known_Issues.md` (T0020.3 baseline),
    and the §4 secrets note (real `DATABASE_URL`/`HEALTHCHECKS_URL`; placeholder
    `GROQ_API_KEY`/`LANGFUSE_*`) matches the `[LOW · NOTE]` Known_Issues entry.
  - **Files:** `docs/T0020.4_Cron_Activation_Runbook.md` (committed — was untracked, unchanged
    content), `docs/Tickets.md` (new `## T0020` milestone block + 1 light Backlog cross-ref line),
    `docs/Known_Issues.md` (moved the `[LOW · OPEN]` "T0020 has no milestone block" entry out +
    category count 3→2), `docs/Resolved_Issues.md` (received the resolved entry, Documentation-drift
    count 2→3), `docs/Repo_Current_State.md` (T0020.4 status line + "Next recommended ticket"), this
    file. **No `src/`, `config/`, `tests/`, `.github/` change.**
  - **Commands run:** `git checkout -b feature/t0020.4-cron-activation`, `git add
    docs/T0020.4_Cron_Activation_Runbook.md`, `git log origin/main --
    .github/workflows/ingestion.yml`, `grep` for `min_yield`/`expire_after_days`/the MVG anchors,
    `git status --short`, `git diff --stat`.
  - **Build & test:** docs-only — no build/tests run (nothing under `src/`/`tests/`/`config/`
    changed; no green run is claimed).
  - **Manual verification:** runbook shows as tracked/added in `git status`; `git log origin/main --
    .github/workflows/ingestion.yml` confirms the P1 precondition; `grep "^### T0020\.[1-4]:"
    docs/Tickets.md` → 4 lines between T0019.10 and `## Backlog`; the old ":358" entry text is
    absent from `Known_Issues.md` and present (dated) in `Resolved_Issues.md`; neither the
    Completion_Reports entry nor the Repo_Current_State "Next recommended ticket" claims the cron is
    live.
  - **Wording note (honesty):** the cron is **not** activated by this ticket. The **final activation
    sign-off entry will be appended by the maintainer** per runbook §7 once every gate
    (D2/D6/activation/D10) clears — this entry is the docs slice, not that sign-off.
  - **Follow-ups:** maintainer executes the runbook (D2/D6/activation/D10); after sign-off, move the
    T0019.5 "never run against live Postgres" HIGH item and the cron-dormant items to
    `Resolved_Issues.md` and set "Next recommended ticket" to the T0021/T0022 track. The next
    **coder** work is the T0021/T0022 track (release integrity → honesty → v1.0 tag).
  - **Docs updated:** `docs/Tickets.md`, `docs/Known_Issues.md`, `docs/Resolved_Issues.md`,
    `docs/Repo_Current_State.md`, `docs/T0020.4_Cron_Activation_Runbook.md`, this file.

## Milestone 21 — Release integrity

## T0021.1 — API read-path startup schema assertion

- **Summary:** Added a boot-time `clean_jobs` schema guard on the serving (read) path, closing the
  read-path half of the 2026-07-15 drift incident (T0019.5 covered the write path). On any schema
  mismatch — a missing/renamed/extra column, an absent table, or a DB-inspection failure — the
  FastAPI boot now aborts loudly with `SchemaGuardError` naming the diff, instead of starting a
  server that errors mid-query on the first request. The guard lives in the **API layer** and
  imports only `src.core.*` + `sqlalchemy`; per the ticket's layer-isolation rule it does **not**
  import the `src.services.ingestion` package, so the expected 22-column set is a frozen literal
  (`EXPECTED_COLUMNS`) duplicated deliberately rather than derived from the ingestion ORM.
- **Branch:** `feature/t0021.1-read-path-schema-assertion`, cut from `main` (`bcc81db`). Implemented
  in a dedicated git worktree (`../IHA-t0021.1`) to avoid colliding with a concurrent T0020 session
  that had uncommitted edits to `docs/Known_Issues.md` and `docs/Repo_Current_State.md` in the
  shared working tree.
- **Files created:**
  - `src/api/schema_guard.py` — `SchemaGuardError(RuntimeError)`, the `EXPECTED_COLUMNS` frozenset
    (22 columns, with the "frozen contract" provenance comment), and `assert_serving_schema()`.
    Distinct log events `api.schema_ok` / `api.schema_drift` keep serving-path drift separable from
    the ingestion path's `ingestion.schema_*`.
  - `tests/api/test_schema_guard.py` — six cases mirroring `test_safety.py`'s mock-`session_factory`
    style, patching `src.api.schema_guard.session_factory`: correct schema (no raise), missing
    column, renamed column (both directions named), unexpected extra, empty result → table-missing,
    `OperationalError` → inspect failure.
- **Files changed:**
  - `src/api/app.py` — added `import asyncio` and `from src.api.schema_guard import
    assert_serving_schema`; the `lifespan` hook now calls `await
    asyncio.to_thread(assert_serving_schema)` after `load_settings()` and before
    `build_checkpointer_pool()`. `SchemaGuardError` is left uncaught so the boot aborts.
  - `docs/Known_Issues.md`, `docs/Repo_Current_State.md`, `docs/Manual_Verification_Guide.md`, this
    file.
- **Commands run:** `uv run pytest -q tests/api/test_schema_guard.py` → `6 passed`; `uv run pytest
  -q` (full) → `335 passed, 8 skipped, 19 deselected, 4 subtests passed` (+6 over the 329 baseline);
  `uv run ruff check .` → all checks passed; `uv run mypy` → the same 2 pre-existing baselined
  errors, no third; `git grep -n "services.ingestion" src/api/` → no match.
- **Build/test results:** green. ruff clean, mypy at baseline, full suite +6.
- **Manual verification:** see `archive/Manual_Verification_Archive.md` → T0021.1. Checks A (suite)
  and B
  (layer-isolation greps) run and passing. **Checks C (happy boot) and D (drift-fails-boot) were NOT
  run** — both need Docker Postgres, which was unavailable this session. The automated cases patch
  `session_factory` and prove the diff/exception logic but not the live-DB boot end-to-end.
- **Risks / known issues logged (both `Known_Issues.md` → Config, startup & deployment):**
  - `[LOW · NOTE]` The 22-column expected set is duplicated between `schema_guard.py` and `CleanJob`
    — required by the isolation rule; a real schema change must update both. Fails safe (drift vs
    the live DB is caught loudly at boot), but the maintenance coupling is real. Possible future
    refactor (out of scope): promote the ORM to a shared `src/core` location.
  - `[LOW · NOTE]` Exact-match semantics mean a future *additive* migration to `clean_jobs` aborts
    the live API boot until `EXPECTED_COLUMNS` is updated — the accepted trade-off for symmetry with
    the write-path guard (required-subset semantics deliberately not chosen).
- **Follow-ups:** run manual checks C and D against a live Postgres at least once before relying on
  the guard in production; the shared-`src/core`-ORM refactor if the duplication becomes a
  maintenance burden. Both are out of scope here.
- **Docs updated:** `docs/Known_Issues.md`, `docs/Repo_Current_State.md`,
  `docs/Manual_Verification_Guide.md`, this file.
- **Merge note (2026-08-09):** merged `origin/main` (`56d74d9`) to clear conflicts before review.
  That merge brought in the **Neon-baseline finding** — production `clean_jobs` has only 19 columns,
  missing `first_seen_at`/`is_active`/`last_seen_at`. `assert_serving_schema` therefore **fails
  against production as it stands today**, and this PR must not merge until Neon is migrated to
  Alembic head (`T0020.4_Cron_Activation_Runbook.md` §3, steps 3a–3d). That is not a defect in this
  ticket — the guard correctly detected real drift, pre-merge rather than in production, which is
  exactly what it was built to do. See `Known_Issues.md` → *"Neon production is still at the Alembic
  baseline."*

## T0022.8 - Research prune, decision harvest, and link rewrite

- **Summary:** Harvested 34 durable decisions into `docs/Decision_Log.md`, archived the nine
  completed research records without changing their contents, and redirected every live reference
  to the archive. Added the archive index and policy, and recorded the evaluation quota headline in
  `Tech_Stack.md`.
- **Files created:** `docs/Decision_Log.md` and `research/archive/README.md`.
- **Files moved:** Nine completed research records moved unchanged to `research/archive/`.
- The archive index names each record and its current destination.
- **Files changed:** live inbound-reference documents, `docs/Tech_Stack.md`,
  `docs/Repo_Current_State.md`, `scripts/docs_lint.py`, and this report.
- **Commands run:** `uv run python scripts/docs_lint.py --check link-path` before and after the
  move; a candidate-name sweep with `git grep`; and a live research-file inventory.
- **Build and test:** documentation-only ticket. The link check still fails on pre-existing stale
  live references. Archive records are intentionally excluded, matching the documented policy.
- **Manual verification:** confirm `research/` has five live research files plus `README.md`; open
  `Decision_Log.md` and locate the `tech_stack` rationale; follow five decision-log links; and run
  the per-filename candidate sweep from T0022.8.
- **Risks:** the repository-wide link check was already failing before this ticket, so its zero-exit
  acceptance gate remains blocked by pre-existing stale links outside this ticket's scope.
- **Follow-up tickets:** T0022.9 owns the remaining index rewrite and blocking CI enforcement.
- **Docs that need updating:** T0022.9 should replace the transitional archive references in the
  research and docs indexes with their final curated navigation.

## T0022.9 - Index, ledger, and enforcement

- **Summary:** Completed the documentation-system closing ticket.
  The documentation indexes now distinguish live records from archive evidence.
  The Fact Ledger assigns every tracked fact class a sole owner.
  Documentation lint now checks living-document verification stamps and the CI docs job fails on a
  finding.
- **Files created:** None in this ticket.
- **Link-cleanup decisions:** The measured hygiene-audit table remains intact inside a deliberate
  `lint-allow-link-path` region.
  Archived-tag references retain the `archived-on-tag` marker.
  Deliberately unbuilt future artifacts and prose false positives were rephrased so they are not
  represented as current files.
  Stale Langfuse and golden-module references now describe their actual locations.
  Fenced Markdown examples are not link-checked because they document syntax rather than assert
  repository state.
- **Files changed:** `docs/README.md`, `research/README.md`, `docs/Docs_Conventions.md`,
  `docs/Known_Issues.md`, `docs/Tickets.md`, `docs/Repo_Current_State.md`,
  `docs/Resolved_Issues.md`, `evals/v1_scenario_matrix.md`,
  `research/docs-hygiene-and-system-plan.md`, `research/honesty-enforcement-design.md`,
  `AGENTS.md`, `CLAUDE.md`, `.github/workflows/ci.yml`, `scripts/docs_lint.py`, and
  `tests/test_docs_lint.py`.
- **Commands run:** `python scripts/docs_lint.py`; the 20-test dependency-free docs-lint harness;
  `.venv\\Scripts\\ruff.exe check scripts\\docs_lint.py tests\\test_docs_lint.py`;
  `uv run pytest -q`; and `git diff --check`.
- **Build and test results:** All documentation checks passed.
  The 20 docs-lint tests passed through the available Python 3.12 interpreter.
  `uv run pytest -q` could not run locally because the existing uv cache path cannot be created.
- **Manual verification:** Create a PR with a documentation line over 100 characters and confirm the
  `docs` job is red.
  Edit only one of `AGENTS.md` or `CLAUDE.md` and confirm the parity check fails.
  Remove the stamp from `Known_Issues.md` locally and confirm `--check stamp` reports it.
  Open `docs/README.md` and `research/README.md` cold to confirm the ledger and five live research
  records are understandable without archive plans.
- **Risks:** CI failure is now live, but branch protection still decides whether a failing docs job
  blocks merging.
  That maintainer-controlled action remains outside this ticket.
- **Follow-up tickets:** T0023 scopes and executes the v1.0 release cut.
  M20's branch-protection follow-up remains open.
- **Docs that need updating:** None for this ticket.

## T0022.10 - Prune the dead documentation surface

- **Summary:** Removed the seven obsolete documentation artifacts and the unused self-hosted
  Langfuse stack.
  The tracked ticket-prompt skill now owns the playbook structure, and active records consistently
  describe Langfuse Cloud.
- **Files deleted:** `docs/Prompt_Playbook.md`, three obsolete documents in `docs/archive/`, two <!-- archived-on-tag -->
  completed experiment prompts, and the former `infra/` stack. <!-- archived-on-tag -->
- **Files changed:** `skills/generate-ticket-prompt/SKILL.md` and its local Claude mirror;
  active documentation, indexes, issue registers, historical records, and this report.
- **Commands:** Baseline and final documentation link checks; recovery-tag verification;
  `git grep -n "infra/" -- '*.md'`; `git diff --check`; docs-lint tests; and root Compose health <!-- archived-on-tag -->
  verification.
- **Build and test results:** Documentation checks, skill parity, docs-lint tests, and the full
  documentation linter passed.
  Root Compose health verification was not run because Docker was unavailable in this environment.
- **Manual verification:** Confirm `archive/docs-pre-prune` can display the deleted playbook.
  Run `docker compose up -d`, then request `/api/v1/health` and confirm a `200` response.
  Confirm no live documentation claims a self-hosted Langfuse deployment.
- **Risks:** The recovery tag must remain retained while any historical record references it.
- **Follow-up tickets:** T0022.11 remains next; no new issue-register entry was needed.
- **Docs updated:** `Decision_Log.md`, `Known_Issues.md`, `Resolved_Issues.md`,
  `Repo_Current_State.md`, `Tickets.md`, and documentation indexes and records.

## T0022.11 - Collapse the executed research archives

- **Summary:** Collapsed the five fully superseded research records into compact archive decision
  records while retaining every genuine cited section heading.
  Corrected the stale deployment-research banner and reduced the code-review record to its cited
  bug and doc-insight index.
- **Files changed:** `research/archive/deepeval-sql-agent-eval-planning.md`,
  `research/archive/ingestion-milestone-plan.md`,
  `research/archive/demo-ui-and-golive-plan.md`,
  `research/archive/streaming-implementation-plan.md`,
  `research/archive/schema-enrichment-plan.md`,
  `research/archive/deployment-research-plan.md`, `docs/archive/Code_Review_Notes.md`, <!-- archived-on-tag -->
  `docs/Tickets.md`, `docs/Repo_Current_State.md`, and this report.
- **Commands run:** Citation-heading inventory, inbound-reference search, line-count comparison,
  `python scripts/docs_lint.py`, and `git diff --check`.
- **Build and test results:** The direct documentation linter and diff whitespace check passed.
  `uv run` could not execute in this environment because its configured cache path is invalid.
- **Manual verification:** Open D-016, D-020, and D-014 in `Decision_Log.md` and confirm their
  named archive sections remain present.
  Confirm the eight `Code_Review_Notes.md` bug labels and doc insight 3 remain discoverable.
  Run `uv run python scripts/docs_lint.py`.
- **Citation audit:** Checked 39 cited section headings, all present.
  The inventory's ingestion sections 4.2 and 11 were confirmed as false positives because they
  refer to `deployment-research-plan.md` rather than this record.
- **Risks:** Historical research prose was reduced from 2,241 to 955 total lines across the five
  records (700 excluding blank lines), so readers needing removed planning scaffolding must use
  Git history. The comparable T0022.11 target was ~700-900 total lines; 955 is modestly over,
  because every genuine cited section was retained as a heading.
- **Follow-up tickets:** T0022.12 owns the unharvested archive records and `Known_Issues.md`
  re-triage.
- **Docs that need updating:** No additional documentation update is required for this ticket.

## T0022.12 - Harvest the gaps and rebuild `Known_Issues.md`

- **Summary:** Harvested two previously unrepresented archive decisions and re-triaged the active
  register against the checked-out code and current operational records.
  The register now has 36 actionable entries in a fixed five-line shape, with no note-only entries.
- **Review correction (2026-08-11):** the first pass retired `[HIGH · OPEN]` "pinging keep-alive
  24/7 exhausts Render's 750 free instance-hours" into a single descriptive line in
  `Operations.md`. Nothing had resolved that risk, and it is not note-class, so under this
  ticket's own rule — a closure must name its evidence, and absent evidence the entry stays open
  — it was restored. It guards the still-open cold-start entry, whose obvious fix is continuous
  pinging.
- **Entry accounting:** 72 before, 36 after. 21 note-class facts relocated to `Operations.md` and
  `Tech_Stack.md`, 3 closed into `Resolved_Issues.md` with cited evidence, and the remainder
  merged or rewritten. A removed-entry-by-entry audit was not performed and is the residual risk
  below.
- **Files changed:** `docs/Decision_Log.md`, `docs/Known_Issues.md`, `docs/Operations.md`,
  `docs/Resolved_Issues.md`, `docs/Tech_Stack.md`, `docs/Repo_Current_State.md`,
  `docs/Tickets.md`, and this report.
- **Commands run:** Register inventory and state checks; source, code, and test searches;
  `git diff --check`; `uv run python scripts/docs_lint.py`; and the focused docs-lint test command.
- **Build and test results:** The documentation linter, focused docs-lint tests (20 passed),
  whitespace check, category recount, state-key check, and five-line entry-shape check passed.
  The full `uv run pytest -q` suite exceeded a five-minute timeout without reporting a failure;
  collection completed as 367 of 386 tests, with 19 eval tests deselected.
- **Manual verification:** Open `Known_Issues.md` and confirm the triage table totals 35 entries.
  Open D-036 and D-037 and confirm the source-market and reproducibility decisions are clear.
  Confirm the two remaining HIGH entries are blocked verification work, not unlabelled risks.
- **Risks:** Live provider, database, GitHub, and Render state remains unverified where recorded as
  blocked or maintainer-owned.
- **Follow-up tickets:** T0022.13 is next; T0021.3 and T0021.4 retain the relevant service fixes.
- **Docs that need updating:** No additional documentation update is required for this ticket.

## T0022.13 - Restructure the surviving documents

- **Summary:** Split the serving-path and offline-pipeline designs, moved completed M22 ticket plans
  into the archive, and reshaped the surviving documentation around its reader and owner.
- **Files changed:** `docs/Tickets.md`, `docs/archive/Tickets_Archive.md`,
  `docs/MVP_Technical_Design.md`, `docs/Offline_Pipelines_Design.md`, `docs/README.md`, the seven
  smaller structural targets, both project registers, and this report.
  `docs/archive/Code_Review_Notes.md` was retired; the unique fallback insight now lives in <!-- archived-on-tag -->
  `Resolved_Issues.md`.
- **Commands run:** Baseline and final `python scripts/docs_lint.py`, citation and stale-reference
  searches, line counts, and `git diff --check`.
  The citation audit checked 16 references to design sections 7-8 against the retained headings.
- **Build and test results:** The final documentation linter and whitespace check passed.
  The serving design is 709 lines and `Tickets.md` is 179 lines, inputs to T0022.14's cap decision.
- **Manual verification:** Open `Tickets.md` and confirm active work is visible immediately.
  Open `Offline_Pipelines_Design.md` and verify sections 7-8 retain their numbering.
  Follow the three cron-runbook section-7 references, and use the Decision Log index to find D-014.
- **Risks:** The 709-line serving design remains above the proposed 650-line T2 cap.
  The 179-line Tickets register remains above the prior 150-line T3 cap.
- **Follow-up tickets:** T0022.14 owns the cap decision and enforcement.
- **Docs that need updating:** No additional documentation update is required for this ticket.

## T0022.14 - Enforce the caps

- **Summary:** Added ten blocking documentation checks, with per-document caps parsed from the
  marked documentation map. Capped documents now declare an eviction rule; correction banners,
  orphaned documents, and cap-table drift fail the gate. The link-path check now distinguishes a
  branch name from a missing repository path.
- **Files changed:** `scripts/docs_lint.py`, `tests/test_docs_lint.py`, the documentation map,
  capped-document headers, `Docs_Conventions.md`, project registers, and this report.
- **Commands run:** Baseline and final `uv run python scripts/docs_lint.py`, focused docs-lint
  tests, focused Ruff, and `git diff --check`.
- **Build and test results:** The full documentation linter passed with all ten checks active.
  `uv run pytest tests/test_docs_lint.py -q` passed with 26 tests, and focused Ruff passed.
  `uv run pytest -q` exceeded the 60-second execution window without a result; the ticket changed
  documentation tooling only, so its focused suite is the completed automated coverage.
- **Manual verification:** Add 200 lines to `Known_Issues.md`, remove an `Eviction:` header, add an
  unmarked amendment phrase to a capped document, and create an unlinked `docs/scratch.md`; each <!-- lint-allow-link-path -->
  must fail the matching check and clear when reverted. Change or remove a caps-table row and
  confirm `size-cap` immediately reports the affected document. Confirm a backticked
  `docs/some-branch` stays silent while a missing `docs/example.md` still fails link-path. <!-- lint-allow-link-path -->
- **Risks:** Caps depend on maintainers keeping the documentation map honest. The blocking
  unindexed-document check covers the living `docs/` surface; live research remains governed by
  its index and the orphan check.
- **Follow-up tickets:** Scope a freshness check for `Last verified:` stamps, including the
  trade-off that comparing a stamp with git mtime would require a bump after whitespace-only edits.
- **Docs that need updating:** No additional documentation update is required for this ticket.

## T0021.2 - Agent-path error logging at swallowed catch sites

- **Summary:** Logged the original exception cause at both job-query tool catch sites and logged
  streaming failures with their provider-busy classification.
  Public response wording remained unchanged, as intended for this observability-only ticket.
- **Files created:** None.
- **Files changed:** `src/agents/service.py`, `src/agents/tools/query_clean_jobs.py`,
  `src/agents/tools/get_job_details.py`, `tests/agents/test_service.py`,
  `tests/agents/tools/test_query_clean_jobs.py`, `tests/agents/tools/test_get_job_details.py`,
  `docs/Known_Issues.md`, `docs/Resolved_Issues.md`, and `docs/Tickets.md`.
- **Commands run:** Historical implementation: `git show 6ae9941` confirms the completed changes.
  Recovery verification on 2026-08-12: `uv run pytest -q tests/agents/test_service.py
  tests/agents/tools/test_query_clean_jobs.py tests/agents/tools/test_get_job_details.py`,
  `uv run ruff check src tests`, and `uv run mypy src`.
- **Build and test results:** Recovery verification passed: 24 tests, Ruff, and mypy were green.
- **Manual verification:** Cause a tool `ExecutorError` and a streaming runtime failure.
  Confirm that the public response remains safe while structlog contains the true cause on
  `query_clean_jobs.db_error`, `get_job_details.db_error`, or `stream_agent_response.failed`.
- **Risks:** The ticket deliberately retained one blanket public busy message.
  T0021.4 subsequently replaced it with distinct provider-pressure and unattributed-failure text.
- **Follow-up tickets:** T0021.3 owned accurate provider classification and residual operator
  signals.
  T0021.4 owned visitor-facing error and freshness wording.
- **Docs that need updating:** None.

## T0021.3 - Truthful failure classification and remaining operator signals

- **Summary:** Prevented `psycopg` and `psycopg_pool` failures from being classified as provider
  pressure.
  The checkpointer pool now validates idle connections before borrowing them.
  Added warning signals for synchronous and streaming empty-answer fallbacks and rejected SQL.
- **Files created:** `tests/core/test_errors.py`.
- **Files changed:** `src/core/checkpointer.py`, `src/core/errors.py`,
  `src/agents/service.py`, `src/agents/tools/query_clean_jobs.py`,
  `tests/core/test_checkpointer.py`, `tests/agents/test_service.py`,
  `tests/agents/tools/test_query_clean_jobs.py`, `docs/Known_Issues.md`,
  `docs/Resolved_Issues.md`, `docs/Repo_Current_State.md`, `docs/Tickets.md`, and this report.
- **Commands run:** Reproduced the original defect with
  `uv run python -c "... classify_provider_busy_error(PoolTimeout(...)) ..."`.
  Ran focused pytest, Ruff, mypy, documentation lint, and `git diff --check`.
  The full `uv run pytest -q` run exceeded the 124-second command limit without output.
- **Build and test results:** Focused tests passed, 24 passed.
  `uv run ruff check src tests` and `uv run mypy src` passed before the documentation updates.
  Final documentation and whitespace validation passed.
- **Manual verification:** Start the stack, stop Postgres, and submit a demo question.
  Confirm the `stream_agent_response.failed` structlog event contains the pool cause with
  `reclassified_busy=false`.
  Force empty synchronous and streaming responses with a stub runtime and confirm the two warning
  event names while the fallback text remains unchanged.
  Submit a prompt that generates rejected SQL and confirm `query_clean_jobs.sql_rejected` includes
  the validator reason while the tool response keeps its existing wording.
- **Risks:** A live Neon connection-drop scenario remains manual verification because this ticket
  uses deterministic pool and classifier tests rather than a production database fault.
- **Follow-up tickets:** T0021.4 owns visitor-facing failure and freshness wording.
- **Docs that need updating:** No additional documentation update is required for this ticket.

## T0021.4 - Honest failure and freshness messages

- **Summary:** Added a generic public message for unattributed service failures while retaining the
  busy message exclusively for classified provider pressure.
  Added readiness-date provenance so the demo presents a snapshot date only when it is measured.
- **Files changed:** `src/core/errors.py`, `src/agents/service.py`,
  `src/api/routes/query.py`, `src/api/routes/health.py`, `src/api/static/app.js`,
  `src/api/static/index.html`, `tests/agents/test_service.py`,
  `tests/api/test_query.py`, `tests/api/test_stream.py`, `tests/api/test_ready.py`,
  `tests/api/test_static_serving.py`, `docs/Tickets.md`, `docs/Known_Issues.md`,
  `docs/Resolved_Issues.md`, `docs/Repo_Current_State.md`, and this report.
- **Commands run:** Focused pytest, Ruff, mypy, documentation lint, the default pytest suite, and
  `git diff --check`.
- **Build and test results:** Focused tests passed with 36 tests.
  The default test roots passed when run individually: 362 passed, 1 skipped, and 4 subtests passed.
  Ruff, mypy, documentation lint, and `git diff --check` passed.
- **Manual verification:** Stop Postgres, submit a demo question, and confirm the generic failure
  message appears.
  Restore Postgres and confirm a healthy answer streams.
  Simulate a 429-shaped provider failure and confirm the busy message appears instead.
  Call `/api/v1/ready` with a healthy database and after a date-query failure, then confirm that
  `data_snapshot_date_provenance` changes and the browser only calls measured data a snapshot.
- **Risks:** Browser-driven verification could not connect to the local Uvicorn process in this
  workspace, so the user-visible checks retain the listed manual steps in addition to deterministic
  route and static-asset coverage.
- **Follow-up tickets:** T0023 remains the next release ticket once the ingestion schedule is live.
- **Docs that need updating:** No additional documentation update is required for this ticket.

## T0025.0 - Build the evaluation fixture from Alembic, not the snapshot script

- **Summary:** The evaluation fixture now applies Alembic through head before loading its unchanged
  22 seed rows.
  Fixture resets also clear the Alembic version marker, ensuring the next rebuild creates the full
  serving schema.
- **Files created:** `evals/fixtures/test_loader.py`.
- **Files changed:** `evals/fixtures/loader.py`, `evals/fixtures/test_fixture_counts.py`,
  `scripts/init_db.sql`, `scripts/reset_db.sql`, `README.md`, `docs/Operations.md`,
  `docs/Known_Issues.md`, `docs/Repo_Current_State.md`, `docs/MVP_Technical_Design.md`,
  `research/v1-release-readiness-plan.md`, and this report.
- **Commands run:** `uv run --no-sync pytest -q evals/fixtures/test_loader.py
  tests/api/test_schema_guard.py`, `uv run --no-sync python -m evals.fixtures.loader`, fixture
  schema-guard and lifecycle-default checks, `uv run --no-sync pytest -q
  evals/fixtures/test_fixture_counts.py`, Ruff, mypy, documentation lint, and `git diff --check`.
  The full default pytest suite was also attempted but exceeded the 124-second command limit.
- **Build and test results:** Focused loader and schema-guard tests passed: 8 passed.
  Database-backed fixture tests passed: 8 passed.
  The rebuild printed `COUNT(*) = 22`, the API guard logged `api.schema_ok`, and the lifecycle
  query returned `(22, True, 0)` for total rows, active rows, and NULL active rows.
  Ruff, mypy, documentation lint, and `git diff --check` passed.
- **Manual verification:** Start local Postgres, run `uv run python -m evals.fixtures.loader`, then
  boot the API with `DATABASE_URL` pointing at `internhunter_eval`.
  Confirm startup logs `api.schema_ok`, the loader prints `COUNT(*) = 22`, and every
  `clean_jobs.is_active` value is true rather than NULL.
- **Risks:** The full default pytest suite exceeded the local 124-second command limit without
  output; focused and database-backed checks passed.
  The FastAPI lifespan reached `api.schema_ok` against the fixture, then hit the existing Windows
  `ProactorEventLoop` incompatibility in the asynchronous psycopg checkpointer pool.
- **Follow-up tickets:** None.
- **Docs that need updating:** None.

## T0025.1 - Harvest the archived instrument and delete the duplicate case list

- **Summary:** Restored the archived 29-scenario registry and 2026-07-14 observed-answer artifact.
  The registry is now the only case list.
  The stale 18-case JSON dataset and duplicate loader are removed, while DeepEval goldens are
  generated in memory from the YAML.
  The live harness now reads the registry's native expected-behavior field.
- **Files created:** `evals/scenarios.py`, `evals/scenarios_v1.yaml`,
  `evals/v1_scenario_matrix.observed.json`, and `evals/test_scenarios.py`.
- **Files changed:** `evals/harness.py`, `evals/test_three_seams.py`, `evals/test_judge.py`,
  `evals/fixtures/seed_eval_db.sql`, `docs/Repo_Current_State.md`, and this report.
- **Files deleted:** `evals/goldens/golden_dataset.json`, `evals/goldens/__init__.py`,
  `evals/test_goldens_load.py`, and `evals/test_judge_scaffold.py`.
- **Commands run:** Restored the two archived artifacts from `archive/t0015.4-scenario-matrix`.
  Ran `uv run python -m evals.scenarios --scenario A2`, focused pytest, Ruff, mypy,
  `uv run pytest -q`, `git diff --check`, and the documentation linter.
- **Build and test results:** The no-model dry run reported A2's corrected AI Engineer input and
  expected behavior.
  Focused evaluation tests passed: 6 passed and 30 live tests deselected.
  The default suite passed: 384 passed, 1 skipped, 30 live tests deselected, and 4 subtests passed.
  Ruff and mypy passed.
- **Manual verification:** Run `uv run python -m evals.scenarios --scenario A2`.
  Confirm the output says `List the AI Engineer jobs.` and shows the expected behavior without a
  model call.
  Then run `uv run pytest -q evals/test_scenarios.py` and confirm all 15 probe flags match
  `docs/Agent_Behavior_Spec.md` section 4.
- **Risks:** The historical observed answers are evidence for analysis, not a current agent result.
  The legacy HTTP runner remains intentionally archived; T0025.3 will build over the in-process
  harness instead.
- **Follow-up tickets:** T0025.2 analyzes the restored answers before any new model calls.
- **Docs that need updating:** No additional documentation update is required for this ticket.

## T0025.5 follow-up - Projection-safe execution accuracy

- **Summary:** Fixed execution-accuracy comparison so listing queries compare the unordered multiset
  of `id` values when both sides project `id`.
  Extra listing columns and column aliases no longer create false failures.
  Aggregate and non-`id` results compare positional values, so aggregate aliases are ignored while
  different value projections still fail.
  Updated references to follow the SQL-generation prompt's `ILIKE` rule and corrected the ML
  abstraction reference to use `machine learning` rather than `%ML%`.
- **Files created:** None.
- **Files changed:** `evals/execution_accuracy.py`, `evals/test_execution_accuracy.py`,
  `evals/scenarios_v1.yaml`, and this report.
- **Commands run:** Focused pytest and Ruff reruns were attempted with both the default and
  task-local uv cache paths.
  Both were blocked before Python startup by the broken uv-managed interpreter.
  `git diff --check` completed without findings.
  The local database port was probed and Docker connectivity was blocked by Docker config access
  permissions.
- **Build and test results:** The new projection and aggregate-alias regression tests were added.
  The prior focused suite had passed before the uv interpreter became unavailable.
  Post-fix execution against the real fixture could not be completed in this environment.
- **Manual verification:** Run the focused execution-accuracy tests once uv is repaired.
  Run the persisted-run grader against the seeded fixture.
  Confirm an `id` query with an extra `tech_stack` column passes, reordered rows pass, and
  `COUNT(*)` aliases pass.
- **Risks:** ID-based comparison intentionally treats all other listing columns as explanatory
  projection and does not grade their completeness.
  Reference SQL remains coupled to the frozen fixture and scenario intent.
- **Follow-up tickets:** T0025.6 must assert the cross-currency caveat at the answer seam rather
  than relying on execution accuracy to reject a ranking query.
- **Docs that need updating:** No additional documentation update is required for this follow-up.

## T0025.5 follow-up - Native driver fixture binding and provenance

- **Summary:** Native `python -m evals.driver` runs now bind `DATABASE_URL` to the configured eval
  fixture before importing the harness.
  Manifest `fixture_hash` now fingerprints resolved `clean_jobs` contents and records the database
  name and row count, preventing a seed-file hash from certifying a production run.
  Native eval runs disable Langfuse and set serving and judge provider SDK retries to zero so the
  driver's retry policy owns retry accounting.
  The stale `evals/runs/run.json` artifact was removed.
- **Files created:** None.
- **Files changed:** `evals/driver.py`, `evals/test_driver.py`, `src/agents/runtime/provider.py`,
  `src/agents/tracing/langfuse.py`, `docs/Completion_Reports.md`, and `docs/Repo_Current_State.md`.
- **Commands run:** Python syntax compilation, repository diff validation, and local database/Docker
  connectivity checks.
- **Build and test results:** Syntax compilation passed.
  Pytest could not start because the uv-managed interpreter is unavailable.
  The fixture port responded, but Docker inspection was blocked by Docker config permissions.
- **Manual verification:** Run `uv run python -m evals.driver --ids HLP-COUNT-1 --output
  evals/runs/fixture-smoke.json` and verify the manifest reports `database_name` as
  `internhunter_eval`, `database_row_count` as 22, and the answer count as 5.
  Confirm `manifest.fixture_hash` changes when fixture data changes, while
  `manifest.fixture_seed_hash` tracks only the seed file.
- **Risks:** A full database-content fingerprint adds one read-only scan of `clean_jobs` when a run
  starts.
  Langfuse trace IDs are unavailable for native eval runs by design.
- **Follow-up tickets:** Restore a deliberately enabled tracing mode only after a reachable Langfuse
  endpoint is available.
- **Docs that need updating:** No additional documentation update is required for this follow-up.

## T0025.8 - Rename the registry onto a class-first taxonomy

- **Summary:** Renamed all 29 evaluation scenarios to self-describing `SAF`, `HON`, and `HLP`
  identifiers, without changing inputs, expected behavior, or probe flags.
  Registry scenarios now carry explicit `name`, `requirements`, and nullable `decision` fields.
  The 2026-07-14 matrix remains a dated record and now carries a complete old-to-new map.
- **Files changed:** `evals/scenarios.py`, `evals/scenarios_v1.yaml`,
  `evals/test_scenarios.py`, `evals/v1_scenario_matrix.observed.json`,
  `evals/v1_error_analysis.md`, `evals/v1_scenario_matrix.md`,
  `docs/Agent_Behavior_Spec.md`, `docs/Decision_Log.md`, `docs/Repo_Current_State.md`,
  `docs/Tickets.md`, `research/evaluation-strategy.md`, `research/prompt-refinement-methods.md`,
  and this report.
- **Commands run:** `uv run --no-sync python -m evals.scenarios --scenario HON-CURRENCY-1`,
  `uv run --no-sync pytest -q evals/test_scenarios.py`, Ruff, mypy, documentation lint,
  `git diff --check`, and a full `pytest -q` run.
- **Build and test results:** The no-model dry run resolved HON-CURRENCY-1 and displayed its
  class-first name and unchanged expected behavior.
  The focused registry suite passed: 7 passed.
  Ruff, mypy, documentation lint, and whitespace validation passed.
  The full suite exceeded the local 64-second limit without output.
- **Manual verification:** Run `uv run python -m evals.scenarios --scenario HON-CURRENCY-1`.
  Confirm 29 scenarios and 15 probes with `uv run pytest -q evals/test_scenarios.py`.
  Compare every legacy identifier in the dated matrix with its one-to-one map.
- **Risks:** The full repository suite exceeded the local 64-second limit without output.
  This working tree includes earlier uncommitted tickets, so this change was not isolated on a
  dedicated ticket branch.
- **Follow-up tickets:** T0025.3 can now use the stable scenario taxonomy for persisted runs.
- **Docs that need updating:** None.

## T0025.2 - Error analysis on the recovered answers

- **Summary:** Open-coded all 73 final answers in the recovered 2026-07-14 artifact and grouped the
  visible failures into ranked modes.
  The analysis confirms eight empty-answer `INFRA` outcomes across B1, C2, M-G03, M-D4, M-D7, and
  M-D8, plus C3's distinct database-error outcome.
  M-D7 is now correctly recorded as under-measured rather than an unqualified behavior failure.
  The report makes no claim about routing or SQL generation because the historical artifact contains
  final answers only.
- **Files created:** `evals/v1_error_analysis.md`.
- **Files changed:** `research/evaluation-strategy.md`, `docs/Repo_Current_State.md`, and this
  report.
- **Commands run:** Read-only corpus reconciliation against the YAML registry and observed JSON,
  documentation lint, and `git diff --check`.
- **Build and test results:** No application code changed and no model or judge quota was spent.
  Documentation validation passed.
- **Manual verification:** Follow the four-item checklist in `evals/v1_error_analysis.md`.
  Confirm its ledger has 29 rows, its empty-answer set has 8 turns, C3's error is separate, and no
  upstream attribution appears.
- **Risks:** The artifact proves answer-level failures only.
  The causes of `INFRA` outcomes and visible answer defects remain unassigned until T0025.3 captures
  all three seams.
- **Follow-up tickets:** T0025.3 captures the evidence needed to attribute the ranked modes.
- **Docs that need updating:** No additional documentation update is required for this ticket.

## T0025.5 - Reference SQL and execution accuracy

- **Summary:** Added hand-authored reference SQL for every single-result-set scenario and explicit
  reasons for non-query exemptions.
  Added a fixture-backed comparator that executes generated and reference SQL read-only and compares
  unordered row multisets, preserving duplicate rows.
  Added persisted-run grading with `PASS`, `FAIL`, `INFRA`, `UNRUN`, and `EXEMPT` outcomes.
- **Files created:** `evals/execution_accuracy.py`, `evals/test_execution_accuracy.py`.
- **Files changed:** `evals/scenarios.py`, `evals/scenarios_v1.yaml`, `docs/Completion_Reports.md`,
  and `docs/Repo_Current_State.md`.
- **Commands run:** `uv run pytest -q evals/test_scenarios.py evals/test_execution_accuracy.py
  evals/test_driver.py`, `uv run ruff check evals/execution_accuracy.py evals/scenarios.py
  evals/test_execution_accuracy.py`, and `git diff --check`.
- **Build and test results:** Focused evaluation and driver tests passed: 16 passed.
  Ruff passed.
  The fixture-backed live database check was not run because the local uv interpreter cache became
  unavailable after the focused suite completed.
- **Manual verification:** Run `uv run python -m evals.execution_accuracy evals/runs/run.json`.
  Change one reference query temporarily and confirm its scenario becomes `FAIL` while its persisted
  answer remains unchanged.
  Reorder equivalent `WHERE` terms and confirm the scenario remains `PASS`.
  Confirm every `EXEMPT` result includes a non-empty reason.
- **Risks:** Reference SQL expresses the intended fixture result sets and must be reviewed when the
  frozen fixture or scenario behavior changes.
  Live fixture execution remains environment-dependent on local Postgres.
- **Follow-up tickets:** T0025.6 can consume execution accuracy as its structural seam-2 assertion.
- **Docs that need updating:** No additional documentation update is required for this ticket.

## T0025.6 - The three-tier grader

- **Summary:** Added deterministic structural and textual grading over persisted seam evidence.
  Structural checks run first, including tool usage, execution accuracy, answer counts, and the
  cross-currency no-winner rule.
  Textual checks then validate caveat substance and forbidden phrasing.
  Existing harness judge scores can be consumed at tier 3 without adding new judge metrics.
  Results preserve `PASS`, `FAIL`, `INFRA`, and `UNRUN`, and class summaries exclude the last two
  statuses from pass-rate denominators.
- **Files created:** `evals/grader.py`, `evals/holdout.py`, `evals/test_grader.py`, and
  `evals/holdout_report.md`.
- **Files changed:** `config/prompts.yaml`, `src/agents/runtime/prompts.py`, `evals/driver.py`,
  `docs/Tickets.md`, `docs/Known_Issues.md`, `docs/Repo_Current_State.md`, and this report.
- **Commands run:** Focused grader, scenario, driver, execution-accuracy, and viewer pytest
  commands.
  Also ran `uv run pytest -q evals`,
  `uv run pytest -q tests/agents/runtime/test_prompts.py`, Ruff for the changed evaluation files,
  the glossary loader smoke check, and the documentation lint.
- **Build and test results:** The focused evaluation suite passed 30 tests.
  The full evaluation suite passed 47 tests with 30 live eval tests deselected.
  The prompt loader suite passed 10 tests.
  Ruff passed.
  The holdout reported 1.00 overall accuracy and 1.00 precision and recall for structural and
  textual failure detection.
  No provider or judge calls were made.
- **Manual verification:** Run `uv run python -m evals.grader --observed
  evals/v1_scenario_matrix.observed.json` and confirm the answer-only artifact remains explicitly
  under-measured rather than being scored as behavior.
  Run the persisted-run grader with a T0025.3 artifact and its T0025.5 execution-accuracy result.
  Feed an answer containing the cross-currency caveat that also names a highest-paid job and
  confirm tier 1 returns `FAIL` without a model call.
  Break a deterministic assertion and confirm `evals/test_grader.py` fails.
- **Risks:** The historical 2026-07-14 artifact contains answers only, so structural grading of
  that artifact remains `INFRA` until a persisted three-seam run is available.
  Live fixture execution and credentialed judge scoring remain environment-dependent.
- **Follow-up tickets:** T0025.7 diagnoses the empty-answer fallback.
  The later judge-fidelity and release-policy decisions remain governed by the evaluation strategy.
- **Docs that need updating:** None beyond this completion report, the current-state sheet, the
  ticket roadmap, and the Known Issues register updated here.

## Backlog reconciliation - 2026-08-13

- **Summary:** Reconciled the stale backlog in `Tickets.md` against the numbered roadmap and the
  current operational source of truth.
  Promoted or completed items now point to T0016, T0017, T0018, T0019, T0020, T0022.5, or T0024.
  The custom-domain follow-up remains explicitly deferred because it is cosmetic and requires a
  domain decision.
- **Files changed:** `docs/Tickets.md`, `docs/Repo_Current_State.md`, and this report.
- **Commands run:** `uv run python scripts/docs_lint.py`, `python scripts/docs_lint.py`,
  `python -m pytest -q tests/test_docs_lint.py`, and `git diff --check`.
- **Build and test results:** The configured uv command could not start because its local cache and
  managed interpreter are unavailable.
  The system-Python documentation lint passed, and `git diff --check` completed without whitespace
  errors.
  The system Python has no pytest module, so the focused test suite could not run.
- **Manual verification:** Open `docs/Tickets.md` and confirm the first-screen milestone index
  shows only the custom domain as deferred backlog.
  Confirm every former backlog row has an owner or explicit disposition.
  Follow the `Operations.md` link and verify it is the operational source of truth.
- **Risks:** The custom-domain decision remains outside this ticket and has no effect on the v1.0
  release path.
- **Follow-up tickets:** None required for backlog reconciliation.
  A future post-v1.0 ticket may scope a custom domain if the maintainer supplies the domain choice.
- **Docs that need updating:** None.

## M25 evaluation milestone rescope - 2026-08-13

- **Summary:** Reframed M25 as an evaluation-instrument milestone with an evidence-based closure
  gate, rather than a behavior-improvement or sampling-selection milestone.
  Replaced the confounded T0025.7 sampling A/B with current-configuration acceptance, provenance
  hardening, and instrumented empty-answer verification.
  Rescoped T0025.9 as the real-output grader audit and committed no-model replay CI gate.
  Narrowed the completed T0025.6 wording to the deterministic grader and crafted contract suite
  that were actually delivered.
  Added T0025.10 for record consolidation and milestone closeout.
  Assigned behavior fixes and any evidence-triggered single-variable sampling experiment to M24.
- **Files created:** `.lavish/evaluation-milestone-review.html`.
- **Files changed:** `docs/Tickets.md`, `research/evaluation-strategy.md`,
  `docs/Decision_Log.md`, `docs/Known_Issues.md`, `docs/Repo_Current_State.md`, and this report.
- **Commands run:** Inspected the milestone registry, evaluation strategy, decision log, current
  state, known issues, evaluation code, scenarios, persisted artifacts, CI workflow, and Git state.
  Ran `uv run --no-sync --cache-dir .uv-cache pytest -q evals/test_scenarios.py
  evals/test_driver.py evals/test_viewer.py evals/test_execution_accuracy.py evals/test_grader.py`.
  Ran `uv run --no-sync --cache-dir .uv-cache ruff check evals`,
  `uv run --no-sync --cache-dir .uv-cache mypy src`,
  `uv run --no-sync --cache-dir .uv-cache python scripts/docs_lint.py`, and `git diff --check`.
- **Build and test results:** The focused evaluation suite passed 39 tests.
  Ruff passed for `evals`.
  Mypy reported no issues in 43 source files.
  Documentation lint passed after keeping `Repo_Current_State.md` at its 150-line cap.
  `git diff --check` passed.
  The default uv cache remains unusable with Windows error 183, while the task-local `.uv-cache`
  completed all validation successfully.
- **Manual verification:** Open `.lavish/evaluation-milestone-review.html` and review the milestone
  closure gate, evidence matrix, ticket sequence, and risk register.
  Read the M25 block in `docs/Tickets.md` and confirm the remaining order is T0025.7, T0025.9,
  then T0025.10.
  Confirm no remaining live document requires the bundled sampling A/B or treats the crafted
  holdout as empirical grader calibration.
  Confirm `docs/Repo_Current_State.md` points to T0025.7 and the two new evaluation risks are in
  `docs/Known_Issues.md`.
- **Risks:** The current worktree is dirty and includes untracked M25 implementation files, so no
  run from it can yet qualify as a reproducible baseline.
  The only persisted live smoke contains one scenario and its prompt hash predates the current
  prompt.
  No provider call was made during this documentation rescope, and token or finish telemetry may
  remain unavailable for some provider responses.
- **Follow-up tickets:** Execute T0025.7 for current-configuration instrument acceptance.
  Execute T0025.9 for rule audit, real-output labels, and committed replay CI.
  Execute T0025.10 to consolidate records and close M25.
  M24 then owns behavior improvement, including any justified single-variable sampling experiment.
- **Docs that need updating:** T0025.10 must fold the durable cost record into the evaluation
  strategy, archive completed M25 ticket bodies, and mark the milestone complete after its gates
  pass.

## T0025.7 - Partial instrument acceptance attempt

- **Summary:** Added scenario-registry and worktree provenance to the run manifest.
  Dirty and unknown worktrees are ineligible as baselines and cannot be compared.
  The harness now records latency, provider-reported token usage, and finish reasons per completed
  turn, using `unavailable` instead of inferring missing values.
  Two unchanged-current-configuration live attempts stopped before their first turns when Groq
  rejected the requested token budgets at the TPM limit.
- **Files created:** Ignored `evals/runs/t0025.7-current-config*.json` artifacts and a local
  viewer HTML file.
- **Files changed:** `evals/driver.py`, `evals/harness.py`, `evals/test_driver.py`,
  `evals/viewer.py`, `docs/Known_Issues.md`, `docs/Repo_Current_State.md`, and this report.
- **Commands run:** Rebuilt the 22-row fixture through `python -m evals.fixtures.loader`.
  Ran the seven required scenario IDs with `python -m evals.driver`.
  Ran the no-model execution-accuracy grader, deterministic grader, and local viewer against the
  persisted artifact.
  Ran focused pytest, Ruff, and `git diff --check`.
- **Build and test results:** Focused tests passed 22 of 22 and Ruff passed.
  Both live runs are `PARTIAL_QUOTA`, with one `INFRA` repeat and six `UNRUN` scenarios each.
  The deterministic grader reported 1 `INFRA`, 6 `UNRUN`, and zero measured turns.
  No empty-answer recurrence or provider telemetry was observed because no provider call completed.
- **Manual verification:** After TPM headroom recovers, begin a new capture from a clean worktree.
  Confirm its manifest is baseline eligible and contains Git, fixture, scenario, prompt, and config
  hashes.
  Then run execution accuracy and deterministic grading, open the viewer, and record only each
  turn's first wrong seam.
- **Risks:** The historical empty-answer symptom remains unmeasured under the current configuration.
  This partial artifact is inspectable but is not a baseline or behavioral result.
- **Follow-up tickets:** Continue T0025.7 with a new clean live capture after quota recovery.
  T0025.9 remains blocked on the completed real-output sample.
- **Docs that need updating:** Update the current-state sheet and Known Issues entry after the
  replacement capture completes.

## T0025.7 follow-up - Gradeable acceptance artifacts

- **Summary:** Made execution-accuracy CLI reports safe for date and decimal result values.
  Completed empty-answer turns are now `INFRA`, and the deterministic grade summary carries an
  explicit `empty_answer_count`.
- **Files changed:** `evals/execution_accuracy.py`, `evals/grader.py`, their focused tests,
  `docs/Resolved_Issues.md`, `docs/Repo_Current_State.md`, and this report.
- **Commands run:** Ran the real `HON-CREATED-ON-1` reference query through the CLI.
  Ran the persisted-run grader against a completed empty-answer record.
  Ran focused tests, Ruff, full evaluation tests, mypy, documentation lint, and `git diff --check`.
- **Build and test results:** The real CLI returned `PASS` and printed `created_on` as JSON text.
  The completed empty-answer record returned `INFRA` with `empty_answer_count: 1`.
- **Manual verification:** Run execution accuracy over a real current-configuration capture that
  returns date or decimal fields.
  Confirm the output can be supplied to `evals.grader --execution-accuracy` without a JSON error.
  Confirm a captured empty answer is counted as `INFRA`, not `UNRUN`.
- **Risks:** T0025.7 acceptance remains blocked by provider TPM headroom, not these local paths.
- **Follow-up tickets:** Resume T0025.7 acceptance from a clean worktree after quota recovery.
- **Docs that need updating:** The current-state sheet and risk register remain current until the
  replacement live capture finishes.

## T0025.7 follow-up - UTF-8 execution-accuracy reports

- **Summary:** The date and decimal fix exposed the next failure on the same command.
  The CLI printed `ensure_ascii=False` JSON, so redirecting it into the grader's
  `--execution-accuracy` input raised `UnicodeEncodeError` under Windows cp1252 whenever a report
  carried the fixture's Vietnamese company names, and redirection was the only way to produce that
  file.
  `evals.execution_accuracy` now takes `--output` and writes UTF-8 directly, matching the trace
  viewer's convention. The stdout path is unchanged.
- **Files changed:** `evals/execution_accuracy.py`, `evals/test_execution_accuracy.py`,
  `docs/Resolved_Issues.md`, `docs/Repo_Current_State.md`, and this report.
- **Commands run:** Built a fixture-backed run whose rows carry a Vietnamese company name, a
  `created_on` date, and decimal salaries, then wrote its report through `--output` and graded it
  with `evals.grader --execution-accuracy`.
  Ran the full evaluation tests, the whole suite, Ruff, mypy, documentation lint, and
  `git diff --check`.
- **Build and test results:** The report was written and consumed with no `PYTHONUTF8` override.
  Evaluation tests passed 62 of 62 and the full suite passed 424 with 1 skipped.
- **Manual verification:** Run
  `uv run python -m evals.execution_accuracy <run>.json --output <accuracy>.json`, confirm it
  prints the output path and that the file opens as UTF-8 with company names intact.
  Then pass that file to `uv run python -m evals.grader --run <run>.json --execution-accuracy
  <accuracy>.json` and confirm the accuracy checks join.
- **Risks:** The deterministic grader's own CLI still prints to stdout, which is safe only while its
  report stays ASCII. It is built from registry tokens and fixed strings today, and echoes no answer
  text or database rows, so no report can carry the fixture's non-ASCII values.
- **Follow-up tickets:** None. T0025.7 acceptance still waits only on provider TPM headroom.
- **Docs that need updating:** None beyond this report and the registers updated here.

## T0025.7 follow-up - Paced capture and partial acceptance

- **Summary:** Three acceptance attempts captured zero turns, all stopping on TPM before a first
  turn. Comparing a completed probe turn against the failures established how the ceiling actually
  binds: Groq admits a call when window usage plus the request's own `max_tokens` reserve stays
  under 8000, so a turn's later calls compete with the tokens its earlier calls just spent.
  Retrying re-ran the whole turn inside the window it had filled, which could never recover.
  The driver now idles `eval.driver.turn_pacing_seconds` before every turn after the first and
  passes the same pause into the conversational path, whose turns would otherwise run back-to-back
  inside one window. The paced capture measured 13 of 19 turns across 5 of 7 scenarios.
- **Files changed:** `config/settings.yaml`, `evals/driver.py`, `evals/harness.py`,
  `evals/test_driver.py`, `docs/Known_Issues.md`, `docs/Repo_Current_State.md`, and this report.
- **Commands run:** Ran the driver over the seven required ids, resuming onto one artifact as the
  quota allowed. Ran execution accuracy through `--output`, the deterministic grader over the
  result, and the viewer. Ran focused tests, the full suite, Ruff, mypy, documentation lint, and
  `git diff --check`.
- **Build and test results:** Evaluation tests passed 65 of 65 and the full suite passed 427 with 1
  skipped. The capture graded 4 `PASS`, 9 `FAIL`, and 2 `INFRA`, with `empty_answer_count: 0`.
  Three of those failures are the grader's default tool expectation rejecting correct no-tool
  behavior, not agent behavior.
- **Manual verification:** Open `evals/runs/t0025.7-acceptance-viewer.html` and confirm each
  completed turn shows routing, generated SQL, rows, an answer, and populated telemetry.
  Confirm the manifest records a clean worktree, `baseline_eligible: true`, and the pacing value.
  Confirm `HON-PREMISE-CORRECTION-1` passes all three repeats as the regression control.
- **Risks:** The measured set is partial and its class pass rates understate real behavior until the
  grader rule gap is fixed. No conclusion about the historical empty answers is available from 13
  turns, and six of the eight historical empties came from ids this run never reached.
- **Follow-up tickets:** T0025.9 owns the rule audit and the regrade. M24 owns the three measured
  behavior failures. Capturing the two blocked scenarios needs a paid tier.
- **Docs that need updating:** None beyond the registers updated here; T0025.10 folds the durable
  cost mechanics into the evaluation strategy.

## T0025.7 - Closed partial

- **Summary:** Closed on 2026-08-13 with its instrument scope met and its acceptance scope partly
  met, by explicit decision rather than by running out of options.
  Delivered: registry and worktree provenance with baseline eligibility, per-turn latency, token
  usage and finish reasons, turn pacing, and one clean-worktree run that captured, graded, and
  rendered real turns under the frozen configuration.
  Not delivered: `HLP-CONTEXT-1` and `HLP-COMPOUND-1`, which exceed 8000 TPM inside a single turn.
  Both remaining `max_tokens` and `query.max_rows` workarounds would change what the instrument
  measures, so the capture is deferred to a tier decision instead of being forced.
- **Files changed:** `docs/Tickets.md`, `docs/Known_Issues.md`, `docs/Repo_Current_State.md`, and
  this report. No code changed at closure.
- **Commands run:** Documentation lint and `git diff --check`.
- **Build and test results:** Unchanged from the capture entry above; no code was touched.
- **Manual verification:** Confirm the milestone index, the T0025.7 plan header, and the state sheet
  all describe the same partial outcome, and that T0025.9's blocker line names the 13-turn sample it
  inherits.
- **Risks:** A partial baseline invites over-reading. Every register states the measured count, the
  two absent scenarios, and the three spurious grader failures, so no reader should take the class
  pass rates as the agent's real quality.
- **Follow-up tickets:** T0025.9 is unblocked and starts with the confirmed tool-expectation gap.
  T0024.4 meets the same per-minute ceiling and needs the same tier decision.
- **Docs that need updating:** T0025.10 archives this plan and marks M25 complete once .9 lands.

## T0025.9 - Grader audit and committed replay CI gate

- **Summary:** The grader now reads `expected_tools` from all 29 registry scenarios.
  The human audit of 13 completed T0025.7 turns has zero disagreements after fixing the
  `HON-SQL-DESCRIBE-1` no-tool rule.
  A committed sanitized replay validates its schema, pins each question to the registry, compares
  expected execution and grade outcomes, executes generated and reference SQL against the frozen
  fixture, and invokes the deterministic grader in CI without a model, judge, or outbound call.
  Retiring the hardcoded no-tool set flipped two scenarios, not one; the audit now names both and
  marks `SAF-INJECTION-RESILIENCE-1` as asserted without a capture behind it.
- **Files changed:** `.github/workflows/ci.yml`, `evals/scenarios_v1.yaml`, `evals/scenarios.py`,
  `evals/grader.py`, `evals/replay.py`, `evals/replays/t0025.9-committed.json`,
  `evals/grader_audit.md`, `evals/test_scenarios.py`, `evals/test_grader.py`,
  `evals/test_replay.py`, `docs/Known_Issues.md`, `docs/Resolved_Issues.md`,
  `docs/Repo_Current_State.md`, and this report.
- **Commands run:** Rebuilt the fixture with `uv run python -m evals.fixtures.loader`.
  Regraded the T0025.7 capture using `evals.execution_accuracy` and `evals.grader`.
  Ran focused tests, the full suite, Ruff, mypy, documentation lint, and
  `uv run python -m evals.replay` against the frozen fixture.
- **Build and test results:** Focused grader, scenario, and replay tests passed 25 of 25.
  The full suite passed 438 tests with 1 environmental skip.
  The committed replay passed locally with four `PASS` turns and one intentional cross-currency
  `FAIL` turn.
  Six deliberate breaks each blocked the gate: wrong generated SQL, a compliant refusal answer, an
  unexpected tool call, a leaked `SELECT`, an injected connection string, and an extra schema key.
- **Manual verification:** Run `uv run python -m evals.fixtures.loader`.
  Run `uv run python -m evals.replay` and confirm generated and reference SQL are graded with no
  provider credentials or network call.
  Replace one replay query with `SELECT 0`, confirm the execution-accuracy result fails, then
  restore it.
  Change the `HON-SQL-DESCRIBE-1` answer so it exposes a `SELECT ... FROM` query, confirm the
  deterministic grade fails, then restore it.
- **Risks:** The empirical agreement sample is 13 selected completed turns, not production-wide
  calibration, and it lives in an ignored capture that a clean checkout cannot reproduce.
  T0025.7 did not capture a safety or conversational turn because quota ended first, so three of
  the five replay turns are hand-written from the registry and prove the schema, not the behavior.
  `SAF-INJECTION-RESILIENCE-1` now requires no tool on registry text alone.
  Both risks are open entries in [`Known_Issues.md`](Known_Issues.md).
- **Follow-up tickets:** M24 owns the observed currency, location-synonym, and abstraction behavior
  failures.
  T0025.10 owns M25 record consolidation, the paid-tier decision behind the two open audit
  caveats, and closeout.
- **Docs that need updating:** T0025.10 should archive this completed ticket body and fold the
  durable evaluation acceptance facts into the active strategy record.

## T0025.10 - Consolidate the evaluation records and close M25

- **Summary:** M25 is closed. The evaluation strategy is now the single live evaluation record: the
  quota and cost record was folded into its sections 4a and 4b and archived, and section 4a was
  rewritten to state the serving-side admission ceiling T0025.7 measured, which supersedes the
  earlier judge-side reading that tokens-per-minute was never the constraint.
  Settled decisions D-1 through D-7 were harvested into the Decision Log as D-041 through D-044,
  with D-7 and the milestone boundary already recorded as D-040.
  All ten M25 ticket bodies moved to the ticket archive, leaving the active register with a
  completed-milestone summary that names M24 as the owner of behavior improvement and the release
  gate as the owner of ship thresholds and judge calibration.
- **Files changed:** `research/evaluation-strategy.md`, `research/README.md`,
  `research/archive/README.md`, `research/archive/eval-cost-and-rate-limits.md` (moved),
  `research/docs-hygiene-and-system-plan.md`, `docs/Decision_Log.md`, `docs/Tickets.md`,
  `docs/archive/Tickets_Archive.md`, `docs/README.md`, `docs/Known_Issues.md`,
  `docs/Repo_Current_State.md`, `docs/Tech_Stack.md`, `scripts/docs_lint.py`, and this report.
- **Commands run:** `uv run pytest -q`, `uv run ruff check .`, `uv run mypy`,
  `uv run python scripts/docs_lint.py`, `uv run python -m evals.fixtures.loader`,
  `uv run python -m evals.replay`, and `git diff --check`.
- **Build and test results:** 438 passed, 1 skipped, 30 live eval tests deselected, 4 subtests
  passed. Ruff, mypy, and all ten documentation checks passed. The replay gate passed against the
  rebuilt fixture with no provider call. `git diff --check` is clean.
- **Caps moved, both measured after the change.** `Tickets.md` 500 to 300, measured at 131 once the
  M25 bodies were evicted - the fix `docs/README.md` had already named. `Decision_Log.md` 350 to
  450, measured at 368; harvesting is that document's purpose, and a decision leaves only by being
  revoked, so the cap is the only lever. Both are recorded in the documentation map with reasons.
- **Registers trued up:** counting the register found three stale tallies, two of them predating
  this ticket - `Agent runtime & prompts` claimed 8 with 7 entries, `Evaluation harness` claimed 7
  with 10, and the MED triage row was understated. All are now measured values.
- **Manual verification:**
  1. `docs/Tickets.md` contains no M25 ticket body, and its ownership table names M24, T0024.4, and
     the release gate. Confirm the ten bodies are in `docs/archive/Tickets_Archive.md`.
  2. `research/README.md` lists the evaluation strategy and the still-live M24 honesty design, with
     no cost record. Confirm `research/archive/eval-cost-and-rate-limits.md` exists and that no live
     document links to the old path.
  3. From a clean checkout: `docker compose up -d`, `uv run python -m evals.fixtures.loader`, then
     `uv run python -m evals.replay`. It must pass with no provider credential.
  4. `uv run python scripts/docs_lint.py`, `uv run pytest -q`, `uv run ruff check .`,
     `uv run mypy`, and `git diff --check` all pass.
- **Risks:** The instrument is accepted on a 13-turn sample that is attested rather than
  reproducible, and two scenarios have never been measured. Neither is resolved here, and neither is
  resolvable without a paid tier, so both stay open in `Known_Issues.md` as a maintainer decision
  rather than being closed to make the milestone look finished.
  Folding the cost record required overriding one of its conclusions; the archived original is
  preserved verbatim and now disagrees with section 4a on purpose.
- **Follow-up tickets:** T0023 is the next recommended ticket. M24 owns the currency,
  location-synonym, and abstraction failures the instrument found. T0024.4 owns the full
  29-scenario remeasurement and meets the same tier decision.
- **Docs that need updating:** None outstanding. The strategy record's section 10 states the
  remaining limits, and the release gate still owns D-A, D-B, and D-C.

## T0026.1 - A front door for `evals/`, and one owner for the fixture URL

- **Summary:** `evals/README.md` now states the pipeline order, what each module owns, and which
  two commands spend provider quota. `fixture_database_url()` in `evals/fixtures/loader.py` is the
  single resolver, replacing two implementations that raised different error types and one private
  cross-module import. Five `evals/` documents that the documentation map had never listed now
  have an owner, tier, cap, and reader.
- **The dedupe went the opposite way from the plan.** The ticket assumed the driver's copy was
  redundant. It was load-bearing. `src.core.config.load_settings()` constructs and *caches*
  `Settings()`, taking `DATABASE_URL` from the environment and `.env`. `evals/driver.py` resolves
  the fixture DSN and only then writes it into `DATABASE_URL`, so resolving through `settings`
  would freeze the cache against the serving database and make the bind a silent no-op - a capture
  would have run the agent against production data. The shared function therefore reads
  `config/settings.yaml` directly and never imports `src.core.config`, which is documented at the
  function and in the README.
- **Files changed:** `evals/README.md` (new), `evals/fixtures/loader.py`, `evals/driver.py`,
  `evals/execution_accuracy.py`, `evals/fixtures/test_fixture_counts.py`,
  `evals/fixtures/test_loader.py`, `evals/test_driver.py`, `evals/holdout_report.md`,
  `docs/README.md`, `docs/Known_Issues.md`, `docs/Tickets.md`, `docs/Repo_Current_State.md`,
  and this report.
- **Commands run:** `uv run pytest -q`, `uv run ruff check .`, `uv run mypy`,
  `uv run python scripts/docs_lint.py`, `uv run python -m evals.fixtures.loader`,
  `uv run python -m evals.replay`, and a scripted driver-bind check.
- **Build and test results:** 439 passed, 1 skipped, 30 live eval tests deselected, 4 subtests
  passed - one more than before, the new regression test. Ruff, mypy, and all ten documentation
  checks passed. The replay gate passed against the rebuilt fixture.
- **The regression test was proven to fail.** The new test in `evals/test_driver.py`
  patches `load_settings` to raise. Reintroducing the settings-based resolution made it fail with
  the expected assertion; restoring the direct read made it pass. A pin that has never been seen
  red is not a pin.
- **Caps moved:** `Known_Issues.md` 250 to 275, measured at 258. It sat exactly at its cap while
  three consecutive tickets each found something real. The map records eviction of the stale
  `LOW · OPEN` entries as the cheaper fix next time.
- **Manual verification:**
  1. `uv run python -m evals.fixtures.loader` prints `COUNT(*) = 22`, then
     `uv run python -m evals.replay` exits 0.
  2. `python -c "import os; from evals import driver; print(os.environ['DATABASE_URL'])"` prints the
     `internhunter_eval` DSN, not the serving URL from `.env`.
  3. In the same process, `src.core.config._settings_cache` is still `None` after importing the
     driver - proof the bind happened before anything froze `Settings()`.
  4. `uv run python scripts/docs_lint.py` passes, including the caps check on the five new entries.
  5. Open `evals/README.md` and confirm the quota table names exactly `evals.driver` and the
     `eval`-marked tests as the paid paths.
- **Risks:** `fixture_database_url()` now reads YAML directly rather than through the project's
  settings loader. That is a deliberate exception to the usual configuration path, justified by the
  freeze hazard and documented at the call site; a future refactor that "tidies" it back onto
  `settings` would reintroduce the bug, which is what the regression test exists to catch.
- **Follow-up tickets:** T0026.2 and T0026.3 remain and are independent of each other. One new
  `[LOW · OPEN]` entry was appended to `docs/Known_Issues.md`: fixture-backed tests hang rather
  than skip when Postgres is down, which is how the missing Docker engine presented during this
  ticket.
- **Docs that need updating:** None outstanding.

---

## T0026.2 - Move the deterministic eval tests under `tests/`

- **Summary:** Nine test modules moved from `evals/` and `evals/fixtures/` into `tests/evals/`.
  `evals/` now holds the instrument plus the two modules that call a provider. The redirect in
  `evals/conftest.py` became an autouse fixture scoped to that directory instead of a module-level
  `os.environ` write that fired on every pytest collection.
- **The plan under-counted, in two ways.** It listed six deterministic modules and missed
  `test_writeback.py`, which is deterministic, carries no `eval` marker, and meets the same
  criterion; it moved with the others. It also assumed the two `eval`-marked modules were whole
  modules: `evals/test_judge.py` marks a single test, and its other case runs in the default suite.
  It stays where the ticket put it, since a live case lives there.
- **One rename was forced.** `tests/` has no `__init__.py`, so pytest derives module names from
  basenames and `tests/services/ingestion/test_loader.py` already owns `test_loader`. The fixture
  loader's test is now `tests/evals/test_fixture_loader.py`, which also says what it tests.
- **Narrowing the redirect took two changes, not one.** `evals/driver.py` binds `DATABASE_URL`
  process-wide at import, deliberately. Moving the driver test into `tests/` would have carried
  that bind into the general suite as a collection side effect, so `tests/evals/conftest.py`
  restores the environment on `pytest_collection_finish`. No test there reads `DATABASE_URL`; the
  ones that need the fixture ask `fixture_database_url()` for it by name.
- **The remaining redirect also clears two caches.** Setting the environment variable alone would
  be decorative: if an earlier test has read `settings.DATABASE_URL` or opened the engine, the
  cached `Settings()` and SQLAlchemy engine still hold the serving DSN. The fixture resets both,
  and `monkeypatch` restores them afterwards.
- **Files changed:** `evals/conftest.py`, `evals/README.md`, `tests/evals/conftest.py` (new), the
  nine moved modules under `tests/evals/`, `docs/Known_Issues.md`, `docs/Resolved_Issues.md`,
  `docs/Tickets.md`, `docs/Repo_Current_State.md`, and this report. One line changed inside a moved
  module: `tests/evals/test_scenarios.py` anchors the observed-answers artifact on the `evals`
  package rather than on its own location, since the data stayed behind.
- **Commands run:** `uv run pytest -q` before and after, `uv run pytest -q tests/evals`,
  `uv run pytest -q evals/`, `uv run pytest -m eval --collect-only -q`, `uv run ruff check .`,
  `uv run mypy`, `uv run python scripts/docs_lint.py`, `uv run python -m evals.replay`, and a
  scripted harness that reports `DATABASE_URL` after a run.
- **Build and test results:** 439 passed, 1 skipped, 30 live eval tests deselected, 4 subtests
  passed - identical to the pre-move baseline. `tests/evals` alone reports 76 passed. Ruff, mypy,
  and all ten documentation checks passed. The replay gate passed.
- **The narrowing was proven load-bearing.** With the autouse fixture set to `autouse=False`, a
  probe test inside `evals/` failed on the serving DSN; restoring it made the probe pass. The probe
  was temporary and is not committed.
- **Manual verification:**
  1. `uv run pytest -q` reports 439 passed, 1 skipped, 30 deselected, 4 subtests - the same as
     before the move, with the same single `SCRATCH_DATABASE_URL` skip.
  2. `uv run pytest -q tests/evals` collects and passes the moved modules on their own.
  3. `uv run pytest -m eval --collect-only -q` still lists `evals/test_three_seams.py` and
     `evals/test_judge.py` at their old paths.
  4. Run one non-eval module in a process that clears `DATABASE_URL` first, then read the variable
     back: it holds the serving DSN, not `internhunter_eval`. The same check after the full suite
     now also holds the serving DSN, where before it held the fixture.
- **Risks:** the two live eval modules cannot be run without provider quota, so the autouse fixture
  is verified by a deterministic probe and by `evals/test_judge.py`'s unmarked case rather than by
  a live capture. The mechanism is the same one those tests use.
- **Follow-up tickets:** T0026.3 remains. Two follow-ups were recorded rather than fixed here: the
  linter's `link-path` check treats `docs/Completion_Reports.md` as a live index when it is a dated
  record, so the file now carries a whole-file exemption where treating it like `docs/archive/`
  in `scripts/docs_lint.py` would be the real fix; and `research/evaluation-strategy.md` still
  names `evals/test_judge_scaffold.py`, a module deleted when the goldens were retired.
- **Docs that need updating:** None outstanding. The `Evaluation harness` index count in
  `docs/Resolved_Issues.md` said 10 against 16 measured entries and was corrected to the measured
  value while adding the entry.

---

## T0026.3 - Move the grader's rule table into the scenario registry

- **Summary:** 24 scenarios now carry a `grading:` block holding `expected_answer_count`, the
  required and forbidden answer terms, and the one bespoke structural flag. `grader.py::_rule_for`
  is a registry lookup. The grader keeps how a rule is applied - the three tiers, the four
  outcomes, and the two regexes that are logic rather than data - and owns nothing about what a
  given scenario expects. This finishes the migration T0025.9 started with `expected_tools`.
- **The blocks were generated, not retyped.** A migration whose entire contract is "change no
  verdict" cannot be carried out by copying 99 literal strings by hand. A throwaway script read the
  in-code table through `_rule_for` and emitted each block; the script is not committed.
- **One field could not move as plain data.** `HON-CURRENCY-1` quoted the behavior glossary, so the
  registry carries `{glossary: CROSS_CURRENCY}` and the grader resolves it against
  `config/prompts.yaml`. Pasting the sentence into the registry would let the prompt's wording and
  the grader's expectation drift apart with neither file looking wrong.
- **Where the glossary name is checked, and why it is not the loader.** The registry loader
  validates the *shape* of a reference; `grader.py` validates the *name*. Resolving the name in
  `evals/scenarios.py` would pull `src.core.config` into the registry loader, and that module is
  imported on paths that must not construct and cache `Settings()` before the driver binds the
  fixture database - the T0026.1 hazard. A test asserts every reference in the registry resolves,
  so a typo fails the suite rather than one scenario's grade.
- **Files changed:** `evals/scenarios_v1.yaml`, `evals/scenarios.py`, `evals/grader.py`,
  `evals/holdout.py`, `evals/README.md`, `tests/evals/test_scenarios.py`,
  `tests/evals/test_grader.py`, `docs/Tickets.md`, `docs/Repo_Current_State.md`, and this report.
- **Commands run:** `uv run python -m evals.grader --run evals/runs/t0025.7-acceptance.json
  --execution-accuracy evals/runs/t0025.7-acceptance-accuracy.json` before and after,
  `uv run python -m evals.replay`, `uv run pytest -q`, `uv run ruff check .`, `uv run mypy`, and
  `uv run python scripts/docs_lint.py`.
- **Build and test results:** 445 passed, 1 skipped, 30 live eval tests deselected, 4 subtests
  passed - six more than before, all of them new. Ruff, mypy, and all ten documentation checks
  passed. The replay gate passed against the committed artifact, unmodified.
- **The invariant held more strictly than it was written.** The ticket required the regrade to stay
  7 `PASS` / 6 `FAIL` / 2 `INFRA` with per-turn statuses unchanged. The regrade output is
  **byte-identical** to the pre-change run, so every check name and every detail string is
  unchanged as well.
- **The migrated rules were proven load-bearing.** Replacing `SAF-DESTRUCTIVE-REFUSAL-1`'s required
  phrases with a phrase no refusal contains dropped holdout agreement from 1.0 to 0.833 - the
  grader called `FAIL` where the recorded human label says `PASS` - and two tests failed. Restoring
  the rule restored both.
- **Manual verification:**
  1. Regrade the acceptance capture and diff it against the pre-change output. It is identical.
  2. `uv run python -m evals.replay` exits 0 with the committed artifact untouched.
  3. Break one migrated rule in `scenarios_v1.yaml`, then run
     `uv run pytest -q tests/evals/test_grader.py` and confirm the holdout disagrees with its
     recorded human label. Restore it.
  4. Add `expected_answer_counts: 5` to any scenario's `grading:` block and confirm
     `uv run python -m evals.scenarios` refuses to load the registry.
- **Risks:** the registry can now express a rule that the loader accepts and no scenario intends -
  an over-broad `required_any` group weakens a check without failing anything. The holdout is the
  guard, and it only guards the six scenarios it covers. The independence rule that keeps it
  meaningful is stated in `evals/holdout.py`: its answers and labels are authored against the
  behavior spec with the `grading:` block closed, and widening a rule until a holdout case passes
  makes the suite agree with itself.
- **Follow-up tickets:** none. M26 is complete.
- **Docs that need updating:** None outstanding. D-041 already records the registry as the single
  source of truth for scenario data; this ticket completes it rather than changing it.

---

## T0028.1 - Give evaluation facts an owner, and a check that enforces it

- **Summary:** The Fact Ledger in `docs/README.md` assigned an owner to fourteen fact classes and
  none of them was an evaluation fact, which is how the 29-scenario matrix came to be hand-written
  in five files with nothing able to detect drift between the copies. Added three ledger rows:
  scenario definitions and expectations (`evals/scenarios_v1.yaml`), behavior requirements and the
  probe protocol (`docs/Agent_Behavior_Spec.md`), and the graded outcomes of a dated run (that
  dated record under `evals/`). Added an eleventh `scripts/docs_lint.py` check, `scenario-id`, that
  scans tracked Markdown for `HLP-`, `HON-`, and `SAF-` identifiers and fails on any absent from the
  registry, using the same `lint-allow-*` escape-hatch style as the existing ten checks.
- **The check reads the registry as text, not YAML.** `registered_scenario_ids` pulls `- id: NAME`
  lines with a regular expression instead of parsing `evals/scenarios_v1.yaml`, matching how the
  rest of `docs_lint.py` avoids adding a dependency to a script whose contract is "no dependencies."
- **ID existence only, no text comparison.** The check catches a renamed or deleted scenario that
  left a stale name behind in documentation; it does not compare a scenario's expected text across
  the five files that duplicate it. Cutting that duplication is `T0028.2` and `T0028.3`.
- **Files changed:** `docs/README.md`, `docs/Docs_Conventions.md`, `docs/Tickets.md`,
  `docs/Repo_Current_State.md`, `scripts/docs_lint.py`, `tests/test_docs_lint.py`, and this report.
- **Commands run:** `uv run python scripts/docs_lint.py`, `uv run pytest -q`,
  `uv run ruff check .`, `uv run mypy`.
- **Build and test results:** Docs lint passed with zero findings across all eleven checks. Ruff
  reported no issues. Mypy found no issues in 43 source files. `pytest -q` ran 447 passed, 2
  skipped, 30 deselected (live eval tests needing API keys or a paid tier), 4 subtests passed. Two
  failures in `tests/evals/test_driver.py`
  (`test_driver_persists_all_seams_and_resumes_completed_scenario` and
  `test_quota_exhaustion_marks_remaining_scenarios_unrun`) are environmental, not caused by this
  change: both need a local Postgres fixture database on `localhost:5433`, which was not running in
  this session, and neither test touches documentation or the scenario registry.
- **Manual verification:**
  1. `uv run python scripts/docs_lint.py` exits 0.
  2. Temporarily add `HLP-NOT-A-SCENARIO-9` to a tracked Markdown file and re-run the linter; it <!-- lint-allow-scenario-id -->
     fails, naming both the file and the ID. Revert the edit.
  3. `docs/README.md` shows the three new Fact Ledger rows and stays under its 150-line cap, which
     the `size-cap` check enforces and which passed above.
- **Risks:** the `scenario-id` pattern matches any `HLP-`/`HON-`/`SAF-` token shape, so prose that
  names an example ID on purpose (as this ticket's own manual-verification step does) needs the
  `<!-- lint-allow-scenario-id -->` marker or the check reports a false positive. The marker is
  already applied where that happens in `docs/Tickets.md`.
- **Follow-up tickets:** `T0028.2` - cut the duplicated scenario table out of the behavior spec, now
  unblocked because this check can prove no scenario ID is dropped in the process.
- **Docs that need updating:** None outstanding.

---

## T0028.2 - Cut the duplicated scenario table out of the behavior spec

- **Summary:** `docs/Agent_Behavior_Spec.md` §4a-4c (the registry, coverage-gap, and
  decision-specific probe tables) carried six columns each - ID, requirements or decision, fixture
  row IDs, input or turns, expected behavior, and probe status - and four of those columns
  duplicated `evals/scenarios_v1.yaml`, which D-041 already names the sole owner of that data.
  Reduced every table to the three columns the spec owns: scenario ID, the requirement (or decision)
  under test, and probe status. The legend above §4a now states explicitly that the registry owns
  the fixture rows, input, and expected behavior the tables used to restate.
- **No scenario ID, requirement, decision, or probe flag changed.** A script compared the ID set in
  the registry against the ID set matched in the spec by the same `HLP|HON|SAF` pattern
  `scripts/docs_lint.py` uses; both sets are the 29 registry IDs, exactly.
- **The freeze note now says what it protects.** The file's `Status` block said "Frozen:
  2026-07-11" without saying what freezing meant for editability. Added one sentence: the freeze
  protects the requirements under test, the probe protocol, and the settled decisions, not the
  per-scenario expectations this ticket cut - matching the maintainer's 2026-08-14 confirmation
  recorded in `docs/Tickets.md`. Added a `> **Last verified:** 2026-08-14` stamp per
  `Docs_Conventions.md`; the file previously had none.
- **Files changed:** `docs/Agent_Behavior_Spec.md`, `docs/Repo_Current_State.md`, and this report.
- **Commands run:** `uv run python scripts/docs_lint.py`, a one-off Python check comparing the
  registry's ID set against the spec's referenced ID set, and a tree-wide search for
  `COUNT(*) via query_clean_jobs`.
- **Build and test results:** Docs lint passed with zero findings across all eleven checks. The ID
  comparison found no ID missing from either side. The search for the retired expected-behavior
  phrase returned the registry (`evals/scenarios_v1.yaml`), the sealed snapshot
  (`evals/v1_scenario_matrix.md`), and this ticket's own text in `docs/Tickets.md` quoting the
  search string - not the behavior spec. This ticket edits documentation only; no test suite covers
  its content, and no code changed.
- **Manual verification:**
  1. Every ID in `evals/scenarios_v1.yaml` still appears in §4a-4c of the behavior spec.
  2. `uv run python scripts/docs_lint.py` exits 0.
  3. Searching the tree for `COUNT(*) via query_clean_jobs` returns the registry and the dated
     records only, not the behavior spec.
- **Risks:** none identified. The spec's requirement-to-scenario mapping is unchanged; a reader
  now makes one hop through the registry link to see a scenario's input and expected behavior
  instead of finding it inline.
- **Follow-up tickets:** none new. `T0028.3` (seal the frozen records, merge the two instrument
  reports) and `T0028.4` (operating manual, stale-claim sweep) remain open and are independent of
  this ticket per the milestone scoping.
- **Docs that need updating:** None outstanding.

---

## T0028.3 - Seal the frozen records, and merge the two instrument reports

- **Summary:** `evals/v1_scenario_matrix.md` (the 2026-07-14 raw measurement) and
  `evals/v1_error_analysis.md` (its open-coded failure modes) sat beside the living evaluation
  docs with nothing marking them sealed. Moved both, unchanged, into a new `evals/archive/` and
  extended `scripts/docs_lint.py::is_archive()` to exempt it the same way `docs/archive/` and
  `research/archive/` already are. Merged `evals/grader_audit.md` and `evals/holdout_report.md`
  into a single `evals/Instrument_Report.md`, and updated the caps rows in `docs/README.md` and
  every inbound link across the tree to the new paths.
- **Neither dated record's content changed, and neither merged report's numbers were
  re-derived.** A line-by-line diff against the pre-move content of all four files - stripping
  only headings and the status/eviction blockquotes that had to change shape for the merge -
  shows the only additions are the merged eviction rule and a one-sentence note that the merge
  changed no content or numbers.
- **Historical prose that named the old paths as fact, not as a live pointer, was left as
  written and marked, not rewritten.** `docs/Tickets.md`'s own "Measured on 2026-08-14" scoping
  paragraph and this ticket's Objective/Notes text describe the pre-move state; so does a
  2026-08-09-dated reflow decision in `research/docs-hygiene-and-system-plan.md` and a
  2026-07-16 design record in `research/honesty-enforcement-design.md`. Each got
  `<!-- lint-allow-link-path -->` rather than an edit, matching the convention `Docs_Conventions.md`
  already sets for a historical audit's stale paths. Functional pointers meant to keep resolving
  - `docs/README.md`, `evals/README.md`, `docs/Decision_Log.md`, `docs/Known_Issues.md`,
  `docs/Agent_Behavior_Spec.md`, `docs/Repo_Current_State.md`, `docs/Tickets.md`'s T0024.6 entry,
  and `research/evaluation-strategy.md` - were updated to the new paths instead.
  `docs/Completion_Reports.md` needed no change: its historical entries already sit inside the
  file's existing `lint-allow-link-path:begin/end` region.
- **The stale `REFLOW_TARGETS` entry for `evals/v1_scenario_matrix.md` was removed, not
  renamed.** Once the file lives under `evals/archive/`, `is_archive()` exempts it from reflow the
  same way `docs/archive/**` is exempt (documented rationale: archived files are read rarely and
  edited never), so keeping a now-unreachable string in the whitelist would be dead configuration.
- **Files changed:** `evals/v1_scenario_matrix.md` and `evals/v1_error_analysis.md` (moved to
  `evals/archive/`), `evals/grader_audit.md` and `evals/holdout_report.md` (removed, merged into
  the new `evals/Instrument_Report.md`), `scripts/docs_lint.py`, `docs/README.md`,
  `evals/README.md`, `docs/Decision_Log.md`, `docs/Known_Issues.md`, `docs/Agent_Behavior_Spec.md`,
  `docs/Repo_Current_State.md`, `docs/Tickets.md`, `research/docs-hygiene-and-system-plan.md`,
  `research/evaluation-strategy.md`, `research/honesty-enforcement-design.md`, and this report.
- **Commands run:** `uv run python scripts/docs_lint.py`,
  `uv run pytest -q tests/test_docs_lint.py`, `uv run ruff check .`, `uv run mypy`, a tree-wide
  search for every moved or renamed filename, and a scripted diff of the merged report's content
  against the pre-merge files.
- **Build and test results:** Docs lint passed with zero findings across all eleven checks. Ruff
  and mypy reported no issues. `tests/test_docs_lint.py` passed 30, skipped 1 (environmental,
  unrelated). This ticket touches documentation and one lint script only; no other test suite
  covers its content.
- **Manual verification:**
  1. `uv run python scripts/docs_lint.py` exits 0.
  2. No Markdown file in the tree links to a moved or renamed path (verified by the passing
     `link-path` check plus a manual `grep` for each old filename, confirming every remaining
     mention is either inside `docs/archive/`, inside `docs/Completion_Reports.md`'s exempted
     region, or carries a `lint-allow-link-path` marker).
  3. `docs/README.md` lists `evals/Instrument_Report.md` and no longer lists `grader_audit.md` or
     `holdout_report.md` separately.
- **Risks:** none identified. The merged report's cap (250 lines) gives the same rough headroom
  as the sum of the two caps it replaces (200 + 50); the file is 162 lines today.
- **Follow-up tickets:** none new. `T0028.4` (operating manual, stale-claim sweep) remains open
  and is independent of this ticket per the milestone scoping.
- **Docs that need updating:** None outstanding.

<!-- lint-allow-link-path:end -->
