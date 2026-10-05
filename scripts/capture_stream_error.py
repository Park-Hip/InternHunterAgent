"""Diagnostic capture for the trailing SSE `error` event on a real turn.

DIAGNOSTIC TOOL, NOT PRODUCTION CODE. Nothing here is imported by the service.
It exists to answer one question recorded on issue #580: which `error` payload a
real turn emits, and therefore which of the two causes in
`src/agents/service.py` produced it.

It drives the same `stream_agent_response` the HTTP route serves, so the event
sequence and the `error` payload are the ones a client receives. The route only
serializes that generator into SSE, so the payload itself is identical.

Usage:

    DATABASE_URL=postgresql+psycopg://internhunter:internhunter@localhost:5433/internhunter_eval \\
    AGENT_DATABASE_URL=postgresql+psycopg://internhunter_agent:internhunter@localhost:5433/internhunter_eval \\
    uv run python scripts/capture_stream_error.py --query "Luong Data Analyst o Da Nang la bao nhieu?"

Every emitted event is printed in order, and the terminal `error` payload is
summarised with its `code` and `message` so the discriminator is explicit.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Windows-only: psycopg's async I/O refuses uvicorn's Proactor loop, and this
# script owns its loop, so pin a Selector loop before any async pool opens.
# Production runs on Linux, where this is the default.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from src.agents.mcp.adapter import list_job_tools  # noqa: E402
from src.agents.mcp.job_server import create_job_mcp_server  # noqa: E402
from src.agents.runtime.react_agent import AgentRuntime  # noqa: E402
from src.agents.service import stream_agent_response  # noqa: E402
from src.core.checkpointer import build_checkpointer, build_checkpointer_pool  # noqa: E402


async def capture(query: str) -> dict[str, Any]:
    """Run one streamed turn and record every event it emits."""

    pool = build_checkpointer_pool()
    await pool.open()
    started = time.monotonic()
    events: list[dict[str, Any]] = []
    error_payload: dict[str, Any] | None = None
    token_count = 0
    try:
        checkpointer = await build_checkpointer(pool)
        runtime = AgentRuntime(
            checkpointer=checkpointer,
            tools=await list_job_tools(create_job_mcp_server()),
        )
        async for event in stream_agent_response(
            query=query,
            runtime=runtime,
            session_id="diagnostic-580",
        ):
            recorded = dict(event)
            if recorded.get("type") == "token":
                recorded["text"] = "<token>"
                token_count += 1
            events.append(recorded)
            if recorded.get("type") == "error":
                error_payload = recorded
    finally:
        await pool.close()

    return {
        "query": query,
        "elapsed_seconds": round(time.monotonic() - started, 1),
        "token_count": token_count,
        "event_types": [event.get("type") for event in events],
        "error_payload": error_payload,
        "events": events,
    }


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", required=True)
    parser.add_argument("--json", action="store_true", help="print the full capture as JSON")
    arguments = parser.parse_args()

    result = await capture(arguments.query)
    if arguments.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(f"query:              {result['query']}")
    print(f"elapsed_seconds:    {result['elapsed_seconds']}")
    print(f"token_count:        {result['token_count']}")
    print(f"event_types:        {result['event_types']}")
    print(f"error_payload:      {json.dumps(result['error_payload'], ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))