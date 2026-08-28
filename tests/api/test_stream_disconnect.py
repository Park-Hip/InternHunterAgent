from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from starlette.requests import Request

from src.api.routes.query import stream_query_agent
from src.api.schemas import QueryRequest


class StreamDisconnectTests(unittest.IsolatedAsyncioTestCase):
    @patch("src.api.routes.query.logger")
    async def test_asgi_disconnect_cancels_runtime_and_logs_once(
        self, mock_logger
    ) -> None:
        producer_started = asyncio.Event()
        producer_cancelled = asyncio.Event()
        disconnect_messages: asyncio.Queue[dict[str, str]] = asyncio.Queue()

        async def slow_stream(**_kwargs):
            producer_started.set()
            try:
                await asyncio.Event().wait()
            finally:
                producer_cancelled.set()
            yield {"type": "token", "text": "unreachable"}

        runtime = MagicMock()
        runtime.astream.side_effect = slow_stream
        scope = {
            "type": "http",
            "asgi": {"spec_version": "2.3"},
            "method": "POST",
            "path": "/api/v1/agent/chat/stream",
            "headers": [],
            "app": SimpleNamespace(state=SimpleNamespace(runtime=runtime)),
        }

        async def receive() -> dict[str, str]:
            # The ASGI channel supplies one disconnect message only. Further
            # receive calls block rather than replaying that message.
            return await disconnect_messages.get()

        async def send(_message):
            pass

        request = Request(scope, receive=receive)
        # Keep the route's non-blocking heartbeat probe off the channel so the
        # EventSourceResponse listener consumes the sole disconnect message.
        request.is_disconnected = AsyncMock(return_value=False)
        response = await stream_query_agent(
            QueryRequest(query="slow request", session_id="session-disconnect"), request
        )

        response_task = asyncio.create_task(response(scope, receive, send))
        await asyncio.wait_for(producer_started.wait(), timeout=0.5)
        await disconnect_messages.put({"type": "http.disconnect"})
        await asyncio.wait_for(response_task, timeout=0.5)

        await asyncio.wait_for(producer_cancelled.wait(), timeout=0.5)
        mock_logger.info.assert_called_once_with(
            "stream.client_disconnected", session_id="session-disconnect"
        )
