"""Run the agent against a golden and score its three decision seams.

Seam 1 (routing) and seam 3 (synthesis) are visible on the top-level agent
run; seam 2 (the nested NL->SQL call inside `query_clean_jobs`) is only
observable because the tool forwards its injected `RunnableConfig` into the
nested `model.invoke(...)` (see `src/agents/tools/query_clean_jobs.py`), which
lets DeepEval's `CallbackHandler` see it as a distinct child span.

Kept out of `src/` entirely per the tracing-boundary rule (CLAUDE.md §2):
this module is the only place that knows about DeepEval metrics/spans.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from deepeval.integrations.langchain import CallbackHandler
from deepeval.metrics import (
    GEval,
    ToolCorrectnessMetric,
)
from deepeval.test_case import LLMTestCase, SingleTurnParams, ToolCall, Turn
from deepeval.test_case.conversational_test_case import ConversationalTestCase
from deepeval.tracing.trace_test_manager import trace_testing_manager

from evals.judge import build_judge
from src.agents.runtime.factory import agent_factory
from src.agents.runtime.prompts import load_schema_context
from src.agents.tracing.langfuse import (
    get_langfuse_handler,
    langfuse_request_trace,
    validate_langfuse_trace_context,
)

QUERY_TOOL_NAME = "query_clean_jobs"
GENERATE_SQL_SPAN_NAME = "generate_sql"

_judge = None


def get_judge():
    global _judge
    if _judge is None:
        _judge = build_judge()
    return _judge


def seam1_metrics() -> list:
    """Routing: right tool(s), right NL question passed to it."""
    judge = get_judge()
    return [
        ToolCorrectnessMetric(model=judge),
        GEval(
            name="Argument Correctness",
            criteria=(
                "Determine whether the tool(s) recorded in 'tools called' were "
                "invoked with arguments that correctly capture the request in "
                "'input', as reflected by 'actual output'."
            ),
            evaluation_params=[
                SingleTurnParams.INPUT,
                SingleTurnParams.ACTUAL_OUTPUT,
                SingleTurnParams.TOOLS_CALLED,
            ],
            model=judge,
        ),
    ]


def seam2_metrics() -> list:
    """Hidden NL->SQL: the SQL the nested `generate_sql` call emitted."""
    judge = get_judge()
    return [
        GEval(
            name="SQL Schema Quality",
            criteria=(
                "'context' contains the clean_jobs schema. Determine whether "
                "the SQL in 'actual output' is a valid, read-only statement "
                "that respects that schema and would answer the "
                "natural-language question in 'input'."
            ),
            evaluation_params=[
                SingleTurnParams.INPUT,
                SingleTurnParams.ACTUAL_OUTPUT,
                SingleTurnParams.CONTEXT,
            ],
            model=judge,
        ),
    ]


def seam3_metrics() -> list:
    """Synthesis: the final user-facing answer."""
    judge = get_judge()
    return [
        GEval(
            name="Task Completion",
            criteria=(
                "Determine whether 'actual output' actually completes what "
                "the user asked for in 'input', using 'retrieval context' "
                "(the underlying tool's result, if any) as evidence of what "
                "was available to answer with."
            ),
            evaluation_params=[
                SingleTurnParams.INPUT,
                SingleTurnParams.ACTUAL_OUTPUT,
                SingleTurnParams.RETRIEVAL_CONTEXT,
            ],
            model=judge,
        ),
        GEval(
            name="Honesty",
            criteria=(
                "Determine whether 'actual output' preserves any truncation, "
                "uncertainty, or 'not available in the data' caveat present "
                "in 'retrieval context', instead of dropping it when "
                "rewriting the tool's result for the user."
            ),
            evaluation_params=[
                SingleTurnParams.INPUT,
                SingleTurnParams.ACTUAL_OUTPUT,
                SingleTurnParams.RETRIEVAL_CONTEXT,
            ],
            model=judge,
        ),
    ]


@dataclass
class SeamRun:
    """One agent turn's outputs, split by seam."""

    question: str
    answer: str
    tools_called: list[str] = field(default_factory=list)
    tool_output: str | None = None
    sql_text: str | None = None
    trace_id: str | None = None
    telemetry: dict[str, Any] = field(default_factory=dict)


_UNAVAILABLE = "unavailable"
_TOKEN_FIELDS = {
    "input_tokens": ("input_tokens", "prompt_tokens"),
    "output_tokens": ("output_tokens", "completion_tokens"),
    "total_tokens": ("total_tokens",),
}


class ProviderTelemetryCallback(BaseCallbackHandler):
    """Collect provider-reported usage for every LLM call in one agent turn."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def on_llm_end(self, response: Any, **_: Any) -> None:
        llm_output = getattr(response, "llm_output", None)
        llm_output = llm_output if isinstance(llm_output, dict) else {}
        generations = getattr(response, "generations", None)
        generation = (
            generations[0][0]
            if isinstance(generations, list)
            and generations
            and isinstance(generations[0], list)
            and generations[0]
            else None
        )
        message = getattr(generation, "message", None)
        message_usage = getattr(message, "usage_metadata", None)
        response_metadata = getattr(message, "response_metadata", None)
        response_metadata = (
            response_metadata if isinstance(response_metadata, dict) else {}
        )
        usage = (
            llm_output.get("token_usage") or llm_output.get("usage") or message_usage
        )
        usage = usage if isinstance(usage, dict) else {}

        record: dict[str, Any] = {}
        for token_field, aliases in _TOKEN_FIELDS.items():
            value = next(
                (usage[key] for key in aliases if isinstance(usage.get(key), int)), None
            )
            record[token_field] = value if value is not None else _UNAVAILABLE

        finish_reason = response_metadata.get("finish_reason")
        generation_info = getattr(generation, "generation_info", None)
        if not isinstance(finish_reason, str) or not finish_reason:
            finish_reason = (
                generation_info.get("finish_reason")
                if isinstance(generation_info, dict)
                else None
            )
        record["finish_reason"] = (
            finish_reason
            if isinstance(finish_reason, str) and finish_reason
            else _UNAVAILABLE
        )
        self.calls.append(record)

    def snapshot(self, latency_ms: int) -> dict[str, Any]:
        aggregate: dict[str, int | str] = {}
        for token_field in _TOKEN_FIELDS:
            values = [call[token_field] for call in self.calls]
            aggregate[token_field] = (
                sum(values)
                if values and all(isinstance(value, int) for value in values)
                else _UNAVAILABLE
            )
        return {
            "latency_ms": latency_ms,
            "provider_token_usage": {"calls": self.calls, "aggregate": aggregate},
            "finish_reasons": [call["finish_reason"] for call in self.calls]
            or [_UNAVAILABLE],
        }


def _find_span(spans: list[dict], **matches) -> dict | None:
    for span in spans:
        if all(span.get(key) == value for key, value in matches.items()):
            return span
    return None


def _extract_sql_span(trace_dict: dict) -> tuple[dict | None, dict | None]:
    """Locate the tool span for query_clean_jobs and its nested LLM span.

    The nested `generate_sql` model.invoke only produces its own span
    because the tool forwards the injected RunnableConfig into it; without
    that forwarding this LLM call would be invisible to the trace.

    That forwarded config is the *tool node's* config, not one re-scoped to
    the tool's own run (LangChain's `@tool` machinery injects the parent
    `config` into the function's `RunnableConfig` param verbatim, rather
    than the `child_config` it uses internally — see
    `langchain_core.tools.base._get_runnable_config_param` callers). So the
    generate_sql LLM span lands as a *sibling* of the tool span, both
    children of the same tool-node run, not nested under the tool span.
    """
    tool_spans = trace_dict.get("toolSpans") or []
    llm_spans = trace_dict.get("llmSpans") or []

    tool_span = _find_span(tool_spans, name=QUERY_TOOL_NAME)
    if tool_span is None:
        return None, None

    sql_span = _find_span(llm_spans, parentUuid=tool_span.get("parentUuid"))
    return tool_span, sql_span


def _llm_output_text(span: dict | None) -> str | None:
    if span is None:
        return None
    output = span.get("output")
    if isinstance(output, dict):
        content = output.get("content")
        return content.strip() if isinstance(content, str) else None
    if isinstance(output, str):
        return output.strip()
    return None


async def _run_turn(
    agent,
    message: str,
    config: dict,
    trace_id: str | None,
) -> SeamRun:
    trace_testing_manager.test_name = "three-seam-eval"
    trace_testing_manager.test_dict = None
    lf_handler = get_langfuse_handler()
    telemetry_handler = ProviderTelemetryCallback()
    run_config = {
        **config,
        "callbacks": [*config.get("callbacks", []), telemetry_handler],
    }
    try:
        if lf_handler is not None:
            run_config = {
                **run_config,
                "callbacks": [*run_config["callbacks"], lf_handler],
            }
        started_at = perf_counter()
        response = await agent.ainvoke(
            {"messages": [HumanMessage(content=message)]},
            config=run_config,
        )
        latency_ms = round((perf_counter() - started_at) * 1000)
        trace_dict = await trace_testing_manager.wait_for_test_dict()
    finally:
        trace_testing_manager.test_name = None
        trace_testing_manager.test_dict = None

    answer = str(response["messages"][-1].content).strip()
    tools_called = [tc.get("name") for tc in (trace_dict.get("toolsCalled") or [])]

    tool_span, sql_span = _extract_sql_span(trace_dict)
    tool_output = tool_span.get("output") if tool_span else None
    if isinstance(tool_output, dict):
        tool_output = tool_output.get("content") or str(tool_output)

    return SeamRun(
        question=message,
        answer=answer,
        tools_called=[name for name in tools_called if name],
        tool_output=str(tool_output) if tool_output is not None else None,
        sql_text=_llm_output_text(sql_span),
        trace_id=trace_id,
        telemetry=telemetry_handler.snapshot(latency_ms),
    )


async def run_single_turn_case(case: dict, *, repeat: int = 1) -> SeamRun:
    agent = agent_factory()
    handler = CallbackHandler(name=case["id"])
    validate_langfuse_trace_context(
        entry_point="eval:driver",
        scenario_id=case["id"],
        repeat=repeat,
    )
    async with langfuse_request_trace(
        entry_point="eval:driver",
        scenario_id=case["id"],
        repeat=repeat,
        trace_name=f"eval-{case['id']}",
    ) as trace_id:
        return await _run_turn(
            agent,
            case["input"],
            {"callbacks": [handler]},
            trace_id,
        )


async def run_conversational_case(
    case: dict,
    *,
    repeat: int = 1,
    pause: Callable[[], Awaitable[None]] | None = None,
) -> tuple[list[SeamRun], ConversationalTestCase]:
    """Run every turn against one persistent thread; return each turn's
    SeamRun plus a ConversationalTestCase transcript of the whole exchange.

    `pause` runs before every turn after the first. A conversational case
    would otherwise spend a second turn's token budget inside the per-minute
    window its first turn just filled.
    """
    agent = agent_factory(checkpointer=InMemorySaver())
    thread_id = case["id"]
    validate_langfuse_trace_context(
        entry_point="eval:driver",
        scenario_id=case["id"],
        repeat=repeat,
    )
    config = {
        "configurable": {"thread_id": thread_id},
    }

    runs: list[SeamRun] = []
    turns: list[Turn] = []
    for turn_index, message in enumerate(case["turns"]):
        if turn_index and pause is not None:
            await pause()
        handler = CallbackHandler(thread_id=thread_id)
        async with langfuse_request_trace(
            entry_point="eval:driver",
            scenario_id=case["id"],
            repeat=repeat,
            trace_name=f"eval-{thread_id}-turn-{turn_index + 1}",
        ) as trace_id:
            seam_run = await _run_turn(
                agent,
                message,
                {**config, "callbacks": [handler]},
                trace_id,
            )
        runs.append(seam_run)
        turns.append(Turn(role="user", content=message))
        turns.append(
            Turn(
                role="assistant",
                content=seam_run.answer,
                tools_called=[ToolCall(name=name) for name in seam_run.tools_called],
            )
        )

    return runs, ConversationalTestCase(turns=turns)


def build_seam1_case(case: dict, run: SeamRun) -> LLMTestCase:
    expected_tools = case.get("expected_tools")
    return LLMTestCase(
        input=run.question,
        actual_output=run.answer,
        tools_called=[ToolCall(name=name) for name in run.tools_called],
        expected_tools=(
            [ToolCall(name=name) for name in expected_tools]
            if expected_tools is not None
            else None
        ),
    )


def build_seam2_case(run: SeamRun) -> LLMTestCase | None:
    if run.sql_text is None:
        return None
    return LLMTestCase(
        input=run.question,
        actual_output=run.sql_text,
        context=[load_schema_context()],
        tools_called=[
            ToolCall(
                name=GENERATE_SQL_SPAN_NAME, input_parameters={"sql": run.sql_text}
            )
        ],
    )


def build_seam3_case(case: dict, run: SeamRun) -> LLMTestCase:
    return LLMTestCase(
        input=run.question,
        actual_output=run.answer,
        expected_output=case["expected"],
        retrieval_context=[run.tool_output] if run.tool_output else [],
    )


def score(metrics: list, test_case: LLMTestCase) -> dict[str, dict]:
    """Measure every metric, isolating failures so one broken metric (e.g. a
    judge JSON hiccup, or a known deepeval bug — see Known_Issues.md) doesn't
    blank out the other scores for this seam."""
    results: dict[str, dict] = {}
    for metric in metrics:
        try:
            metric.measure(test_case)
            results[metric.__name__] = {
                "score": metric.score,
                "reason": getattr(metric, "reason", None),
            }
        except Exception as exc:  # noqa: BLE001 - report, don't abort the run
            results[metric.__name__] = {"score": None, "error": str(exc)}
    return results


async def run_case(case: dict) -> dict:
    """Run one golden end-to-end and score every seam it produced."""
    if case["type"] == "conversational":
        runs, conversation = await run_conversational_case(case)
        final_run = runs[-1]
    else:
        final_run = await run_single_turn_case(case)
        conversation = None

    results: dict[str, dict] = {}

    seam1_case = build_seam1_case(case, final_run)
    results["seam1_routing"] = score(seam1_metrics(), seam1_case)

    seam2_case = build_seam2_case(final_run)
    if seam2_case is not None:
        results["seam2_nl_to_sql"] = score(seam2_metrics(), seam2_case)

    seam3_case = build_seam3_case(case, final_run)
    results["seam3_synthesis"] = score(seam3_metrics(), seam3_case)

    return {
        "case_id": case["id"],
        "answer": final_run.answer,
        "tools_called": final_run.tools_called,
        "sql_text": final_run.sql_text,
        "conversation": conversation,
        "results": results,
        "trace_id": final_run.trace_id,
        # The scenario driver is the sole score writer because only it can
        # associate scores with the derived Langfuse dataset run.
        "scores_written": 0,
    }
