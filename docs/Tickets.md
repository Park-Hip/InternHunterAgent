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
| 27 | T0027 | DeepSeek Provider Integration | 🔨 | Scoped 2026-08-14 (.1-.4), following the deferred T0015.6 procedure · **.1 complete**: all five spike checks pass · next is .2, the provider branch behind config |
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

---

## T0027: Milestone 27 - DeepSeek Provider Integration - 📋 Scoped 2026-08-14

The agent has run on one provider since M0, and Groq's free tier is now the binding constraint on
measurement: 8K TPM is what forces `eval.driver.turn_pacing_seconds: 75` and spreads a
29-scenario matrix over roughly three daily windows, which is why T0025.7 closed partial. DeepSeek
publishes no TPM or TPD ceiling - only account concurrency - at an estimated **$0.15 per full
87-turn matrix** on `deepseek-v4-flash`.

**The research is already written** and must be read before any block below is scoped:
[`research/deepseek-provider-evaluation.md`](../research/deepseek-provider-evaluation.md). It
records pricing and limits, the file-level change surface, and the three thinking-mode landmines
that make this more than a config edit: sampling parameters are silently ignored, `tool_choice` is
rejected with HTTP 400, and `reasoning_content` must be echoed back on every tool-carrying turn,
which `ChatDeepSeek` does not do, in an upstream issue closed as not planned. Disabling thinking
mitigates all three, and proving that is what .1 is for.

**This is not the first second provider.** T0015.6 wired Gemini beside Groq and was deferred, not
merged; it survives on `archive/t0015.6-provider-ab` and research §7 harvests its procedure. The
blocks below follow it: one variable changes, each arm runs with its native reasoning knob off,
the judge comes from neither contestant's family, and no unobserved result is ever written down.

**Not release-blocking.** M23 and M24 come first, and this stays a provider *option* until .3
decides otherwise. **Out of scope for the whole milestone:** changing any scenario, threshold,
grader rule, prompt, or agent behavior; removing the Groq branch; moving the judge off Gemini;
rebuilding an A/B harness, which research §8 shows M25 already made unnecessary.

### T0027.1: Spike DeepSeek before committing to it
> **Complete 2026-08-14. All five checks pass, the gate included.**
> `deepseek-v4-flash` on `langchain-deepseek` 1.1.0, 7 calls, $0.0003 provider-reported.
> The thinking switch demonstrably removes `reasoning_content`, the two-leg tool loop completes,
> `temperature: 0.0` returns byte-identical SQL, and streaming carries no reasoning chunks.
> The run corrects research §3: the `reasoning_content` passback failure **did not reproduce**,
> even with thinking left on and 75 chars of reasoning in flight. `tool_choice="required"` stays
> untested because nothing in this repo's agent path forces a tool - probe it before relying on it.
> An earlier attempt returned `402 Insufficient Balance` and was recorded as blocked, not failed;
> the account was funded and the spike re-run.

**Objective:** Decide whether the swap is viable at all, for the price of a few cents, before any
production file changes. The three thinking-mode landmines in research §3 are unproven against
this account until a live call says otherwise.

**In Scope:**
* A throwaway script under `scripts/` (Ruff-excluded, per the research-spike convention) running
  the five checks in [research §6](../research/deepseek-provider-evaluation.md): reachability,
  `extra_body` reaching the wire, a two-leg tool loop that does not 400, determinism at
  `temperature: 0.0`, and streaming that emits no reasoning chunks.
* Record every result in the research record, including a failure. A blocked check is reported as
  blocked, never inferred from the documentation.

**Out of Scope:**
* Any change to `src/`, `config/`, or `pyproject.toml`. The spike proves a claim; it ships nothing.
* Running any scenario from the registry. This is a provider probe, not a measurement.

**Manual verification:**
1. Run the script with `DEEPSEEK_API_KEY` set; all five checks report a live outcome.
2. Check 3 is the gate: if the second tool leg 400s on `reasoning_content`, stop and say so in the
   research record. The milestone does not proceed on a workaround invented at this point.
3. Confirm the spend on the DeepSeek dashboard matches the cents-scale estimate.

**Blockers:** none, beyond a funded API key. **Go/no-go for the milestone.**

### T0027.2: A second provider branch, behind configuration

**Objective:** Make DeepSeek selectable without making it the default, restoring the per-profile
provider seam that `archive/t0015.6-provider-ab` already settled.

**In Scope:**
* Restore that shape in [`provider.py`](../src/agents/runtime/provider.py): read
  `agent.<profile>.provider` with `agent.provider` as fallback, hoist shared arguments into one
  `common_kwargs`, keep each provider's native keys inside its own branch, import the DeepSeek
  package inside that branch, and raise an error naming the profile when its key is missing.
  Widen the return type to `BaseChatModel`.
* Read `EVAL_DRIVER_DISABLE_PROVIDER_RETRIES` in the new branch exactly as the Groq branch does.
  A branch that retries underneath the driver corrupts its retry ledger (research §8).
* Add `DEEPSEEK_API_KEY` to `src/core/config.py` as **optional**, matching `GOOGLE_API_KEY`, plus
  `.env.example`. Do not touch `render.yaml`: the deployed default is still Groq.
* Carry the DeepSeek thinking switch as configuration, not a literal, so .3 can move it.
* Record provenance in `build_manifest()`: the provider per profile, and the native knob each one
  used. A run that cannot say which provider produced it is not evidence.
* Mirror the existing Groq assertions in `tests/agents/runtime/test_provider.py`. The lazy import
  means the new branch is patched at its import site, not as a module attribute.

**Out of Scope:**
* Changing `agent.provider`, any deploy configuration, or the Groq branch's behavior.
* Relaxing `_assert_comparable()`. It is *supposed* to refuse two arms (research §8).

**Manual verification:**
1. `uv run pytest -q`, Ruff, mypy, and documentation lint pass with `agent.provider` still `groq`.
2. Flip one profile to `deepseek` in a scratch config, build the model, confirm the DeepSeek class
   is constructed and the other profile still builds Groq.
3. Unset `DEEPSEEK_API_KEY` with that profile selected: the error names the profile.
4. Start a driver run against the fixture and confirm the manifest names the provider per profile.
5. Boot the API unchanged and answer one question, proving the default path is untouched.

**Blockers:** T0027.1. Spends no quota beyond one hand-run model build.

### T0027.3: Measure DeepSeek on the matrix, then decide

**Objective:** Produce the arm comparison T0015.6 never got to run, under its pre-registered rule.

**In Scope:**
* Run the 29-scenario registry on the DeepSeek arm against the same fixture, in one session,
  sequentially with the Groq arm, using the driver's checkpoint and resume. Write it to its own
  artifact; **never overwrite the frozen baseline**.
* Hold everything else pinned: scenarios, fixture, prompts, temperature, `max_tokens`, timeout,
  tools, graph, judge, and replicate counts. Only provider, model, and each arm's native
  reasoning knob may differ, each set to its behavior-off value.
* Compare **graded outcomes per scenario**, not manifests, and state the intended configuration
  delta. `driver diff` will call the arms incomparable, correctly.
* Apply the pre-registered rule in research §7, in order: safety probes at 100% or the arm is
  disqualified, then honesty, then task and tool quality, then latency, tokens, and quota
  headroom. Write the outcome up as dated evidence with tokens and latency taken from
  `usage_metadata`, never estimated.
* Answer the two scenarios the free tier could never capture. If `HLP-CONTEXT-1` and
  `HLP-COMPOUND-1` land here, say so and update their [Known Issues](Known_Issues.md) entry.

**Out of Scope:**
* Flipping the default, which is .4, and any fix for a behavior this run exposes, which is M24's.
* Declaring a winner from a sub-significant aggregate delta. The rule is lexicographic precisely
  because 29 scenarios cannot resolve small quality differences.

**Manual verification:**
1. Both arms' manifests are `baseline_eligible` with a clean worktree.
2. The baseline artifact's hash is unchanged after the run.
3. Every reported number traces to a captured turn; blocked scenarios appear as blocked.
4. The decision follows the pre-registered order, and the write-up says which step decided it.

**Blockers:** T0027.2, a funded key, and one uninterrupted session for both arms.

### T0027.4: Flip the default, or record why not

**Objective:** Land the .3 decision as configuration and durable rationale, or close the milestone
with DeepSeek as a proven, unselected option.

**In Scope:**
* If .3 selects DeepSeek: move `agent.provider`, declare `DEEPSEEK_API_KEY` in `render.yaml`,
  resolve whether `GROQ_API_KEY` stays required in `src/core/config.py`, and revisit
  `eval.driver.turn_pacing_seconds`, which exists only to survive Groq's per-minute ceiling.
* Either way: a Decision Log entry beside **D-017** recording the measured basis, and rows in
  [Operations](Operations.md) for the key and [Tech Stack](Tech_Stack.md) for the dependency.
* Re-verify the deployed demo end to end after any deploy-affecting change.

**Out of Scope:**
* Removing the Groq branch. Two working branches are what keep the seam honest.

**Manual verification:**
1. A clean checkout boots with only the selected provider's key present.
2. The live demo answers a question and returns a `trace_url`.
3. The replay CI gate still passes untouched; it calls no model and must be indifferent to this.

**Blockers:** T0027.3.
