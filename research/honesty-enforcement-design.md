# Honesty Enforcement Architecture — Design & Recommendation

> **Status:** design record, written 2026-07-16. No implementation. Decides *where honesty
> enforcement lives* for the C-category failures measured in
> `evals/v1_scenario_matrix.md` (branch `feature/t0015.4-v1-scenario-matrix` @ `eba3e1f`).
> Companion evidence: `docs/Known_Issues.md` (§ Agent runtime & prompts),
> `docs/Agent_Behavior_Spec.md` @ `eba3e1f`, `research/pre-deploy-refinement-plan.md` §4/§5f,
> `research/deployment-research-plan.md` §4.2 #3.

---

## 0. TL;DR — the recommendation

**Revive the dead `QueryToolResult` seam and make the query service compute hedge
*obligations* deterministically from the validated SQL plus the result set.** The tool stops
trusting the model to *notice* what needs hedging; instead code detects the condition,
resolves the canonical phrasing from the `behavior_glossary` (already frozen on the M15
track), and places it in the tool message as an explicit, delimited `MANDATORY CAVEATS`
block the model must carry into its answer. One structural system-prompt rule ("preserve
tool-provided caveats") is the only prompt change — a contract change, not a few-shot
tinkering round.

Ship it in three stages, the third conditional on measurement:

1. **Detect + attach** (service layer): `detect_obligations(sql, table)` in
   `src/services/query/`, models in `models.py`, canonical strings from
   `config/prompts.yaml` `behavior_glossary`, rule toggles in `config/settings.yaml`.
2. **Measure**: re-run the T0015.4 manual matrix protocol (needs only Groq + the fixture
   DB — *not* blocked on T0011.5 credentials).
3. **Enforce (conditional)**: a verify-and-append middleware in the runtime layer, built
   *only if* stage 2 shows the model drops explicit caveats. Do not build it speculatively.

**Why this is the answer:** the repo already runs this exact architecture for one honesty
behavior. `TRUNCATION` is computed in code (`resolve_bounds`'s `max_rows + 1` sentinel →
`_build_answer`'s "there are more matches" header) and placed in the tool text — and it is
the **only honesty caveat that passes** (A4: 2/2). Every honesty caveat left to the model
to notice from raw data fails (Category C: 0/7). Even C3's failure is evidence *for* relay
fidelity: the model faithfully echoed the tool's canned zero-results string **including its
defective "internship" wording** ("I don't have any COBOL *internship* job postings" — the
bias is in `_build_answer`'s own string, not the model's imagination). The mechanism that
already works is the mechanism to generalize.

---

## 1. Reading the evidence precisely

The 0/7 is not one failure mode. Splitting it changes the design:

| Scenario | What actually happened (from the matrix) | Failure class |
|---|---|---|
| C1 created-on | Correct row all 3 runs; called it "posted on July 10" all 3 runs | **Missing caveat** — deterministic omission (0/3) |
| C2 cross-currency | r1/r2: empty-answer fallback; r3: crowned the 40M VND row, no hedge | **Missing hedge** + a *separate* empty-answer defect |
| C3 zero-results | r1: "database error"; r2/r3: relayed the tool's canned string, echoing its internship bias | **Tool's own canned string is off-spec** + an unobservable error (logging gap) |
| C4 free-text | r1/r2 hedged (r2 nearly verbatim spec); r3 answered "no remote internships" | **Flaky** — hedge appears when the right SQL ran |
| C5 negotiable | r1 used the exact forbidden phrasing; r2/r3 acceptable | **Flaky**, forbidden phrasing wins ~1/3 |
| C6 seniority | Correct levels both runs, dropped the 3+1 counts | **Not a hedge failure** — answer-completeness |
| C7 absent field | r1/r3 correct decline; r2 relabeled `listing_expires_on` as "application deadline" | **Flaky relabeling** — fabrication by mislabeling |

Two observations drive everything below:

- **Deterministic omissions (C1: 0/3, C6: 0/2, C2: 0/3) are not "model non-determinism."**
  A behavior that is wrong on every rerun at temp 0.2 is a *missing mechanism*, not noise.
  The 2026-07-02 Known_Issues doctrine note was right that these aren't code *bugs*, and
  right to ban another prompt-tinkering round — but the matrix data shows they aren't
  transient nondeterminism either. The correct reading: the current architecture gives the
  model a task (spot hedge conditions in prose) that this model reliably cannot do, and no
  amount of measurement of *that* architecture will change it.
- **What the model relays, it relays faithfully.** A4's computed truncation notice: kept,
  2/2. C3's canned zero-results string: paraphrased-but-preserved, including its flaws.
  M-G44's "there are 2, not 500" premise correction (grounded in the tool's row count):
  3/3. The model's *relay* channel works; its *inference* channel does not. Move the
  honesty work onto the channel that works.

---

## 2. The candidate loci, evaluated

### 2a. The prompt (status quo) — rejected as the primary locus

Four prose lines produced 0/7. The proposed remedy (glossary few-shots) is the exact move
the 2026-07-02 note forbids, and it attacks the wrong problem: few-shots teach the model
*how to phrase* a hedge, but C1/C2/C6 show the model never *decides* to hedge. Few-shots
also cost system-prompt tokens on every turn against an 8k TPM ceiling. The prompt keeps a
role, but a narrower one: one structural rule that defines the caveat-relay contract, and
(in the separately re-scoped T0015.5) few-shots for the failures that are genuinely
linguistic (see §7).

### 2b. Deterministic post-processing of tool output, before the model sees it — adopted (this is stage 1)

This is where the hedge conditions are all still visible: the validated SQL string and the
structured rows exist side by side inside `query_clean_jobs` for exactly four lines
(`format_rows` → `_build_answer`) before both are flattened into prose. Every detection in
§4's table is a pure function over `(validated_sql, TableArtifact)`. The precedent is
in-repo and passing (truncation). The cost is near zero: no extra LLM calls, no new
dependency, no new layer.

### 2c. The dead `QueryToolResult` seam — revive, with one amendment

`QueryToolResult(answer, table, refusal)` and `QueryRefusal(reason)` in
`src/services/query/models.py` are precisely the shape a structured tool boundary needs,
and they're dead because nothing ever computed anything worth structuring. Obligations are
that thing. Amendment: `refusal` models "the tool won't answer"; hedges are "the tool
answers, *with strings attached*" — a separate field:

```python
# src/services/query/models.py (illustrative)
class HedgeObligation(BaseModel):
    token: str   # behavior_glossary key, e.g. "CROSS_CURRENCY"
    text: str    # canonical phrasing resolved from config/prompts.yaml

class QueryToolResult(BaseModel):
    answer: str
    table: TableArtifact | None = None
    refusal: QueryRefusal | None = None
    obligations: list[HedgeObligation] = []
```

The tool still returns a **string** to the model (LangChain tool message), rendered from
the structured result — structure internally, prose at the boundary. Rendered shape:

```
Found 5 result(s) with columns: id, title, company, salary_min, salary_max, salary_currency.
- id=7, title=Data Scientist, company=Sonat Game, salary_max=40000000, salary_currency=VND
- ...
MANDATORY CAVEATS — your answer must reflect each of these; rephrase but do not weaken or omit:
[CROSS_CURRENCY] These salaries are in different currencies (USD and VND), so I can't rank
them against each other directly — want me to compare within one currency?
```

Do **not** return raw JSON to the model: qwen3.6-27b's relay fidelity is measured on
prose tool messages (A4/C3/M-G44); JSON-in-tool-message is an unmeasured behavior change.

### 2d. Middleware (`src/agents/runtime/middleware.py`) — wrong locus for detection, possible locus for enforcement

By the time `wrap_model_call` sees a `ModelRequest`, the SQL and the rows have been
flattened to prose — detection there means re-parsing text the service layer had as
structure four calls earlier. Rejected for detection. It *is* the right layer for the
conditional stage 3 (verify the final answer carries the pending obligation tokens'
content; append the canonical string if dropped), because that check reads only message
content and stays inside the runtime layer. Build it only on adverse stage-2 evidence: it
adds a streaming seam (the appended caveat must be emitted as trailing tokens before
`done`) and a real risk of incoherent answers (see §5 on C2 — an appended footnote cannot
un-crown a winner the body already crowned, so the append is a floor, not a fix).

### 2e. Post-hoc answer rewriting as the *primary* mechanism — rejected

Guarantees caveat *presence* but not answer *correctness* (C2's body still crowns #7), puts
words in the model's mouth outside any conversational flow, and complicates streaming for
every turn rather than the rare failure. Kept only as 2d's conditional safety net.

### 2f. Runtime LLM self-critique (second model pass) — rejected

Doubles Groq spend per turn against an already-exhausted free tier, adds latency to a demo
with a 60 s cold-start problem, and replaces a nondeterministic writer with a
nondeterministic checker. Over-engineering per CLAUDE.md §1.

---

## 3. The architecture (recommended)

```
question
  → generate_sql (LLM)                          [unchanged]
  → validate_sql                                 [unchanged + one refusal upgrade, §4 C7]
  → resolve_bounds                               [unchanged]
  → execute_validated_sql                        [unchanged]
  → format_rows → TableArtifact                  [unchanged]
  → detect_obligations(validated_sql, table)     [NEW — pure function, service layer]
  → QueryToolResult(answer, table, obligations)  [revived seam]
  → render_tool_message(result)                  [NEW — replaces _build_answer]
  → model answers                                [one new system-prompt rule: preserve caveats]
  → (stage 3, conditional) verify-and-append middleware
```

- **Layer isolation holds.** Detection and rendering are query-service code; the tool
  composes them; the runtime and API layers are untouched in stages 1–2; tracing untouched.
- **Models in `models.py`, parameters in `settings.yaml`, canonical strings in
  `prompts.yaml`** (the glossary is the machine source of truth per Behavior Spec
  decision #5):

```yaml
# config/settings.yaml (illustrative)
agent:
  query:
    obligations:
      enabled: true          # master switch — off restores today's behavior exactly
      rules:                 # per-rule toggles, so measurement can bisect
        zero_results: true
        created_on_caveat: true
        free_text_hedge: true
        cross_currency: true
        negotiable_salary: true
        listing_expiry_not_deadline: true
```

- **Both tools participate.** `get_job_details` returns full fixed-shape rows, so the
  row-scan rules (negotiable salary; later `is_active`) apply to it with no SQL inspection.
  Without this, a salary question routed through `get_job_details` bypasses enforcement.
- **`_build_answer`'s own strings come up to spec** in the same change: the zero-results
  canned answer becomes glossary `ZERO_RESULTS` (killing the "internship" bias the model
  faithfully echoed in C3), and the truncation header becomes glossary `TRUNCATION`.

### What this does *not* claim

Attaching obligations moves the model's task from *notice* (measured 0/7) to *relay*
(measured analogs: A4 2/2, C3 2/2 of non-error runs, M-G44 3/3). It does not make final
phrasing deterministic — the model can still drop or weaken an explicit caveat. That
residual is (a) a strictly easier task with in-repo passing evidence, (b) measurable
per-rule via the toggles, and (c) backstopped by the pre-designed stage 3 if measurement
demands it. This is the honest version of the guarantee; anything stronger requires
speaking for the model (§2e, rejected).

---

## 4. Per-scenario mapping — the seven C failures

| # | Detection (pure function over validated SQL + TableArtifact) | Fixed structurally? | Residue & why it's acceptable |
|---|---|---|---|
| **C3 zero-results** | `row_count == 0` → answer *is* glossary `ZERO_RESULTS` (already deterministic today; only the string is wrong) | **Yes — fully.** Code already owns this answer; fixing its wording is a code fix | Paraphrase risk only. r1's "database error" is a separate defect, unobservable until the executor-logging register item lands (rider, §8) |
| **C1 created-on** | `created_on` referenced in SQL → attach `CREATED_ON_CAVEAT` | **Yes — detection is total.** Fires on exactly the queries that touch the column | Relay residue: model must keep the caveat. Best-case profile for relay (A4-style additive footnote; nothing in the answer to contradict) |
| **C4 free-text** | `description\s+(NOT\s+)?ILIKE` in SQL → attach `FREE_TEXT_HEDGE` | **Yes, when the free-text query runs** (r1/r2 pattern) | r3 failed on *SQL choice*, not hedging — no `description ILIKE` ran, so no rule can fire. That's SQL-generation quality (spec decision #8, prompt-side), out of this mechanism's scope by design |
| **C5 negotiable** | salary columns present in result AND any row has `is_salary_negotiable = true` or both `salary_min`/`salary_max` NULL → attach `NEGOTIABLE_SALARY`; same row-scan in `get_job_details` | **Mostly.** Supplied canonical phrasing displaces the forbidden "not in the data" formulation | If the model's SQL omits all salary columns for a pay question, detection is blind. Deliberately *not* fixed by injecting columns into the SELECT — that is the exact T0009.11 line (§5). Judged unlikely for pay questions; measured in stage 2 |
| **C2 cross-currency** | `ORDER BY salary_min/salary_max` or `MAX/MIN(salary_…)` in SQL → attach `CROSS_CURRENCY` (fires on the *question shape*, independent of what was selected — a result-set distinct-currency count would miss single-currency-scoped SQL that still answers "highest-paid" incompletely) | **Partially.** Detection is total; compliance is not | The required behavior is *not crowning a winner* — an integration act, not a footnote. The obligation is in context before the model writes, which is the strongest available position short of writing the answer for it; stage 3 can guarantee the caveat's presence but not the un-crowning. r1/r2 were the empty-answer fallback — a distinct, already-registered defect this design does not solve |
| **C7 absent field** | Two halves. (i) Model invents a column → today an opaque "database error"; upgrade: executor maps Postgres `UndefinedColumn` to a structured `QueryRefusal` rendered with `ABSENT_FIELD` (error-driven, no SQL parsing). (ii) Model *relabels* `listing_expires_on` as a deadline → attach a new schema-fact caveat whenever `listing_expires_on` is in SQL ("stated listing expiry, not an application deadline" — new glossary entry via the spec's process) | **Partially** | The relabeling in r2 happened with correct SQL; the caveat arms the model against it but can't force the right label. Residue is bounded: with the caveat present, a relabeled answer contradicts its own quoted caveat — a state stage 2 will surface if it occurs |
| **C6 seniority** | — | **No, and it shouldn't be.** C6 is not a hedge: it's an answer-completeness failure (levels given, 3+1 counts dropped). There is no false statement to detect | Correctly belongs to the prompt pass (§7). Acceptable residue: the failure mode is incompleteness (priority-ladder rung 3), not fabrication (rung 2). Forcing counts into answers from code would be answer-writing, not honesty enforcement |

Cheap extras the same rules cover for free: M-D8/M-D9 partially (their expected
`FREE_TEXT_HEDGE` fires when the fallback query runs); an optional
`title ILIKE '%senior%'` → `SENIOR_TITLE_HEDGE` rule covers M-D2's hedge half (its SQL
half stays prompt-side). Not scope-critical; listed in the ticket as optional toggles.

**Net honest accounting:** 3 of 7 fixed structurally (C1, C3, C4-when-queried), 2 more
displaced onto supplied phrasing with high confidence (C5, C7ii), 1 armed-but-model-
dependent at its core (C2's un-crowning), 1 out of scope by nature (C6). Plus the mechanism
is the designated future home of the `is_active` hedge (§6).

---

## 5. The tool boundary, reconciled with T0009.11

T0009.11 declined to force-inject `id` into model-generated SQL because that "would blur
the tool boundary between model-generated SQL and deterministic enforcement." Read against
what the repo *actually does*, the line it protects is precise — and this design is on the
safe side of it:

| Deterministic code already… | Where | Verdict in repo |
|---|---|---|
| Rejects the model's SQL outright | `validate_sql` (7 checks) | Trust boundary — required |
| Rewrites the model's `LIMIT`, adds a sentinel row | `resolve_bounds` | Shipped (T0010.5/.7) |
| Deletes a column from what the model sees | `format_rows` (drops `description`) | Shipped |
| Computes an honesty notice and puts it in the tool text | `_build_answer` truncation header | Shipped — and it's the passing honesty behavior |
| **Changes what data the query returns** (inject `id` into SELECT) | — | **Declined (T0009.11)** |

The practiced boundary: deterministic code may **read** the model's SQL, **bound** it
inside a safety envelope, and **annotate its results** — it may not **rewrite the query's
semantic intent** (change what data comes back, silently answer a different question).
Obligation detection reads the SQL and annotates the result; it never edits the query.
It is `resolve_bounds`-class, not id-injection-class. The T0009.11 precedent stands
untouched — and this design re-affirms it concretely by *rejecting* the one variant that
would cross it (widening C5's SELECT to force salary columns into the result, §4).

The same test disposes of the `is_active` alternatives already ruled out in
`deployment-research-plan.md` §4.2 #3: a hide-inactive view and `WHERE is_active`
injection both change what data comes back — semantic rewriting. Hedging on what *did*
come back does not.

---

## 6. Resolving the doctrine ↔ plan contradiction

The 2026-07-02 note ("model non-determinism, not code defects… do not treat them as bugs
to be closed by another round of prompt-tinkering") and the matrix's remedy footer ("add
glossary-backed few-shots for …") genuinely conflict. Resolution:

- **The note's ban stands, and this design obeys it.** Nothing here re-tunes prompt wording
  hoping the model starts noticing. The one prompt change (the caveat-relay rule) alters
  the *contract* between tool and model — it accompanies a mechanism, it is not the
  mechanism.
- **The note's diagnosis is superseded by the note's own prescribed process.** It demanded
  measurement before action; T0015.4 *is* that measurement, and it returned deterministic
  0/N failures — which are not non-determinism. The doctrine's conclusion ("wait and
  measure") completed; the evidence licenses a mechanism.
- **The remedy footer was scoped too broadly.** Few-shots are the right tool for the
  genuinely linguistic failures and the wrong tool for mechanically detectable conditions.
  **Re-scope T0015.5 accordingly** (this is the concrete plan change): drop
  `CREATED-ON-CAVEAT`, `CROSS-CURRENCY`, `ZERO-RESULTS`, `FREE-TEXT-HEDGE`,
  `NEGOTIABLE-SALARY`, `ABSENT-FIELD` from its few-shot list (owned by the mechanism);
  keep the persona internship-bias rebalance, multi-turn/compound few-shots (B1, M-G03),
  synonym/abstraction guidance (M-D7/M-D8/M-D9), `DISCRIMINATORY-DECLINE` (M-G29),
  `SQL-DESCRIBE-ONLY` (M-D4), and C6's counts — behaviors where wording *is* the substance.
- **Forward consistency:** `deployment-research-plan.md` §4.2 #3 planned the `is_active`
  hedge as "a prompt nudge — best-effort, like the existing role/salary/id-first nudges,"
  gated on the Evaluation milestone confirming the model honors nudges. That gate has now
  effectively *failed* (hidden-salary 2/2 violation, freshness 1/3, C-category 0/7).
  This mechanism is the replacement: "list result contains `is_active = false` rows" is a
  row-scan rule — one more entry in the detector when exposure lands (post-T0019.3, gated
  as already planned). Update §4.2 #3's enforcement sentence when this design's milestone
  ships. `Tickets.md` T0019's out-of-scope line "deterministic hedge enforcement …
  answer post-processing" excluded this from the *ingestion* milestone; it names §4.2 #3's
  view/injection rejections plus answer rewriting — result-annotation obligations are none
  of those, and get their own milestone here rather than being folded into T0019.

---

## 7. Track convergence (M15 ↔ deploy lineage)

The mechanism needs exactly one artifact from the M15 track to build: the
`behavior_glossary` block in `config/prompts.yaml` @ `eba3e1f` (machine source of truth
for canonical strings, per spec decision #5). The spec, matrix, and scenario YAML are
measurement artifacts and can stay on their track until the re-run.

Convergence plan: **cherry-pick/merge the glossary block (and `prompt_version` keying)
into the deploy lineage as the first ticket** — config + docs only, no code conflicts
expected (the deployed `prompts.yaml` has no glossary block to collide with). The matrix
re-run (stage 2) then happens on a branch that has both the mechanism and the frozen
scenario definitions — recorded as a v2 matrix file next to the v1 one, same protocol,
same fixture, same model/temp, new `prompt_version`. The wider main-reconciliation problem
(main stuck at T0009) is explicitly out of scope here and stays where it's tracked.

---

## 8. Ticket breakdown — proposed Milestone T0020: Honesty Enforcement (obligation seam)

Sequencing vs T0019 (ingestion): independent code surfaces (`src/services/query/` + config
vs ingestion pipeline); can proceed in parallel. The only contention is the Groq daily
token budget for T0020.4's matrix run vs any T0019 live verification.

### T0020.1: Glossary convergence — `behavior_glossary` onto the deploy lineage
**Objective:** Land the canonical-phrasing block (machine SoT, spec decision #5) where code
can read it, without waiting for full M15 merge.
**In Scope:**
* Merge/cherry-pick the `behavior_glossary` block and `prompt_version` key from
  `eba3e1f:config/prompts.yaml` into the deploy lineage's `config/prompts.yaml`.
* Loader function in `src/agents/runtime/prompts.py` style: `load_behavior_glossary() -> dict[str, str]`, with a test that every token the detector will reference exists.
* Add the one new schema-fact string this design needs: `LISTING_EXPIRY_NOT_DEADLINE`
  (follow the spec's process — record it in the question-bank/spec on the M15 track too).
**Out of Scope:** any detection code; any system-prompt change; merging the spec/matrix files.
**Manual verification:** `uv run python -c "from src.agents.runtime.prompts import load_behavior_glossary; print(load_behavior_glossary()['CROSS_CURRENCY'])"` prints the canonical string; `uv run pytest -q` green.
**Blockers:** none. **Do first.**

### T0020.2: Obligation detection + the revived structured seam — **blocked on T0020.1**
**Objective:** Compute hedge obligations deterministically from validated SQL + result set;
revive `QueryToolResult` as the tool's internal result shape.
**In Scope:**
* `src/services/query/models.py`: add `HedgeObligation`; extend `QueryToolResult` with
  `obligations: list[HedgeObligation]` (keep `refusal`).
* `src/services/query/obligations.py`: `detect_obligations(sql: str, table: TableArtifact) -> list[HedgeObligation]` implementing the §4 rules (zero_results, created_on_caveat, free_text_hedge, cross_currency, negotiable_salary, listing_expiry_not_deadline; optional senior_title_hedge behind a default-off toggle). Pure function, no I/O.
* `src/services/query/table_formatter.py` or a sibling `render_tool_message()`: serialize
  `QueryToolResult` to the tool-message string with the delimited `MANDATORY CAVEATS` block; canned zero-results answer becomes glossary `ZERO_RESULTS`; truncation header becomes glossary `TRUNCATION` (removes the internship-bias wording C3 echoed).
* `query_clean_jobs.py` + `get_job_details.py`: compose detection into the return path
  (`get_job_details` uses the row-scan rules only).
* Executor-error upgrade: map Postgres `UndefinedColumn` to a structured `QueryRefusal`
  rendered with `ABSENT_FIELD` instead of the generic "database error" string.
* `config/settings.yaml`: `agent.query.obligations.enabled` + per-rule toggles.
* Unit tests per rule (SQL/rows fixtures → expected obligations), renderer tests, toggle tests.
**Out of Scope:** any prompt change (T0020.3); middleware; SQL rewriting of any kind; streaming changes.
**Manual verification:** with the local fixture DB, run the agent REPL and ask C1's question — the Langfuse trace's tool message shows the `[CREATED_ON_CAVEAT]` block; ask C3's — tool message is the canonical `ZERO_RESULTS` string; set `obligations.enabled: false`, rebuild, confirm tool output matches today's byte-for-byte shape.
**Blockers:** T0020.1.

### T0020.3: Caveat-relay contract in the system prompt (structural rule, version bump) — **blocked on T0020.2**
**Objective:** Tell the model what the `MANDATORY CAVEATS` block is and that it must be
carried into the answer — the delivery half of the contract.
**In Scope:**
* One rule block in `prompts.system_prompt` (≈2–3 lines: tool results may include mandatory
  caveats; reflect each in your answer; rephrase but never weaken or omit; when a caveat
  conflicts with a direct answer — e.g. cross-currency ranking — the caveat wins). This is
  the priority-ladder rung 2 in mechanical form.
* Bump `prompt_version` (v1 → v2-structural or per the spec's versioning), so the stage-2
  matrix is comparable and labeled.
**Out of Scope:** few-shots (re-scoped T0015.5, §6); any other wording change; glossary edits.
**Manual verification:** C1 question in the REPL → answer contains the created-on caveat substance; A1/A2 smoke — no caveat block leaks verbatim markers like `[CREATED_ON_CAVEAT]` into user-visible text.
**Blockers:** T0020.2.

### T0020.4: Scenario-matrix re-run (the ship gate) — **blocked on T0020.3 + a fresh Groq TPD window**
**Objective:** Measure the mechanism with the same protocol that produced the 0/7.
**In Scope:**
* Re-run the 29-scenario T0015.4 protocol (probes ≥3×, determinism grading) against the
  fixture DB: full C category + full regression on the 13 passing scenarios; record as
  `evals/v2_scenario_matrix.md` with `prompt_version` and mechanism config noted.
* Per-rule bisect on any C row that still fails (toggles exist for exactly this).
* Decision record: per-scenario pass/fail deltas; explicit go/no-go for stage 3
  (T0020.5) based on whether explicit caveats were dropped.
**Out of Scope:** the automated T0011.5 baseline (separate, still blocked on creds); prompt edits in reaction to results (that's the re-scoped T0015.5).
**Manual verification:** the matrix file itself is the artifact; fixture confirmation line (`COUNT(*) = 22`) present as in v1.
**Blockers:** T0020.3; Groq daily quota (the 2026-07-14 v1 run completed within a day's window — treat one full day as the budget, checkpoint mid-run as the eval memory notes).

### T0020.5 (conditional): Verify-and-append enforcement middleware — **blocked on adverse T0020.4 evidence; do not build otherwise**
**Objective:** Deterministic floor for caveat presence if (and only if) measurement shows
the model drops explicit caveats.
**In Scope (if triggered):**
* Runtime middleware (beside `TrimMessagesMiddleware`): after the final model response,
  scan this turn's tool messages for obligation markers; if the answer lacks the caveat's
  substance (token-keyed check), append the canonical string; streaming path emits the
  appendix as trailing tokens before `done`.
* Config: `agent.obligations_enforcement.enabled`.
**Out of Scope:** answer rewriting beyond appending; any detection logic (stays in the service layer).
**Manual verification (if built):** force-drop via a stub model in tests → appended caveat present; live REPL C1 with rule on → no double-caveat when the model already complied.
**Blockers:** T0020.4 outcome.

**Riders (registered, not folded in — per CLAUDE.md §1):** the executor-error logging gap
(`Known_Issues.md` § Query tooling, MED) should land before or with T0020.4 so C3-r1-class
failures are diagnosable; the empty-answer fallback (B1/C2/M-G03/M-D4/M-D8) stays its own
tracked defect — this design neither causes nor fixes it, and stage-2 grading must not
attribute its failures to the mechanism.

---

## 9. What must be measured before this ships — and the T0011.5 interaction

**The ship gate is T0020.4, and it is runnable today** — the manual matrix protocol needs
only Groq free tier + the local fixture DB (proven 2026-07-14). It is deliberately *not*
gated on the blocked T0011.5 automated baseline. Specifically:

1. **C-category deltas under the determinism protocol** (the point of the exercise):
   C1/C3 expected → PASS; C4/C5/C7 expected → PASS with the flaky runs converted;
   C2 expected → improved, judged on whether the answer stops crowning a cross-currency
   winner (its r1/r2 empty-answer failures are excluded from the mechanism's scorecard and
   tracked under the fallback defect).
2. **Regression on the 13 passing scenarios** — the mechanism adds text to tool messages;
   verify A1–A4/B2/D/E/M rows hold, and that no `[TOKEN]` markers leak into answers.
3. **Relay-fidelity rate per rule** (drop/weaken events across reruns) — this is the number
   that decides T0020.5.
4. **Token-cost delta** of the caveat block + relay rule against the 8k TPM ceiling
   (obligations add ~1–3 short lines per tool message; confirm no new 413s).

**T0011.5 interaction:** when maintainer credentials unblock it, the v1 *manual* matrix
already preserves the pre-mechanism "before" state, so nothing is lost by shipping first.
Run the automated baseline against the post-mechanism build and record the mechanism
config + `prompt_version` in the baseline metadata (the reproducibility rule of §5h). The
mechanism also strengthens the eval harness's hand: obligation presence becomes partially
assertable deterministically (token-keyed substring checks on the answer), which is
exactly the "deterministic where you can, GEval where you must" principle (§5b), and feeds
the §5f plan to sharpen the coarse Honesty GEval's `evaluation_steps` around explicit
caveat conditions.

---

## 10. Rejected alternatives — one line each

- **Prompt-only few-shots as the fix:** forbidden by the 2026-07-02 doctrine and mis-aimed — the model fails to *decide*, not to *phrase* (kept only for the §6 residue).
- **Force-widening the model's SELECT (inject salary columns / id):** the actual T0009.11 line — changes what data the query returns.
- **`WHERE is_active` injection / hide-inactive view:** already ruled out in §4.2 #3; same semantic-rewriting violation.
- **Middleware as the detection locus:** structure is already flattened to prose there; would re-parse what the service layer had as objects.
- **Post-hoc answer rewriting as primary:** guarantees presence, not correctness (can't un-crown C2); speaks for the model; kept only as the conditional stage 3.
- **Runtime LLM self-critique pass:** doubles free-tier spend and latency; nondeterministic checker for a nondeterminism problem.
- **JSON tool returns to the model:** unmeasured behavior change; relay fidelity is only evidenced on prose tool messages.
- **Model swap / temp 0.0:** rider not thesis per the brief; temp 0.0 is already the spec's recorded fallback if probes stay flaky *after* the mechanism (§5 of the spec).
- **Fine-tuning:** out of budget and out of scope.
- **Folding this into T0019:** different concern, different layer; T0019 explicitly cut all prompt/eval/agent-surface work — honesty enforcement deserves its own milestone and gate.

---

## 11. Assumptions I could not verify

1. **Relay fidelity of qwen3.6-27b for an explicit delimited caveat block.** The A4
   truncation (2/2), C3 canned-string echo (2/2 of non-error runs), and M-G44 premise
   correction (3/3) are the only measured analogs; none used a `MANDATORY CAVEATS` framing.
   T0020.4 exists to measure exactly this.
2. **What SQL the model actually generated per C scenario.** The matrix records answers,
   not SQL (the observed JSON was not examined row-by-row here, and the executor logging
   gap hides SQL errors) — so C5's "salary columns present in result" premise and C4-r3's
   "wrong SQL ran" reading are inferences from answer text, not observed queries.
3. **The cause of C3-r1's "database error" and the empty-answer fallbacks** (B1, C2 r1/r2,
   M-G03, M-D4, M-D8): unobservable with today's swallowed-error logging; assumed
   independent of this mechanism.
4. **Groq TPD headroom for a full 29-scenario ≥3× rerun in one window.** The v1 run
   completed 2026-07-14, but past sessions have exhausted the 200k TPD cap; budgeted as
   one full day with checkpointing, unverified.
5. **Clean merge of the `behavior_glossary` block onto the deploy lineage.** Diff not
   executed against every intervening prompts.yaml change; expected trivial (additive
   top-level key), unverified.
6. **Token-cost delta stays under the 8k TPM ceiling** with caveat blocks attached to
   worst-case 20-row results; arithmetic says 1–3 short lines is negligible, not measured.
7. **That `get_job_details` is actually on the C5 answer path in practice** (the matrix
   answers suggest `query_clean_jobs` handled it, but tool-call sequences weren't recorded
   in the matrix file).
8. All measured numbers cited here are from the brief's named artifacts (the v1 matrix,
   Known_Issues, the spec) — no new measurements were taken; nothing in this design has
   been executed against the app, Groq, or the live demo.
