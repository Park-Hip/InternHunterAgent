# DeepSeek serves the agent, on measured throughput

> **Status:** Active · **Decided:** 2026-08-15 · **Amended:** 2026-10-16

## Context

Groq's free tier rationed evaluation to days; throughput, not answer quality, was the constraint.

## Decision

Both profiles serve on DeepSeek: the 29-scenario registry captured in 5m20s, 77 of 77 turns, zero
retries, about four US cents.
Steps 1 to 3 of the pre-registered rule (safety, honesty, task and tool quality) found no resolvable
difference; the decision was taken at step 4.

## Consequences

Driver turn pacing moved to 0 (it existed for Groq's per-minute ceiling).
The deployment a served profile selects must carry its key at boot (amended 2026-10-16 by #641): the serving lifespan refuses to start when it is unset or empty, naming the variable, instead of booting green and failing every question.
Each branch still validates its own key on first use, and a declared deployment no served profile selects stays optional.
The Groq branch stays selectable - two working branches keep the provider seam honest, and DeepSeek
has no free tier to fall back on.

## Evidence

[The DeepSeek arm record](../../evals/t0027_deepseek_arm.md).
The pre-swap provider evaluation is preserved on git tag docs-history-pre-redesign.
