# Semantic Judge

> **Source:** `evals/judge.py`, `evals/semantic.py:232`, `config/settings.yaml`

## Overview

The semantic judge is a `DeepEvalBaseLLM` wrapper around a LangChain chat model. It is the model that `ConversationalGEval` calls to evaluate a full conversation transcript against a scenario-specific rubric.

## Provider arms

Three provider arms are wired in `build_judge()`:

| Provider | Model | Why it exists |
|---|---|---|
| `google` | `gemma-4-31b-it` | **Primary.** Google AI Studio directly; no thinking knob needed; free-tier friendly. |
| `groq` | (configurable) | Free-tier arm at 8000 TPM / 200K TPD. Requires `turn_pacing_seconds: 75` to survive the per-minute window. |
| `openrouter` | (configurable) | OpenAI-wire-protocol fallback; retained for flexibility but not the default. |

**Why the judge is on Google/gemma and not the serving provider:** D-017 — the judge runs on a provider that does not serve the agent. This keeps evaluation load off the serving account and prevents a provider from judging its own arm.

## DeepEvalJudge wrapper

`DeepEvalJudge` extends `deepeval.models.base_model.DeepEvalBaseLLM`:

```python
class DeepEvalJudge(DeepEvalBaseLLM):
    def __init__(self, chat_model: BaseChatModel, model_name: str, rpm: int = 0)
    def generate(self, prompt: str) -> str
    async def a_generate(self, prompt: str) -> str
    def get_model_name(self) -> str
```

### `_content_to_text` — thinking-block filter

Some providers (notably `google/gemma`) return content as a list of blocks, including `{'type': 'thinking'}` blocks before the answer. `_content_to_text` flattens the content into parseable text by keeping only `text` blocks:

```python
@staticmethod
def _content_to_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(str(block.get("text", "")))
            elif getattr(block, "type", None) == "text":
                parts.append(str(getattr(block, "text", "")))
        return "\n".join(p for p in parts if p)
    return str(content)
```

Without this filter, DeepEval's response parsers would see thinking-content mixed with the actual answer and fail to extract a clean score.

### `_RpmThrottle` — free-tier limiter

The sliding-window throttle keeps judge calls under the provider's RPM cap so a ~120-call judge run does not look stuck on 429 retries:

```python
class _RpmThrottle:
    def __init__(self, rpm: int)
    def wait(self) -> None          # sync
    async def a_wait(self) -> None  # async
```

## Configuration

All settings live in `config/settings.yaml` under `eval.judge`:

```yaml
eval:
  judge:
    provider: google               # google | groq | openrouter
    model: gemma-4-31b-it
    temperature: 0.0
    rpm: 10                        # free-tier cap binds before 30 RPM at ~1k tok/call
    timeout_seconds: 120           # default 30 was too tight for CoT prompts (50-90s)
```

| Setting | Default | Purpose |
|---|---|---|
| `provider` | `google` | Which provider arm to use |
| `model` | `gemma-4-31b-it` | Model name (provider-dependent) |
| `temperature` | `0.0` | Deterministic scoring |
| `rpm` | `10` | Sliding-window rate limit (0 = no limit) |
| `timeout_seconds` | `120` | Client socket timeout; gemma CoT prompts take 50-90s |

## How it is called

`evals/semantic.py:232` constructs the DeepEval metric:

```python
metric = ConversationalGEval(
    name="Semantic Behavior",
    criteria=_criteria(scenario),
    evaluation_params=[MultiTurnParams.CONTENT],
    model=build_judge(),
    async_mode=False,
)
```

`MultiTurnParams.CONTENT` tells DeepEval to evaluate the full conversation transcript (all turns), not just the final answer.

## Return semantics

`evaluate_semantic_repeat()` returns a `SemanticJudgeResult`:

| Field | Meaning |
|---|---|
| `AVAILABLE` | Judge returned a score and rationale |
| `UNAVAILABLE` | Provider failed (quota, timeout, JSON error) — rerunnable |

An `UNAVAILABLE` result is preserved as evidence and does not become `PASS` or `FAIL`. The scorer resumes after interruption (R3.5).

## Tests

- `tests/evals/test_semantic.py` — mock-based tests for `evaluate_semantic_repeat`, criteria assembly, exemplar selection, and JUDGE-1..JUDGE-6 failure-mode annotations.
- `evals/test_judge.py` — no-network unit tests for config-to-model wiring (builds `ChatOpenAI` with a dummy key without hitting the network).
