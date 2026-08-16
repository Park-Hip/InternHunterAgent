# InternHunter — Tickets & Roadmap

> **Last verified:** 2026-08-14 against the active ticket plan and completion records.

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
| 25 | T0025 | **Evaluation Instrument** | ✅ | .0-.10 complete 2026-08-13: registry, driver, viewer, execution accuracy, three-tier grader, replay CI gate · .7 closed partial (13 of 19 turns; 2 scenarios need a paid tier) |
| 26 | T0026 | Evaluation Workspace Hygiene | ✅ | Complete 2026-08-14 (.1 front door and one fixture-URL owner, .2 tests into `tests/evals/`, .3 grading rules into the registry). No verdict changed |
| 27 | T0027 | DeepSeek Provider Integration | ✅ | Complete 2026-08-15 (.1-.4), following the deferred T0015.6 procedure · the spike passed, the arm measured 29/29 scenarios in 5m20s for ~$0.04, and .4 flipped both profiles to DeepSeek (D-045) with pacing at 0 and no provider key required at boot · the Groq branch stays selectable |
| 28 | T0028 | Evaluation Documentation Ownership | ✅ | Complete 2026-08-14 (.1 Fact Ledger rows + `scenario-id` check, .2 dedupe the behavior spec, .3 seal + merge the instrument reports, .4 operating manual + stale-claim sweep). No verdict, rule, or threshold changed |
| 29 | T0029 | Evaluation Readability | ✅ | .1 complete 2026-08-15: the verdict, the run's identity, and telemetry rendered in the viewer. Spent no quota; changed no rule |
| 30 | T0030 | Evaluation Evidence Durability | 📋 | .1 freeze command, .2 freeze the exposed captures, .3 the telemetry decision · closes the `[MED · DECISION]` left open by T0025.10 |
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
  [`evals/archive/v1_error_analysis.md`](../evals/archive/v1_error_analysis.md): six turns of
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

---

## T0028: Milestone 28 - Evaluation Documentation Ownership - Complete 2026-08-14

The four ticket plans are archived in
[`archive/Tickets_Archive.md`](archive/Tickets_Archive.md); their outcomes are in
[Completion Reports](Completion_Reports.md).

**What the milestone delivered.** Three Fact Ledger rows in [`README.md`](README.md) name an
owner for scenario definitions, behavior requirements, and dated graded outcomes, enforced by a
new `scenario-id` lint check. `docs/Agent_Behavior_Spec.md` §4a-4c links to the registry instead
of duplicating it. The two dated snapshots moved into `evals/archive/`; the grader audit and
holdout report merged into [`evals/Instrument_Report.md`](../evals/Instrument_Report.md). A new
[`evals/Operating_Manual.md`](../evals/Operating_Manual.md) explains why the instrument exists,
the three seams, grading, and its stated limits, and `Offline_Pipelines_Design.md` §8.6-8.7 now
names the shipped CI replay gate and the configured model.
No scenario, grading rule, threshold, or replay artifact changed.

---

## T0029: Milestone 29 - Evaluation Readability

M28 gave every evaluation fact an owner. This milestone makes a *recorded run* readable, which is
the step that still costs a person an afternoon now that capturing one costs four cents.

### T0029.1: Show the verdict, the run, and the telemetry in the viewer

> **Complete 2026-08-15.** `--grade` joins a grader report per turn; each turn shows its verdict
> and tier with every non-passing check drawn beside the seam it judges, the toolbar filters by
> grade status separately from capture status, a manifest-built run header names provider, model,
> and sampling per profile, and telemetry renders as labelled fields. No rule, threshold, verdict,
> or replay artifact changed. Outcome in [Completion Reports](Completion_Reports.md).

**Objective:** Make one capture answerable in the viewer alone - what failed, on which rule, under
which provider and sampling.

The measured arm produced 77 turns and 33 failures. Finding them meant pressing "Next" 77 times,
because [`viewer.py`](../evals/viewer.py) opens the driver artifact only: the verdict sits in a
separate `-grade.json` the viewer never reads, the manifest's provider and sampling never reach
the screen, and telemetry renders as one `json.dumps` blob in a text field. Triaging those 33 into
23 real behaviors and 10 grader phrasing artifacts was done with throwaway Python at a terminal,
which is the work this ticket removes.

**In Scope:**
* A `--grade <path>` input, joined on scenario / repeat / turn - already the viewer's `key`. Show
  each turn's `PASS`/`FAIL`/`INFRA`/`UNRUN` and its tier, and render every failing check's `name`
  and `detail` beside the seam it judges. `detail` carries what the rule wanted against what it
  saw, which is the field that makes a verdict explicable rather than merely visible.
* Filter the turn list by grade status. Note this is **not** the `status` the viewer shows today,
  which is capture status (`COMPLETE`, `PARTIAL_QUOTA`); both must be legible without collision.
* A run header built from the manifest: provider and model per profile, temperature, `max_tokens`,
  the reasoning knob, `git_sha`, and `baseline_eligible`. Two arms must be distinguishable on
  screen - today the string `deepseek` appears nowhere in the generated HTML, although T0027.2 put
  `providers` in the manifest precisely so a capture could say what produced it.
* Telemetry as labelled fields rather than one blob: latency, input / output / total tokens, the
  per-call breakdown, and finish reasons.
* The real-artifact invocation in [`evals/README.md`](../evals/README.md), which documents
  `--sample` only. Commands belong there, not in the Operating Manual.

**Out of Scope:**
* Judge-tier UI. No scenario sets `judge_metric`, so all 77 grades resolved structural or textual
  and there is nothing to draw. Render the `tier` field generically and a judge check appears the
  day a rule declares one.
* Any change to a grading rule, a threshold, or a verdict. The viewer reads evidence and never
  writes it, which is what lets it stay outside the replay gate.
* [`Operating_Manual.md`](../evals/Operating_Manual.md), which owns why the instrument is built
  this way rather than how to run it, and any new dependency. The viewer is one self-contained
  HTML file with no external asset, and stays that way.

**Manual verification:**
1. `uv run python -m evals.viewer --sample` still renders with no run artifact and no grade file,
   proving the grade input is optional rather than required.
2. Generate against a capture plus its grade file: filtering to `FAIL` yields the same count the
   grade summary reports, and the header names the model and per-profile temperature.
3. Open a `SAF` turn graded `FAIL` and read the failing check's `detail`. It must show the
   substring the rule wanted - that is how the 10 phrasing artifacts were identified by hand.
4. Regenerate from the frozen replay evidence and confirm the gate is untouched.

**Blockers:** None. Spends no quota; every input is a recorded artifact.

---

## T0030: Milestone 30 - Evaluation Evidence Durability

M29 made a recorded run readable. This milestone makes it survive.

A capture is the only irreplaceable output of the loop: grading, execution accuracy, and the viewer
are pure functions of `capture + registry + fixture` and regenerate forever, but a lost capture is
gone. The model is non-deterministic and `git_sha` and `prompt_hash` move underneath it, so a
re-run is a new arm, never the same one.

On 2026-08-16 the T0027.3 DeepSeek capture was lost: 77 turns, 29 of 29 scenarios, the only full
measurement the project has ever taken.
`evals/runs/` is ignored, the worktree holding it was removed when PR #50 merged, and
`git log --all --diff-filter=A -- "evals/runs/*"` confirms no commit on any ref ever contained it.
The findings survive in [the arm record](../evals/t0027_deepseek_arm.md); the per-turn evidence
does not.

The mechanism to prevent this already exists and was simply never automated.
[`evals/replays/t0025.9-committed.json`](../evals/replays/t0025.9-committed.json) is a sanitized
projection of a capture, and `replay.py` already defines the schema (`_TURN_KEYS`, `_SEAM_KEYS`)
and already rejects unsanitized content (`_FORBIDDEN_CONTENT` matches `trace_id`, `langfuse`,
`api_key`, and `postgres://`).
What is missing is a writer: `replay.py` only reads and validates, so that file was assembled by
hand, which is why it covers 4 scenarios out of 29.
Preserving evidence is manual work, so it does not happen.

### T0030.1: Give the replay format a writer

**Objective:** Make freezing a capture one command, so preservation stops depending on discipline.

**In Scope:**
* A `freeze` subcommand on the driver - `python -m evals.driver freeze <run>.json --grade
  <grade>.json -o evals/replays/<arm>.json` - emitting exactly the schema
  `replay.py::validate_replay` already accepts, and refusing to write anything
  `_FORBIDDEN_CONTENT` matches.
* Populate `source_capture` with the originating artifact name and `run_id` from its manifest, so a
  frozen replay names the capture it came from even after that capture is gone.
* Tests in `tests/evals/` that round-trip a capture through `freeze` and back through
  `validate_replay`, and that assert a trace ID in the input is refused rather than written.

**Out of Scope:**
* Any change to the replay schema itself, to a grading rule, or to a threshold. This ticket moves
  evidence, never verdicts.
* Un-ignoring `evals/runs/`. Raw captures stay uncommitted by design (**D-046** in .3); the frozen
  projection is what enters the repository.

**Manual verification:**
1. Freeze `evals/runs/t0025.7-acceptance.json` with its grade file <!-- lint-allow-link-path -->;
   `uv run python -m evals.replay
   --replay <the new file>` exits 0 against the frozen fixture.
2. Hand-insert a `trace_id` into a copy of the capture and confirm `freeze` refuses it by name.
3. Confirm the written file contains no `latency_ms`, no token counts, and no trace ID.

### T0030.2: Freeze the captures that are still exposed

**Objective:** Get the two surviving labelled captures into the repository before they follow the
DeepSeek one.

`evals/runs/t0025.7-acceptance.json` and its grade report <!-- lint-allow-link-path --> are the
only copies of the 13-turn
labelled sample behind [`evals/Instrument_Report.md`](../evals/Instrument_Report.md), and they exist
on one machine in one ignored directory.

**In Scope:**
* Freeze the T0025.7 acceptance capture with the .1 command and commit the result.
* Repoint the `<!-- lint-allow-link-path -->` references in `Instrument_Report.md` and
  [the arm record](../evals/t0027_deepseek_arm.md) at committed replays where one now exists, so the
  documentation gate enforces preservation instead of excusing its absence.
* Close the `[MED · DECISION]` entry in [`Known_Issues.md`](Known_Issues.md) that T0025.10 left
  open, and record the DeepSeek loss in [`Resolved_Issues.md`](Resolved_Issues.md) as the reason the
  decision finally landed.

**Out of Scope:**
* Re-measuring the DeepSeek arm. That is a fresh capture under M24's re-measurement, not a recovery,
  and it must not be presented as restoring what was lost.
* Any edit to a sealed dated record's findings. The arm record is superseded by re-measurement,
  never edited.

**Manual verification:**
1. `git clean -xdff` a fresh clone, then `uv run python -m evals.replay --replay
   evals/replays/t0025.7-acceptance.json` passes with no `evals/runs/` present.
2. `uv run python scripts/docs_lint.py` passes with fewer `lint-allow-link-path` exemptions than
   before, and the count is stated in the completion report.

### T0030.3: Decide what telemetry a frozen replay keeps

**Objective:** Settle the one open question in the format, in the Decision Log, rather than leaving
it to whoever writes the next freezer.

`evals/runs/` is ignored because captures carry latency, token usage, finish reasons, and trace IDs
([`Known_Issues.md`](Known_Issues.md)).
Of those, only the trace ID is genuinely sensitive - it resolves to a Langfuse trace.
T0029.1 then made telemetry visible in the viewer, so a strictly sanitized replay is now a capture
the viewer can grade but cannot fully show.

**In Scope:**
* A **D-046** entry deciding one of: keep the strict schema and let aggregate telemetry live in the
  dated arm record as prose, as the DeepSeek record already does ("77 turns in 5m20s for about
  $0.04"); or admit token and latency fields while continuing to strip trace IDs.
* Whichever is chosen, state the reason in terms of what a future reader needs to reproduce a
  finding, not in terms of file size.

**Recommendation to evaluate, not a foregone conclusion:** keep the strict schema. Per-turn latency
has no evidentiary value once the aggregate is recorded, and every field admitted is a field the
sanitizer must be trusted to police forever.

**Out of Scope:** implementing the outcome, which belongs to .1 if it changes the writer at all.

**Manual verification:** the Decision Log names D-046, and `evals/README.md` states in one line what
a frozen replay does and does not carry.

**Blockers:** None. Spends no quota; every input is a recorded artifact or a decision.
