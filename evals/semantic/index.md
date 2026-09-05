# Semantic Evaluation Tier

> **Status:** Diagnostic until calibration authorizes a stated use.
> See [Operating_Manual.md](../Operating_Manual.md#authority-and-the-three-kinds-of-check) for the authority boundary.

## What this tier is for

The semantic tier evaluates **behavior over a complete conversational trajectory**, not phrasing or isolated sentences. It asks whether the assistant's final answer satisfied a behavior requirement given all prior turns — context accumulation, pronoun resolution, error recovery, and safety carry-over.

This is the only tier that reasons about meaning rather than observable facts or fixed text patterns. Because of that, it is inherently less deterministic and more expensive (judge calls, throttled to ~120 calls per full registry).

## Authority

The semantic result is **diagnostic** until a maintainer authorizes its calibrated use. The current metric must not be read as a production release gate unless that authorization is recorded in the calibration agreement report.

- During calibration, a human label wins over the judge.
- After authorization, the calibrated grader may own that stated use.
- Structural checks always win over semantic checks (D-042).

## Relationship to D-042

D-042 (structural wins) means a failed structural check overrides any favorable semantic score. The semantic judge has no authority to overwrite a structural result. This document exists alongside that invariant, not in tension with it.

## Navigation

| File | Content |
|---|---|
| [judge.md](judge.md) | How the judge is built: provider arms, throttle, wrapper, config |
| [rubric.md](rubric.md) | The SAF/HON/HLP class rubrics, failure-mode annotations, anti-fabrication directives |
| [exemplars.md](exemplars.md) | How few-shot exemplars are selected per scenario |
| [not-evaluated.md](not-evaluated.md) | What NOT_EVALUATED means in the semantic context |

## Key properties

- Uses `DeepEval.ConversationalGEval` with `MultiTurnParams.CONTENT` to evaluate the full conversation, not just the final turn.
- Provider is deliberately on **Google/gemma** (not the serving provider) to keep evaluation load off the serving account and avoid provider judging its own arm (D-017).
- Scored separately from the deterministic pass via `evals/score.py` — never inside `driver.py`.
- Results are `AVAILABLE` (judge returned a score) or `UNAVAILABLE` (provider failure). Both are rerunnable evidence.
