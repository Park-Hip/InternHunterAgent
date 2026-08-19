# InternHunter — Tickets & Roadmap

> **Last verified:** 2026-08-19 against the active ticket plan and completion records.

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
| 24 | T0024 | Honesty Enforcement (obligation seam) | ✅ ⚠ | Complete 2026-08-18 (.1/.6 `73b058a` glossary + `prompt_version` + decision #10 · .2 PR #68 `detect_obligations` and the `MANDATORY CAVEATS` block · .3 PR #69 the caveat-relay contract, `v2`→`v3` · .4 PR #70 the frozen gate). .5 measured out and never built. The gate reads **11 PASS / 7 FAIL over 18 turns**: `HON-CURRENCY-1` 0/3 → 3/3, but `HON-CREATED-ON-1` and `HON-ABSENT-FIELD-1` fail 3/3 and no `v2` control was captured — residuals in [`Known_Issues.md`](Known_Issues.md) |
| 25 | T0025 | **Evaluation Instrument** | ✅ | .0-.10 complete 2026-08-13: registry, driver, viewer, execution accuracy, three-tier grader, replay CI gate · .7 closed partial (13 of 19 turns; 2 scenarios need a paid tier) |
| 26 | T0026 | Evaluation Workspace Hygiene | ✅ | Complete 2026-08-14 (.1 front door and one fixture-URL owner, .2 tests into `tests/evals/`, .3 grading rules into the registry). No verdict changed |
| 27 | T0027 | DeepSeek Provider Integration | ✅ | Complete 2026-08-15 (.1-.4), following the deferred T0015.6 procedure · the spike passed, the arm measured 29/29 scenarios in 5m20s for ~$0.04, and .4 flipped both profiles to DeepSeek (D-045) with pacing at 0 and no provider key required at boot · the Groq branch stays selectable |
| 28 | T0028 | Evaluation Documentation Ownership | ✅ | Complete 2026-08-14 (.1 Fact Ledger rows + `scenario-id` check, .2 dedupe the behavior spec, .3 seal + merge the instrument reports, .4 operating manual + stale-claim sweep). No verdict, rule, or threshold changed |
| 29 | T0029 | Evaluation Readability | ✅ | .1 complete 2026-08-15: the verdict, the run's identity, and telemetry rendered in the viewer. Spent no quota; changed no rule |
| 30 | T0030 | Evaluation Evidence Durability | ✅ | Complete 2026-08-17 (PR #61): .1 the `freeze` command, .2 the surviving T0025.7 capture frozen to `evals/replays/`, .3 **D-046** on telemetry · closed the `[HIGH · DECISION]` capture-preservation entry. The lost T0027.3 capture stays lost |
| 31 | T0031 | Parallel Agent Workflow | ✅ | Complete 2026-08-17 (.1 PR #53 registry, frozen registers, per-ticket entries · .2 PR #57 three registers generated from the entries · .3 PR #59 `Repo_Current_State.md` derived from the tree · .4 PR #62 `registry`, `scope`, and `frozen` checks in CI). Build status and the branch check stayed undone, both recorded |
| 32 | T0032 | Prompt Surface Pass | ✅ | Complete 2026-08-18 (.4 PR #63 selected the English prompt plus a Vietnamese-output rule for later promotion · .1 PR #65 finished decision #10 on the two Python sites · .3 PR #66 pinned the column list across the three prompt blocks · .2 PR #67 recorded the model-facing string surface behind an AST scan). Prompt wording in `config/prompts.yaml` is unchanged and no instruction was pruned, both by design |
| 33 | T0033 | **Vietnamese Language Milestone** | ▶ | .1-.5 scoped 2026-08-19: the `Always answer in Vietnamese` rule and the vocabulary bridge, the 19 glossary strings with their grader anchors, the eval registry, the demo UI, and the tool literals. Every sequencing block it was allocated behind (M24, M32, M34, M38) closed on 2026-08-18; the `--arm A0 --runs 3` re-run is the one open input |
| 34 | T0034 | Serving Memory Window Hardening | ✅ | Complete 2026-08-18 (.1 PR #73 reproduced message-count eviction at the sixth one-tool turn and the fourth sequential-two-tool turn; .2 PR #74 replaced the 20-message cap with a six-turn policy that retains complete turns). The multi-turn issue is resolved; the six-turn bound is the intentional token-growth trade-off |
| 35 | T0035 | Capture Lineage Stamp | ✅ | Complete 2026-08-18 (.1 PR #72): `prompt_version` is recorded in the capture manifest, required by `freeze_capture`, validated at replay `schema_version` 2, and drawn in the viewer's run header. The three committed replays were backfilled from the prompt version in the commit each capture ran at. An unlabelled capture cannot become a labelled-looking replay |
| 36 | T0036 | Scope Check Generated-Region Exemption | ✅ | Complete 2026-08-18 (.1 PR #64): `check_scope` gained the `only_generated_changed` exemption `check_frozen` has carried since T0031.2, so a ticket branch that adds a `docs/entries/` file can run the mandatory generator and still pass. Unblocked the three M32 PRs; the docs job being advisory rather than required is left open as a maintainer decision |
| 37 | T0037 | Ingestion Failure Bounding | ✅ | Complete 2026-08-18 (.1 PR #71): `api.max_elapsed_seconds` 600 bounds the whole VietnamWorks fetch, so a total-source outage returns from `fetch()` and reaches `main()`'s abort path instead of being cancelled at the workflow's 15-minute ceiling. Verified against a real non-routable blackhole: 21.8s against an unbounded worst case of 336s. `timeout-minutes` was in scope and deliberately left at 15 |
| 38 | T0038 | Grader Correctness | ✅ | Complete 2026-08-18: glossary and registry anchors replace bare textual rules, SQL accuracy has explicit comparison modes, honesty seam 3 remains visible when seam 2 fails, and the frozen v3 replay now grades 15 PASS / 3 FAIL without a new capture |
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
>
> ⚠ **M24:** the milestone shipped its whole mechanism, but the gate it shipped against records a
> **measured honesty limitation rather than a clean pass** — 11 PASS / 7 FAIL over 18 turns, no
> `v2` control, and six of the 29 scenarios covered. T0023's DoD sweep owes decision **D9** those
> numbers, not a tick. The residuals are filed in [`Known_Issues.md`](Known_Issues.md) and the plan
> is archived in [`archive/Tickets_Archive.md`](archive/Tickets_Archive.md).

---

## T0033: Milestone 33 - Vietnamese Language Milestone (T0033.1-.5)

The agent answers in English, against a corpus whose company names and descriptions are Vietnamese,
for users who type Vietnamese.
T0032.4 measured five prompt arms on 2026-08-17 and settled the shape: arm A1 - the existing English
system prompt plus one explicit output-language rule - beat the fully translated A2 prompt, kept the
canonical `Hanoi` literal in generated SQL on all three list probes, and held its canonical literals
in all nine vocabulary rows.
This milestone promotes that measured arm.
It does not translate the system prompt, and it does not touch the SQL-generation prompt's English.

**The release criterion.** Purity is measured on agent prose only.
Three-way token split: the agent's own prose must be Vietnamese; canonical column values (`role`,
`location`, `job_level`) and source values (company names, titles, descriptions) pass through
verbatim and are exempt.
Purity is therefore measured on the remainder after stripping, by lookup against the returned row,
every value the answer quotes back.
A correct Vietnamese answer necessarily contains English, so an answer-level detector cannot pass
one; the spike's `ENGLISH_FRAGMENT` regex is replaced by a row-aware check rather than tightened.

**Vietnamese only.** The fixed `Always answer in Vietnamese` rule exactly as A1 spiked it.
Not bilingual: no arm ever measured a mirror-the-user rule, so there is no measurement to ship.

**What the milestone does not carry.** The turn-six instability was the conversation memory
window, not multilingual decay, and closed as M34 on 2026-08-18.
The `listing_expires_on`-as-application-deadline error is an honesty defect and went to M24.

**Reconciled 2026-08-19, against the tree rather than against the brief.** Three facts moved since
M33 was allocated, and each changes a ticket body:

* Every sequencing block is spent. M24, M32, M34 and M38 all closed on 2026-08-18, so T0033.1 and
  T0033.2 are free of M24's prompt scope, and T0033.5 is free of M32.
* The glossary is 19 entries, not 18, and M38 gave each one an anchor-term set in
  `behavior_glossary_anchors`. `evals/grader.py` loads both at import and enforces that every anchor
  is a substring of its canonical sentence, so a translated glossary with English anchors raises
  `ValueError` before a single scenario is graded. T0033.2 owns 38 strings, and both halves must
  move in the same commit.
* That coupling reaches the CI gate. `evals/replays/t0025.9-committed.json` carries a per-turn
  `expected_grade` that CI re-grades live against `config/prompts.yaml`, so translating the glossary
  flips the honesty turns to FAIL on captures whose answers are English and correct. The frozen
  replays are evidence of English behaviour and stay that way; T0033.2 re-states their expectations
  or the milestone lands red.

**Prerequisite, still open.** Decision D4 of the scoping brief asks for
`uv run python scripts/vietnamese_prompt_spike.py --arm A0 --runs 3` and a hand read of the
`HON-ABSENT` rows before ticket work starts. <!-- lint-allow-scenario-id -->
A0 shipped one run against A1's and A2's three, and the spike never reported what A0 did on the
deadline probe, so it is still unknown whether answering in Vietnamese caused that regression or
merely displayed a pre-existing English one.
M38 answered half of it from the English side - the `HON-ABSENT-FIELD-1` failure was a grader
artifact, and the frozen v3 replay now grades 15 PASS / 3 FAIL - but the Vietnamese side is
unmeasured.
The re-run costs one arm and gates T0033.1's wording only; T0033.3, T0033.4 and T0033.5 do not wait
on it.

---

### T0033.1: The Vietnamese output rule and the vocabulary bridge

**Objective.** Promote arm A1 exactly as it was measured, and give the SQL generator the accented
Vietnamese vocabulary it needs to keep emitting canonical English literals.

**In scope.**
`config/prompts.yaml` - append the fixed `Always answer in Vietnamese` output-language rule to
`system_prompt`, verbatim as A1 spiked it.
Add a Vietnamese vocabulary block sourced from the accented `city_alias_map` and `role_taxonomy`
already in `config/ingestion.yaml`: the map exists, is accented, and the spike hand-wrote an
unaccented subset of it, so this is a promotion rather than an authoring job.
Add one bilingual free-text rule to `sql_generation` stating that `description` holds Vietnamese
prose and that a free-text concept must be matched in both its English and Vietnamese forms.
Bump `prompt_version` `v3` to `v4`.
Tests in `tests/agents/runtime/test_prompts.py` pinning the rule's presence and the vocabulary
block's agreement with `config/ingestion.yaml`.

**Out of scope.**
Translating `system_prompt`, `schema_context` or `sql_generation` - A2 measured worse and is ruled
out on this evidence.
The behaviour glossary, which is T0033.2.
Lifting `city_alias_map` out of ingestion ownership into a shared module: A4 shows a prompt block is
sufficient, so the move is optional and not required by this milestone.
Accent-insensitive SQL (`unaccent`), which the brief leaves conditional.

**Manual verification.**
Ask a Vietnamese Data Engineer question naming Hanoi with full diacritics against the fixture
database, and confirm the answer is Vietnamese prose while the generated SQL still holds `Hanoi`,
not `Ha Noi`.
Ask the same question unaccented and confirm the same canonical literal - A4 never ran against
accented input, and accented input is what the product receives.
Ask a remote-work question in Vietnamese and confirm the generated SQL matches both the English and
the Vietnamese form of the concept.

**Blockers.** The D4 A0 re-run above, which decides whether the rule ships alone or with a
reinforcing honesty clause.
Bumping `prompt_version` invalidates the three committed replays as a comparison baseline, which is
what the M35 stamp exists to make visible - re-run the gate rather than comparing across it.

---

### T0033.2: The behaviour glossary in Vietnamese, with its grader anchors

**Objective.** Translate the agent's canonical caveat sentences, which are agent prose and therefore
unambiguously inside the purity criterion, without silently breaking the instrument that grades
them.

**In scope.**
`config/prompts.yaml` - all 19 `behavior_glossary` sentences in Vietnamese, and all 19
`behavior_glossary_anchors` sets re-derived from the translated sentences.
`evals/grader.py` validates that each anchor is a substring of its canonical sentence, so the two
move together or nothing grades at all.
`docs/Agent_Behavior_Spec.md` - the glossary table restated against the translated strings.
`evals/replays/` - re-state the `expected_grade` values the translation moves, and record in the
replay why an English capture now grades against Vietnamese anchors.

**Out of scope.**
Re-capturing the honesty scenarios against a live model, which is T0033.3's call and this ticket's
follow-up.
Changing any caveat's meaning or adding a new one: this is a translation, and a behaviour change
smuggled into it would invalidate M24's gate silently.
Turning the judge tier on.

**Manual verification.**
Ask about a posting with no disclosed salary and confirm the negotiable-salary caveat appears in
Vietnamese and reads naturally rather than as a literal gloss.
Run `uv run pytest tests/evals` and confirm the committed replay gate is green on the re-stated
expectations rather than skipped.
Ask about an application deadline and confirm the absent-field and listing-expiry caveats both read
as Vietnamese refusals.

**Blockers.** None on sequencing - M24 and M38 both closed on 2026-08-18.
The head-on collision this ticket was allocated behind is spent; the anchor coupling M38 introduced
replaced it and is the real constraint.

---

### T0033.3: The eval registry in Vietnamese, and a purity check that can pass

**Objective.** Make the instrument able to measure a correct Vietnamese answer, which today it
cannot.

**In scope.**
`evals/scenarios_v1.yaml` - Vietnamese inputs across the 29 scenarios, with translated
`required_any` and `forbidden_any` lexicons, and new probes on accented input that A4 never ran.
`evals/grader.py` - Vietnamese number words in `_answer_count`, whose table today holds `one`
through `twelve` in English only, and the row-aware purity check that strips every canonical and
source value found in the returned row before judging the remainder.
`tests/evals/` - coverage for the purity check on a constructed answer that mixes Vietnamese prose
with verbatim English values, which must pass.

**Out of scope.**
Spending a full 29-scenario capture, which is a quota decision rather than a code change.
Expanding replay coverage past the 12 scenarios `KI-2026-08-18-freezer-rejects-no-sql-turns` owns.
Any prompt edit - this ticket measures, it does not steer.

**Manual verification.**
Run the purity check by hand over the worked specimen in the scoping brief - Vietnamese prose around
`Data Engineer`, `Hanoi`, a Vietnamese company name and `Python, SQL` - and confirm it passes.
Run it over an answer carrying a genuine English prose fragment and confirm it fails.
Confirm `_answer_count` accepts the Vietnamese word for three where it accepts `three`.

**Blockers.** None. Disjoint from M24's spent scope and unblocked today.

---

### T0033.4: The demo UI in Vietnamese

**Objective.** Make the front end match the language the agent now answers in, and render stacked
diacritics without clipping.

**In scope.**
`src/api/static/index.html` - `lang="vi"`, the masthead, standfirst, lede, composer placeholder and
the four example chips in Vietnamese.
`src/api/static/app.js` - the status and error strings: the dateline fallback, the reading-listings
placeholder, the send-button busy label, the trace link, and the two failure messages.
`src/api/static/styles.css` - the typography decision this ticket owes.
Today the stack is `Charter, Georgia, 'Iowan Old Style', 'Times New Roman', serif` with a deliberate
`no font files, CSP-clean` comment, and Charter has no Vietnamese coverage, so accented text falls
through to a system fallback mid-paragraph.
Either self-host a Vietnamese-complete serif and record the CSP consequence, or reorder the stack
onto faces that do cover Vietnamese and record why no file was added.
Raise `line-height` where stacked diacritics need the room.

**Out of scope.**
Any language switcher: D3 settled Vietnamese-only, and a switcher is a second product surface no
measurement supports.
A CDN font link, which the same-origin static posture rules out.
Renaming the product - the `InternHunter` name over-promising on internships is raised, unowned, and
deliberately not folded in here.

**Manual verification.**
Load the demo and confirm no English string survives in the shell.
Compare a heading carrying stacked diacritics against the body serif at 400% browser zoom and
confirm one face renders the whole line.
Confirm the diacritics on a two-line heading do not collide with the line above.

**Blockers.** None. Disjoint from every other ticket in this milestone.

---

### T0033.5: The tool literals in Vietnamese

**Objective.** Close the last surface that reaches the user in English - the strings the tools
return directly, which no prompt rule can restyle because the model relays them.

**In scope.**
`src/agents/tools/query_clean_jobs.py` - `_build_answer`'s truncation header and its
`Found N result(s) with columns:` header, the `I can't run that query:` refusal, and the database
error literal.
`src/agents/tools/get_job_details.py` - `_build_answer`'s `Showing details for N of M requested.`
and `No posting found for id N.`.
`tests/agents/tools/` - assertions on the translated wording.

**Out of scope.**
The `ZERO_RESULTS` and `ABSENT_FIELD` paths, which T0024.2 already routed through
`load_behavior_glossary()` and which T0033.2 therefore translates at the source.
Tool docstrings, which are model-facing instructions rather than user-facing prose and stay English
under the A1 result.
`tests/test_prompt_surface.py`'s inventory beyond the entries these strings already occupy.

**Manual verification.**
Force a truncated result and confirm the header is Vietnamese while the column names stay canonical.
Ask a question that trips SQL validation and confirm the refusal is Vietnamese.
Ask for details on an id that does not exist and confirm the miss line is Vietnamese.

**Blockers.** None - M32 closed on 2026-08-18.
Check the registry's pinned lexicons before starting, and sequence after T0033.3 if any of these
literals is pinned there.
