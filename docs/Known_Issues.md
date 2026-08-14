# Known Issues & Risks
> **Last verified:** 2026-08-14 against checked-out code, tests, configuration, and active runbooks.

This register holds actionable risks that are open, blocked, or awaiting a maintainer decision.
> **Eviction:** An entry leaves when fixed, superseded, or reclassified in its owning document.
Closed history is preserved in [Resolved Issues](Resolved_Issues.md).

## Triage

| Severity | Open | Blocked | Decision |
|---|---:|---:|---:|
| HIGH | 1 | 3 | 1 |
| MED | 6 | 2 | 2 |
| LOW | 16 | 3 | 0 |

**State key:** `OPEN` needs implementation or verification, and `BLOCKED` needs a live service,
or maintainer action, and `DECISION` needs a product or operational choice.

## Config, startup & deployment (12)

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

- **`[HIGH · DECISION]` VietnamWorks terms leave public listing display unresolved.**
  - **Found:** T0019.1 terms review.
  - **Impact:** The demo may exceed an internal-use restriction, and this gates rearming the cron.
  - **Next:** Choose attribution, restricted access, accepted risk, or permission before rearming.
  - **History:** [deployment research §11](../research/archive/deployment-research-plan.md).

- **`[LOW · OPEN]` Native Windows `uvicorn` startup is incompatible with the checkpointer pool.**
  - **Found:** T0019.2 manual verification.
  - **Impact:** Local API development hangs on Windows while Docker and Render continue to work.
  - **Next:** Use Docker today; scope a fix if native development is needed.
  - **History:** [Operations](Operations.md) records the current workaround.

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

- **`[HIGH · BLOCKED]` The ingestion schedule is disabled pending its activation gates.**
  - **Found:** T0020.4.
  - **Impact:** Scheduled refresh is a Definition-of-Done capability, so v1.0 cannot be tagged.
  - **Next:** Complete a green manual dispatch and signed gates before uncommenting the cron.
  - **History:** [Cron Activation Runbook](T0020.4_Cron_Activation_Runbook.md).

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

## Agent runtime & prompts (7)

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

## Query tooling & SQL safety (1)

- **`[LOW · OPEN]` An honored explicit result count does not state that further matches exist.**
  - **Found:** T0010.7.
  - **Impact:** "Found 3" after a request for three can be mistaken for a total.
  - **Next:** Fetch one additional row for explicit limits and add a soft more-results hint.
  - **History:** `src/services/query/row_bound.py` owns result limits.

## Evaluation harness (10)

- **`[MED · OPEN]` `SAF-INJECTION-RESILIENCE-1` asserts a no-tool rule no capture has tested.**
  - **Found:** T0025.9 audit on 2026-08-13.
  - **Impact:** Retiring the grader's hardcoded no-tool set flipped two scenarios, not one.
    `HON-SQL-DESCRIBE-1` rests on three human-labelled turns; this one rests on registry text alone,
    because T0025.7 exhausted quota first. An agent that queries to check the inline posting exists
    now fails on an untested judgement.
  - **Next:** Capture the scenario when a tier decision lands, then confirm or relax the rule.
  - **History:** [`evals/grader_audit.md`](../evals/grader_audit.md) records both flips.

- **`[MED · DECISION]` The 13-turn label sample cannot be reproduced from a clean checkout.**
  - **Found:** T0025.9 audit on 2026-08-13.
  - **Impact:** `evals/runs/` is ignored because its turns carry latency, token usage, and finish
    reasons, so the capture is uncommitted. Two turns survive in the replay; 11 are attested only.
  - **Next:** Maintainer call, left open by T0025.10: commit a sanitized full capture, or supersede
    the sample with a paid-tier re-measurement under T0024.4 - the same decision as the entry below.
  - **History:** `.gitignore` line 9 and [`evals/grader_audit.md`](../evals/grader_audit.md).

- **`[LOW · OPEN]` DeepEval live commands require UTF-8 output and an explicit `-m eval`.**
  - **Found:** T0011.1, T0011.6, and T0012.7.
  - **Impact:** Native Windows runs can crash or silently select no eval cases.
  - **Next:** Keep the documented `PYTHONUTF8=1 ... -m eval` command until upstream changes.
  - **History:** [Repo Current State](Repo_Current_State.md) lists the working command.

- **`[LOW · OPEN]` Fixture-backed tests hang instead of skipping when Postgres is down.**
  - **Found:** T0026.1 on 2026-08-14, with Docker Desktop stopped.
  - **Impact:** `tests/evals/test_driver.py` and `tests/evals/test_fixture_counts.py` block on the
    connect to port 5433 rather than skipping, so the suite appears to hang with no message. The
    state sheet calls these environmental skips, which holds only while the fixture is reachable.
  - **Next:** Guard them with a reachability check that skips naming `docker compose up -d`.
  - **History:** `tests/evals/test_fixture_counts.py`; the paths moved in T0026.2.

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
  - **History:** [evaluation strategy](../research/evaluation-strategy.md), section 4b.

- **`[MED · BLOCKED]` Two acceptance scenarios exceed the free tier's per-minute token ceiling.**
  - **Found:** T0025.7 paced capture on 2026-08-13.
  - **Impact:** `HLP-CONTEXT-1` and `HLP-COMPOUND-1` stay `INFRA`, so the acceptance set is measured
    at 13 of 19 turns. Groq admits a call when window usage plus the request's `max_tokens` reserve
    stays under 8000 TPM, and both scenarios pass that inside one turn: `HLP-CONTEXT-1` peaks at
    10231 on synthesis, `HLP-COMPOUND-1` spends 7653 on routing. Pacing between turns cannot clear
    a window one turn fills by itself.
  - **Next:** Decide the tier; T0025.7 closed partial rather than hold for this, so the capture is
    deferred, not pending. Reducing `max_tokens` or `query.max_rows` would fit them but changes what
    the instrument measures. T0024.4's 29-scenario run meets the same ceiling and the same decision.
  - **History:** Ignored `evals/runs/t0025.7-acceptance.json` holds each rejection and its usage. <!-- lint-allow-link-path -->

- **`[MED · OPEN]` No empty answer recurred, on evidence too small to close the question.**
  - **Found:** T0025.7 paced capture on 2026-08-13.
  - **Impact:** 13 measured turns produced 13 answers and `empty_answer_count: 0`, every one
    reporting `finish_reason: stop`. That is no recurrence observed in 13 turns, not determinism or
    a root cause.
  - **Next:** Judge recurrence only after the blocked scenarios and the full 29-scenario run are
    measured; six of the eight historical empties came from IDs not yet captured.
  - **History:** Ignored `evals/runs/t0025.7-acceptance.json` <!-- lint-allow-link-path -->
    carries latency, token usage, and finish reasons per turn.

- **`[MED · OPEN]` Three agent behaviors failed under the frozen configuration.**
  - **Found:** T0025.7 paced capture on 2026-08-13.
  - **Impact:** `HON-CURRENCY-1` named one highest-paid job across mixed VND and USD listings in all
    three repeats. `HLP-ABSTRACTION-1` matched `%ML%` against `tech_stack` twice, pulling in MLOps
    and MLflow. `HLP-LOCATION-SYNONYM-1` split 1 of 2: one repeat mapped Saigon to Ho Chi Minh City
    for 8 rows, the other matched Saigon alone, returned none, and reported no postings.
  - **Next:** M24 owns these; T0025.7 measures them and changes no prompt or runtime behavior.
  - **History:** Ignored `evals/runs/t0025.7-acceptance.json` and its grade report. <!-- lint-allow-link-path -->

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
