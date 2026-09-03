"""Unit tests for `evals/harness.py` span-extraction helpers."""

from __future__ import annotations

from evals.harness import _extract_sql_span, DETAIL_TOOL_NAME, QUERY_TOOL_NAME


def _make_trace(
    tool_spans: list[dict] | None = None,
    llm_spans: list[dict] | None = None,
) -> dict:
    return {"toolSpans": tool_spans or [], "llmSpans": llm_spans or []}


def _tool_span(name: str, parent_uuid: str = "parent-1") -> dict:
    return {"name": name, "parentUuid": parent_uuid, "output": {"content": f"result-for-{name}"}}


def _llm_span(parent_uuid: str, name: str = "generate_sql") -> dict:
    return {"name": name, "parentUuid": parent_uuid, "output": {"content": "SELECT 1"}}


class TestExtractSqlSpan:
    """Tests for `_extract_sql_span`, which locates the tool span and its
    optional nested LLM span for both `query_clean_jobs` and `get_job_details`.
    """

    def test_finds_query_clean_jobs_with_sibling_generate_sql_span(self) -> None:
        parent = "p-1"
        trace = _make_trace(
            tool_spans=[_tool_span(QUERY_TOOL_NAME, parent_uuid=parent)],
            llm_spans=[_llm_span(parent_uuid=parent, name="generate_sql")],
        )
        tool_span, sql_span = _extract_sql_span(trace)
        assert tool_span is not None
        assert tool_span["name"] == QUERY_TOOL_NAME
        assert sql_span is not None
        assert sql_span["name"] == "generate_sql"

    def test_finds_get_job_details_without_sql_span(self) -> None:
        parent = "p-2"
        trace = _make_trace(
            tool_spans=[_tool_span(DETAIL_TOOL_NAME, parent_uuid=parent)],
            llm_spans=[],
        )
        tool_span, sql_span = _extract_sql_span(trace)
        assert tool_span is not None
        assert tool_span["name"] == DETAIL_TOOL_NAME
        assert sql_span is None

    def test_returns_none_when_neither_tool_is_present(self) -> None:
        trace = _make_trace(
            tool_spans=[_tool_span("some_other_tool")],
            llm_spans=[],
        )
        tool_span, sql_span = _extract_sql_span(trace)
        assert tool_span is None
        assert sql_span is None

    def test_get_job_details_ignores_unrelated_sibling_llm_span(self) -> None:
        """A `get_job_details` tool span may have a sibling LLM span from
        the agent's reasoning loop; it must not be mistaken for a SQL span.
        """
        parent = "p-3"
        trace = _make_trace(
            tool_spans=[_tool_span(DETAIL_TOOL_NAME, parent_uuid=parent)],
            llm_spans=[_llm_span(parent_uuid=parent, name="reasoning_loop")],
        )
        tool_span, sql_span = _extract_sql_span(trace)
        assert tool_span is not None
        assert tool_span["name"] == DETAIL_TOOL_NAME
        assert sql_span is None

    def test_query_clean_jobs_without_sql_span_returns_tool_only(self) -> None:
        """When the generate_sql span is missing, the tool span is still
        returned so the tool_output seam is captured.
        """
        parent = "p-4"
        trace = _make_trace(
            tool_spans=[_tool_span(QUERY_TOOL_NAME, parent_uuid=parent)],
            llm_spans=[],
        )
        tool_span, sql_span = _extract_sql_span(trace)
        assert tool_span is not None
        assert tool_span["name"] == QUERY_TOOL_NAME
        assert sql_span is None

    def test_prefer_query_clean_jobs_over_get_job_details_when_both_present(self) -> None:
        """If a trace contains spans for both tools, the function returns the
        first match (query_clean_jobs) to preserve existing behavior.
        """
        parent_qcj = "p-5a"
        parent_gjd = "p-5b"
        trace = _make_trace(
            tool_spans=[
                _tool_span(DETAIL_TOOL_NAME, parent_uuid=parent_gjd),
                _tool_span(QUERY_TOOL_NAME, parent_uuid=parent_qcj),
            ],
            llm_spans=[_llm_span(parent_uuid=parent_qcj, name="generate_sql")],
        )
        tool_span, sql_span = _extract_sql_span(trace)
        assert tool_span is not None
        assert tool_span["name"] == QUERY_TOOL_NAME
        assert sql_span is not None
        assert sql_span["name"] == "generate_sql"
