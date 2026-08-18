# Known Issues & Risks
> **Last verified:** 2026-08-17 against checked-out code, tests, configuration, and active runbooks.

This register holds actionable risks that are open, blocked, or awaiting a maintainer decision.
> **Eviction:** An entry leaves when fixed, superseded, or reclassified in its owning document.
Closed history is preserved in [Resolved Issues](Resolved_Issues.md).

## Triage

<!-- generated:triage:begin -->
| Severity | Open | Blocked | Decision |
|---|---:|---:|---:|
| HIGH | 1 | 1 | 1 |
| MED | 11 | 1 | 2 |
| LOW | 17 | 2 | 0 |
<!-- generated:triage:end -->

**State key:** `OPEN` needs implementation or verification, and `BLOCKED` needs a live service,
or maintainer action, and `DECISION` needs a product or operational choice.

The table is counted from the `[SEVERITY · STATE]` badge on every entry below, including the
unfiled ones, by `scripts/docs_build.py`. It is a tally of this register rather than a claim about
it. The counts were recounted by hand on 2026-08-17 rather than incremented, because every pass
until then had adjusted them from what that pass alone had changed, and they had drifted; since
T0031.2 they cannot drift again. The per-section counts in the headings below are still hand
tallies. The seven deferred preferences at the foot of this document carry no badge and so are
excluded from the table, which is the behaviour that pass chose for them: nothing is owed on them.

## Raised, not yet filed

Issues a ticket recorded in its file under [`entries/`](entries/README.md) that no maintainer has
filed into a topic section yet. Filing one means moving it into the section it belongs to,
**keeping its `KI-` id**: the id is what drops it from this region on the next build, so the two
copies can never drift. Entries that predate the id convention are never inboxed here.

<!-- lint-allow-link-path:begin -->
<!-- generated:registered:begin -->
- `KI-2026-08-17-vietnamese-spike-multiturn` **`[MED - OPEN]` Multi-turn tool following is
  unstable.**
  - **Found:** A3 used `get_current_time` for an application-deadline question in two of three runs.
  - **Impact:** A Vietnamese conversation can lose reliable tool selection after turn six.
  - **Next:** Add a behavior ticket that reproduces and corrects the instability.
  - **History:** Found during T0032.4 on 2026-08-17 against the fixture database and DeepSeek.
<!-- generated:registered:end -->
<!-- lint-allow-link-path:end -->

## Config, startup & deployment (11)

- **`[MED · OPEN]` Render auto-deploy stalled for three days and the reason is unexplained.**
  - **Found:** the 2026-08-13 serving outage, diagnosed 2026-08-16.
  - **Impact:** `render.yaml` declares `autoDeploy: true` on `main`, yet the service ran `de237a6`
    while PR #48 and #49 merged undeployed. An undeployed `main` stays invisible until a visitor
    reports it, because `/health` and `/ready` both pass on a broken build.
  - **Next:** After the next merge that changes `src/`, compare the deployed static-asset hashes
    against `main`; if they differ, check the GitHub hook and Render's deploy history.
  - **History:** [Resolved Issues](Resolved_Issues.md) records the outage and its elimination trail.

- **`[LOW · OPEN]` A retired serving-model pin would fail the tool loop with no advance warning.**
  - **Found:** T0011.5 preparation.
  - **Impact:** A retired or incompatible model ID fails at the first tool call, not at boot.
  - **Next:** Re-run one tool-using query against the configured pin whenever the provider changes.
  - **History:** The `qwen` pin was confirmed live on 2026-08-16, but `main` then moved the serving
    profiles to DeepSeek, so that confirmation does not carry to the current pin.

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
  - **Impact:** The public portfolio demo may exceed an internal-use content restriction.
  - **Next:** Choose attribution, restricted access, accepted risk, or permission for the demo.
    The maintainer ruled on 2026-08-13 that this does **not** gate cron activation: §7 restricts
    republishing, which is a question about what the demo displays today, not what the cron fetches.
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

- **`[LOW · OPEN]` `expired_count` reports rows matching the stale predicate, not newly expired.**
  - **Found:** T0020.4, when three consecutive runs all logged exactly `expired_count: 47`.
  - **Impact:** Nightly logs cannot distinguish fresh expiries from long-expired rows.
  - **Next:** Add `AND is_active` to the `UPDATE` so `rowcount` counts state changes only.
  - **History:** `src/services/ingestion/clean_store.py::expire_stale_clean_jobs`.

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

## Agent runtime & prompts (4)

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
  - **History:** [`evals/Instrument_Report.md`](../evals/Instrument_Report.md) records both flips.

- `KI-2026-08-17-deepseek-capture-lost` **`[HIGH · RESOLVED]` Captures are unpreserved, and one has
  already been lost.** Closed by M30 on 2026-08-17; the record is in
  [Resolved Issues](Resolved_Issues.md#evaluation-harness). The T0027.3 capture stays lost - what
  closed is the exposure, not the loss.

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

- **`[MED · OPEN]` `prompt_hash` and `config_hash` are not portable between checkouts on Windows.**
  - **Found:** T0027.3 on 2026-08-14, comparing the DeepSeek arm against the frozen baseline.
  - **Impact:** `build_manifest()` hashes working-tree bytes, and `core.autocrlf=true` with no
    `.gitattributes` rule gives one committed blob different bytes per checkout:
    `config/prompts.yaml` holds 102 CRLF in this worktree and 71 CRLF plus 31 bare LF in main, while
    `git diff` reports no change. So `_assert_comparable()` will refuse two runs that are in fact
    comparable, and a hash match cannot be read as content equality. This is the same class of
    problem `SEEDED_COLUMNS` already solves for `fixture_hash`, which is stable across rebuilds.
  - **Next:** Hash the committed blob rather than the file on disk, or normalise line endings
    through `.gitattributes`. Not urgent while runs come from one checkout.
  - **History:** [T0027.3 DeepSeek arm](../evals/t0027_deepseek_arm.md).

- **`[LOW · OPEN]` A grader rule can fail a correct answer on phrasing alone.**
  - **Found:** T0027.3 on 2026-08-14, inspecting all 18 safety turns of the measured arm.
  - **Impact:** 10 of 33 failing turns are correct behavior scored against a hand-written substring
    whitelist. Four `SAF-*` scenarios refuse correctly and say "I'm not able to delete" where the
    rule holds only `can't delete` and `cannot delete`; `SAF-INJECTION-RESILIENCE-1` is failed for
    quoting the payload it just refused; `HON-ZERO-RESULTS-1` says "there are no COBOL jobs" where
    the rule holds `no postings` and `no matches`. Safety reads 11/18 measured against 18/18
    behaviorally, so the aggregate understates the agent and any arm comparison inherits the noise.
  - **Next:** Widen the rules in `evals/scenarios_v1.yaml`, or route refusal wording through the
    prompt glossary so rule and prompt cannot drift. None of these rules reference the glossary
    today. M27 forbids touching a grading rule, so this belongs to the registry owner or M24.
  - **History:** [T0027.3 DeepSeek arm](../evals/t0027_deepseek_arm.md).

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

- `KI-2026-08-17-replay-needs-a-database` **`[MED · OPEN]` `evals.replay` fails with `INFRA`
  verdicts when no Postgres is listening, so the gate cannot run on a bare checkout.**
  - **Found:** T0031.3, running the documented build-status commands with 5433 and 5432 both
    refusing connections.
  - **Impact:** `uv run python -m evals.replay` exits non-zero with an outcome mismatch on five
    turns. The register describes it as replaying committed evidence "with no model or judge call",
    which reads as needing nothing external; it still needs a database for the execution seam.
  - **Next:** Either document the database as a precondition beside the command, or have the
    replay skip rather than fail when the seam is unreachable, so a genuine regression stays
    distinguishable from an absent database.
  - **History:** Same root cause as the fixture-Postgres hang already recorded for the test suite.

## Workflow & documentation (8)

- **`[MED · OPEN]` A fresh worktree cannot run the test suite.**
  - **Found:** T0031.1 on 2026-08-16.
  - **Impact:** `.env` is gitignored, so a new worktree has no Langfuse keys and ten test modules
    fail at collection with `ConfigLoadError` - a first-run trap for every agent, since §3 now
    requires each writing session to work in its own worktree.
  - **Next:** Copy `.env` from the primary worktree, or supply test-only conftest placeholders.
  - **History:** `.gitignore`; `CLAUDE.md` §3.

- **`[MED · DECISION]` M23 has been indexed and unscoped since 2026-08-09.**
  - **Found:** T0031.1 on 2026-08-16, auditing numbering drift.
  - **Impact:** M26 through M31 all shipped past the v1.0 release cut, so the release sits behind
    work that keeps arriving and nothing arbitrates that.
  - **Next:** A maintainer decides where M23 sits; sequencing is not a ticket's call.
  - **History:** [Tickets](Tickets.md) M23; [`roadmap.yaml`](roadmap.yaml).

- `KI-2026-08-17-section-counts-are-hand-tallies` **`[LOW · OPEN]` The per-section counts in the
  headings of this register are hand tallies that nothing checks.**
  - **Found:** T0031.2, generating the triage table beside them.
  - **Impact:** `## Config, startup & deployment (12)` and its six siblings drift the same way the
    triage table did, and the integration pass that recounted the triage table on 2026-08-17 had
    to recount these by hand in the same sitting.
  - **Next:** Either generate the heading counts or drop them. Cheap either way.
  - **History:** The triage table is generated as of T0031.2; these are what is left.

- `KI-2026-08-17-entries-lack-issue-ids` **`[LOW · OPEN]` T0031.1's five known issues predate the
  id convention and can never be inboxed.**
  - **Found:** T0031.2, writing the dedup rule.
  - **Impact:** None today, because all five were filed by hand on 2026-08-17. It means the inbox
    cannot be used to audit whether an older entry was fully filed.
  - **Next:** Nothing, unless an entry is ever found to have been missed. Recorded so the gap in
    coverage is stated rather than assumed away.
  - **History:** [`entries/T0031.1.md`](entries/T0031.1.md) `## Known issues`.

- **`[LOW · OPEN]` An issue fixed on arrival has no way out of the generated inbox.**
  - **Found:** the integration step on 2026-08-17, folding T0031.2.
  - **Impact:** `render_registered` drops an id once it appears outside the generated regions of
    this file, so an issue the integrator *fixes* rather than files has to be named here anyway,
    with a pointer to [Resolved Issues](Resolved_Issues.md), or it stays listed as unfiled forever.
    `KI-2026-08-17-tickets-names-resolved-issues` is the first case and is handled exactly that way.
  - **Next:** Let the dedup also read `Resolved_Issues.md`, or give the inbox a closed state.
    Fold it into T0031.4, which already owns the un-id'd-bullet check.
  - **History:** `scripts/docs_build.py::render_registered`.

- **`[LOW · OPEN]` A worktree lock can outlive the session that took it.**
  - **Found:** T0031.1 on 2026-08-16; the prune sweep ran on 2026-08-17.
  - **Impact:** The sweep removed three finished worktrees, but `t0031-parallel-docs-workflow`
    stayed because its lock names a dead pid, and a lock nothing can release blocks the next sweep.
  - **Next:** Release it by hand once its owner is confirmed gone; only then consider automating.
  - **History:** `git worktree list`; `CLAUDE.md` §3.

- `KI-2026-08-17-snapshot-region-unverified` **`[LOW · OPEN]` The `snapshot` region of
  `Repo_Current_State.md` has no staleness check.**
  - **Found:** T0031.3, by design rather than by defect.
  - **Impact:** The branch, commit, and worktree block can describe an older clone with nothing
    failing. Every other generated region in the repository is gated.
  - **Next:** Have a check require that an integration commit ran `docs_build.py --snapshot`.
    T0031.4 shipped the `frozen` check without this, so it needs its own ticket rather than a
    milestone that is now closed.
  - **History:** Introduced when T0031.3 split clone-local facts out of the gated regions, because
    a check that runs in CI cannot verify a fact that differs in CI.

- `KI-2026-08-17-lint-checks-silent-without-base` **`[LOW · OPEN]` The `scope` and `frozen` checks
  pass silently when no diff base resolves.**
  - **Found:** T0031.4, by design rather than by defect.
  - **Impact:** A CI checkout that stops fetching the base branch disables two protocol checks
    without turning the build red. The failure looks identical to compliance.
  - **Next:** Have CI assert that `--diff-base` resolved, or add a flag that makes an unresolvable
    base an error rather than silence.
  - **History:** Chosen so the linter stays runnable in a shallow clone or offline copy, the same
    trade T0031.3 made for the snapshot region.

## Demo UI (1)

- **`[LOW · OPEN]` The mid-stream error bubble has no deterministic end-to-end test hook.**
  - **Found:** T0018.3.
  - **Impact:** A provider failure after stream start can only be tested by inducing a real fault.
  - **Next:** Add a test-only synthetic stream error when this UI path changes.
  - **History:** `src/api/static/app.js::showErrorBubble`.

## Deferred preferences (7)

Reclassified out of the register on 2026-08-17 under its own eviction rule, when it bound at its
cap a second time. Each of these had said in substance "act only if X happens", which makes it a
standing preference rather than an open risk: nothing is owed until its trigger fires. They are
kept in one line each so the trigger stays findable, and they return to a full entry above if one
of them fires.

| Deferred | Trigger that revives it | Where |
|---|---|---|
| Investigate keep-alive ping timeouts on overnight Render wake-up (T0019.7) | Failures recur | [Operations](Operations.md) |
| Short-circuit the agent's full reasoning before it declines an unsupported attribute (T0007.2) | Behavior work resumes | `config/prompts.yaml` |
| Enforce the id-first SQL convention with a few-shot rather than prompt text (T0009.11) | Evaluation observes the omission | `config/prompts.yaml` |
| Centralize the hardcoded GEval criteria into project configuration (T0011.3) | More metrics make the duplication costly | `evals/harness.py` |
| Generalize the browser SSE parser past single-line framing (T0018.3) | The server frame contract changes | `src/api/routes/query.py::_server_sent_event` |
| Add an `AbortController` idle guard to the stream reader (T0018.3) | Public load expands | `src/api/static/app.js::ask` |
| Render streamed Markdown as rich text instead of literal text (T0018.3) | Formatted answers become a product need | `src/api/static/app.js::appendToken` |

