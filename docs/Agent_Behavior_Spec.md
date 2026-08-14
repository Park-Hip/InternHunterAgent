# Agent Behavior Spec — InternHunterAgent (Resumi)
> **Last verified:** 2026-08-14

> **Status**
> - Frozen: 2026-07-11 under T0015.2. The freeze protects the requirements under test, the probe
>   protocol, and the settled decisions — not the per-scenario inputs and expected outputs that
>   §4a-4c duplicated from `evals/scenarios_v1.yaml`, which T0028.2 cut on 2026-08-14.
> - `behavior_glossary` is not landed in `config/prompts.yaml`.
> - Recover the 18 canonical strings from `archive/t0015.2-behavior-glossary`.

The [v1 scenario matrix](../evals/archive/v1_scenario_matrix.md) preserves the measured behavior
record that informs this specification.

> **Eviction:** A behavior requirement leaves when an approved replacement is measured against the
> evaluation baseline and adopted into the prompt contract.

---

## 1. Priority ladder (decision #6 — the explicit tie-breaker)

When two directives collide, the higher rung wins, and the agent briefly says why:

1. **Safety / refusal** — destructive/write requests (G25), prompt injection & jailbreak (G26),
   secret/config disclosure (G27), discriminatory filters (G29).
2. **Honesty / grounding** — never fabricate; never rank across currencies; preserve caveats; answer
   only from tool results (G05, G07, G08, G09, G10, G17).
3. **Helpfulness / completeness** — answer every part of a compound ask; offer the closest available
   thing (G03, G28, G39).
4. **Conciseness / style** — the Resumi voice, length calibration (G35, G37).

This ladder is applied in the system prompt in T0015.5; here it is the reference order for reading
every "Expected behavior" cell below.

---

## 2. Settled decisions (from question-bank §12 — frozen 2026-07-11)

| # | Decision | Resolution | Canonical string / lever |
|---|---|---|---|
| 1 | E1 "jobs?" vague input | Ask **one** narrow clarifying question | `E1-CLARIFY` |
| 2 | "Senior roles" (title text) | Title matches **with** hedge; `job_level` is the grounded field | `SENIOR-TITLE-HEDGE` |
| 3 | Compound destructive + read | Refuse the mutation, answer the read separately | `DESTRUCTIVE-REFUSAL` + separate read |
| 4 | "Show me the SQL" | Plain-language description; never raw SQL | `SQL-DESCRIBE-ONLY` |
| 5 | Canonical phrasings home | Final; machine SoT in `prompts.yaml` glossary, human SoT here | G47 §10 |
| 6 | Priority ladder | Safety > Honesty > Helpfulness > Style (SP) | §1 above |
| 7 | Location synonyms | SG maps Saigon → Ho Chi Minh City before `ILIKE` | SG rule (T0015.5) |
| 8 | Tech abstractions | `tech_stack` primary; hedged `description`/`title` fallback for abstractions; expand abbreviations (`%machine learning%` not `%ML%`) | `FREE-TEXT-HEDGE` + SG rule |
| 9 | Role→title fallback | Non-canonical term → `title`/`description` `ILIKE`, note `role='Other'` | SG rule (T0015.5) |
| 10 | Persona internship-bias | SP line 3 → "AI/Data job and internship postings" | SP edit (T0015.5) |

Items #7/#9/#10 and the ladder (#6) are **prompt edits applied in T0015.5**; T0015.2 only freezes
the target.

---

## 3. Canonical phrasings (G47 — FINAL)

The verbatim strings live in [`research/archive/agent-behavior-question-bank.md`
§10](../research/archive/agent-behavior-question-bank.md) and the `behavior_glossary` block of
`config/prompts.yaml`. Phrase IDs referenced below:
`NEGOTIABLE-SALARY`, `ABSENT-FIELD`, `FRESHNESS-REFUSAL`, `CREATED-ON-CAVEAT`, `FREE-TEXT-HEDGE`,
`SENIOR-TITLE-HEDGE`, `CROSS-CURRENCY`, `TRUNCATION`, `ZERO-RESULTS`, `E1-CLARIFY`,
`OFF-TOPIC-REDIRECT`, `DESTRUCTIVE-REFUSAL`, `INJECTION-REFUSAL`, `SECRET-REFUSAL`,
`SQL-DESCRIBE-ONLY`, `FUTURE-FEATURE`, `GENERAL-KNOWLEDGE-DECLINE`, `DISCRIMINATORY-DECLINE`.

---

## 4. Frozen scenario matrix

Fixture facts (post-`RESTART IDENTITY`, rows `#1`–`#22` in `evals/fixtures/seed_eval_db.sql`):
AI Engineer `#1–5`, Data Scientist `#6–9`, Data Engineer `#10–13`, ML Engineer `#14–17`,
Data Analyst `#18–21`, Other/BI `#22`. Python in 12 rows; Python∩Hanoi = 7. Top raw number = `#7`
40,000,000 VND (cross-currency trap); top USD = `#1` 5,000. Negotiable/NULL salary =
`#4`,`#9`,`#19`.
"remote" in free text of `#3`,`#11` only. Java = `#11`,`#17`. Internships =
`#2`,`#4`,`#9`,`#18`,`#20`.
Data Engineer `job_level` = 3× Experienced (non-manager) + 1× Manager. Newest `created_on` = the
Home Credit Data Analyst row. No COBOL / Rust / Google rows.

**Legend:** `Probe?` = honesty/safety-critical → must be correct on **all** reruns (G45, ≥3×).
Every scenario is carried by [`evals/scenarios_v1.yaml`](../evals/scenarios_v1.yaml), which owns
each scenario's fixture rows, input (or turns), and expected behavior; the tables below name the
scenario and the requirement it tests, and do not restate that data.

### 4a. Registry scenarios

| ID | Requirements | Probe? |
|---|---|---|
| HLP-COUNT-1 | G01,G14,G30,G33 | no |
| HLP-LIST-1 | G14,G33,G35 | no |
| HLP-TECH-STACK-1 | G13,G33,G35 | no |
| HLP-TRUNCATION-1 | G08,G34,G36 | no |
| HLP-CONTEXT-1 | G20,G21,G12 | no |
| HLP-REFERENT-1 | G20,G21,G16 | no |
| HON-CREATED-ON-1 | G17,G07 | **yes** |
| HON-CURRENCY-1 | G09,G04 | **yes** |
| HON-ZERO-RESULTS-1 | G06,G44 | **yes** |
| HON-FREE-TEXT-1 | G05,G12,G08 | **yes** |
| HON-NEGOTIABLE-SALARY-1 | G05,G07 | **yes** |
| HLP-SENIORITY-1 | G18,G14 | no |
| HON-ABSENT-FIELD-1 | G05,G07 | **yes** |
| SAF-DESTRUCTIVE-REFUSAL-1 | G25 | **yes** |
| SAF-OFF-TOPIC-REDIRECT-1 | G24 | **yes** |
| SAF-INJECTION-REFUSAL-1 | G26,G27 | **yes** |
| HLP-CLARIFY-1 | G02,G40 | no |
| HLP-REFERENT-2 | G20,G02 | no |

### 4b. Coverage-gap scenarios

The manual pass needs only Groq + the fixture DB, so these high-value scenarios remain in the
registry. **Decision (T0015.2): include all five in v1.**

| ID | Requirements | Probe? |
|---|---|---|
| HLP-COMPOUND-1 | G03 | no |
| HON-GENERAL-KNOWLEDGE-1 | G10 | **yes** |
| SAF-INJECTION-RESILIENCE-1 | G26 | **yes** |
| SAF-DISCRIMINATORY-DECLINE-1 | G29 | **yes** |
| HON-PREMISE-CORRECTION-1 | G44 | **yes** |

### 4c. Decision-specific probe scenarios (verify the settled §12 picks)

| ID | Decision | Probe? |
|---|---|---|
| HLP-SENIOR-TITLE-1 | #2 senior title | no |
| HON-SQL-DESCRIBE-1 | #4 show SQL | **yes** |
| HLP-LOCATION-SYNONYM-1 | #7 synonym | no |
| HLP-ABSTRACTION-1 | #8 abstraction | no |
| HLP-ROLE-FALLBACK-1 | #9 role fallback | no |
| SAF-DESTRUCTIVE-REFUSAL-2 | #3 compound refuse | **yes** |

---

## 5. Determinism protocol (G45)

Every row marked **Probe? = yes** is safety- or honesty-critical and must be **correct on all
reruns** — run each **≥3×** in T0015.4. A probe that is right 2/3 is a **FAIL**, not a pass
(T0009.8 saw freshness fabricate 1-in-3). Cosmetic variation (wording, list order) on non-probe
rows is acceptable. If probes stay flaky after the T0015.5 few-shots, record the evidence and the
`temperature: 0.0` recommendation as a decision (do not flip it silently — plan §3a).

---

## 6. Out of scope (per T0015.2)

- Running the scenarios (T0015.4) or editing prompt content — few-shots, SP/SG rule edits for
  decisions #6/#7/#9/#10 (T0015.5).
- Adding any of the §4b gap scenarios to `golden_dataset.json` (harness-track follow-up).
- Any schema/DDL/API change (frozen at T0013.5) and the automated judge harness (separate track).

## Provenance

> **Provenance (restored 2026-07-22).** Recovered from `archive/t0015.4-scenario-matrix`
> (`eba3e1f`) during a branch-cleanup pass. It had been stranded on an unmerged branch since
> T0015.2 — `docs/Tickets.md` marks that ticket *(done)*, but neither this file nor the
> `behavior_glossary` it names had ever reached the mainline.
>
> **⚠️ The "machine source of truth" referenced below is frozen but NOT LANDED.**
> `config/prompts.yaml` on this branch has **no `behavior_glossary` block** — none of the
> canonical phrase IDs appear in it, and the live prompts express a subset of these behaviors
> as **prose instruction** instead (e.g. "if a user asks about salary and the value is missing
> or negotiable, say so plainly"). The glossary itself is **complete and recoverable** — 18
> strings, committed 2026-07-11 in `62f2089`, preserved at tag
> **`archive/t0015.2-behavior-glossary`**:
>
> ```bash
> git show archive/t0015.2-behavior-glossary:config/prompts.yaml
> ```
>
> So treat the phrase IDs below as **specified and written, but not yet what the system
> emits**. Landing them is owned work, tracked in `docs/Known_Issues.md` → Repo state &
> version control. Note the ID spelling differs: this doc hyphenates (`NEGOTIABLE-SALARY`),
> the config uses underscores (`NEGOTIABLE_SALARY`).
>
> **Status:** Spec of record — **frozen 2026-07-11 (T0015.2)**. This is the human-readable
> single source of truth for *how Resumi should behave*, scenario by scenario, against the frozen
> 16-column v1 schema ([`Schema_Contract.md`](Schema_Contract.md)) and the `internhunter_eval`
> fixture. It is the target the T0015.4 manual matrix measures against and the T0015.5 few-shots
> optimize toward.
>
> **Companion artifacts:**
> - Research/rationale + the full behavioral question catalog:
> [`research/archive/agent-behavior-question-bank.md`](../research/archive/agent-behavior-question-bank.md)
> (groups
> `G01`–`G47`; settled decisions in §12; final glossary in §10).
> - Machine source of truth for the canonical strings: the `behavior_glossary` block in
> [`config/prompts.yaml`](../config/prompts.yaml).
> - This doc does **not** replace `skills/generate-ticket-prompt/SKILL.md`, the separate
> ticket-template artifact.
