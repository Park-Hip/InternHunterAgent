from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from deepeval.tracing.trace_test_manager import trace_testing_manager
from evals.harness import (
    QUERY_TOOL_NAME,
    _extract_sql_span,
    _llm_output_text,
    _run_turn,
)


def _trace(*, llm_spans: list[dict], tool_spans: list[dict] | None = None) -> dict:
    return {
        "toolSpans": tool_spans
        if tool_spans is not None
        else [
            {
                "name": QUERY_TOOL_NAME,
                "uuid": "tool-uuid",
                "parentUuid": "node-uuid",
            }
        ],
        "llmSpans": llm_spans,
    }


def test_extract_sql_span_finds_child_of_mcp_tool_span() -> None:
    tool_span = {
        "name": QUERY_TOOL_NAME,
        "uuid": "tool-uuid",
        "parentUuid": "node-uuid",
    }
    sql_span = {"parentUuid": "tool-uuid", "output": "SELECT 1"}

    assert _extract_sql_span(_trace(llm_spans=[sql_span], tool_spans=[tool_span])) == (
        tool_span,
        sql_span,
    )


def test_extract_sql_span_prefers_child_over_sibling() -> None:
    child_span = {"parentUuid": "tool-uuid", "output": "SELECT child"}
    sibling_span = {"parentUuid": "node-uuid", "output": "SELECT sibling"}

    assert _extract_sql_span(
        _trace(llm_spans=[sibling_span, child_span])
    ) == (_trace(llm_spans=[])["toolSpans"][0], child_span)


def test_extract_sql_span_falls_back_to_sibling_hierarchy() -> None:
    sql_span = {"parentUuid": "node-uuid", "output": "SELECT 1"}

    assert _extract_sql_span(_trace(llm_spans=[sql_span])) == (
        _trace(llm_spans=[])["toolSpans"][0],
        sql_span,
    )


def test_extract_sql_span_does_not_match_unrelated_llm_spans() -> None:
    spans = [
        {"parentUuid": "other-tool-uuid", "output": "SELECT unrelated FROM secrets"},
        {"parentUuid": "another-node-uuid", "output": "SELECT another_unrelated"},
    ]

    tool_span, sql_span = _extract_sql_span(_trace(llm_spans=spans))

    assert tool_span is not None
    assert sql_span is None


def test_extract_sql_span_returns_none_when_tool_span_is_absent() -> None:
    assert _extract_sql_span(_trace(llm_spans=[], tool_spans=[])) == (None, None)


def test_extract_sql_span_ignores_missing_uuid_in_malformed_tool_span() -> None:
    tool_span = {"name": QUERY_TOOL_NAME, "parentUuid": "node-uuid"}
    malformed_match = {"parentUuid": None, "output": "unrelated"}

    assert _extract_sql_span(
        _trace(llm_spans=[malformed_match], tool_spans=[tool_span])
    ) == (tool_span, None)


def test_llm_output_text_trims_output_and_handles_missing_span() -> None:
    assert _llm_output_text({"output": "  SELECT 1  "}) == "SELECT 1"
    assert _llm_output_text(None) is None


@pytest.mark.asyncio
async def test_missing_sql_span_still_emits_warning(monkeypatch, caplog) -> None:
    async def missing_trace() -> dict:
        return _trace(llm_spans=[])

    class FakeAgent:
        async def ainvoke(self, *_args, **_kwargs) -> dict:
            return {"messages": [SimpleNamespace(content="answer")]}

    monkeypatch.setattr(trace_testing_manager, "wait_for_test_dict", missing_trace)
    monkeypatch.setattr("evals.harness.get_langfuse_handler", lambda: None)

    with caplog.at_level(logging.WARNING):
        run = await _run_turn(FakeAgent(), "question", {}, None)

    assert run.sql_text is None
    assert any(
        "eval.scoring.sql_span_missing" in record.getMessage()
        for record in caplog.records
    )
