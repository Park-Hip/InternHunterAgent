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

from dataclasses import dataclass, field

from langchain.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from deepeval.integrations.langchain import CallbackHandler
from deepeval.metrics import (
    ArgumentCorrectnessMetric,
    FaithfulnessMetric,
    GEval,
    TaskCompletionMetric,
    ToolCorrectnessMetric,
)
from deepeval.test_case import LLMTestCase, SingleTurnParams, ToolCall, Turn
from deepeval.test_case.conversational_test_case import ConversationalTestCase
from deepeval.tracing.trace_test_manager import trace_testing_manager

from evals.judge import build_judge
from src.agents.runtime.factory import agent_factory
from src.agents.runtime.prompts import load_schema_context

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
        ArgumentCorrectnessMetric(model=judge),
    ]


def seam2_metrics() -> list:
    """Hidden NL->SQL: the SQL the nested `generate_sql` call emitted."""
    judge = get_judge()
    return [
        ArgumentCorrectnessMetric(model=judge),
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
        TaskCompletionMetric(model=judge),
        FaithfulnessMetric(model=judge),
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


async def _run_turn(agent, message: str, config: dict) -> SeamRun:
    trace_testing_manager.test_name = "three-seam-eval"
    trace_testing_manager.test_dict = None
    try:
        response = await agent.ainvoke(
            {"messages": [HumanMessage(content=message)]},
            config=config,
        )
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
    )


async def run_single_turn_case(case: dict) -> SeamRun:
    agent = agent_factory()
    handler = CallbackHandler(name=case["id"])
    return await _run_turn(agent, case["input"], {"callbacks": [handler]})


async def run_conversational_case(case: dict) -> tuple[list[SeamRun], ConversationalTestCase]:
    """Run every turn against one persistent thread; return each turn's
    SeamRun plus a ConversationalTestCase transcript of the whole exchange."""
    agent = agent_factory(checkpointer=InMemorySaver())
    thread_id = case["id"]
    config = {"configurable": {"thread_id": thread_id}}

    runs: list[SeamRun] = []
    turns: list[Turn] = []
    for message in case["turns"]:
        handler = CallbackHandler(thread_id=thread_id)
        seam_run = await _run_turn(agent, message, {**config, "callbacks": [handler]})
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
        tools_called=[ToolCall(name=GENERATE_SQL_SPAN_NAME, input_parameters={"sql": run.sql_text})],
    )


def build_seam3_case(case: dict, run: SeamRun) -> LLMTestCase:
    return LLMTestCase(
        input=run.question,
        actual_output=run.answer,
        expected_output=case.get("expected_output"),
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
            results[metric.__name__] = {"score": metric.score, "reason": getattr(metric, "reason", None)}
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
    }
