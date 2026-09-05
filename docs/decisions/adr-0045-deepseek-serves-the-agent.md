# DeepSeek serves the agent, on measured throughput

> **Status:** Active · **Decided:** 2026-08-15

## Context

Groq's free tier rationed evaluation to days; throughput, not answer quality, was the constraint.

## Decision

Both profiles serve on DeepSeek: the 50-scenario registry captured in 5m20s, 77 of 77 turns, zero
retries, about four US cents.
Steps 1 to 3 of the pre-registered rule (safety, honesty, task and tool quality) found no resolvable
difference; the decision was taken at step 4.

## Consequences

Driver turn pacing moved to 0 (it existed for Groq's per-minute ceiling).
No provider key is required at boot; each branch validates its own.
The Groq branch stays selectable - two working branches keep the provider seam honest, and DeepSeek
has no free tier to fall back on.

## Evidence

[The DeepSeek arm record](../../evals/t0027_deepseek_arm.md).
The pre-swap provider evaluation is preserved on git tag docs-history-pre-redesign.
