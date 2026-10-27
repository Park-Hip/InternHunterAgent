# The baseline is split by role, and safety is a scored smoke set

> **Status:** Active · **Decided:** 2026-10-27
>
> **Refs:** [#761](https://github.com/Park-Hip/InternHunterAgent/issues/761), row 7 D6 of
> [#617](https://github.com/Park-Hip/InternHunterAgent/issues/617)

## Context

The 36-question baseline had 12 held-out cases, and those 12 had already been used while tuning
`sql_generation`; the run that reported 31/32 also showed how few cases were scored.
Ten held-out cases cannot distinguish 85% from 95%, and a held-out case that shaped a prompt rule is
no longer held out.
The 12 old cases cannot be made fresh by relabelling alone, but they are still useful regression
cases.
Safety existed only as the track C scenarios that ADR-0066 deleted.
`answerable` in the YAML was written as `yes`/`no`, which PyYAML resolves to booleans, so one field
held `True`, `False`, and `'partial'`.

## Decision

1. **The four baseline files have one role each.**
   `evals/datasets/baseline.yaml` is the 36-question dev corpus; all 36 are dev now.
   `paraphrases.yaml` holds dev paraphrases of a subset of those questions.
   `held_out.yaml` holds 30 fresh questions written after the dev corpus was frozen.
   `safety.yaml` holds the safety smoke set.
   The old 12 held-out cases keep their ids and reference SQL but are dev.
2. **The loader is the gate.**
   `evals/baseline_dataset.py` validates every case before a runner reads it: the split must match
   its file, the reference SQL shape must match the comparison mode and pass `validate_sql`, a
   paraphrase must keep the original's SQL and comparison, and a safety or refused-statement case
   must carry an `expect` block instead of reference SQL.
3. **`answerable` and `expect.refusal` are quoted enums.**
   The loader checks the YAML node before `safe_load`, so a bare `yes`/`no` is a refusal, not a
   silent boolean.
4. **Held-out is measured, not tuned.**
   `baseline_sql generate --split dev` keeps held-out cases out of a tuning pass.
   A held-out run is generated at a milestone and committed before its per-question failures are
   read.
   The how-to describes that workflow.
5. **Safety is scored, not prose.**
   The agent run adds `safety_refusal`.
   A case with an `expect` block passes when the expected refusal is present and no value in
   `forbid_any` appears in the answer.
   The smoke set covers a destructive request, an instruction injection, a secret-exfiltration
   request, and an injection carried by posting text.
   It is a smoke set, not a proof.
6. **The cases from #745 are in the fresh held-out file.**
   The two split breakdowns over multi-value columns, the four-turn paging conversation (first page,
   continuation, and a page past the end), and three refused statements (star, whole row, server
   identity functions).
7. **Every run binds every file.**
   The milestone manifest records a digest per case file and a combined digest.
   A re-score refuses a changed file.
   The byte-identical 2026-10-19 dataset is kept under `evals/datasets/archive/` and named by that
   committed run, so the dataset expansion does not make its evidence unreproducible.

## Why this shape

- **Split by file, not by a mutable field.** A case cannot move between the dev and held-out
  corpora by editing one word; the file it lives in decides, and the loader refuses a contradiction.
- **Paraphrases stay dev.** Their purpose is to catch wording sensitivity in a change being tuned,
  so they must be readable while tuning. Held-out cases are the only ones fenced off.
- **The old held-out cases are relabelled rather than deleted.** They are real regression cases, and
  deleting evidence of a past failure would hide it. Their historical Layer 1 scores stay
  historical.
- **The safety check is literal.** A model judge would be unstable (issue #589), so the check is a
  short refusal cue list and exact forbidden substrings. It will miss a clever refusal, and it will
  not prove safety; it will catch a change that deletes the boundary.

## Consequences

- A committed run now binds four files. Editing any one of them is a refusal on re-score.
- `evals/baseline_sql.py` and `evals/baseline_agent.py` read cases through the loader instead of
  parsing `baseline.yaml` themselves.
- `evals/milestone.py` records `dataset.files` and `dataset.files_sha256`, and verifies every entry.
- A held-out run is a milestone, so it costs one model pass per held-out question. That is the price
  of not tuning against it.
- The safety metric is reported beside B2 to B5 and never changes them.
- No schema, migration, API, or serving behavior changes.

## Verification

| Check | Method | Expected result |
| --- | --- | --- |
| The grammar rejects an unquoted yes/no | `uv run pytest tests/evals/test_baseline_dataset.py -k quoted` | Green, with a `quoted` refusal |
| The fresh held-out set carries the #745 shapes | `uv run pytest tests/evals/test_baseline_dataset.py -k "745 or safety"` | Green |
| Every reference statement executes | `uv run pytest tests/evals/test_baseline_dataset.py -k fixture` | Green against the fixture, or skipped when it is down |
| The safety metric separates refusal from leaking | `uv run pytest tests/evals/test_baseline_agent.py -k safety` | Green |
| A committed run still verifies | `uv run pytest tests/evals/test_milestone.py` | Green |
| The docs resolve | `uv run python scripts/docs_lint.py` | Exit 0 |

## Rollback

Revert this change.
The archive file and the case files revert with it, and the committed run's manifest returns to the
live `baseline.yaml` path.
No stored data or external contract is involved.
