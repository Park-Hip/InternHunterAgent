"""Throwaway spike (T0027.1): decide whether DeepSeek can serve this agent at all.

research/deepseek-provider-evaluation.md documents three thinking-mode landmines that
would break the ReAct runtime: sampling parameters are ignored, tool_choice is rejected,
and reasoning_content must be echoed back on every tool-carrying turn - which
ChatDeepSeek does not do (langchain #37174, closed as not planned). All three are
supposed to disappear when thinking is disabled. None of that is proven against this
account until a live call says so.

Five checks, each with its control where absence alone would prove nothing. Check 3 is
the gate: if the second leg of a tool loop 400s with thinking disabled, the milestone
stops here.

Run with the dependency held out of the project, because .1 ships nothing:

    uv run --with langchain-deepseek python scripts/deepseek_provider_spike.py

Not imported by anything. Discard once T0027.2 promotes the configuration.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

MODEL = "deepseek-v4-flash"
THINKING_OFF = {"thinking": {"type": "disabled"}}

# deepseek-v4-flash, cache-miss rates, USD per 1M tokens (pricing captured 2026-08-14).
INPUT_USD_PER_M = 0.14
OUTPUT_USD_PER_M = 0.28

_usage: list[tuple[int, int]] = []


class AccountBlocked(RuntimeError):
    """The account cannot transact, so no check can produce a behavioral result.

    A 402 is not a failed check. Reporting it as one would claim DeepSeek failed the
    gate when nothing about the model was ever exercised.
    """


def classify(exc: Exception) -> Exception:
    status = getattr(exc, "status_code", None)
    if status is None:
        status = getattr(getattr(exc, "response", None), "status_code", None)
    text = str(exc).lower()
    if status in {401, 402, 403} or "insufficient balance" in text or "invalid api key" in text:
        return AccountBlocked(str(exc)[:200])
    return exc


def load_api_key(explicit_env_file: str | None) -> str:
    """Read the key from the environment, else from a .env this checkout can see.

    A git worktree has no .env of its own - it is ignored, so it lives only in the
    main checkout. Look there rather than making the operator copy secrets around.
    """
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if key:
        return key

    candidates: list[Path] = []
    if explicit_env_file:
        candidates.append(Path(explicit_env_file))
    candidates.append(Path(__file__).resolve().parents[1] / ".env")
    try:
        main_worktree = subprocess.check_output(
            ["git", "worktree", "list", "--porcelain"], text=True, stderr=subprocess.DEVNULL
        ).splitlines()[0]
        candidates.append(Path(main_worktree.split(maxsplit=1)[1]) / ".env")
    except (OSError, subprocess.CalledProcessError, IndexError):
        pass

    for candidate in candidates:
        if not candidate.is_file():
            continue
        for line in candidate.read_text(encoding="utf-8").splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "DEEPSEEK_API_KEY":
                value = value.strip().strip('"').strip("'")
                if value:
                    print(f"  (key read from {candidate})")
                    return value
    return ""


def build_model(api_key: str, **overrides: Any):
    """One construction point, so every check differs only in what it means to differ."""
    from langchain_deepseek import ChatDeepSeek

    kwargs: dict[str, Any] = {
        "model": MODEL,
        "temperature": 0.2,
        "max_tokens": 256,
        "timeout": 60,
        "max_retries": 0,
        "api_key": api_key,
    }
    kwargs.update(overrides)
    return ChatDeepSeek(**kwargs)


def record_usage(message: Any) -> str:
    usage = getattr(message, "usage_metadata", None) or {}
    prompt_tokens = int(usage.get("input_tokens", 0) or 0)
    completion_tokens = int(usage.get("output_tokens", 0) or 0)
    _usage.append((prompt_tokens, completion_tokens))
    return f"{prompt_tokens} in / {completion_tokens} out"


def reasoning_of(message: Any) -> str:
    """Provider-reported thinking text, wherever the integration parked it."""
    extra = getattr(message, "additional_kwargs", None) or {}
    for field in ("reasoning_content", "reasoning"):
        value = extra.get(field)
        if value:
            return str(value)
    return ""


def check_1_reachable(api_key: str) -> tuple[bool, str]:
    model = build_model(api_key, max_tokens=32)
    response = model.invoke("Reply with the single word: ready")
    text = str(response.content).strip()
    return bool(text), f"answered {text!r} ({record_usage(response)})"


def check_2_thinking_switch(api_key: str) -> tuple[bool, str]:
    """Absence of reasoning_content proves nothing unless the default produces some."""
    prompt = "Which is larger, 9.11 or 9.9? Answer in one sentence."

    default = build_model(api_key).invoke(prompt)
    default_reasoning = reasoning_of(default)
    record_usage(default)

    disabled = build_model(api_key, extra_body=THINKING_OFF).invoke(prompt)
    disabled_reasoning = reasoning_of(disabled)
    record_usage(disabled)

    detail = (
        f"thinking on -> {len(default_reasoning)} chars of reasoning; "
        f"thinking off -> {len(disabled_reasoning)} chars"
    )
    if default_reasoning and not disabled_reasoning:
        return True, detail + " (control held: the switch is what removed it)"
    if not default_reasoning and not disabled_reasoning:
        return False, detail + " (INCONCLUSIVE: no reasoning to suppress either way)"
    return False, detail


def _tool_loop(api_key: str, *, thinking_disabled: bool) -> tuple[bool, str]:
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    from langchain_core.tools import tool

    @tool
    def get_row_count(table: str) -> str:
        """Return how many rows a table holds."""
        return "22"

    overrides: dict[str, Any] = {"extra_body": THINKING_OFF} if thinking_disabled else {}
    model = build_model(api_key, **overrides).bind_tools([get_row_count])

    messages: list[Any] = [
        HumanMessage(content="How many rows are in the clean_jobs table? Use the tool, then answer.")
    ]
    first = model.invoke(messages)
    record_usage(first)
    tool_calls = getattr(first, "tool_calls", []) or []
    if not tool_calls:
        return False, "first leg returned no tool call, so the loop never started"

    messages.append(AIMessage(content=first.content, additional_kwargs=first.additional_kwargs, tool_calls=tool_calls))
    messages.append(ToolMessage(content="22", tool_call_id=tool_calls[0]["id"]))

    second = model.invoke(messages)  # the leg that 400s when reasoning_content is dropped
    record_usage(second)
    answer = str(second.content).strip().replace("\n", " ")
    return True, f"two legs completed, tool {tool_calls[0]['name']!r}, answered {answer[:70]!r}"


def check_3_tool_loop(api_key: str) -> tuple[bool, str]:
    """The gate. A 400 here with thinking off ends the milestone."""
    passed, detail = _tool_loop(api_key, thinking_disabled=True)

    try:
        control_passed, control_detail = _tool_loop(api_key, thinking_disabled=False)
        control = (
            "thinking on ALSO survived the second leg"
            if control_passed
            else f"thinking on failed differently: {control_detail}"
        )
    except Exception as exc:  # noqa: BLE001 - the documented 400 is the interesting outcome
        control = f"thinking on raised {type(exc).__name__}: {str(exc)[:110]}"

    return passed, f"{detail} | control: {control}"


def check_4_determinism(api_key: str) -> tuple[bool, str]:
    prompt = (
        "Write one PostgreSQL statement and nothing else. "
        "Count the rows in clean_jobs where location is 'Ha Noi'."
    )
    model = build_model(api_key, temperature=0.0, extra_body=THINKING_OFF)
    first = str(model.invoke(prompt).content).strip()
    second = str(model.invoke(prompt).content).strip()
    identical = first == second
    detail = f"{first[:60]!r} vs {second[:60]!r}"
    return identical, detail if identical else "DIFFERED: " + detail


def check_5_streaming(api_key: str) -> tuple[bool, str]:
    model = build_model(api_key, extra_body=THINKING_OFF)
    chunks = list(model.stream("Name three programming languages, one per line."))
    text_chunks = [chunk for chunk in chunks if str(chunk.content)]
    leaked = [chunk for chunk in chunks if reasoning_of(chunk)]
    passed = len(text_chunks) > 1 and not leaked
    return passed, f"{len(chunks)} chunks, {len(text_chunks)} carrying text, {len(leaked)} carrying reasoning"


CHECKS = (
    ("1. model reachable", check_1_reachable),
    ("2. thinking switch reaches the wire", check_2_thinking_switch),
    ("3. multi-turn tool loop (GATE)", check_3_tool_loop),
    ("4. determinism at temperature 0.0", check_4_determinism),
    ("5. streaming without reasoning chunks", check_5_streaming),
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", help="Path to a .env holding DEEPSEEK_API_KEY")
    parser.add_argument("--output", help="Write the results as JSON to this path")
    args = parser.parse_args()

    api_key = load_api_key(args.env_file)
    if not api_key:
        print("DEEPSEEK_API_KEY is not set and no .env supplied one.")
        return 2

    print(f"T0027.1 spike against {MODEL}\n")
    results: list[dict[str, Any]] = []
    blocked_reason = ""
    for name, check in CHECKS:
        if blocked_reason:
            status, detail = "BLOCKED", "not attempted: the account cannot transact"
        else:
            try:
                passed, detail = check(api_key)
                status = "PASS" if passed else "FAIL"
            except Exception as exc:  # noqa: BLE001 - a live failure is a result, not a crash
                classified = classify(exc)
                if isinstance(classified, AccountBlocked):
                    blocked_reason = str(classified)
                    status, detail = "BLOCKED", f"account cannot transact: {blocked_reason}"
                else:
                    status, detail = "FAIL", f"{type(exc).__name__}: {str(exc)[:400]}"
        print(f"[{status}] {name}\n       {detail}\n")
        results.append({"check": name, "status": status, "detail": detail})

    prompt_tokens = sum(row[0] for row in _usage)
    completion_tokens = sum(row[1] for row in _usage)
    spend = prompt_tokens / 1e6 * INPUT_USD_PER_M + completion_tokens / 1e6 * OUTPUT_USD_PER_M
    print(
        f"{len(_usage)} calls, {prompt_tokens} prompt + {completion_tokens} completion tokens, "
        f"provider-reported spend ${spend:.4f}"
    )

    gate = next(row for row in results if row["check"].endswith("(GATE)"))
    if blocked_reason:
        print(
            "\nBLOCKED, not failed: the key authenticated and the account has no balance, so no "
            "check ran.\nDeepSeek has no free tier. Fund the account and re-run; nothing here "
            "says anything\nabout the model's behavior, and no result may be inferred from it."
        )
    elif gate["status"] != "PASS":
        print("\nGATE FAILED: the tool loop does not survive with thinking disabled. Stop T0027.")

    if args.output:
        Path(args.output).write_text(
            json.dumps(
                {
                    "model": MODEL,
                    "results": results,
                    "calls": len(_usage),
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "usd": round(spend, 4),
                    "blocked_reason": blocked_reason,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    if blocked_reason:
        return 3
    return 0 if all(row["status"] == "PASS" for row in results) else 1


if __name__ == "__main__":
    sys.exit(main())
