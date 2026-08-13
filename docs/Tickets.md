# InternHunter — Tickets & Roadmap

> **Last verified:** 2026-08-13 against the active ticket plan and completion records.

> **Eviction:** A ticket plan leaves when its completion report is recorded and its historical scope
> is moved to the ticket archive.

Ticket specs and delivery sequence for the MVP. Each entry below is the **plan** for one open
ticket (Objective / In Scope / Out of Scope). The milestone index keeps every milestone, open or
closed; plans for the closed ones live in
[`archive/Tickets_Archive.md`](archive/Tickets_Archive.md).
What a ticket *actually did* lives in [`Completion_Reports.md`](Completion_Reports.md), and the
current snapshot lives in [`Repo_Current_State.md`](Repo_Current_State.md).

**Legend:** ✅ Done · 🔨 In progress · ▶ Next · ⏸ Parallel / paused · 📋 Backlog

| M | Ticket | Milestone | Status | Goal |
|---|--------|-----------|:--:|------|
| 0–5 | T0000–05 | Foundation → Hardening | ✅ | FastAPI boot, request flow, ReAct runtime, Langfuse, tracing, hardening |
| 6 | T0006 | First Real SQL Tool | ✅ | Read-only `query_clean_jobs`; answer-only API |
| 7 | T0007 | Conversation Memory | ✅ | Postgres checkpointer, session→thread, trim cap |
| 8 | T0008 | System Prompt & Persona | ✅ | Resumi persona, honesty rules, schema → config |
| 9 | T0009 | Data Ingestion (VietnamWorks) | ✅ | `raw_jobs` + `clean_jobs`, idempotent loader |
| 10 | T0010 | Pre-deploy Hardening | ✅ | Typed errors, single-table allowlist, off-loop LLM |
| 11 | T0011 | Model Evaluation Harness | ✅ ⚠ | DeepEval judge, fixture DB, 3-seam metrics, writeback |
| 12 | T0012 | Hardening & Known-Issue Fixes | ✅ | qwen leak fix, metric unblock, `trace_url`, fallbacks |
| 13 | T0013 | Pre-Deploy Refinement | ✅ | `tech_stack` rebuild, 16-col v1 schema freeze |
| 14 | T0014 | Pre-Deploy Known-Issue Fixes | ✅ | Config-load robustness, register housekeeping |
| 15 | T0015 | Agent Behavior Spec & Scenario Matrix | ✅ | Closed 2026-08-12: spec, glossary, `prompt_version`, one graded matrix run; remainder absorbed by M24/M25 |
| 16 | T0016 | Security Posture | ✅ | CORS, rate limit, input cap, `/docs` decision |
| 17 | T0017 | Streaming Response Delivery | ✅ | `astream` + no-leak filter, SSE endpoint |
| 18 | T0018 | Clickable Demo (UI + go-live) | ✅ | .1–.4 done · **live: https://internhunteragent.onrender.com** |
| 19 | T0019 | Ingestion Deploy Readiness (live-DB) | ✅ | .1–.10 done; landed on `main` via PR #29 |
| 20 | T0020 | Reconciliation & Activation | ✅ ⚠ | `main` reconciled, Render pinned to `main`, CI gate live, cron runbook — **2 maintainer actions open** |
| 21 | T0021 | Serving-Path Hardening | ✅ | .1-.4 complete 2026-08-12; historical plans archived |
| 22 | T0022 | **Docs Hygiene & Documentation System** | ✅ | Phase 1 (.1-.9) complete 2026-08-10: lint gate, front door, Decision Log, research prune · Phase 2 (.10-.14) complete 2026-08-12: prune, archive collapse, register rebuild, restructure, enforcement |
| 23 | T0023 | v1.0 Release Cut | 📋 | DoD sweep, ToS posture, **live cron (D-038)**, tag — renumbered from T0022 on 2026-08-09 |
| 24 | T0024 | Honesty Enforcement (obligation seam) | 📋 | Carved out of M21 on 2026-08-12; designed, indexed, sequenced after T0023 |
| 25 | T0025 | **Evaluation Instrument** | 🔨 | .0-.6, .8, .9 done; .7 closed partial 2026-08-13 (13 of 19 turns; 2 scenarios need a paid tier); .10 closeout remains |
| — | Backlog | Custom domain | 📋 | deferred until after v1.0; cosmetic only |

> ⚠ **M11:** milestone shipped, but the T0011.5 baseline-calibration run is still **blocked** on a
> maintainer executing it. Verified 2026-08-12: the Groq and Google keys are configured locally, so
> the constraint is the Groq daily token budget and operator time, not access. See
> [`Known_Issues.md`](Known_Issues.md).
>
> ⚠ **M20:** complete as a coder milestone; two **maintainer** actions remain open — branch
> protection to *enforce* the CI gate, and the gated cron activation. See
> [`T0020.4_Cron_Activation_Runbook.md`](T0020.4_Cron_Activation_Runbook.md).
> The cron activation now **blocks T0023**: [`Decision_Log.md`](Decision_Log.md) D-038 makes a live
> schedule a required MVP capability, so its gates — including the terms posture — are
> release-blocking rather than optional hardening.

---

## T0024: Milestone 24 - Honesty Enforcement (obligation seam) — 📋 Named, indexed, not scoped
**Carved out of M21 on 2026-08-12.** The model-honesty half of the former *Serving-Path Hardening &
Honesty Baseline* milestone, separated because its blockers are unrelated to the serving path: it
needs the frozen `behavior_glossary` landed in `config/prompts.yaml`, a detection mechanism, and
repeated Groq daily-quota windows for its measurement gate.

**The design is already written** and must be read before any block below is scoped:
[`research/honesty-enforcement-design.md`](../research/honesty-enforcement-design.md). It measures
the 2026-07-14 scenario matrix (C-category 0/7), rejects prompt few-shots as the primary locus, and
adopts deterministic hedge-obligation detection over the validated SQL and result set — the
mechanism the passing truncation notice already proves in this repo. Its §8 proposes five blocks
under the milestone number **T0020**, which reconciliation took; they are re-indexed here and
carry no other change:

* **T0024.1** — land `behavior_glossary` and `prompt_version` on the deploy lineage from
  `archive/t0015.2-behavior-glossary`, with a loader and a token-coverage test. **As a loaded
  artifact, not as system-prompt text** — see
  [`research/prompt-refinement-methods.md`](../research/prompt-refinement-methods.md), which finds
  18 rules sits past the ~8–10 instruction knee and splits data-driven hedges (injected when the
  obligation fires) from request-driven refusals (the five that stay in the prompt). No blockers.
* **T0024.2** — `detect_obligations(sql, table)` plus the revived `QueryToolResult` seam, rendered
  as a delimited caveat block in both tools' output. Blocked on .1.
* **T0024.3** — the caveat-relay rule in the system prompt and a `prompt_version` bump. Blocked
  on .2.
* **T0024.4** — re-run the 29-scenario matrix against the fixture database as the ship gate, and
  record the per-rule deltas. Blocked on .3 and one Groq daily window.
* **T0024.5** — verify-and-append enforcement middleware, built **only** if .4 shows the model drops
  explicit caveats.
* **T0024.6** — apply settled decision **#10** to `config/prompts.yaml`. The persona line still
  opens "helps users explore internship and job postings", and the T0015.5 edit that was to correct
  it never landed. T0025.2 measured the cost in
  [`evals/v1_error_analysis.md`](../evals/v1_error_analysis.md): six turns of
  `INTERNSHIP_SCOPE_NARROWING` and `INTERNSHIP_PERSONA_WORDING` across HON-ZERO-RESULTS-1,
  HON-FREE-TEXT-1, HLP-LOCATION-SYNONYM-1, and HLP-REFERENT-2. Decide
  explicitly whether the sibling decline line inherits the fix — decision #10 names the persona line
  alone, while the measured narrowing implicates both. **Class 3 wording, not obligation-seam
  work**, so it neither blocks nor is blocked by .2-.5. Blocked on .1 for `prompt_version`, which
  exists nowhere today; **run immediately after it**, and before T0025.3's first capture run, so no
  two runs straddle an unversioned prompt change.

**Sequenced after T0023, except .1 and .6**, which are pulled ahead: T0025.6 needs .1's glossary
tokens, and .6 must land before T0025.3's first capture run. D-021 gates `is_active` exposure
behind this work, and the release bar
for the honesty Definition-of-Done bullet is decision **D9** in the readiness plan — answered during
T0023's sweep, not here. A v1.0 tag that records a measured honesty limitation is a legitimate
outcome; this milestone is how the limitation gets closed afterward.

## T0025: Milestone 25 - Evaluation Instrument — 📋 Scoped 2026-08-12

**Read [`research/evaluation-strategy.md`](../research/evaluation-strategy.md) before scoping or
starting any block below.** Where T0024 fixes *how the agent behaves*, this milestone fixes *how we
know*. Agent behavior has been measured exactly once — 29 scenarios on 2026-07-14 — by a runner
that was never merged, graded by hand, with infrastructure failures counted as behavior failures.
Every later honesty claim rests on an instrument that can be re-run cheaply and trusted.

> **Re-scoped 2026-08-12** after the strategy was accepted. The earlier ordering assumed the
> archived HTTP runner had to be restored first; it does not. `evals/harness.py` already captures
> all three seams in-process and never boots the API, so **T0025.0 does not block this milestone** —
> it gates the demo HTTP surface and `/ready`, and runs in parallel.
>
> **Closure boundary.** This milestone ends when a clean, current configuration can produce a
> provenance-complete three-seam artifact that a human can inspect and CI can replay through the
> deterministic graders without a model call. It does not own behavior fixes, production sampling
> selection, judge calibration, release thresholds, or the full post-change behavior matrix.
>
> **Remaining sequence.** T0025.7 closed partial on 2026-08-13: provenance and telemetry are done
> and the capture path is accepted, but the acceptance set measured 13 of 19 turns because two
> scenarios exceed the free tier's per-minute ceiling inside a single turn. T0025.9 closed the
> same day: the grader agrees with all 13 human labels and CI now replays committed evidence.
> T0025.10 consolidates the records and closes the milestone. T0024.4 then uses the accepted
> instrument for its full behavior remeasurement, which needs the tier decision resolved first.
>
> **Shared dependency.** T0025.6 needs the `behavior_glossary` tokens that **T0024.1** lands.
> T0024.1 has no blockers of its own and should be pulled ahead of the rest of its milestone.
>
> **Out of scope for the whole milestone:** any prompt, schema, or agent-behavior change; adding or
> re-authoring scenarios (the 29 match the frozen schema and stay as they are, and .8 renames them
> without touching a case); rewriting `evals/harness.py`; fixing anything the instrument finds,
> except where .7 names a config cause.

### T0025.0: Build the evaluation fixture from Alembic, not the snapshot script
**Objective:** Let the API boot against the evaluation fixture database. `scripts/init_db.sql`
creates 19 `clean_jobs` columns and omits `is_active`, `first_seen_at`, and `last_seen_at`;
`evals/fixtures/loader.py` builds the fixture from that script; `assert_serving_schema` demands all
22 and fails startup on any difference. This blocks any HTTP-driven work against the fixture —
including `/ready`, which reads `MAX(last_seen_at)` — but **not** the rest of this milestone, whose
blocks drive the agent in-process.

**In Scope:**
* Create the fixture schema by running Alembic to head rather than replaying the snapshot script,
  so the fixture cannot drift from production again at the next migration.
* Keep row seeding as it is — the 22 fixture rows and their pinned facts are unchanged, and the
  lifecycle columns take their migration defaults.
* A test asserting the fixture database's column set equals `schema_guard.EXPECTED_COLUMNS`.
* Retire or explicitly scope `scripts/init_db.sql` to whatever still needs it, and update
  [`Known_Issues.md`](Known_Issues.md) when the entry closes.

**Out of Scope:**
* Any schema change. This ticket moves *how the fixture is built*, never what the schema contains.
* Changing fixture rows, counts, or any pinned fact a scenario depends on — that would invalidate
  the 2026-07-14 comparison baseline.
* The production or Neon migration path, which already runs Alembic.

**Manual verification:**
1. Drop and rebuild the fixture database, then boot the API against it: startup logs
   `api.schema_ok` instead of raising `SchemaGuardError`. That flip is the whole ticket.
2. `python -m evals.fixtures.loader` reports `COUNT(*) = 22`, matching the fixture confirmation
   line in `evals/v1_scenario_matrix.md`.
3. Query a row and confirm `is_active` is populated by the migration default rather than NULL.
4. `uv run pytest -q`, `uv run ruff check src tests`, `uv run mypy src`, and
   `uv run python scripts/docs_lint.py` all green.

**Blockers:** none. Parallel — no other block in this milestone waits for it.

### T0025.1: Harvest the archived instrument and delete the duplicate case list
**Objective:** Give "which scenarios exist, and which must be correct on every run" a single
answer. The 29-case registry and the raw 2026-07-14 answers live only on archive tags, while a
checked-in `golden_dataset.json` holds a stale 18-case subset that contradicts the registry on
probe flags (C1, D1, D2, D3) **and on content** — its `A2` asks for data scientist roles where the
registry's asks for AI Engineer jobs. Two case lists means every later number is ambiguous.

**In Scope:**
* Recover `evals/scenarios_v1.yaml` and `evals/v1_scenario_matrix.observed.json` from tag `archive/t0015.4-scenario-matrix` onto the mainline. <!-- archived-on-tag -->
* Make the registry the single source of truth: generate the goldens from it and delete the
  checked-in copy. Collapse the duplicate loaders and the two judge test modules.
* A test asserting every generated probe flag matches `docs/Agent_Behavior_Spec.md` §4.

**Out of Scope:**
* Any grader or assertion logic (T0025.6); any scenario edit; any model call.

**Manual verification:**
1. A dry-run lists a named scenario and its expected behavior without calling the model.
2. Regenerate the goldens; the diff shows the corrected probe flags **and** the corrected `A2`
   input. A regenerate that reproduces the old file byte-for-byte means the generator is wrong.
3. `uv run pytest -q`, `uv run ruff check src tests`, `uv run mypy src`, and
   `uv run python scripts/docs_lint.py` all green.

**Blockers:** none. **Do first.** Spends no quota.

### T0025.2: Error analysis on the recovered answers
**Objective:** Convert the strategy's failure taxonomy from inference into evidence, using answers
already on disk. This is the cheapest useful work in the project: no code, no quota, and it decides
what every later ticket measures.

**In Scope:**
* Open-code the recovered answers, then group into failure modes and rank by frequency × severity.
* Confirm the `INFRA` set against the T0015.5 record: 8 empty-answer instances across
  HLP-CONTEXT-1, HON-CURRENCY-1, HLP-COMPOUND-1, HON-SQL-DESCRIBE-1,
  **HLP-LOCATION-SYNONYM-1**, and HLP-ABSTRACTION-1, plus HON-ZERO-RESULTS-1's separate
  database-error answer. Correct HLP-LOCATION-SYNONYM-1, currently recorded as a behavior failure.
* Record which findings the answer-only artifact **cannot** settle — anything needing SQL or
  routing evidence is deferred to T0025.3, not guessed.

**Out of Scope:**
* Any conclusion about seam 1 or seam 2; the recovered artifact contains neither.
* Fixing anything, and re-authoring any scenario.

**Manual verification:**
1. Every 2026-07-14 scenario carries a failure-mode label or an explicit "not determinable here".
2. The ranked list names a top mode, and `research/evaluation-strategy.md` §3 is corrected where
   this analysis contradicts it.

**Blockers:** T0025.1. Spends no quota.

### T0025.3: Scenario driver over the existing harness, with manifest and checkpointing
**Objective:** Make the instrument runnable. `evals/harness.py` already captures all three seams —
tools called, the nested `generate_sql` SQL, tool output, answer, trace id — and has no way to run
a suite; the archived runner has the orchestration and captures only answers. This ticket writes
the missing driver, and **does not restore the archived HTTP transport**.

**In Scope:**
* A driver that loads the registry, runs each scenario at its repeat count (3 probes / 2 others)
  through the harness in-process, and persists every turn's three seams.
* A per-run manifest: commit SHA, fixture hash, prompt and config hash, model IDs, sampling
  parameters, timestamps, retry events, scorer version.
* Checkpoint after each scenario and resume from it. On quota exhaustion: halt, persist the partial
  result with its manifest, mark uncollected scenarios `UNRUN`.
* Retry policy: two backed-off retries per turn; exhaustion records `INFRA`, never `FAIL`.
* Capture-only mode that skips the judge entirely, so an analysis run costs no judge quota.
* Refuse to diff two runs whose fixture, prompt, or config hashes differ — report incomparable.

**Out of Scope:**
* Rewriting `evals/harness.py`, or any Langfuse or tracing-layer change.
* Grading (T0025.6); any HTTP transport.

**Manual verification:**
1. Run two scenarios in capture-only mode; the manifest is fully populated and no judge call is
   made. Confirm the persisted record contains the generated SQL, not just the answer.
2. Interrupt mid-scenario, re-run, and confirm it resumes rather than restarts.
3. Edit `config/prompts.yaml`, re-run, and confirm the two runs report as incomparable.

**Blockers:** T0025.1.

### T0025.4: Trace viewer and the first-upstream-failure rule
**Objective:** Make reading a run take an hour instead of a day. Operator attention is the binding
constraint on this project, and it is why the matrix has been graded once. Production practice
names a custom trace viewer the highest-return investment in an evaluation practice.

**In Scope:**
* A single-file local viewer rendering one turn per screen from T0025.3's records: question,
  routing decision, generated SQL, rows returned, final answer, and a note field.
* The annotation rule written into the review procedure: mark the **earliest** wrong seam only, and
  stop. Recording downstream symptoms of an upstream defect is what makes a taxonomy unusable.

**Out of Scope:**
* Grading or scoring of any kind; any hosted or authenticated UI. This is a local reading tool, not
  a product surface, and must not be wired into `src/api/`.

**Manual verification:**
1. Open the viewer on a recorded run; every turn shows all three seams without expanding raw JSON.
2. Annotate one turn, reload, and confirm the note survives.

**Blockers:** T0025.3.

### T0025.5: Reference SQL and execution accuracy
**Objective:** Grade seam 2, which has never been graded. Execution accuracy is the field's standard
text-to-SQL metric and needs reference SQL plus a stable database — the two conditions production
systems usually lack and this project already has. It settles by measurement the question the
strategy record can only infer: whether a wrong answer came from a wrong query.

**In Scope:**
* One hand-authored reference query per answerable scenario, stored beside it in the registry.
* A comparator that executes the generated and reference queries against the pinned fixture and
  compares result sets as **unordered row multisets** — never as query text, since many different
  queries are correct.
* An explicit exemption flag for scenarios with no single correct query (refusals, clarifications),
  recorded rather than forced into a comparison.

**Out of Scope:**
* Judging SQL style, efficiency, or readability. Correct result set, or not.
* Changing any scenario's expected behavior.

**Manual verification:**
1. A deliberately wrong reference query fails its scenario on execution accuracy while the answer
   text is unchanged — this proves the check is independent of seam 3.
2. A semantically equivalent query written differently (reordered `WHERE` terms) still passes.
3. Every exempt scenario states why it is exempt.

**Blockers:** T0025.1, T0025.3.

### T0025.6: The three-tier grader
**Objective:** Implement the deterministic grading layers and outcome model needed before the
grader can be audited against real captured outputs.

**In Scope:**
* Per-scenario assertions authored at the **highest applicable tier**: (1) structural — tool called
  or not, SQL validity, execution accuracy from T0025.5, row counts, how many jobs the answer
  names; (2) textual — required caveat substance present, forbidden phrasing absent; (3) judge —
  deferred to the existing harness metrics, not re-scoped here.
* `PASS` / `FAIL` / `INFRA` / `UNRUN` as four distinct outcomes, with the last two excluded from
  pass-rate denominators. Results split by class — safety, honesty, helpfulness — never blended.
* A six-scenario crafted holdout spanning all three classes, used as a contract suite for the
  structural and textual assertions.
* No-model replay of the historical answer-only artifact, preserving `INFRA` where seam evidence is
  unavailable rather than inventing a behavior score.

**Out of Scope:**
* The judge tier's metric set and thresholds — a later milestone re-scopes them.
* Acting on any result: no prompt edit, no mechanism change, no register triage here.
* Empirical grader agreement on real model outputs and a committed three-seam replay CI gate;
  T0025.9 owns those acceptance requirements.

**Manual verification:**
1. Re-grade the recorded 2026-07-14 answers and confirm answer-only cases remain explicitly
   under-measured where structural seam evidence is absent.
2. Feed a crafted answer that recites the cross-currency caveat *and* still names one highest-paid
   job — the structural tier must fail it. This check is the ticket's point.
3. Break a deterministic assertion deliberately; the focused grader and holdout tests fail without
   any model call.

**Blockers:** cleared by T0025.3, T0025.5, and the T0024.1 glossary landing.

### T0025.7: Instrument acceptance, provenance hardening, and empty-answer verification
> **Closed partial 2026-08-13.** Provenance, telemetry, and the capture path are accepted: one
> clean-worktree run captured, graded, and rendered real turns under the frozen configuration.
> The acceptance set measured 13 of 19 turns across 5 of 7 scenarios with `empty_answer_count: 0`,
> recorded as no recurrence observed in 13 turns.
> `HLP-CONTEXT-1` and `HLP-COMPOUND-1` were **not** captured: each exceeds the free tier's 8000 TPM
> ceiling inside a single turn, which no pacing can clear, and the `max_tokens` and `query.max_rows`
> workarounds would change what the instrument measures. That capture is deferred to a paid-tier
> decision and tracked in [`Known_Issues.md`](Known_Issues.md), not reopened here.
> The run also confirmed a grader rule gap and three agent behaviors; T0025.9 and M24 own those.

**Objective:** Prove that the assembled instrument can capture, inspect, and grade real turns from
the current prompt and model configuration, with enough provenance to reproduce the evidence.
The existing live smoke contains one scenario and predates the current prompt hash. The historical
eight empty-answer outcomes establish a symptom, while the answer-only artifact cannot establish
its cause. This ticket verifies whether that symptom recurs without changing sampling variables.

**In Scope:**
* Extend the run manifest with a hash of `evals/scenarios_v1.yaml` and an explicit clean or dirty
  worktree state. A run from a dirty tree may be inspected, but it cannot be labelled a baseline or
  used for a before-and-after comparison.
* Capture per-turn latency, provider token usage, and finish or stop reason when the provider and
  LangChain expose them. Persist an explicit unavailable value when they do not; never infer hidden
  reasoning tokens from a blank answer alone.
* Run the six historically affected scenario IDs under the unchanged current configuration:
  HLP-CONTEXT-1, HON-CURRENCY-1, HLP-COMPOUND-1, HON-SQL-DESCRIBE-1,
  HLP-LOCATION-SYNONYM-1, and HLP-ABSTRACTION-1. Include HON-PREMISE-CORRECTION-1 as the
  previously-passing regression control.
* Pass the artifact through execution accuracy and the deterministic grader, then inspect every
  turn in the viewer using the first-upstream-failure rule.
* Record the observed empty-answer count and telemetry in [`Known_Issues.md`](Known_Issues.md).
  If none recur, state "no recurrence observed in N runs" rather than claiming determinism or a
  proven root cause.

**Out of Scope:**
* Any sampling A/B, temperature change, reasoning-effort change, presence-penalty change, prompt
  edit, or agent-behavior fix.
* The full 29-scenario behavior run, judge calibration, release thresholds, or selecting a
  production sampling configuration.
* Claiming that the historical 1,024-token exhaustion diagnosis explains the later empty answers
  unless current telemetry reproduces that mechanism.

**Manual verification:**
1. Start from a committed prompt and configuration. Confirm the manifest records the current Git
   SHA, scenario hash, prompt hash, config hash, fixture hash, and a clean worktree.
2. Complete the targeted set with its frozen repeat counts. Every turn must contain an answer,
   routing evidence, and either generated SQL plus tool output or an explicit non-query path.
3. Run execution accuracy and the deterministic grader over the same artifact, then open it in the
   viewer and record the first wrong seam for each non-passing turn.
4. Confirm telemetry fields are populated where supported and explicitly unavailable otherwise.
5. Run the focused evaluation tests, Ruff, mypy, documentation lint, and `git diff --check`.

**Blockers:** T0025.3 through T0025.6 and T0025.8; the current prompt lineage must be committed.
The live verification spends one bounded Groq quota window.

### T0025.8: Rename the registry onto a class-first taxonomy
**Objective:** Ids encode the authoring batch and hide the class. Every report splits safety,
honesty, and helpfulness, yet `M-G26d` is safety, `M-G10` honesty, and `M-D7` helpfulness, so no
results table reads without a lookup. `M-` marks a golden-versus-matrix split that ended when
T0025.1 deleted the golden set; `D` means the refusal category in `D2` and decision #2 in `M-D2`.

**In Scope:**
* Rename all 29 to `<CLASS>-<BEHAVIOR>-<n>`, composed from the class split and the canonical tokens
  in [the behavior spec](Agent_Behavior_Spec.md) §3, so an id describes itself.
* Move traceability into fields: `requirements` (a list of `G` codes) and `decision` (an optional
  integer), plus a `name` carrying the full phrase for the T0025.4 viewer.
* Migrate every live reference in one pass: the registry, `v1_scenario_matrix.observed.json`,
  `evals/scenarios.py`, `evals/test_scenarios.py`, the spec §4a-4c, this register, and
  `evals/v1_error_analysis.md` — whose ledger and ranked-mode table are keyed by the old ids.
* Freeze `evals/v1_scenario_matrix.md` as a dated record, appending the old-to-new map to it.
* Record the rename in [the Decision Log](Decision_Log.md); it supersedes **D-5** on labels only.

**Out of Scope:**
* Any change to an `input`, `expected`, or `probe`. This renames and re-authors nothing.
* Editing an archive, or rewriting ids inside the dated 2026-07-14 record.

**Manual verification:**
1. `uv run python -m evals.scenarios --scenario HON-CURRENCY-1` resolves, with no model call.
2. 29 scenarios and 15 probes survive, and the observed-answer join still resolves.
3. Every old id in a live document reaches exactly one new id through the appended map.
4. `uv run pytest -q`, ruff, mypy, and `uv run python scripts/docs_lint.py` all green.

**Blockers:** T0025.2; run before **T0025.3** so the driver and viewer get the final shape.

### T0025.9: Grader audit and committed replay CI gate
> **Closed 2026-08-13.** All 29 tool expectations now come from the registry, all 29 rules are
> audited in [`evals/grader_audit.md`](../evals/grader_audit.md), and the regrade of the 13
> completed T0025.7 turns agrees with every human label: 7 `PASS`, 6 `FAIL`.
> A five-turn sanitized replay and a blocking CI gate execute the recorded SQL against the frozen
> fixture and grade it with no model, judge, or outbound call.
> Two caveats are carried to [`Known_Issues.md`](Known_Issues.md) rather than closed here: the
> `SAF-INJECTION-RESILIENCE-1` no-tool rule flipped on registry text with no capture behind it,
> and the 13-turn sample lives in an ignored capture that a clean checkout cannot reproduce.

**Objective:** Establish that the grader measures the frozen behavior target on real captured
evidence, and make future capture or grader drift fail in CI without spending provider quota.
The six crafted holdout cases are valuable contract tests, but their 1.00 precision and recall do
not estimate performance on model outputs.

**In Scope:**
* Audit all 29 scenarios against the behavior specification. Record for each scenario its expected
  tool behavior, execution-accuracy requirement or exemption, answer-level structural obligation,
  textual rule, and any semantic remainder that genuinely requires a judge or human review.
* Replace the grader's implicit default tool expectation with explicit scenario-owned or
  registry-validated expectations, including deliberate no-tool and mixed-intent cases.
* Human-label the T0025.7 turns before comparing them with grader output. Report every disagreement
  and the real-sample precision and recall with its sample size; retain the crafted holdout as a
  contract suite, not as empirical calibration evidence.
* Commit a small sanitized replay artifact derived from T0025.7. It must cover all three classes,
  a conversational case, a query case, and a no-query case, while excluding credentials and live
  trace URLs.
* Add a blocking CI replay that validates the artifact schema, runs generated and reference SQL
  against the frozen fixture, and passes the results through the deterministic grader. It must call
  neither the serving model nor the judge.

**Out of Scope:**
* New scenarios, behavior fixes, prompt changes, model calls in CI, or judge-fidelity validation.
* Treating a small real sample as proof of production-wide accuracy. The report states its size and
  uses disagreements to improve the assertions, not to claim statistical certainty.

**Manual verification:**
1. Review the 29-row rule audit and confirm every scenario has an explicit answer for each grader
   tier, including a documented reason when a tier does not apply.
2. Change one replayed generated query so execution accuracy fails, then restore it.
3. Change one expected answer obligation so the grader disagrees with its human label, then restore
   it. CI must fail in both deliberate-break cases without a model call.
4. Run the full local CI command set and confirm the committed replay contains no secret or live
   trace identifier.

**Blockers:** cleared 2026-08-13 by T0025.7's partial close, which leaves a 13-turn real
sample in `evals/runs/t0025.7-acceptance.json` to audit and label. Spends no provider or
judge quota.

### T0025.10: Consolidate the evaluation records and close M25
**Objective:** Make the accepted instrument the sole current evaluation path, move completed plans
out of the active register, and leave M24 and the release gate with clear ownership.

**In Scope:**
* Fold the durable quota and cost mechanics from
  [the cost record](../research/eval-cost-and-rate-limits.md) into the evaluation strategy, then
  retire the separate cost record from the research index.
* Keep [the honesty enforcement design](../research/honesty-enforcement-design.md) as M24's behavior
  design until that mechanism ships. The evaluation strategy links to it but does not duplicate it.
* Harvest settled evaluation decisions D-1 through D-7 into the
  [Decision Log](Decision_Log.md), including the milestone boundary and the withdrawal of the
  confounded sampling A/B.
* Archive the completed T0025 plans, mark M25 complete, update the current-state sheet, and record
  the final acceptance commands and results in the completion report.
* Confirm all M25 implementation and replay files are tracked, the branch is clean, and the full CI
  gate passes before closure is reported.

**Out of Scope:**
* Honesty behavior changes, a full 29-scenario model run, production sampling selection, judge
  calibration, release policy, online evaluation, or `is_active` exposure.

**Manual verification:**
1. The active ticket register contains no completed M25 ticket bodies and names M24 as the owner of
   behavior improvement and the release gate as the owner of ship thresholds.
2. The research index has one evaluation strategy plus the still-live M24 honesty design, with no
   duplicated cost record.
3. A clean checkout can run the committed replay gate using documented commands.
4. Documentation lint, the full test suite, Ruff, mypy, and `git diff --check` pass.

**Blockers:** T0025.9; T0025.7 closed partial. Spends no provider or judge quota.
