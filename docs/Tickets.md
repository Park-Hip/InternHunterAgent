# InternHunter — Tickets & Roadmap

> **Last verified:** 2026-08-17 against the active ticket plan and completion records.

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
| 24 | T0024 | Honesty Enforcement (obligation seam) | 🚧 | .1 glossary + `prompt_version` and .6 decision #10 shipped 2026-08-17 (`73b058a`) · .2-.5 re-scoped 2026-08-18: the deadline mislabel joins .2, .2 is sequenced after M32, and .4 is an unblocked instrument run |
| 25 | T0025 | **Evaluation Instrument** | ✅ | .0-.10 complete 2026-08-13: registry, driver, viewer, execution accuracy, three-tier grader, replay CI gate · .7 closed partial (13 of 19 turns; 2 scenarios need a paid tier) |
| 26 | T0026 | Evaluation Workspace Hygiene | ✅ | Complete 2026-08-14 (.1 front door and one fixture-URL owner, .2 tests into `tests/evals/`, .3 grading rules into the registry). No verdict changed |
| 27 | T0027 | DeepSeek Provider Integration | ✅ | Complete 2026-08-15 (.1-.4), following the deferred T0015.6 procedure · the spike passed, the arm measured 29/29 scenarios in 5m20s for ~$0.04, and .4 flipped both profiles to DeepSeek (D-045) with pacing at 0 and no provider key required at boot · the Groq branch stays selectable |
| 28 | T0028 | Evaluation Documentation Ownership | ✅ | Complete 2026-08-14 (.1 Fact Ledger rows + `scenario-id` check, .2 dedupe the behavior spec, .3 seal + merge the instrument reports, .4 operating manual + stale-claim sweep). No verdict, rule, or threshold changed |
| 29 | T0029 | Evaluation Readability | ✅ | .1 complete 2026-08-15: the verdict, the run's identity, and telemetry rendered in the viewer. Spent no quota; changed no rule |
| 30 | T0030 | Evaluation Evidence Durability | ✅ | Complete 2026-08-17 (PR #61): .1 the `freeze` command, .2 the surviving T0025.7 capture frozen to `evals/replays/`, .3 **D-046** on telemetry · closed the `[HIGH · DECISION]` capture-preservation entry. The lost T0027.3 capture stays lost |
| 31 | T0031 | Parallel Agent Workflow | ✅ | Complete 2026-08-17 (.1 PR #53 registry, frozen registers, per-ticket entries · .2 PR #57 three registers generated from the entries · .3 PR #59 `Repo_Current_State.md` derived from the tree · .4 PR #62 `registry`, `scope`, and `frozen` checks in CI). Build status and the branch check stayed undone, both recorded |
| 32 | T0032 | Prompt Surface Pass | 🔄 | T0032.4 complete 2026-08-17 (PR #63): selected the English prompt plus a Vietnamese-output rule for later promotion; .1-.3 remain open |
| — | Backlog | Custom domain | 📋 | deferred until after v1.0; cosmetic only |

> **Numbers are allocated in [`roadmap.yaml`](roadmap.yaml), not here.** This table is a reader's
> index of what the registry already decided. M29 and M30 merged on 2026-08-17 as PRs #51 and #52
> and each added its own row on the way in; T0031.1 adds only its own. That is the last row a
> ticket adds - once this milestone lands, the table is frozen and the integration step maintains
> it.

> ⚠ **M11:** milestone shipped, but the T0011.5 baseline-calibration run is still **blocked** on a
> maintainer executing it. Verified 2026-08-12: the Groq and Google keys are configured locally, so
> the constraint is the Groq daily token budget and operator time, not access. See
> [`Known_Issues.md`](Known_Issues.md).
>
> ⚠ **M20:** complete as a coder milestone; one **maintainer** action remains open — branch
> protection to *enforce* the CI gate. See
> [`T0020.4_Cron_Activation_Runbook.md`](T0020.4_Cron_Activation_Runbook.md).
> The cron activation **closed on 2026-08-17**: four consecutive unattended `schedule` runs
> succeeded on 2026-08-14 through 08-17, which satisfies the runbook's §7 last row and clears the
> [`Decision_Log.md`](Decision_Log.md) D-038 requirement that a live schedule is an MVP capability.
> T0023 is therefore unblocked on the cron, and owes its DoD sweep and the terms posture.

---

## T0024: Milestone 24 - Honesty Enforcement (obligation seam) - 🚧 In progress (.1 and .6 shipped)
**Carved out of M21 on 2026-08-12.**
The model-honesty half of the former *Serving-Path Hardening & Honesty Baseline* milestone,
separated because its blockers are unrelated to the serving path.

**The design is already written** and must be read before any block below is scoped:
[`research/honesty-enforcement-design.md`](../research/honesty-enforcement-design.md).
It measures the 2026-07-14 scenario matrix (C-category 0/7), rejects prompt few-shots as the
primary locus, and adopts deterministic hedge-obligation detection over the validated SQL and
result set - the mechanism the passing truncation notice already proves in this repo.
Its §8 proposes five blocks under the milestone number **T0020**, which reconciliation took;
they are re-indexed here.

**Re-scoped 2026-08-18** against everything that landed after the design was written
(M25-M31, the DeepSeek move, and the T0032.4 Vietnamese spike).
The changes are recorded per block below; the design's architecture is unchanged.

* **T0024.1** - ✅ **Shipped 2026-08-17** (merged as `73b058a`).
  `prompt_version: v2` and the 18-token `behavior_glossary` live in `config/prompts.yaml`, with
  `load_prompt_version()` / `load_behavior_glossary()` in `src/agents/runtime/prompts.py` and a
  token-coverage test.
  Landed as a loaded artifact, not as system-prompt text, per
  [`research/prompt-refinement-methods.md`](../research/prompt-refinement-methods.md).
* **T0024.6** - ✅ **Shipped 2026-08-17** (same merge).
  Decision **#10** applied to `config/prompts.yaml`, and the open question is answered: the sibling
  decline line inherited the fix, so both lines now read "AI/Data job and internship postings".
  The Python half of the same bias is **T0032.1's** work and is still open on an unmerged branch.
* **T0024.2** - `detect_obligations(sql, table)` plus the revived `QueryToolResult` seam, rendered
  as a delimited caveat block in both tools' output.
  Three additions on 2026-08-18.
  First, it owns the `listing_expires_on`-as-application-deadline mislabel, rehoused here by the
  T0032.4 spike triage: the spike saw it in all three absent-field probes of both Vietnamese arms,
  it is C7 in the design, and it is obligation-shaped, so it becomes a detection rule resolving
  `ABSENT_FIELD` rather than its own ticket.
  Second, it collapses the duplication T0032.1 deliberately leaves between `_build_answer`'s
  zero-results string and the `ZERO_RESULTS` glossary entry, which puts `src/agents/tools/` in
  scope and makes this block **blocked on M32 merging** as well as on .1.
  Third, every phrasing must resolve through `load_behavior_glossary()[TOKEN]` with no inlined
  literal, so M33's Vietnamese glossary needs no rework here.
* **T0024.3** - the caveat-relay rule in the system prompt and a `prompt_version` bump to `v3`.
  Blocked on .2.
  Decide here whether the edit is net-neutral on instruction count: the prompt is already past the
  ~8-10 knee, M33.1 adds an output-language rule of its own, and M32 deliberately excluded pruning
  and sequenced it after this milestone.
* **T0024.4** - the ship gate.
  **The Groq daily-window blocker is void**: M27 moved both profiles to DeepSeek (**D-045**) and
  measured 29 scenarios in 5m20s for about $0.04, so the gate is an `evals/` instrument run against
  the registry with registry-owned grading, frozen to `evals/replays/` per T0030.1 - not the
  retired manual matrix protocol.
  It must **capture its own `v2` control first**: T0024.6 changed prompt strings, so the frozen
  `t0025.7-acceptance.json` baseline predates the current prompt and is not comparable to it.
  Record the per-rule deltas.
  Blocked on .3.
* **T0024.5** - verify-and-append enforcement middleware, built **only** if .4 shows the model drops
  explicit caveats.
  It touches `src/agents/runtime/middleware.py` and therefore intersects M34; sequence the two only
  if this block is actually built.

**Sequencing.**
M32 lands first, then .2, .3, .4, and .5 only if measured necessary.
M33's T0033.1 and T0033.2 follow this milestone, and T0033.2 owes either a re-gate of the honesty
scenarios after translation or a recorded decision not to re-measure.
**M35** (capture lineage stamp) is best landed before .4 captures its control, so that control is
the first correctly-labelled baseline.
D-021 gates `is_active` exposure behind this work, and the release bar for the honesty
Definition-of-Done bullet is decision **D9** in the readiness plan - answered during T0023's sweep,
not here.
A v1.0 tag that records a measured honesty limitation is a legitimate outcome; this milestone is how
the limitation gets closed afterward.

---

## T0032: Milestone 32 - Prompt Surface Pass

The prompt this agent runs on is spread across a YAML file and three Python modules, and nothing
records that.
A settled behavior decision is half-applied because two of its four sites are Python source rather
than configuration, and the sixteen-column schema list is hand-maintained in three separate prompt
blocks with no test that they agree.
Each of those is a defect today and a multiplier the moment a second language exists.

This milestone makes the surface knowable, finishes the decision that is already settled, and runs
the throwaway measurement that decides how the Vietnamese prompt should be written.
It changes no prompt wording in `config/prompts.yaml` and prunes no instructions.

---

#### T0032.1: Finish decision #10 across the tool surface - 📋 Planned

**Objective.** Apply behavior-spec decision #10 to the two sites that carry the internship bias in
Python, so the persona scope is consistent on every surface the model reads.

**In scope.**
`src/agents/tools/query_clean_jobs.py` - rewrite the `query_clean_jobs` tool docstring to the
standard its sibling already sets.
`get_job_details.__doc__` is 268 characters and states purpose, a selection rule, and where the
arguments come from; `query_clean_jobs.__doc__` is 78 characters and states a wrong scope.
The replacement states the correct scope (AI and data job and internship postings), when to prefer
this tool over `get_job_details`, and what the `question` argument should contain.
Correct `_build_answer`'s zero-results string to cover job postings, and align its
wording with the `ZERO_RESULTS` glossary entry.
Tests in `tests/agents/tools/` asserting that neither string narrows the scope, and that the
zero-results text matches the glossary entry's meaning.

**Out of scope.**
Loading the glossary in the tool.
Replacing the literal with `load_behavior_glossary()["ZERO_RESULTS"]` is **T0024.2's** work, named
explicitly in `research/honesty-enforcement-design.md` §8, and doing it here would be implementing
a future ticket.
This ticket leaves a deliberate, tested duplication between the code string and the glossary entry,
which T0024.2 collapses.
Also out: any edit to `config/prompts.yaml`, the `get_current_time` docstring, and the truncation
header.

**Manual verification.**
Start the app against the fixture database and ask a question with no matches - for example "Do you
have any COBOL jobs?".
The answer must not contain the word "internship".
Ask "What can you help with?" and confirm the reply describes AI and data roles rather than
internships specifically.
Inspect the Langfuse trace for either turn and confirm the tool schema sent to the model carries the
new description.

**Blockers.** None.
Independent of `feature/t0024.6-persona-scope`, which fixes the other two sites in YAML.

---

#### T0032.2: Record the model-facing string surface - 📋 Planned

**Objective.** Make it impossible to answer "where is the prompt?" wrongly, and impossible to add a
new model-facing string without noticing.

**In scope.**
`tests/test_prompt_surface.py` holding an explicit inventory of every string that reaches a model: <!-- lint-allow-link-path -->
the four `config/prompts.yaml` blocks, the three tool docstrings, and the returned literals in
`query_clean_jobs.py`, `get_job_details.py`, and `time.py`.
An AST scan over `src/agents/tools/` that collects every string literal returned from a function or
used as a docstring, and asserts the set is exactly the recorded inventory - so a new string fails
the suite until it is recorded.
The inventory carries, per entry, the owning file and whether the string is user-visible,
model-visible, or both.

**Out of scope.**
Moving any string.
Introducing a message catalogue, an i18n library, or any indirection layer - the deliverable is a
list and an assertion, not an abstraction.
Scanning `src/services/` or `src/api/`; the tool modules are the surface that reaches the model, and
widening the scan is a follow-up if it ever pays.

**Manual verification.**
Add a throwaway `return "test string"` to any tool function and run `uv run pytest
tests/test_prompt_surface.py` - it must fail and name the unrecorded string.
Remove it and confirm the suite passes.
Read the inventory top to bottom and confirm it matches what a Langfuse trace shows being sent.

**Blockers.** None.
Best sequenced after T0032.1 so the inventory records the corrected strings rather than the ones
being replaced.

---

#### T0032.3: Pin the column list across the three prompt blocks - 📋 Planned

**Objective.** Stop three hand-maintained copies of the sixteen-column schema from drifting, and
pin them against a translation that might move one copy and not the others.

**In scope.**
`tests/test_prompt_consistency.py` asserting that the column names named in <!-- lint-allow-link-path -->
`prompts.system_prompt` ("The database exposes these columns: ..."), in `prompts.schema_context`,
and in `prompts.sql_generation` ("Reference only real columns: ...") are the same set.
The test parses the three blocks from `config/prompts.yaml` and compares sets, so wording may differ
and membership may not.
A second assertion that the set matches the `clean_jobs` columns the SQLAlchemy model declares, so
the prompts cannot drift from the schema either.

**Out of scope.**
Generating the three blocks from one source.
Deduplicating them, or removing the duplicate list from `sql_generation`, which is instruction-count
work and belongs to the deferred pruning ticket.
Editing `config/prompts.yaml` at all - this ticket only reads it.
A new test file rather than `tests/agents/runtime/test_prompts.py`, because that path is inside
M24's declared scope.

**Manual verification.**
Temporarily remove one column name from the `sql_generation` list and run `uv run pytest
tests/test_prompt_consistency.py` - it must fail and name the missing column.
Restore it.
Run the whole suite and confirm it is green.

**Blockers.** None.

---

#### T0032.4: Vietnamese prompt spike - ✅ Complete 2026-08-17 (PR #63)

**Objective.** Decide, on measured evidence rather than argument, whether the system prompt's
instructions should be written in Vietnamese or stay English with an explicit output-language rule -
and whether the serving model can hold a Vietnamese conversation past the turn where multilingual
instruction following is reported to decay.

**In scope.**
`scripts/vietnamese_prompt_spike.py`, a throwaway spike in the shape of <!-- lint-allow-link-path -->
`scripts/deepseek_provider_spike.py`, run against the fixture database.
Five arms:

| Arm | Prompt language | Output language | Questions | Settles |
|---|---|---|---|---|
| A0 | English | English | control subset | today's behaviour, measured on the same day as the rest |
| A1 | English plus one output-language rule | Vietnamese | same subset, translated | whether an English prompt holds when the answer is Vietnamese |
| A2 | Vietnamese | Vietnamese | same subset, translated | whether a Vietnamese prompt follows better or worse |
| A3 | winner of A1/A2 | Vietnamese | conversational cases, extended past turn 6 | the multi-turn gap, which single-turn probes cannot see |
| A4 | winner of A1/A2, plus the VI vocabulary | Vietnamese | Vietnamese place and role questions | whether SQL literals stay canonical English |

Recorded per run: the answer, **the generated SQL string**, the tools called, answer-language purity
(any English fragment inside a Vietnamese answer counts as a failure, not a rounding error), and
per-rule instruction compliance rather than an aggregate score.
Findings written to `research/vietnamese-prompt-spike.md` with an explicit recommendation on the <!-- lint-allow-link-path -->
prompt-language question.

**Out of scope.**
Translating `evals/scenarios_v1.yaml`.
The spike carries its own hand-translated subset - roughly ten cases covering the honesty class and
the conversational class - inside the script, because building the eval registry to run the spike
would invert the dependency the spike exists to inform.
Promoting anything to `config/settings.yaml` or `config/prompts.yaml`.
Changing the shipped prompt in any way.
Using the DeepEval judge as the sole instrument: its Vietnamese grading is itself unmeasured, so the
honesty cases are graded by hand and the judge's agreement with those hand grades is recorded as a
side finding.

**Manual verification.**
`uv run python scripts/vietnamese_prompt_spike.py --arm A0` completes and its output matches the
recorded English behaviour for the same questions.
Each of A1-A4 completes and writes a row per run.
The written research record names a winner between A1 and A2, or states plainly that the arms did
not separate.

**Blockers.**
A running fixture database.
Provider budget for roughly five arms of ten cases with three runs each on the honesty probes.

**Outcome.**
All five arms completed with 72 recorded rows.
The research record selects A1: retain the English system prompt and add one Vietnamese-output
rule only when a later ticket defines the source-value language policy.
The spike made no production prompt or settings changes.
