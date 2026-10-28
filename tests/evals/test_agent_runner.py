"""The agent runner: service-driven turns and the eval-side tool seam.

The tests never call a model provider and never read a database. One integration
case uses the real ``AgentRuntime`` and LangGraph checkpointer with a
history-aware fake model, so the follow-up memory claim is exercised through the
same seam the runner uses. The tool tests use the real in-process MCP tools with
their behavior functions patched, so the wrapper is tested against the message
contract the agent actually sees.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult, LLMResult
from langgraph.checkpoint.memory import InMemorySaver

from evals import agent_runner, baseline_agent, baseline_dataset, milestone
from src.agents.mcp.adapter import list_job_tools
from src.agents.mcp.job_server import create_job_mcp_server
from src.agents.tools.failures import ToolFailure
from src.services.query.models import JobDetailsResult, QueryResult

QUERY = "query_clean_jobs"
DETAILS = "get_job_details"


# ---------------------------------------------------------------------------
# A stub runtime for service/error tests


class StubRuntime:
    """The smallest runtime shape ``stream_agent_response`` drives."""

    def __init__(
        self, answers: dict[str, str], failures: set[str] | None = None
    ) -> None:
        self.answers = answers
        self.failures = failures or set()

    async def astream(self, **kwargs: Any):
        query = kwargs["query"]
        if query in self.failures:
            raise RuntimeError("provider failed")
        from src.agents.models import StreamMetadataEvent, StreamTokenEvent

        yield StreamTokenEvent(type="token", text=self.answers.get(query, "ok"))
        yield StreamMetadataEvent(
            type="metadata",
            trace_id=None,
            trace_url=None,
            answer_source="model",
        )


# ---------------------------------------------------------------------------
# A history-aware model for the memory integration test


class HistoryAwareModel(BaseChatModel):
    """Answer from the number of human messages the graph was given."""

    @property
    def _llm_type(self) -> str:
        return "history-aware"

    def _generate(
        self,
        messages: list[Any],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        humans = [message for message in messages if isinstance(message, HumanMessage)]
        text = "follow-up" if len(humans) > 1 else "first"
        message = AIMessage(
            content=text,
            usage_metadata={
                "input_tokens": 11,
                "output_tokens": 7,
                "total_tokens": 18,
            },
        )
        return ChatResult(
            generations=[ChatGeneration(message=message)],
            llm_output={
                "token_usage": {
                    "prompt_tokens": 11,
                    "completion_tokens": 7,
                    "total_tokens": 18,
                }
            },
        )


async def _history_factory(*, checkpointer=None, system_prompt=None, tools=None):
    return create_agent(
        model=HistoryAwareModel(),
        tools=[],
        system_prompt=system_prompt,
        checkpointer=checkpointer,
    )


async def _trimmed_factory(*, checkpointer=None, system_prompt=None, tools=None):
    from src.agents.runtime.middleware import TrimTurnsMiddleware

    return create_agent(
        model=HistoryAwareModel(),
        tools=[],
        system_prompt=system_prompt,
        checkpointer=checkpointer,
        middleware=[TrimTurnsMiddleware(1)],
    )


class ToolCallingModel(BaseChatModel):
    """Call the one tool once, then answer from the tool message."""

    @property
    def _llm_type(self) -> str:
        return "tool-calling"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ToolCallingModel":
        return self

    def _generate(
        self,
        messages: list[Any],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        if any(isinstance(message, ToolMessage) for message in messages):
            message = AIMessage(content="Có 2 tin phù hợp.")
        else:
            message = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": QUERY,
                        "args": {"request": "find AI jobs"},
                        "id": "call-1",
                    }
                ],
            )
        return ChatResult(generations=[ChatGeneration(message=message)])


async def _tool_factory(*, checkpointer=None, system_prompt=None, tools=None):
    return create_agent(
        model=ToolCallingModel(),
        tools=list(tools or []),
        system_prompt=system_prompt,
        checkpointer=checkpointer,
    )


# ---------------------------------------------------------------------------
# Tests


def test_usage_reads_streaming_metadata_once_and_falls_back_to_llm_output() -> None:
    metadata_result = LLMResult(
        generations=[
            [
                ChatGeneration(
                    message=AIMessage(
                        content="",
                        usage_metadata={
                            "input_tokens": 11,
                            "output_tokens": 7,
                            "total_tokens": 18,
                        },
                    )
                )
            ]
        ],
        llm_output={
            "token_usage": {
                "prompt_tokens": 11,
                "completion_tokens": 7,
                "total_tokens": 18,
            }
        },
    )
    assert agent_runner.usage_from_response(metadata_result) == (11, 7, 18)

    llm_only = LLMResult(
        generations=[],
        llm_output={
            "token_usage": {
                "prompt_tokens": 3,
                "completion_tokens": 2,
                "total_tokens": 5,
            }
        },
    )
    assert agent_runner.usage_from_response(llm_only) == (3, 2, 5)
    assert agent_runner.usage_from_response(LLMResult(generations=[])) is None


def test_token_usage_keeps_missing_fields_null_and_sums_turns() -> None:
    usage = agent_runner.TokenUsage()
    assert usage.as_capture() is None

    usage.add(10, 4, 14)
    usage.add(1, None, 5)
    assert usage.as_capture() == {"input": 11, "output": 4, "total": 19}

    inferred = agent_runner.TokenUsage()
    inferred.add(10, 4, None)
    assert inferred.as_capture() == {"input": 10, "output": 4, "total": 14}


def test_a_rejected_query_records_the_validator_verdict() -> None:
    recorder = agent_runner.ToolCallRecorder()
    tool = _discovered_tool(QUERY)
    wrapped = agent_runner.RecordingTool.wrap(tool, recorder)
    recorder.begin()
    # The guard is never executed: the failure maps to the message the model
    # would see, and the wrapper records the validator verdict beside it.
    with patch(
        "src.agents.mcp.job_server.run_query_clean_jobs",
        side_effect=ToolFailure("rejected", "star selects are not allowed"),
    ):
        message = asyncio.run(
            wrapped.ainvoke(
                _tool_call(QUERY, {"request": "show me everything"}, "call-reject")
            )
        )
    assert isinstance(message, ToolMessage)
    assert message.status == "error"
    calls = recorder.end()
    assert calls == [
        {
            "name": QUERY,
            "arguments": {"request": "show me everything"},
            "error": "rejected: star selects are not allowed",
            "validator": {"valid": False, "reason": "star selects are not allowed"},
        }
    ]


def test_a_query_result_records_executed_sql_and_derived_facts() -> None:
    recorder = agent_runner.ToolCallRecorder()
    wrapped = agent_runner.RecordingTool.wrap(_discovered_tool(QUERY), recorder)
    result = QueryResult(
        sql=(
            "SELECT id, title, source_url FROM clean_jobs ORDER BY created_on DESC, id "
            "LIMIT 20 OFFSET 40"
        ),
        columns=["id", "title", "source_url"],
        rows=[
            [1, "A", "https://example.com/1"],
            [2, "B", "https://example.com/2"],
        ],
        row_count=20,
        total_rows=65,
    )
    request = "AI Engineer in Da Nang, " + "x" * 200
    recorder.begin()
    with patch("src.agents.mcp.job_server.run_query_clean_jobs", return_value=result):
        message = asyncio.run(
            wrapped.ainvoke(_tool_call(QUERY, {"request": request}, "call-ok"))
        )

    assert isinstance(message, ToolMessage)
    calls = recorder.end()
    assert calls == [
        {
            "name": QUERY,
            "arguments": {"request": request},
            "validator": "accepted",
            "executed_sql": result.sql,
            "result_shape": "rows",
            "total_rows": 65,
            "rows_returned": 20,
            "page_offset": 40,
            "truncated": True,
            "count_values": [],
            "source_urls": ["https://example.com/1", "https://example.com/2"],
        }
    ]
    # The request survives in full; the public tool event truncates it, the
    # capture must not.
    assert calls[0]["arguments"]["request"] == request


def test_an_empty_page_past_the_end_is_not_truncated() -> None:
    recorder = agent_runner.ToolCallRecorder()
    wrapped = agent_runner.RecordingTool.wrap(_discovered_tool(QUERY), recorder)
    result = QueryResult(
        sql=(
            "SELECT id FROM clean_jobs ORDER BY created_on DESC, id LIMIT 20 OFFSET 60"
        ),
        columns=["id"],
        rows=[],
        row_count=0,
        total_rows=60,
    )
    recorder.begin()
    with patch("src.agents.mcp.job_server.run_query_clean_jobs", return_value=result):
        asyncio.run(wrapped.ainvoke(_tool_call(QUERY, {"request": "next page"})))
    call = recorder.end()[0]
    assert call["page_offset"] == 60
    assert call["rows_returned"] == 0
    assert call["truncated"] is False


def test_count_and_summary_shapes_capture_the_figures() -> None:
    count_call = agent_runner.capture_tool_result(
        QUERY,
        {"request": "how many"},
        _success_message(
            QueryResult(
                sql="SELECT COUNT(*) AS count FROM clean_jobs WHERE role = 'AI Engineer'",
                columns=["count"],
                rows=[[11]],
                row_count=1,
                total_rows=1,
            )
        ),
    )
    assert count_call["result_shape"] == "match_count"
    assert count_call["count_values"] == [11]
    assert count_call["truncated"] is False

    summary_call = agent_runner.capture_tool_result(
        QUERY,
        {"request": "breakdown by city"},
        _success_message(
            QueryResult(
                sql=(
                    "SELECT location, COUNT(*) AS count FROM clean_jobs "
                    "GROUP BY location"
                ),
                columns=["location", "count"],
                rows=[["Hanoi", 3], ["Da Nang", 2]],
                row_count=2,
                total_rows=2,
            )
        ),
    )
    assert summary_call["result_shape"] == "summary"
    assert summary_call["count_values"] == [3, 2]
    assert summary_call["truncated"] is False


def test_a_detail_result_records_rows_and_links_only() -> None:
    recorder = agent_runner.ToolCallRecorder()
    wrapped = agent_runner.RecordingTool.wrap(_discovered_tool(DETAILS), recorder)
    result = JobDetailsResult(
        jobs=[
            {"id": 1, "source_url": "https://example.com/1"},
            {"id": 2, "source_url": "https://example.com/2"},
        ],
        not_found=[9],
        not_fetched=[],
    )
    recorder.begin()
    with patch("src.agents.mcp.job_server.run_get_job_details", return_value=result):
        asyncio.run(wrapped.ainvoke(_tool_call(DETAILS, {"ids": [1, 9, 2]})))

    assert recorder.end() == [
        {
            "name": DETAILS,
            "arguments": {"ids": [1, 9, 2]},
            "rows_returned": 2,
            "source_urls": ["https://example.com/1", "https://example.com/2"],
        }
    ]


def test_the_wrapped_tool_works_inside_the_real_tool_node() -> None:
    recorder = agent_runner.ToolCallRecorder()
    wrapped = agent_runner.RecordingTool.wrap(_discovered_tool(QUERY), recorder)
    runtime = agent_runner.create_runtime(
        [wrapped],
        recorder,
        agent_runner.UsageCallbackHandler(),
        agent_factory=_tool_factory,
        checkpointer=InMemorySaver(),
    )
    case = {
        "id": "T01",
        "split": "dev",
        "need": "find",
        "turns": ["find AI jobs"],
    }
    result = QueryResult(
        sql="SELECT id, title, source_url FROM clean_jobs LIMIT 20",
        columns=["id", "title", "source_url"],
        rows=[[1, "A", "https://example.com/1"]],
        row_count=1,
        total_rows=1,
    )
    with patch("src.agents.mcp.job_server.run_query_clean_jobs", return_value=result):
        records = asyncio.run(
            agent_runner.capture_conversations(
                [case],
                runtime=runtime,
                recorder=recorder,
                repeats=1,
                session_prefix="tool-node",
            )
        )

    turn = records[0]["turns"][0]
    assert turn["answer"] == "Có 2 tin phù hợp."
    assert turn["tool_calls"] == [
        {
            "name": QUERY,
            "arguments": {"request": "find AI jobs"},
            "validator": "accepted",
            "executed_sql": result.sql,
            "result_shape": "rows",
            "total_rows": 1,
            "rows_returned": 1,
            "page_offset": 0,
            "truncated": False,
            "count_values": [],
            "source_urls": ["https://example.com/1"],
        }
    ]


def test_memory_makes_the_follow_up_different_and_broken_memory_shows_it() -> None:
    case = {
        "id": "T02",
        "split": "dev",
        "need": "narrow",
        "turns": ["find AI jobs", "only in Hanoi"],
    }
    recorder = agent_runner.ToolCallRecorder()
    runtime = agent_runner.create_runtime(
        [],
        recorder,
        agent_runner.UsageCallbackHandler(),
        agent_factory=_history_factory,
        checkpointer=InMemorySaver(),
    )
    records = asyncio.run(
        agent_runner.capture_conversations(
            [case],
            runtime=runtime,
            recorder=recorder,
            repeats=1,
            session_prefix="memory-on",
        )
    )
    answers = [turn["answer"] for turn in records[0]["turns"]]
    assert answers == ["first", "follow-up"]
    assert [turn["tokens"] for turn in records[0]["turns"]] == [
        {"input": 11, "output": 7, "total": 18},
        {"input": 11, "output": 7, "total": 18},
    ]

    broken_recorder = agent_runner.ToolCallRecorder()
    broken = agent_runner.create_runtime(
        [],
        broken_recorder,
        agent_runner.UsageCallbackHandler(),
        agent_factory=_history_factory,
        checkpointer=None,
    )
    broken_records = asyncio.run(
        agent_runner.capture_conversations(
            [case],
            runtime=broken,
            recorder=broken_recorder,
            repeats=1,
            session_prefix="memory-off",
        )
    )
    assert [turn["answer"] for turn in broken_records[0]["turns"]] == ["first", "first"]

    trimmed_recorder = agent_runner.ToolCallRecorder()
    trimmed = agent_runner.create_runtime(
        [],
        trimmed_recorder,
        agent_runner.UsageCallbackHandler(),
        agent_factory=_trimmed_factory,
        checkpointer=InMemorySaver(),
    )
    trimmed_records = asyncio.run(
        agent_runner.capture_conversations(
            [case],
            runtime=trimmed,
            recorder=trimmed_recorder,
            repeats=1,
            session_prefix="memory-trimmed",
        )
    )
    assert [turn["answer"] for turn in trimmed_records[0]["turns"]] == [
        "first",
        "first",
    ]


def test_a_failed_turn_is_recorded_without_losing_the_next_turn() -> None:
    case = {
        "id": "T03",
        "split": "dev",
        "need": "narrow",
        "turns": ["first question", "second question"],
    }
    runtime = StubRuntime(
        {"second question": "second answer"},
        failures={"first question"},
    )
    recorder = agent_runner.ToolCallRecorder()
    records = asyncio.run(
        agent_runner.capture_conversations(
            [case],
            runtime=runtime,
            recorder=recorder,
            repeats=1,
            session_prefix="errors",
        )
    )
    first, second = records[0]["turns"]
    assert first["answer"] == ""
    assert first["error"].startswith("internal_error:")
    assert second["answer"] == "second answer"
    assert "error" not in second


def test_the_runner_capture_passes_the_committed_contract() -> None:
    recorder = agent_runner.ToolCallRecorder()
    records = asyncio.run(
        agent_runner.capture_conversations(
            baseline_dataset.load_cases(),
            runtime=StubRuntime({}),
            recorder=recorder,
            repeats=1,
            session_prefix="contract",
        )
    )
    capture = {
        "schema_version": milestone.SCHEMA_VERSION,
        "runner": milestone.RUNNER_AGENT,
        "repeats": 1,
        "records": records,
    }
    baseline_agent.validate_capture(capture, require_complete=True)


def test_run_writes_the_capture_and_calls_the_milestone_writer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import src.agents.mcp.adapter as adapter
    import src.agents.mcp.job_server as job_server
    import src.agents.runtime.prompts as prompts
    import src.agents.runtime.provider as provider
    import src.core.config as config

    record = {
        "id": "T04",
        "split": "dev",
        "need": "find",
        "repeat": 1,
        "turns": [],
    }

    async def fake_capture(cases: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return [record]

    async def fake_list_job_tools(_server: Any) -> list[Any]:
        return []

    class Deployment:
        model = "test/model"

    class AgentSettings:
        def deployment_for(self, _profile: str) -> Deployment:
            return Deployment()

    class Settings:
        agent = AgentSettings()

    baseline = agent_runner.baseline_config.BaselineSettings(
        layer1_repeats=1,
        agent_repeats=1,
        agent_max_rows=20,
    )
    written: list[tuple[dict[str, Any], str]] = []

    def fake_write_agent_run(
        capture: dict[str, Any], label: str, **kwargs: Any
    ) -> Path:
        written.append((capture, label))
        return tmp_path / "run"

    monkeypatch.setenv("AGENT_DATABASE_URL", "postgresql://before")
    monkeypatch.setattr(agent_runner, "verify_reader_role", lambda _url: None)
    monkeypatch.setattr(
        agent_runner.snapshot_manifest, "verify_snapshot", lambda _url: None
    )
    monkeypatch.setattr(adapter, "list_job_tools", fake_list_job_tools)
    monkeypatch.setattr(job_server, "create_job_mcp_server", lambda: object())
    monkeypatch.setattr(prompts, "load_resolved_prompt_versions", lambda: {})
    monkeypatch.setattr(provider, "assert_profile_credential", lambda _profile: None)
    monkeypatch.setattr(config, "load_settings", lambda force_reload=False: Settings())
    monkeypatch.setattr(
        agent_runner.baseline_config, "load_baseline_settings", lambda: baseline
    )
    monkeypatch.setattr(agent_runner, "create_runtime", lambda *args, **kwargs: object())
    monkeypatch.setattr(agent_runner, "capture_conversations", fake_capture)
    monkeypatch.setattr(agent_runner.milestone, "write_agent_run", fake_write_agent_run)

    capture = asyncio.run(
        agent_runner.run(
            database_url="postgresql://unused",
            out=tmp_path / "capture.json",
            split="dev",
        )
    )
    assert capture["model"] == "test/model"
    assert capture["repeats"] == 1
    assert capture["records"] == [record]
    assert json.loads((tmp_path / "capture.json").read_text(encoding="utf-8")) == capture

    asyncio.run(
        agent_runner.run(
            database_url="postgresql://unused",
            milestone_label="agent-v1",
        )
    )
    assert len(written) == 1
    written_capture, written_label = written[0]
    assert written_label == "agent-v1"
    assert written_capture["records"] == [record]


def test_run_refuses_a_partial_milestone_before_touching_a_database() -> None:
    with pytest.raises(ValueError, match="every split"):
        asyncio.run(
            agent_runner.run(
                database_url="postgresql://unused",
                milestone_label="agent-v1",
                split="dev",
            )
        )
    with pytest.raises(ValueError, match="needs --milestone or --out"):
        asyncio.run(agent_runner.run(database_url="postgresql://unused"))
    with pytest.raises(milestone.MilestoneError, match="label"):
        asyncio.run(
            agent_runner.run(
                database_url="postgresql://unused",
                milestone_label="Not a label",
            )
        )


def test_write_capture_round_trips_utf8(tmp_path: Path) -> None:
    capture = {
        "schema_version": 1,
        "runner": "agent",
        "repeats": 1,
        "records": [],
        "note": "Kỹ sư AI",
    }
    path = tmp_path / "nested" / "captures.json"
    agent_runner._write_capture(path, capture)
    assert path.read_text(encoding="utf-8").endswith("\n")
    assert "Kỹ sư AI" in path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Helpers


def _tool_call(name: str, args: dict[str, Any], call_id: str = "call-1") -> dict:
    return {"type": "tool_call", "id": call_id, "name": name, "args": args}


def _discovered_tool(name: str):
    tools = {
        tool.name: tool for tool in asyncio.run(list_job_tools(create_job_mcp_server()))
    }
    return tools[name]


def _success_message(result: Any) -> ToolMessage:
    return ToolMessage(
        content=result.model_dump_json(),
        name=QUERY,
        tool_call_id="call-1",
        artifact={"structured_content": result.model_dump()},
    )
