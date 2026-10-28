"""Drive every baseline conversation through the application service.

The runner from #759 is the capture half of the agent baseline. It owns the
conversation and the evidence; ``evals.baseline_agent`` owns the contract and
the offline scorer, and ``evals.milestone`` owns the committed run layout.

One command runs the dataset end to end and writes a milestone:

    uv run python -m evals.baseline_agent run --milestone agent-v1 \\
      --database-url "$BASELINE_DATABASE_URL"

The runner reads through the column-granted snapshot reader (#730) and refuses
to start unless ``verify_reader_role`` and ``verify_snapshot`` both pass. It
then drives each conversation through ``stream_agent_response`` on a real
``AgentRuntime``, with an in-memory checkpointer so follow-up turns see the
conversation the service would see. No eval-only branch is added to the
service.

**Capture point for executed SQL.** The production MCP tools are discovered as
usual and wrapped on the eval side. The wrapper sees the exact tool arguments
and the ``ToolMessage`` the production tool returns. On success the message's
``artifact["structured_content"]`` is the typed ``QueryResult``, whose ``sql``
field is the bounded statement the tool actually ran. That value is recorded as
``executed_sql``. A ``generated_sql`` (the model's pre-bound statement) is not
returned to a caller without changing production code, so it is not captured;
the scorer already supports an executed-only basis. A rejection reaches the
wrapper as an error-status message beginning with ``rejected:``, and is recorded
as the validator verdict.

**Tokens.** A callback handler is bound to the compiled agent for the run. It
reads the per-turn context and sums every model call in the turn, including the
SQL-generation call nested inside ``query_clean_jobs``. A provider that reports
no usage leaves ``tokens`` null rather than inventing a number.

Use ``--out`` for a standalone capture (it is not scored as a milestone) and
``--split dev`` to keep the held-out and safety files out of a tuning pass.
A milestone always requires every split: an incomplete capture is refused by
``milestone.write_agent_run``.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable, Sequence
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from typing import Any
from uuid import uuid4

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import ToolMessage
from langchain_core.outputs import LLMResult
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from pydantic import Field

from evals import baseline_config, baseline_dataset, milestone, snapshot_manifest
from evals.sql_check import verify_reader_role
from src.services.query.result_shape import classify_result_shape, counted_total
from src.services.query.statement import parse_statement

QUERY_TOOL = "query_clean_jobs"
DETAIL_TOOL = "get_job_details"
ALL_SPLITS = "all"


# ---------------------------------------------------------------------------
# Token usage


@dataclass
class TokenUsage:
    """The token totals one turn's model calls reported."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    calls: int = 0

    def add(
        self,
        input_tokens: int | None,
        output_tokens: int | None,
        total_tokens: int | None,
    ) -> None:
        if input_tokens is None and output_tokens is None and total_tokens is None:
            return
        self.calls += 1
        self.input_tokens = _sum_optional(self.input_tokens, input_tokens)
        self.output_tokens = _sum_optional(self.output_tokens, output_tokens)
        self.total_tokens = _sum_optional(self.total_tokens, total_tokens)

    def as_capture(self) -> dict[str, int | None] | None:
        if self.calls == 0:
            return None
        total = self.total_tokens
        if (
            total is None
            and self.input_tokens is not None
            and self.output_tokens is not None
        ):
            total = self.input_tokens + self.output_tokens
        return {
            "input": self.input_tokens,
            "output": self.output_tokens,
            "total": total,
        }


_active_usage: ContextVar[TokenUsage | None] = ContextVar(
    "agent_runner_turn_usage", default=None
)


def _sum_optional(current: int | None, value: int | None) -> int | None:
    if value is None:
        return current
    if current is None:
        return value
    return current + value


def _optional_token_count(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _usage_field(value: Any, *names: str) -> int | None:
    for name in names:
        if isinstance(value, dict):
            candidate = value.get(name)
        else:
            candidate = getattr(value, name, None)
        count = _optional_token_count(candidate)
        if count is not None:
            return count
    return None


def usage_from_response(
    response: LLMResult,
) -> tuple[int | None, int | None, int | None] | None:
    """Read one model call's usage from LangChain's standard result shapes.

    ChatLiteLLM reports non-streaming calls under ``llm_output.token_usage`` and
    streaming calls on the aggregated message's ``usage_metadata``. The two are
    the same figures, so the message form wins and the LLMResult form is only a
    fallback; summing both would double count one call.
    """
    usages: list[tuple[int | None, int | None, int | None]] = []
    for generation_list in response.generations or []:
        for generation in generation_list:
            message = getattr(generation, "message", None)
            metadata = getattr(message, "usage_metadata", None)
            if metadata is None:
                continue
            usage = (
                _usage_field(metadata, "input_tokens"),
                _usage_field(metadata, "output_tokens"),
                _usage_field(metadata, "total_tokens"),
            )
            if any(value is not None for value in usage):
                usages.append(usage)
    if usages:
        return (
            _sum_or_none(usage[0] for usage in usages),
            _sum_or_none(usage[1] for usage in usages),
            _sum_or_none(usage[2] for usage in usages),
        )

    llm_output = response.llm_output or {}
    for key in ("token_usage", "usage"):
        usage = llm_output.get(key)
        if usage is None:
            continue
        return (
            _usage_field(usage, "prompt_tokens", "input_tokens"),
            _usage_field(usage, "completion_tokens", "output_tokens"),
            _usage_field(usage, "total_tokens"),
        )
    return None


def _sum_or_none(values: Iterable[int | None]) -> int | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return sum(present)


class UsageCallbackHandler(BaseCallbackHandler):
    """Add every model call's usage to the turn currently being captured."""

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        usage = _active_usage.get()
        if usage is None:
            return
        extracted = usage_from_response(response)
        if extracted is not None:
            usage.add(*extracted)


# ---------------------------------------------------------------------------
# Tool capture


@dataclass
class ToolCallRecorder:
    """Collect the derived facts of each tool call in the current turn."""

    calls: list[dict[str, Any]] = field(default_factory=list)
    _current: list[dict[str, Any]] | None = None

    def begin(self) -> None:
        self._current = []

    def end(self) -> list[dict[str, Any]]:
        calls = self._current or []
        self._current = None
        return calls

    def record(self, call: dict[str, Any]) -> None:
        if self._current is None:
            # A call outside a turn is still evidence, but there is no turn to
            # attach it to. Keeping it in the run-level list makes the bug
            # visible instead of silently dropping it.
            self.calls.append(call)
            return
        self._current.append(call)


def _tool_arguments(tool_input: Any) -> dict[str, Any]:
    if isinstance(tool_input, dict):
        args = tool_input.get("args")
        if isinstance(args, dict):
            return dict(args)
        if "args" not in tool_input:
            return dict(tool_input)
    return {"value": tool_input}


def _message_text(message: ToolMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in content:
        if isinstance(block, dict):
            parts.append(str(block.get("text", "")))
        else:
            parts.append(str(block))
    return "".join(parts)


def _structured_content(message: ToolMessage) -> dict[str, Any] | None:
    artifact = getattr(message, "artifact", None)
    if not isinstance(artifact, dict):
        return None
    structured = artifact.get("structured_content")
    return structured if isinstance(structured, dict) else None


def _as_count(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _page_offset(sql: str) -> int:
    try:
        parsed = parse_statement(sql)
    except Exception:
        # The tool only returns SQL it has already validated and run. A parse
        # failure here is therefore an evidence gap, not a reason to drop the
        # call; zero is the honest default when the page start is unknown.
        return 0
    return parsed.offset or 0


def _count_values(shape: str, columns: list[Any], rows: list[list[Any]]) -> list[int]:
    if shape == "match_count":
        total = counted_total(
            [str(column) for column in columns],
            rows,
        )
        if total is not None:
            return [total]
        # counted_total only accepts the exact one-column, one-row shape. A
        # count query with a different projection is still a match count for
        # the scorer's purposes if its single row holds one non-negative
        # integer, so fall back to that figure rather than letting
        # total_rows=1 stand in for the real count.
        for row in rows:
            for cell in row:
                if isinstance(cell, int) and not isinstance(cell, bool) and cell >= 0:
                    return [cell]
        return []
    if shape != "summary":
        return []
    values: list[int] = []
    for row in rows:
        for cell in row:
            if isinstance(cell, bool) or not isinstance(cell, int):
                continue
            if cell not in values:
                values.append(cell)
    return values


def _source_urls(columns: list[Any], rows: list[list[Any]]) -> list[str]:
    index = next(
        (
            position
            for position, column in enumerate(columns)
            if str(column).lower() == "source_url"
        ),
        None,
    )
    if index is None:
        return []
    urls: list[str] = []
    for row in rows:
        if index >= len(row):
            continue
        value = row[index]
        if isinstance(value, str) and value and value not in urls:
            urls.append(value)
    return urls


def _is_truncated(result_shape: str, rows_returned: Any, total_rows: Any) -> bool:
    """Whether a non-empty page shows only part of its match set.

    An empty page past the end is ``no_more``, not ``truncated``. Treating it as
    truncated would make B4 demand both "no more" and "showing 0 of N" for the
    same page, which is not what the reader should say.
    """
    if result_shape != "rows":
        return False
    rows = _as_count(rows_returned)
    total = _as_count(total_rows)
    return rows is not None and total is not None and 0 < rows < total


def capture_tool_result(
    name: str,
    arguments: dict[str, Any],
    message: ToolMessage,
) -> dict[str, Any]:
    """Turn one production tool message into the capture contract's facts."""
    call: dict[str, Any] = {"name": name, "arguments": arguments}
    if message.status == "error":
        error = _message_text(message)
        call["error"] = error
        if name == QUERY_TOOL and error.strip().lower().startswith("reject"):
            kind, _, reason = error.partition(":")
            call["validator"] = {
                "valid": False,
                "reason": reason.strip() or kind.strip() or "rejected",
            }
        return call

    structured = _structured_content(message)
    if structured is None:
        call["error"] = "tool result had no structured content"
        return call

    if name == DETAIL_TOOL:
        jobs = structured.get("jobs")
        job_rows = jobs if isinstance(jobs, list) else []
        call["rows_returned"] = len(job_rows)
        urls: list[str] = []
        for job in job_rows:
            if not isinstance(job, dict):
                continue
            url = job.get("source_url")
            if isinstance(url, str) and url and url not in urls:
                urls.append(url)
        call["source_urls"] = urls
        return call

    if name != QUERY_TOOL:
        # The eval only discovers the two job tools. An unknown tool has no
        # contract, so record the call and nothing invented.
        return call

    sql = structured.get("sql")
    columns = structured.get("columns")
    rows = structured.get("rows")
    column_list = columns if isinstance(columns, list) else []
    row_list = (
        [row for row in rows if isinstance(row, list)] if isinstance(rows, list) else []
    )
    row_count = _as_count(structured.get("row_count"))
    total_rows = _as_count(structured.get("total_rows"))

    call["validator"] = "accepted"
    if isinstance(sql, str) and sql.strip():
        shape = classify_result_shape(sql)
        call["executed_sql"] = sql
        call["result_shape"] = shape
        call["total_rows"] = total_rows
        call["rows_returned"] = row_count
        call["page_offset"] = _page_offset(sql)
        call["truncated"] = _is_truncated(shape, row_count, total_rows)
        call["count_values"] = _count_values(shape, column_list, row_list)
        call["source_urls"] = _source_urls(column_list, row_list)
    return call


class RecordingTool(BaseTool):
    """A production tool with an eval-side recorder around it.

    The wrapper is a normal LangChain ``BaseTool`` with the same name,
    description, and argument schema, so tool binding and the model-facing
    surface are unchanged. It delegates the call itself, then records only the
    derived facts. Nothing in the service knows the wrapper exists.
    """

    delegate: BaseTool = Field(exclude=True)
    recorder: ToolCallRecorder = Field(exclude=True)

    @classmethod
    def wrap(cls, delegate: BaseTool, recorder: ToolCallRecorder) -> "RecordingTool":
        return cls(
            name=delegate.name,
            description=delegate.description or "",
            args_schema=delegate.args_schema,
            return_direct=delegate.return_direct,
            tags=delegate.tags,
            metadata=delegate.metadata,
            response_format="content",
            delegate=delegate,
            recorder=recorder,
        )

    def _record(self, tool_input: Any, result: Any) -> None:
        if isinstance(result, ToolMessage):
            self.recorder.record(
                capture_tool_result(self.name, _tool_arguments(tool_input), result)
            )
            return
        self.recorder.record(
            {
                "name": self.name,
                "arguments": _tool_arguments(tool_input),
                "error": f"tool returned {type(result).__name__}, not a ToolMessage",
            }
        )

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError("RecordingTool is asynchronous")

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError("RecordingTool delegates through ainvoke")

    def invoke(
        self,
        input: Any,
        config: RunnableConfig | None = None,
        **kwargs: Any,
    ) -> Any:
        try:
            result = self.delegate.invoke(input, config=config, **kwargs)
        except Exception as exc:
            self.recorder.record(
                {
                    "name": self.name,
                    "arguments": _tool_arguments(input),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            raise
        self._record(input, result)
        return result

    async def ainvoke(
        self,
        input: Any,
        config: RunnableConfig | None = None,
        **kwargs: Any,
    ) -> Any:
        try:
            result = await self.delegate.ainvoke(input, config=config, **kwargs)
        except Exception as exc:
            self.recorder.record(
                {
                    "name": self.name,
                    "arguments": _tool_arguments(input),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            raise
        self._record(input, result)
        return result


# ---------------------------------------------------------------------------
# Conversation capture


def select_cases(split: str = ALL_SPLITS) -> list[dict[str, Any]]:
    cases = baseline_dataset.load_cases()
    if split == ALL_SPLITS:
        return cases
    if split not in baseline_dataset.SPLITS:
        raise ValueError(
            f"unknown baseline split {split!r}; expected all, dev, held-out, or safety"
        )
    return [case for case in cases if case["split"] == split]


def _record_summary(record: dict[str, Any]) -> str:
    turns = record["turns"]
    calls = sum(len(turn.get("tool_calls") or []) for turn in turns)
    errors = sum(1 for turn in turns if turn.get("error"))
    suffix = f", {errors} turn error(s)" if errors else ""
    return (
        f"{record['id']} repeat {record['repeat']}: {len(turns)} turns, "
        f"{calls} tool calls{suffix}"
    )


async def capture_turn(
    *,
    runtime: Any,
    recorder: ToolCallRecorder,
    case_id: str,
    repeat: int,
    turn_number: int,
    question: str,
    session_id: str,
) -> dict[str, Any]:
    """Drive one turn through the service and return its capture record."""
    from src.agents.models import (
        StreamErrorEvent,
        StreamMetadataEvent,
        StreamTokenEvent,
    )
    from src.agents.service import stream_agent_response

    usage = TokenUsage()
    recorder.begin()
    usage_token = _active_usage.set(usage)
    started = time.perf_counter()
    answer_parts: list[str] = []
    answer_source: str | None = None
    error: str | None = None
    try:
        async for event in stream_agent_response(
            query=question,
            runtime=runtime,
            session_id=session_id,
            user_id=f"agent-run:{case_id}:{repeat}",
        ):
            if isinstance(event, StreamTokenEvent):
                answer_parts.append(event.text)
            elif isinstance(event, StreamMetadataEvent):
                answer_source = event.answer_source
            elif isinstance(event, StreamErrorEvent):
                error = f"{event.code}: {event.message}"
    except Exception as exc:  # a broken turn is evidence, not a reason to stop
        error = f"{type(exc).__name__}: {exc}"
    finally:
        latency_ms = round((time.perf_counter() - started) * 1000)
        _active_usage.reset(usage_token)
        tool_calls = recorder.end()

    return {
        "turn": turn_number,
        "question": question,
        "answer": "".join(answer_parts),
        "answer_source": answer_source,
        "latency_ms": latency_ms,
        "tokens": usage.as_capture(),
        "tool_calls": tool_calls,
        **({"error": error} if error else {}),
    }


async def capture_conversations(
    cases: Sequence[dict[str, Any]],
    *,
    runtime: Any,
    recorder: ToolCallRecorder,
    repeats: int,
    session_prefix: str | None = None,
    on_record: Callable[[dict[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    """Run every case and repeat and return one record per conversation."""
    if repeats < 1:
        raise ValueError("repeats must be a positive integer")
    prefix = session_prefix or f"agent-eval-{uuid4().hex[:12]}"
    records: list[dict[str, Any]] = []
    for repeat in range(1, repeats + 1):
        for case in cases:
            session_id = f"{prefix}-{case['id']}-r{repeat}"
            turns: list[dict[str, Any]] = []
            for index, question in enumerate(case["turns"]):
                turns.append(
                    await capture_turn(
                        runtime=runtime,
                        recorder=recorder,
                        case_id=case["id"],
                        repeat=repeat,
                        turn_number=index + 1,
                        question=question,
                        session_id=session_id,
                    )
                )
            record = {
                "id": case["id"],
                "split": case["split"],
                "need": case["need"],
                "repeat": repeat,
                "turns": turns,
            }
            records.append(record)
            if on_record is not None:
                on_record(record)
    return records


def create_runtime(
    tools: Sequence[BaseTool],
    recorder: ToolCallRecorder,
    usage_handler: UsageCallbackHandler,
    *,
    agent_factory: Callable[..., Awaitable[Any]] | None = None,
    checkpointer: Any = None,
) -> Any:
    """Build the runtime the service will drive, with usage capture bound."""
    from src.agents.runtime.factory import agent_factory as default_agent_factory
    from src.agents.runtime.react_agent import AgentRuntime

    factory = agent_factory or default_agent_factory

    async def with_usage(**kwargs: Any) -> Any:
        agent = await factory(**kwargs)
        return agent.with_config(callbacks=[usage_handler])

    return AgentRuntime(
        agent_factory=with_usage,
        checkpointer=checkpointer,
        tools=list(tools),
    )


# ---------------------------------------------------------------------------
# Command


def _write_capture(path: Path, capture: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(capture, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


async def run(
    *,
    database_url: str,
    milestone_label: str | None = None,
    out: Path | None = None,
    split: str = ALL_SPLITS,
    milestone_root: Path | None = None,
) -> dict[str, Any]:
    """Run one agent baseline capture and optionally write it as a milestone."""
    if not milestone_label and out is None:
        raise ValueError("run needs --milestone or --out")
    if milestone_label and split != ALL_SPLITS:
        raise ValueError(
            "a committed milestone must cover every split; use --out for a tuning run"
        )
    if milestone_label:
        milestone.validate_label(milestone_label)

    database_url = database_url.strip()
    if not database_url:
        raise ValueError("a snapshot reader URL is required")

    # The evidence is only meaningful through the production boundary and
    # against the committed snapshot. Both checks run before a model is called.
    verify_reader_role(database_url)
    snapshot_manifest.verify_snapshot(database_url)

    # Settings are lazy, but bind the agent DSN before load_settings so the
    # tool, executor, and startup path all read the snapshot reader.
    os.environ["AGENT_DATABASE_URL"] = database_url
    os.environ.setdefault("DATABASE_URL", database_url)

    from src.agents.mcp.adapter import list_job_tools
    from src.agents.mcp.job_server import create_job_mcp_server
    from src.agents.runtime.prompts import load_resolved_prompt_versions
    from src.agents.runtime.provider import assert_profile_credential
    from src.core.config import load_settings
    from langgraph.checkpoint.memory import InMemorySaver

    settings = load_settings(force_reload=True)
    assert_profile_credential("react")
    assert_profile_credential("sql_generation")
    agent_settings = settings.agent
    if agent_settings is None:
        raise ValueError("Missing 'agent' settings after configuration load")
    baseline = baseline_config.load_baseline_settings()
    cases = select_cases(split)
    print(
        f"Agent baseline: {len(cases)} cases x {baseline.agent_repeats} repeats "
        f"on {agent_settings.deployment_for('react').model}",
        flush=True,
    )

    recorder = ToolCallRecorder()
    discovered = await list_job_tools(create_job_mcp_server())
    tools = [RecordingTool.wrap(tool, recorder) for tool in discovered]
    usage_handler = UsageCallbackHandler()
    runtime = create_runtime(
        tools,
        recorder,
        usage_handler,
        checkpointer=InMemorySaver(),
    )

    records = await capture_conversations(
        cases,
        runtime=runtime,
        recorder=recorder,
        repeats=baseline.agent_repeats,
        on_record=lambda record: print(_record_summary(record), flush=True),
    )
    capture: dict[str, Any] = {
        "schema_version": milestone.SCHEMA_VERSION,
        "runner": milestone.RUNNER_AGENT,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": agent_settings.deployment_for("react").model,
        "prompt_versions": load_resolved_prompt_versions(),
        "repeats": baseline.agent_repeats,
        "records": records,
    }

    if out is not None:
        _write_capture(out, capture)
        print(f"saved {len(records)} conversation records to {out}", flush=True)
    if milestone_label:
        run_dir = milestone.write_agent_run(
            capture,
            milestone_label,
            root=milestone_root or milestone.RUNS_ROOT,
        )
        print(f"Milestone run written to {run_dir}", flush=True)
    return capture
