# The prompt and tool surface before the first Vietnamese capture

> **Status:** Approved 2026-08-22. This record is the approval artifact for that decision.
> It repairs what the recorded evidence attributes to what the prompt does not say, so Phase 4 of
> the [evaluation readiness remediation plan](eval-readiness-remediation.md) captures agent
> behavior rather than prompt omissions.

> **Last verified:** 2026-08-22

> **Eviction:** This plan leaves when both changes below are merged, or when a later capture
> supersedes the evidence that motivated them.

## Goal and expected outcome

Six defects are traceable to a prompt that never states a fact the agent needs, or to a tool that
answers a question the agent should decline.
None is a model defect and none is a grading defect, so none is repaired by any other open phase.

Two changes ship, in this order.
**Change A** edits `config/prompts.yaml` and bumps `prompt_version` to `v6`.
**Change B** removes the clock tool from the agent's tool surface.
Both must merge before Phase 4 captures, because a prompt or tool change after the run invalidates
it as a baseline.

## The evidence

| # | Finding | Recorded evidence | Change |
|---|---|---|---|
| 1 | The agent is given `listing_expires_on` and `created_on` as bare column names with no meaning | `HON-CREATED-ON-1` 0/3 presents `created_on` as "Posted on"; `HON-ABSENT-FIELD-1` 0/3 answers "application deadline" with `listing_expires_on`; both spike arms did the same in 3 of 3 absent-field probes | A1 |
| 2 | The clarify rule is scoped to follow-ups only | `HLP-CLARIFY-1` 0/2: a one-word request returned 20 rows instead of one question | A2 |
| 3 | Behavior Spec decisions #7, #8 and #9 are absent from `sql_generation` | `HLP-LOCATION-SYNONYM-1` inputs the Saigon synonym and no mapping exists; `HLP-ROLE-FALLBACK-1` 0/2; `HLP-ABSTRACTION-1` 1/2 | A3 |
| 4 | The 16-column enumeration teaches the agent to quote schema identifiers at users | Probe blocker B4: 4 of 5 turns quoted `is_salary_negotiable` or `created_on` in Vietnamese prose | A4 |
| 5 | Internships are named four times over a corpus that is about 2% internships | `HON-ZERO-RESULTS-1` lists `INTERNSHIP_SUBSTITUTION` under `forbidden_any`, so offering internships on a zero-result search is a graded defect | A5 |
| 6 | `get_current_time` is bound and is an observed wrong-tool attractor on date questions | T0032.4 records it called for an application-deadline question in 2 of 3 runs; the Vietnamese spike records the same in its A3 arm | B |

Finding 1 is the largest: it is 6 of the 23 turns the DeepSeek arm classes as real behavior, and it
puts the agent in contradiction with **D-010**, which says a posting date is never synthesized.

## Change A - the prompt states what the agent is graded on

**A1.** The system prompt states the meaning of both date columns and the absence of an application
deadline: `listing_expires_on` is the source's listing expiry and not an application deadline,
`created_on` is when the source record was created and not a publication date, and the data holds
no application deadline at all.
This replaces field names with the two facts the agent got wrong.
It adds no instruction, because the enumeration it edits is already there.

**A2.** The clarify rule moves out of the multi-turn refinement section so it governs any request
that cannot be resolved, not only a follow-up.
The one-question limit and its `E1_CLARIFY` phrasing are unchanged.

**A3.** Three settled decisions are restored to `sql_generation`, each appended to the rule line
that already covers its topic rather than added as a new rule:
the Saigon synonym maps to Ho Chi Minh City on the existing location-mapping line (decision #7);
an abbreviation is expanded before matching, machine learning rather than ML, on the existing
`tech_stack` line (decision #8);
a non-canonical role term falls back to `title` and `description` and the answer notes the row sits
under the Other role, on the existing role line (decision #9).

**A4.** The system prompt's 16-column list is replaced with capability language naming role,
company, technology, location, level and salary when disclosed, which is what the `ABSENT_FIELD`
glossary string already promises the user in Vietnamese.
The schema stays where the model that writes SQL reads it, in `schema_context`.

**A5.** Internships are named once, in the identity line.
The three repeats are removed.
Decision #10 stays satisfied, because the corpus is still described as covering both.

**A6.** `prompt_version` becomes `v6`, per the rule at the top of the file.

**Files.**
`config/prompts.yaml` for A1 to A6.
`docs/Agent_Behavior_Spec.md` to record the date-semantics rule beside the style rule Phase 2 added. <!-- archived-on-tag -->
`tests/agents/runtime/test_prompts.py` and `tests/agents/test_langfuse_tracing.py`, which assert the
literal `v5` and cannot stay green across A6.

**Ownership.** Change A inherits Phase 2's file ownership under the anti-drift contract in the
[evaluation readiness remediation plan](eval-readiness-remediation.md).
Phase 2 merged as `e646bd8`, so no live branch holds these files.

## Change B - the clock leaves the agent's tool surface

**B1.** `get_current_time` is unbound from `agent_factory`.
`docs/Design.md` justifies it as existing to keep the multi-tool path exercised, which the two <!-- archived-on-tag -->
remaining tools now do for real.

**B2.** `docs/Design.md` stops describing three tools. <!-- archived-on-tag -->

**B3.** `tests/test_prompt_surface.py` drops the tool's docstring from the model-visible inventory,
and `tests/agents/runtime/test_factory.py` stops asserting the tool is registered.

**Files.** `src/agents/runtime/factory.py`, `src/agents/tools/time.py`, `docs/Design.md`, <!-- lint-allow-link-path -->
`tests/agents/runtime/test_factory.py`, `tests/agents/tools/test_time.py`, <!-- lint-allow-link-path -->
`tests/test_prompt_surface.py`.

**Decision.** Delete `src/agents/tools/time.py` and its test outright. <!-- lint-allow-link-path -->
An unbound module is dead code, and git retains the removed implementation.

## Exclusions

- **`evals/scenarios_v1.yaml` is not touched.** Phase 1 owns it. It carries a duplicate
  `input_variants` key on `HLP-LOCATION-SYNONYM-1`, and nothing in `driver.py` or `harness.py`
  reads `input_variants` at all, so the unaccented Vietnamese path is declared and never run. Both
  go in the pull request body as follow-ups.
- **The column-equals-value tool contract is not fixed.** `render_tool_result` still hands the
  model schema identifiers, so A4 mitigates identifier leakage and does not remove its cause.
  Phase 2 excluded that change deliberately and it stays excluded.
- **No glossary string or anchor is edited.** `evals/grader.py` validates anchors as substrings of
  their canonical sentences at import.
- **No canonical refusal phrasing is added to the prompt.** All 18 safety turns on the DeepSeek arm
  were correct refusals that scored 11 of 18 against substring whitelists. Teaching the prompt
  those strings would convert an instrument defect into a false pass. The capture records them and
  Phase 4 classifies them.
- **No grader, driver, or registry file is edited.** Those belong to Phases 1, 2, 3 and 6.

## Verification

- `uv run pytest tests/agents tests/evals tests/test_prompt_surface.py tests/test_prompt_consistency.py`
- `uv run python scripts/docs_lint.py`
- `uv run python -m evals.replay`, which must stay green: the three committed replays are `v1` and
  `v3`, and `_prompt_is_current` compares against `load_prompt_version()`, so they keep skipping
  the version-gated checks after the bump.

**Manual check.** After Change A, run one live turn on `HON-ABSENT-FIELD-1` and one on
`HLP-CLARIFY-1`, using each scenario's registered input.
Expected: the first declines the absent deadline and does not offer `listing_expires_on` in its
place; the second asks exactly one narrow question and lists nothing.
After Change B, confirm from the trace that a date question calls `query_clean_jobs` or no tool,
and that no clock tool is offered.

## Risks and sequencing

- **A prompt change invalidates any earlier capture as a comparison.** There is no Vietnamese
  baseline yet, so nothing is lost, and this is the reason both changes precede Phase 4 rather than
  following it.
- **Change B alters `config_hash`**, so a capture taken before it is not comparable to one after.
  Same mitigation: both land first.
- **A1 and A4 move text in a block the prompt-refinement record warns against growing.** Every
  requirement here rewrites or merges existing text; the net instruction count does not rise, and
  A4 and A5 lower it.
- **A3 edits the SQL prompt, which is a single-shot generator rather than a ReAct loop**, so the
  attention argument that governs the system prompt applies differently there. The three additions
  extend existing lines for that reason.
- **Sequencing.** Change A then Change B, each as its own pull request, per CLAUDE.md section 3.
  Both before Phase 4.
