# DeepSeek as an Agent Provider - Feasibility Research

> **Last verified:** 2026-08-14

> **Status:** Pre-design evidence for a possible `agent.provider` swap. Nothing here is
> implemented. It feeds a future provider ticket and a Decision Log entry that would sit beside
> [D-017](../docs/Decision_Log.md).

> **Eviction:** This record leaves when the provider decision is taken and harvested into the
> Decision Log, or when DeepSeek is ruled out.

## Bottom line

DeepSeek is a drop-in-shaped swap that is **not** actually drop-in, because of one behavior:
its current models are in thinking mode by default, and thinking mode changes the tool-calling
contract that this agent depends on.

| Question | Answer |
|---|---|
| Can it replace Groq for the ReAct agent? | Yes, but only with thinking mode explicitly disabled |
| Effort | One new provider branch in `provider.py`, one config block, one env var, one spike |
| Money | Roughly **$0.15 per full 87-turn eval matrix** on `deepseek-v4-flash` (estimate) |
| Real payoff | Kills the 75s turn pacing and the ~3-day Groq TPD window for eval runs |
| Main risk | Tool calling in thinking mode is broken for LangChain today (see [§3](#3-the-three-landmines)) |

Recommended shape: add a `deepseek` branch to `AgentProvider`, send
`extra_body={"thinking": {"type": "disabled"}}`, and prove it with a throwaway spike
([§6](#6-the-spike-to-run-before-committing)) before writing any ticket.

## 1. What the API is today

DeepSeek speaks the OpenAI wire format at `https://api.deepseek.com`, so the only structural
change is the client class and the key.

| Fact | Value |
|---|---|
| Models | `deepseek-v4-flash`, `deepseek-v4-pro` |
| Legacy aliases | `deepseek-chat` / `deepseek-reasoner` deprecated 2026-07-24, do not target them |
| Context | 1M context, up to 384K output |
| `deepseek-v4-flash` | $0.14 / 1M input (cache miss), $0.0028 (cache hit), $0.28 / 1M output |
| `deepseek-v4-pro` | $0.435 / 1M input (cache miss), $0.003625 (cache hit), $0.87 / 1M output |
| Off-peak | From 2026-08-16, off-peak UTC windows bill at half the peak rate |
| Limits | No published RPM/TPM. Account concurrency: 2,500 (flash) / 500 (pro), 429 above it |
| Free tier | None. This is a paid provider, unlike the current Groq and Gemini free tiers |

The absence of a TPM ceiling is the whole reason to look at this.
The recorded Groq constraint (8K TPM / 200K TPD) is what forces
`eval.driver.turn_pacing_seconds: 75` and spreads a full matrix over about three daily windows.

## 2. What this repo would have to change

The provider is already isolated behind one class, so the blast radius is small.

| File | Change |
|---|---|
| `src/agents/runtime/provider.py` | Add a `deepseek` branch; widen the return type to `BaseChatModel` |
| `config/settings.yaml` | `agent.provider: deepseek` plus per-profile DeepSeek keys |
| `src/core/config.py` | Add `DEEPSEEK_API_KEY` (optional, or required in place of `GROQ_API_KEY`) |
| `.env.example`, `render.yaml` | Publish the new key |
| `pyproject.toml` | Add `langchain-deepseek>=1.1.0` (pulls `langchain-openai>=1.1.0`) |
| `tests/agents/runtime/test_provider.py` | Mirror the existing Groq assertions for the new branch |

One sharp edge in that table: `GROQ_API_KEY` is `Field(..., min_length=1)` in
[`src/core/config.py`](../src/core/config.py), so it is required at startup no matter which
provider is selected. Add `DEEPSEEK_API_KEY` as optional, the way `GOOGLE_API_KEY` already is,
and validate it inside its own branch. Whether Groq's key stops being required is a question for
the day the default flips, and it has a Render consequence: `render.yaml` declares
`GROQ_API_KEY` and deliberately omits `GOOGLE_API_KEY`.

Two things deliberately do **not** change.
`src/core/errors.py` classifies provider pressure by HTTP status and message text, not by
provider, so DeepSeek 429s already map to `ProviderBusyError` unchanged.
Langfuse tracing hangs off the LangChain callback handler in `src/agents/tracing/langfuse.py`,
which is model-agnostic.

The Groq-only config keys are the sharp edge in `config/settings.yaml`.
`reasoning_format` and `reasoning_effort` are `ChatGroq` arguments, and `agent.react` /
`agent.sql_generation` currently hand them to the constructor unconditionally.
A DeepSeek branch must read its own keys rather than reuse those two.

## 3. The three landmines

These are the reason this is research and not a one-line config edit.

**Thinking mode is on by default, and it silently eats sampling parameters.**
`temperature`, `top_p`, `presence_penalty`, and `frequency_penalty` are accepted but have no
effect while thinking is on.
The `sql_generation` profile runs at `temperature: 0.0` precisely for determinism, so a naive
swap would quietly lose that without raising an error.

**Thinking mode rejects forced tool choice.**
V4 models return HTTP 400 `Thinking mode does not support this tool_choice` for
`tool_choice="required"` or a named function, which is what LangChain's
`with_structured_output()` and any forced-tool path emit.
Only `auto` or omitting the field works.

**Thinking mode requires `reasoning_content` to be echoed back, and LangChain reportedly does not
do it.** Once a request carries `tools`, every later turn must resend the assistant's
`reasoning_content` or the API answers 400.
`ChatDeepSeek._get_request_payload()` was reported to drop it, breaking multi-turn agent loops -
exactly the shape of `agent_factory()` with its three tools - and the upstream report
(`langchain-ai/langchain` #37174) was **closed as not planned**.
**The 2026-08-14 spike did not reproduce this** on `langchain-deepseek` 1.1.0 with
`deepseek-v4-flash`: a tool loop whose first leg carried 75 chars of `reasoning_content`
completed its second leg with no 400. See §6.

All three collapse into one mitigation: disable thinking.
The documented control in the OpenAI-compatible format is the request body field
`{"thinking": {"type": "disabled"}}`, passed through LangChain's `extra_body`.
With thinking off, `temperature` applies again, `tool_choice` is accepted again, and no
`reasoning_content` is produced to lose.

## 4. Implementation options

| Option | Shape | Verdict |
|---|---|---|
| **A. `ChatDeepSeek` + thinking disabled** | New provider branch, `extra_body={"thinking": {"type": "disabled"}}` | **Recommended** |
| B. `ChatOpenAI` pointed at `api.deepseek.com` | No new dependency, same `extra_body` trick | Works, but gives up whatever DeepSeek-specific handling the integration adds |
| C. Keep the agent on Groq, try DeepSeek as the eval judge only | Touches `evals/judge.py`, which already has a two-provider branch | Lowest risk, but does not buy the throughput that motivates the swap |

Option A sketch, matching the existing `build_model()` structure:

```python
from langchain_deepseek import ChatDeepSeek

model_kwargs = {
    "model": model_name,
    "temperature": profile_cfg.get("temperature", 0.2),
    "max_tokens": profile_cfg.get("max_tokens", 1024),
    "timeout": profile_cfg.get("timeout", 30),
    "max_retries": max_retries,
    "streaming": profile_cfg.get("streaming", False),
    "api_key": settings.DEEPSEEK_API_KEY,
    "extra_body": {"thinking": {"type": "disabled"}},
}
return ChatDeepSeek(**model_kwargs)
```

Keep the thinking switch in `config/settings.yaml` rather than hardcoded, so a future ticket can
turn thinking on for the `react` profile once the upstream tool-calling gap closes.

## 5. Cost

Estimated from the recorded ~9.2k tokens per agent turn across its routing, SQL, and synthesis
calls, on `deepseek-v4-flash` at cache-miss rates.

| Workload | Turns | Tokens (est.) | Cost (est.) |
|---|---|---|---|
| One agent turn | 1 | ~9.2K | ~$0.0015 |
| Full v1 matrix (29 scenarios x 3) | 87 | ~800K | **~$0.15** |
| A busy demo day (50 sessions x 3 turns) | 150 | ~1.4M | ~$0.25 |

**Measured 2026-08-14 (T0027.3), and the estimates above are high.** A full 29-scenario capture ran
77 turns for 264,290 input and 23,014 output tokens: ~3.7K tokens per turn, not ~9.2K, and about
**$0.04** rather than $0.15. The gap is not caching. The 9.2K figure counts what Groq *reserves* to
admit a call, which is inputs plus each call's `max_tokens`, and reserved tokens are not spent
tokens. Read 9.2K as an admission cost on a metered tier and 3.7K as the real consumption.

Prompt caching cuts the input side by 50x on repeat system prompts and schema context, which is
most of the payload here, so sustained runs should land well under these figures.
This sits inside the recorded $10/month ceiling with a very large margin.
The judge stays on the Gemini free tier and is unaffected.

## 6. The spike to run before committing

A throwaway script under `scripts/` (excluded from lint), roughly 15 minutes, five checks.
Do not promote any configuration until all five pass.

1. **Model reachable.** One `deepseek-v4-flash` call, non-streaming, returns text.
2. **`extra_body` actually reaches the wire.** Same call with
   `{"thinking": {"type": "disabled"}}` returns no `reasoning_content` in
   `additional_kwargs`.
3. **Multi-turn tool loop.** A two-tool agent that calls a tool and then answers, run twice, with
   no 400 on the second leg. This is the check that decides the whole swap.
4. **Determinism.** `temperature=0.0` twice on the same SQL-generation prompt yields identical
   SQL.
5. **Streaming.** Token-level streaming with thinking off emits no reasoning chunks that the
   demo UI would have to filter.

Record the results in this document before writing a ticket.

### Run of 2026-08-14: all five pass, the gate included

`scripts/deepseek_provider_spike.py` against `deepseek-v4-flash`, `langchain-deepseek` 1.1.0.
Provider-reported: **7 calls, 1681 prompt + 206 completion tokens, $0.0003**.

| Check | Status | Observed |
|---|---|---|
| 1. Model reachable | PASS | answered `ready`, 90 in / 10 out |
| 2. Thinking switch reaches the wire | PASS | thinking on returned 53 chars of `reasoning_content`; with `{"thinking": {"type": "disabled"}}`, 0 |
| 3. Multi-turn tool loop (gate) | PASS | both legs completed, tool called, correct answer |
| 4. Determinism at `temperature: 0.0` | PASS | two runs returned byte-identical SQL |
| 5. Streaming without reasoning chunks | PASS | 9 chunks, 6 carrying text, 0 carrying reasoning |

An earlier run on the same day returned `402 Insufficient Balance` on the first call and was
recorded as **BLOCKED**, not failed: the key authenticated, so nothing about the model had been
exercised. The account was funded and the run above is the result. The spike still exits `3` on a
billing refusal, distinct from `1` for a real check failure, so the two can never be confused.

**Check 2's control is what makes it evidence.** Absence of `reasoning_content` proves nothing on
its own, so the check calls twice: the default produced reasoning, the disabled call produced
none. The switch is what removed it.

**Check 3 revises §3's third landmine.** The loop was also run with thinking left **on**, where
leg 1 carried **75 chars of `reasoning_content`** - and the second leg still completed, with no
400. The documented `reasoning_content` passback failure did not reproduce on this stack, so
`langchain-deepseek` 1.1.0 either serializes the field now or `deepseek-v4-flash` no longer
demands it. One run is not a guarantee, but the defect that looked like a blocker is not one here.

**Still untested:** `tool_choice="required"`, because nothing in this repo's agent path forces a
tool. If T0027.2 or a later ticket introduces `with_structured_output()` or a forced tool, §3's
second landmine has to be probed before relying on it.

Thinking stays disabled anyway, on the two grounds this run did confirm: thinking mode ignores
`temperature`, which check 4's determinism depends on, and reasoning tokens are billed as output.

## 7. The procedure this repo already has for adding a provider

This is not the first second provider. **T0015.6 wired Google Gemini as a second arm beside
Groq**, and the work was deferred rather than merged when the live comparison could not run.
It survives on the tag `archive/t0015.6-provider-ab`, and it is the procedure M27 should follow:

```bash
git show archive/t0015.6-provider-ab:src/agents/runtime/provider.py
git show archive/t0015.6-provider-ab:research/provider-ab-plan.md
```

**The code shape it settled on.** `build_model()` read `agent.<profile>.provider` with the
top-level `agent.provider` as its fallback, so one profile could move providers while the other
stayed put. Shared arguments lived in a single `common_kwargs` dict, each provider branch added
only its own native keys, the second provider's package was imported **inside** its branch, and a
missing key raised an error naming the profile. That shape is what `provider.py` should return to.

**The discipline the plan pinned**, from `provider-ab-plan.md` §2, §7, and §10:

| Rule | Why it exists | M27 consequence |
|---|---|---|
| Change exactly one variable | Anything else that differs invalidates the comparison | Scenarios, fixture, prompts, temperature, `max_tokens`, timeout, tools, graph, judge, and replicate counts stay pinned across arms |
| Each arm runs with its native reasoning knob **off** | Neither arm gets a hidden reasoning advantage | Groq keeps `reasoning_effort: none`; DeepSeek runs `{"thinking": {"type": "disabled"}}`, which §3 shows it needs anyway |
| The judge may not come from a contestant's family | Self-preference bias can flip the winner | The Gemini judge is neutral here: neither arm is Google, so the bias that blocked T0015.6 does not apply |
| Never let an arm hit quota mid-run | A truncated arm looks worse for reasons unrelated to quality | Run arms sequentially against the same fixture in one session, using the driver's checkpoint and resume |
| Tokens and latency from provider-reported usage only | Estimates are not measurements | Read `usage_metadata`; label free-tier latency indicative, never an SLA |
| Pre-register the decision rule before the numbers exist | Stops the winner being rationalized after the fact | Safety probes 100% first, then honesty, then task and tool quality, then operational tie-break |
| Never invent an unobserved result | `provider_ab_results.md` recorded its blocker instead of a number | A blocked arm is reported as blocked |

## 8. What M25 made obsolete, and what still binds

The archived plan proposed building an A/B harness (its T0015.6a) because the runner then drove
the **HTTP endpoint**, which read provider config at server startup. M25 replaced that: the
driver runs the agent in-process, emits a manifest, checkpoints, resumes, and grades
deterministically. Its gaps G1 through G6 are closed, so **M27 must not rebuild that harness**.
Switching arms is a `config/settings.yaml` edit plus a driver run, and the manifest's
`config_hash` records exactly which configuration produced the artifact.

Four things in the current instrument still need attention, and they are ticket scope rather than
open questions:

1. **The manifest records models, not providers.** `build_manifest()` in
   [`evals/driver.py`](../evals/driver.py) writes `models.react` and `models.sql_generation` with
   no provider field, and its `sampling` block captures only the Groq-native `reasoning_effort`
   and `reasoning_format`. A DeepSeek run would therefore not record its provider or whether
   thinking was disabled - the single most behavior-determining knob in this swap.
2. **`_assert_comparable()` will refuse to diff the two arms, and that is correct.** It compares
   `config_hash`, which necessarily differs once the provider changes. Do not relax it to make
   arms diff; compare graded outcomes per scenario and state the intended configuration delta.
   The guard exists to stop exactly the cross-configuration comparison an A/B invites.
3. **The driver owns retry accounting.** It sets `EVAL_DRIVER_DISABLE_PROVIDER_RETRIES=1`, which
   only the Groq branch reads today. A DeepSeek branch that ignores it retries underneath the
   driver and corrupts the retry ledger.
4. **Quota classification is Groq-flavored.** `_is_quota_error()` matches `tpm` and
   `tokens per minute` alongside `429`; DeepSeek's 429 means concurrency, not tokens per minute,
   and its backoff ladder was tuned to Groq's 14-17 second hints.

## 9. Open questions

- Does `langchain-deepseek` 1.1.0 forward `extra_body` unmodified? Inherited from
  `BaseChatOpenAI`, so expected, but check 2 above is the proof.
- Does disabling thinking measurably change SQL-generation quality against the eval matrix? A
  provider swap invalidates the recorded baseline and needs a rerun to compare honestly.
- Should Groq stay as a configured fallback provider, or be removed once DeepSeek is proven?
  Keeping both branches keeps `provider.py` honest about being provider-agnostic.
- Off-peak billing from 2026-08-16 halves the rate. If eval runs are batched into that window the
  cost estimates above roughly halve again.

## Sources

- [DeepSeek pricing](https://api-docs.deepseek.com/quick_start/pricing)
- [DeepSeek rate limits](https://api-docs.deepseek.com/quick_start/rate_limit/)
- [DeepSeek thinking mode](https://api-docs.deepseek.com/guides/thinking_mode/)
- [DeepSeek tool calls](https://api-docs.deepseek.com/guides/tool_calls)
- [ChatDeepSeek integration](https://docs.langchain.com/oss/python/integrations/chat/deepseek)
- [langchain #37174](https://github.com/langchain-ai/langchain/issues/37174) -
  `reasoning_content` passback, closed as not planned
- [DeepSeek-V3 #1376](https://github.com/deepseek-ai/DeepSeek-V3/issues/1376) -
  `tool_choice` rejected in thinking mode
