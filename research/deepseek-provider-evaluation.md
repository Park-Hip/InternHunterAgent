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

**Thinking mode requires `reasoning_content` to be echoed back, and LangChain does not do it.**
Once a request carries `tools`, every later turn must resend the assistant's `reasoning_content`
or the API answers 400.
`ChatDeepSeek._get_request_payload()` drops it, which breaks multi-turn agent loops - exactly the
shape of `agent_factory()` with its three tools.
The upstream report (`langchain-ai/langchain` #37174) was **closed as not planned**, so treat this
as a standing defect, not a bug awaiting a release.

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

## 7. Open questions

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
