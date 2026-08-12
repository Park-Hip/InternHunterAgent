# Known Issues & Risks

> **Last verified:** 2026-08-11 against checked-out code, tests, configuration, and active runbooks.

This register holds actionable risks that are open, blocked, or awaiting a maintainer decision.
> **Eviction:** An entry leaves when fixed, superseded, or reclassified in its owning document.
Closed history is preserved in [Resolved Issues](Resolved_Issues.md).

## Triage

| Severity | Open | Blocked | Decision |
|---|---:|---:|---:|
| HIGH | 0 | 2 | 0 |
| MED | 8 | 2 | 2 |
| LOW | 18 | 3 | 0 |

**State key:** `OPEN` needs implementation or verification, and `BLOCKED` needs a live service,
or maintainer action, and `DECISION` needs a product or operational choice.

## Config, startup & deployment (15)

- **`[LOW · BLOCKED]` The serving-model pin still lacks its final live baseline confirmation.**
  - **Found:** T0011.5 preparation.
  - **Impact:** A retired or incompatible Groq model ID would fail the tool loop at runtime.
  - **Next:** Before the baseline, run a tool-using query with the configured qwen model.
  - **History:** [Resolved Issues](Resolved_Issues.md) records the retired-model replacement.

- **`[HIGH · BLOCKED]` Ingestion safety checks have not been exercised against live Postgres.**
  - **Found:** T0019.5.
  - **Impact:** The abort-before-write safeguards remain proven only by mocked unit tests.
  - **Next:** Run checks B through E in [Manual Verification Guide](Manual_Verification_Guide.md).
  - **History:** `tests/services/ingestion/test_safety.py` covers the isolated logic.

- **`[MED · OPEN]` Render Free cold starts can delay the public demo by about a minute.**
  - **Found:** T0018.4 public deployment.
  - **Impact:** Visitors outside the keep-alive window can see the same-origin UI appear stalled.
  - **Next:** Keep the waking-hours ping or move to Render Starter within the recorded cost ceiling.
  - **History:** [Operations](Operations.md) owns the active keep-alive configuration.

- **`[HIGH · OPEN]` Pinging keep-alive 24/7 would exhaust Render's 750 free instance-hours.**
  - **Found:** 2026-07-16, assessing the cold-start mitigation above.
  - **Impact:** 744 h against a 750 h workspace cap; overrun silently suspends every Free
    service until the month flips, and only a paid plan undoes it.
  - **Next:** Keep the ping windowed — that is the whole mitigation, not a preference.
  - **History:** Cliff detail on `archive/docs-pre-prune`; see [Operations](Operations.md).

- **`[MED · DECISION]` VietnamWorks terms leave public listing display unresolved.**
  - **Found:** T0019.1 terms review.
  - **Impact:** The public portfolio demo may exceed an internal-use content restriction.
  - **Next:** Choose attribution, restricted access, accepted risk, or permission before rearming.
  - **History:** [deployment research §11](../research/archive/deployment-research-plan.md).

- **`[LOW · OPEN]` Native Windows `uvicorn` startup is incompatible with the checkpointer pool.**
  - **Found:** T0019.2 manual verification.
  - **Impact:** Local API development hangs on Windows while Docker and Render continue to work.
  - **Next:** Use Docker today; scope a fix if native development is needed.
  - **History:** [Operations](Operations.md) records the current workaround.

- **`[LOW · OPEN]` `scripts/init_db.sql` is behind the Alembic head for lifecycle columns.**
  - **Found:** T0019.3.
  - **Impact:** A database made only with the script cannot use lifecycle ingestion functions.
  - **Next:** Move fixture setup to Alembic or explicitly retain and document the limited script.
  - **History:** [Operations](Operations.md) defines Alembic as the production migration path.

- **`[LOW · BLOCKED]` The `max_jobs: 150` ceiling has not been remeasured against VietnamWorks.**
  - **Found:** T0019.9.
  - **Impact:** Changed source yield could make the cap truncate coverage again without notice.
  - **Next:** Re-measure after the terms decision.
  - **History:** [Data ingestion stage](../research/archive/data-ingestion-stage.md), section 11.

- **`[LOW · OPEN]` An ingestion run that reaches `max_jobs` emits no truncation signal.**
  - **Found:** T0019.9.
  - **Impact:** Operators cannot distinguish a complete collection from one stopped by the cap.
  - **Next:** Log `truncated: true` or warn when collection exits because the cap was reached.
  - **History:** `src/services/ingestion/sources/vietnamworks.py::_collect`.

- **`[LOW · OPEN]` The cron-job.org keep-alive can time out during an overnight Render wake-up.**
  - **Found:** T0019.7 execution history.
  - **Impact:** One missed ping can permit another cold start before the next scheduled ping.
  - **Next:** Investigate only if failures recur; the operating window and cadence are documented.
  - **History:** [Operations](Operations.md) records the observed first-wake behavior.

- **`[MED · OPEN]` Dead checkpointer connections can be reported as provider pressure.**
  - **Found:** T0019.7 live Render investigation.
  - **Impact:** A Neon pool failure can reach a visitor as the generic busy message.
  - **Next:** Add a psycopg pool health check and preserve pool provenance in error classification.
  - **History:** `src/core/checkpointer.py` and `src/core/errors.py`.

- **`[MED · BLOCKED]` The ingestion schedule is disabled pending its activation gates.**
  - **Found:** T0020.4.
  - **Impact:** Production listings do not refresh automatically while the schedule stays parked.
  - **Next:** Complete a green manual dispatch and signed gates before uncommenting the cron.
  - **History:** [Cron Activation Runbook](T0020.4_Cron_Activation_Runbook.md).

- **`[MED · OPEN]` `/ready` can silently fall back to a snapshot date after a DB error.**
  - **Found:** D6 production migration.
  - **Impact:** A future schema or database failure could make the demo overstate corpus freshness.
  - **Next:** Expose whether the readiness date is measured or fallback-derived.
  - **History:** [Resolved Issues](Resolved_Issues.md) records the prior production occurrence.

- **`[MED · BLOCKED]` CI runs on pull requests, but branch protection needs maintainer setup.**
  - **Found:** T0020.3.
  - **Impact:** A failing CI run does not necessarily prevent a merge to `main`.
  - **Next:** Require the CI check in GitHub branch protection and prove it with a red test PR.
  - **History:** `.github/workflows/ci.yml` and [Tickets](Tickets.md) M20.

- **`[LOW · OPEN]` Two targeted mypy ignores conceal third-party generic mismatches.**
  - **Found:** T0020.3.
  - **Impact:** Static type checking cannot detect incompatible changes at those call sites.
  - **Next:** Resolve the pool and LangChain message generic types in a dedicated typing pass.
  - **History:** `src/core/checkpointer.py` and `src/agents/runtime/middleware.py`.

## Agent runtime & prompts (8)

- **`[LOW · OPEN]` The agent can call `query_clean_jobs` twice with identical arguments.**
  - **Found:** T0006.10 verification.
  - **Impact:** The harmless duplicate query wastes one database round-trip.
  - **Next:** Address only if evaluation shows the pattern is frequent.
  - **History:** `query_clean_jobs` is deterministic and read-only.

- **`[LOW · OPEN]` The agent can reason fully before declining an unsupported attribute.**
  - **Found:** T0007.2 verification.
  - **Impact:** Questions outside the schema receive a truthful but slow refusal.
  - **Next:** Add a short-circuit example when behavior work resumes.
  - **History:** `config/prompts.yaml` owns the visible schema.

- **`[MED · OPEN]` The model does not reliably refuse to invent posting freshness.**
  - **Found:** T0009.8 repeated probe.
  - **Impact:** It can claim a job is most recent despite no trustworthy posting-date field.
  - **Next:** Add and evaluate an explicit freshness refusal before exposing new date semantics.
  - **History:** [Schema Contract](Schema_Contract.md) keeps `posted_date` hidden.

- **`[MED · OPEN]` The hidden-salary honesty wording is not followed reliably.**
  - **Found:** T0009.8 probe.
  - **Impact:** Negotiable pay can be called missing, contrary to the prompt rule.
  - **Next:** Add a canonical few-shot and measure it in the behavior goldens.
  - **History:** [Agent Behavior Spec](Agent_Behavior_Spec.md).

- **`[LOW · OPEN]` The prompt-only id-first SQL convention is not deterministic.**
  - **Found:** T0009.11.
  - **Impact:** A result without `id` cannot chain into a `get_job_details` lookup.
  - **Next:** Reinforce with a few-shot only if omission is observed in evaluation.
  - **History:** `config/prompts.yaml` contains the current convention.

- **`[LOW · OPEN]` Salary-sort SQL can omit the requested single-currency scope.**
  - **Found:** T0012.2 verification.
  - **Impact:** Sorting mixed currencies can produce a misleading ordering.
  - **Next:** Add and evaluate a salary-sort example if the failure repeats.
  - **History:** `config/prompts.yaml` contains the current instruction.

- **`[LOW · BLOCKED]` Live SQL and streaming behavior need credentialed end-to-end verification.**
  - **Found:** T0012.2 and T0017.
  - **Impact:** Unit tests cannot prove provider output, streaming, and no-leak behavior together.
  - **Next:** Run the archived SQL probe, stream curl, and fixture checks with credentials.
  - **History:** [Manual Verification Archive](archive/Manual_Verification_Archive.md).

- **`[MED · OPEN]` The frozen `behavior_glossary` is absent from `config/prompts.yaml`.**
  - **Found:** T0020.1 recovery audit.
  - **Impact:** The behavior specification has no machine-readable canonical phrase source.
  - **Next:** Land the archived 18 entries and re-run goldens before honesty enforcement work.
  - **History:** `archive/t0015.2-behavior-glossary` preserves the source block.

## Query tooling & SQL safety (2)

- **`[LOW · OPEN]` An honored explicit result count does not state that further matches exist.**
  - **Found:** T0010.7.
  - **Impact:** "Found 3" after a request for three can be mistaken for a total.
  - **Next:** Fetch one additional row for explicit limits and add a soft more-results hint.
  - **History:** `src/services/query/row_bound.py` owns result limits.

- **`[LOW · OPEN]` Rejected generated SQL has no structured rejection log.**
  - **Found:** T0021.2 follow-up.
  - **Impact:** Repeated malformed SQL generation is invisible to operators.
  - **Next:** Log the validation reason without returning it to the user.
  - **History:** `src/agents/tools/query_clean_jobs.py`.

## Evaluation harness (5)

- **`[LOW · OPEN]` DeepEval live commands require UTF-8 output and an explicit `-m eval`.**
  - **Found:** T0011.1, T0011.6, and T0012.7.
  - **Impact:** Native Windows runs can crash or silently select no eval cases.
  - **Next:** Keep the documented `PYTHONUTF8=1 ... -m eval` command until upstream changes.
  - **History:** [Repo Current State](Repo_Current_State.md) lists the working command.

- **`[LOW · OPEN]` Eval `conftest.py` redirects `DATABASE_URL` during every pytest collection.**
  - **Found:** T0012.7.
  - **Impact:** Non-eval tests could cross-talk with the fixture database as the suite grows.
  - **Next:** Scope the redirect to an eval fixture or marker-aware setup.
  - **History:** `evals/conftest.py`.

- **`[LOW · OPEN]` GEval criteria remain hardcoded outside the project configuration.**
  - **Found:** T0011.3.
  - **Impact:** Evaluation wording bypasses the normal prompt and parameter ownership convention.
  - **Next:** Centralize only if additional metrics make the duplication costly.
  - **History:** `evals/harness.py`.

- **`[HIGH · BLOCKED]` The full golden evaluation and judge check lack a credentialed run.**
  - **Found:** T0011.6 and T0012.10.
  - **Impact:** The v1 baseline lacks end-to-end evidence for quota behavior and honesty verdicts.
  - **Next:** Run the selected goldens with Groq, Gemini, and the seeded eval database.
  - **History:** [Manual Verification Archive](archive/Manual_Verification_Archive.md).

- **`[MED · DECISION]` The Gemini judge uses `thinking_budget: 0` pending agreement evidence.**
  - **Found:** T0012.10.
  - **Impact:** The cost-saving default might weaken difficult honesty evaluations.
  - **Next:** Retain zero or choose a small nonzero budget after the blocked comparison.
  - **History:** [evaluation cost research](../research/eval-cost-and-rate-limits.md).

## Demo UI (4)

- **`[LOW · OPEN]` The mid-stream error bubble has no deterministic end-to-end test hook.**
  - **Found:** T0018.3.
  - **Impact:** A provider failure after stream start can only be tested by inducing a real fault.
  - **Next:** Add a test-only synthetic stream error when this UI path changes.
  - **History:** `src/api/static/app.js::showErrorBubble`.

- **`[LOW · OPEN]` The browser parser accepts only the service's current single-line SSE framing.**
  - **Found:** T0018.3.
  - **Impact:** A future multiline or comment-bearing SSE frame would break client parsing.
  - **Next:** Generalize the parser only when the server frame contract changes.
  - **History:** `src/api/routes/query.py::_server_sent_event`.

- **`[LOW · OPEN]` The stream reader has no client-side idle timeout.**
  - **Found:** T0018.3.
  - **Impact:** A hung upstream can leave the composer disabled until the connection closes.
  - **Next:** Add an `AbortController` idle guard if public load expands.
  - **History:** `src/api/static/app.js::ask`.

- **`[LOW · OPEN]` Streamed Markdown is displayed as literal text.**
  - **Found:** T0018.3.
  - **Impact:** Model lists and emphasis do not render as readable rich text.
  - **Next:** Add a safe lightweight renderer if formatted answers become a product need.
  - **History:** `src/api/static/app.js::appendToken`.

## Error-handling honesty (2)

- **`[MED · OPEN]` Every streaming failure still tells the user that the demo is busy.**
  - **Found:** T0021.2 follow-up.
  - **Impact:** Database and internal failures are presented as transient provider pressure.
  - **Next:** T0021.4 should add an honest generic message for non-provider failures.
  - **History:** [Resolved Issues](Resolved_Issues.md) records the logging fix.

- **`[MED · OPEN]` Empty synchronous agent answers are replaced without an operator signal.**
  - **Found:** 2026-07-22 error-handling audit.
  - **Impact:** Repeated model or graph failures can look like legitimate fallback responses.
  - **Next:** Log `generate_agent_response.empty_answer_fallback` at warning level.
  - **History:** `src/agents/service.py::generate_agent_response`.
