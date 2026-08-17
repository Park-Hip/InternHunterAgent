# Vietnamese Prompt Spike

> **Last verified:** 2026-08-17 against the seeded `internhunter_eval` fixture and DeepSeek.

> **Status:** Measurement complete.

> **Eviction:** This record is archived when the selected language policy is promoted in a later
> ticket.

## Purpose

This spike measures whether the current English system prompt plus one Vietnamese-output rule or a
Vietnamese system prompt better preserves the agent's instructions.
It also checks whether the selected variant survives a Vietnamese conversation beyond six turns and
whether Vietnamese role and place words preserve canonical English SQL literals.

## Method

Run the fixture-backed production agent through `scripts/vietnamese_prompt_spike.py`.
The script injects the prompt variant only in memory and otherwise uses the normal model, tools, SQL
generator, and fixture database.
It prints a JSON row for each completed run containing the answer, generated SQL string, tools
called, answer-language purity result, and per-rule compliance result.
An optional output file is intentionally untracked evidence until a maintainer decides which dated
result to preserve.

Run A0 through A2 with three independent runs each.
Review every honesty probe by hand because Vietnamese DeepEval grading has not been calibrated.
Record whether an automated language-purity failure is a genuine English prose fragment before
comparing arms.
Choose A1 or A2 only after that review, then pass the winner explicitly to A3 and A4.

| Arm | Prompt language | Output language | Purpose |
|---|---|---|---|
| A0 | English | English | Same-day control for current behavior. |
| A1 | English plus output-language rule | Vietnamese | Tests whether one explicit rule preserves instruction following. |
| A2 | Vietnamese | Vietnamese | Tests a fully Vietnamese system prompt. |
| A3 | A1 or A2 winner | Vietnamese | Tests seven consecutive turns. |
| A4 | A1 or A2 winner plus vocabulary | Vietnamese | Tests role and location vocabulary against canonical SQL. |

## Commands

```powershell
uv run python scripts/vietnamese_prompt_spike.py --arm A0 --runs 3
uv run python scripts/vietnamese_prompt_spike.py --arm A1 --runs 3
uv run python scripts/vietnamese_prompt_spike.py --arm A2 --runs 3
uv run python scripts/vietnamese_prompt_spike.py --arm A3 --winner A1 --runs 3
uv run python scripts/vietnamese_prompt_spike.py --arm A4 --winner A1 --runs 3
```

The fixture database must be running and the selected serving provider must have budget before these
commands can produce a behavioral result.

## Findings

All five arms completed on 2026-08-17.
The run recorded 72 rows: A0 had 6 rows, A1 and A2 had 18 rows each, A3 had 21 rows, and A4 had 9
rows.
The temporary raw JSON evidence was reviewed at the end of the run and is intentionally not a
repository artifact.

| Comparison | Result |
|---|---|
| A1 versus A2 location handling | A1 used the fixture's canonical `Hanoi` literal for all three list probes. A2 used `Ha Noi` and reported no Hanoi Data Engineer postings. |
| A1 versus A2 honesty | Both arms incorrectly treated `listing_expires_on` as an application deadline in all three absent-field probes. Both otherwise stated missing salary, hedged free-text matches, and reported zero results. |
| Vietnamese answer purity | Both arms fail the literal rule because answers include English source values such as `Data Engineer`, technology names, and company names. The current automatic detector also flags those values, so no language-purity rate should be interpreted without deciding whether source values are exempt. |
| A3 multi-turn behavior | The agent completed all seven turns in all three runs. Tool following was unstable after turn six: two runs called `get_current_time` for the application-deadline question, and follow-up detail retrieval was not consistent. |
| A4 vocabulary | All nine rows called `query_clean_jobs` and used canonical English role or location literals in SQL. |

## Recommendation

Choose A1: retain the English system prompt and add one explicit Vietnamese-output rule when the
Vietnamese product policy is promoted.
Do not translate the full system prompt based on this measurement.
The policy must define whether unchanged English source values are allowed in a Vietnamese answer
before answer-language purity can be a release criterion.
Do not change `config/prompts.yaml` or `config/settings.yaml` in this spike.
