# Langfuse observability remediation plan

> **Status:** Draft for maintainer approval.
> This plan turns [Langfuse observability gaps](../research/langfuse-observability-gaps.md) into
> session-sized implementation changes for M28 operational telemetry and M29 production evaluation.

> **Last verified:** 2026-08-21

> **Eviction:** This plan leaves when every approved session is merged or its scope is superseded by
> a recorded decision.

## Goal and expected outcome

Make Langfuse traces accurate, attributable, and useful for comparing evaluation and production
behavior without changing the agent's product behavior or replacing the existing evaluation runner.

The work is a planned, research-led change because it crosses tracing, runtime, configuration,
evaluation, and deployment operations.

## Approved decisions

The maintainer approved the research recommendations below on 2026-08-21.
Implementation may proceed only within the session that owns each decision.

| Decision | Recommendation from research | Needed before |
|---|---|---|
| Prompt authority | Keep `config/prompts.yaml` authoritative and mirror versioned prompts to Langfuse. | Session 6 |
| Eval tracing | Enable it in the `evaluation` Langfuse environment, accepting the Hobby-plan ingestion usage. | Sessions 3 and 8 |
| Dataset ownership | Keep `evals/scenarios_v1.yaml` authoritative and make Langfuse a derived, lint-checked mirror. | Session 8 |
| Cost gate | Measure cost only and do not add a release gate until drift evidence justifies one. | Session 2 |

## Session plan

Each session is one coherent pull request from a worktree based on `origin/main`.
Each pull request includes the repository template, its risks and exclusions, and the manual check
listed below.

### Session 1 - streamed usage metadata

**Scope:** Fix F1 so DeepSeek streamed generations report token usage.

**Files:** Update `config/settings.yaml` with a per-profile `stream_usage` setting, update
`src/agents/runtime/provider.py` to pass it only to the DeepSeek model branch, and extend the
provider tests.

**Verification:** Run focused provider tests, then execute one end-to-end streamed chat with
Langfuse enabled and confirm non-zero input and output token counts on its generation.

**Exclusions:** Do not add model pricing, tags, prompt registration, or tracing lifecycle changes.

**Risk:** A provider arm that does not support `stream_options` must keep the setting disabled.

### Session 2 - reproducible model pricing

**Scope:** Fix F2 with an idempotent script that creates exact Langfuse model definitions from
version-controlled price evidence.

**Files:** Add a narrowly scoped script under `scripts/`, its tests, and the smallest configuration
or data file needed to hold exact model-match patterns and pricing inputs.

**Verification:** Run the script twice against a disposable or designated test project and verify it
does not duplicate definitions, then make a traced turn and reconcile Langfuse cost to recorded
usage and the published price.

**Exclusions:** Do not turn cost into a release gate or create broad regexes that can price another
provider arm incorrectly.

**Risk:** Published provider pricing and cache-token accounting need a dated evidence refresh before
the script's values are approved.

### Session 3 - traffic classification and release attribution

**Scope:** Fix F4 and F8 by introducing the closed environment and tag taxonomy plus deployment
release and prompt-version attribution.

**Files:** Update `config/settings.yaml`, tracing configuration, runtime call sites, eval-driver
configuration, deployment configuration if required, and focused tracing and driver tests.

**Verification:** Run an API chat and an eval capture with tracing enabled, then confirm they appear
in separate `production` or `local` and `evaluation` environments with the prescribed tags,
release, and prompt version.

**Exclusions:** Do not add datasets, prompt registry integration, or new metrics.

**Risk:** Tags must remain a small, validated vocabulary rather than a free-form observability API.

### Session 4 - trace context correctness and readability

**Scope:** Fix F5 and F6 by replacing shared-handler trace-id reads with request-scoped Langfuse
context and assigning useful root trace names, session, user, tags, and version attributes.

**Files:** Update `src/agents/tracing/langfuse.py`, `src/agents/runtime/react_agent.py`, and
focused runtime and concurrency tests.

**Verification:** Run two concurrent end-to-end streamed chats with different session ids, then
confirm each response returns its own trace URL and each trace has the correct query, session, and
name.

**Exclusions:** Do not record trace-level input or output until the current v4 SDK API is confirmed
against authoritative documentation or a local spike.

**Risk:** Context propagation must cover both `ainvoke` and streaming generator lifetimes.

### Session 5 - reliable tracing lifecycle

**Scope:** Fix F10 and the startup part of F15 by adding graceful Langfuse shutdown, non-fatal
startup authentication diagnostics, and a streaming flush after the metadata event.

**Files:** Update the API lifespan, tracing module, runtime streaming flow, and lifecycle tests.

**Verification:** End-to-end check that the final streamed metadata arrives before export draining,
then stop the application and confirm shutdown is called and queued events are exported.

**Exclusions:** Do not make tracing credentials mandatory or change health-contract semantics unless
the existing health contract is separately approved for expansion.

**Risk:** The demo trace link may briefly lead before ingestion completes, which needs manual UX
validation.

### Session 6 - git-authoritative prompt registry and SQL trace structure

**Scope:** Fix the tractable parts of F3 and F13 by registering YAML prompts idempotently and linking
the `sql_generation` prompt through an explicit child generation observation.

**Files:** Add a prompt-registration script and tests, update tracing support and the SQL-generation
call site, and update focused tracing tests.

**Verification:** Change no prompt content, run registration twice, and verify no duplicate version.
Run a SQL-producing query and verify the generation is nested under the tool span and links to the
registered SQL prompt.

**Exclusions:** Do not move authoring to Langfuse or claim that the ReAct system prompt is linked
until an SDK-supported LangGraph integration is proven.

**Risk:** The React prompt remains registered and trace-sliceable by version but not natively linked.

### Session 8 - Langfuse dataset-run integration

**Scope:** Fix F7 by mirroring the scenario registry into a Langfuse dataset and associating each
existing driver capture and score with a dataset run.

**Files:** Add the mirror or synchronization module, update `evals/driver.py` and
`evals/writeback.py`, add drift and writeback tests, and add score-config provisioning if approved.

**Verification:** Run a small real eval capture, confirm one dataset run groups its scenario traces
and scores, and verify a rerun is idempotent without replacing the driver's checkpoint and resume
behavior.

**Exclusions:** Do not migrate execution to `run_experiment()` or remove the local capture artifacts
and viewer.

**Risk:** Dataset mirroring needs a deterministic identity and a CI drift check so Langfuse never
becomes a second editable scenario source.

## Cross-session verification

Run the focused tests for each changed layer in its session and the available full build or test
gates before merging.
After Session 8, conduct a manual production-like chat, a streamed chat, and an evaluation capture
to verify trace separation, correct links, usage, pricing, prompt lineage, and dataset-run grouping
together.

## Explicit exclusions

This plan does not change agent behavior, add user feedback scoring, introduce sampling before
volume requires it, change the Langfuse hosting decision, make latency and cost release gates, or
implement export masking or a retention policy.

## Sequencing constraints

Session 1 must precede Session 2 because cost needs streamed usage.
Session 3 must precede Session 8 because evaluation traces need a separate environment.
Session 4 should precede Session 5 because the lifecycle work must preserve the request-scoped trace
context.
Session 6 can follow its approval decision independently after Session 4.
