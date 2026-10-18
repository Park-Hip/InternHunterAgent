from __future__ import annotations

import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from starlette.requests import Request

from src.agents.models import StreamMetadataEvent, StreamTokenEvent
from src.api.app import create_app
from src.api.routes.query import stream_query_agent
from src.api.schemas import QueryRequest


def _sent_body(messages: list[dict[str, object]]) -> str:
    """The SSE bytes the ASGI response wrote, joined in send order."""
    return b"".join(
        message.get("body", b"")
        for message in messages
        if message["type"] == "http.response.body"
    ).decode()


def _issued_session_id(body: str) -> str | None:
    """The session id the service minted, read from the `session` frame."""
    for block in body.split("\n\n"):
        for line in block.splitlines():
            if not line.startswith("data: "):
                continue
            payload = json.loads(line.removeprefix("data: "))
            if payload.get("type") == "session":
                return payload["session_id"]
    return None


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
            yield StreamTokenEvent(type="token", text="unreachable")

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

    @patch("src.api.routes.query.logger")
    async def test_disconnect_before_done_logs_once_with_the_issued_session_id(
        self, mock_logger
    ) -> None:
        """A first turn has no request session id, so the log names the minted one (#674)."""
        producer_started = asyncio.Event()
        producer_cancelled = asyncio.Event()
        disconnect_messages: asyncio.Queue[dict[str, str]] = asyncio.Queue()
        sent: list[dict[str, object]] = []

        async def slow_stream(**_kwargs):
            producer_started.set()
            try:
                await asyncio.Event().wait()
            finally:
                producer_cancelled.set()
            yield StreamTokenEvent(type="token", text="unreachable")

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
            return await disconnect_messages.get()

        async def send(message: dict[str, object]) -> None:
            sent.append(message)

        request = Request(scope, receive=receive)
        request.is_disconnected = AsyncMock(return_value=False)
        # No session_id: the browser omits it on a first turn, so the service
        # mints one and announces it in the `session` event.
        response = await stream_query_agent(QueryRequest(query="slow request"), request)

        response_task = asyncio.create_task(response(scope, receive, send))
        await asyncio.wait_for(producer_started.wait(), timeout=0.5)
        await disconnect_messages.put({"type": "http.disconnect"})
        await asyncio.wait_for(response_task, timeout=0.5)

        await asyncio.wait_for(producer_cancelled.wait(), timeout=0.5)

        body = _sent_body(sent)
        # The client left before the turn finished: the session frame is all it got.
        self.assertIn("event: session", body)
        self.assertNotIn("event: done", body)
        issued_session_id = _issued_session_id(body)
        self.assertIsNotNone(issued_session_id)
        mock_logger.info.assert_called_once_with(
            "stream.client_disconnected", session_id=issued_session_id
        )


class CompletedStreamDisconnectTests(unittest.TestCase):
    """A stream that reached `done` is not a client that left (#674)."""

    def test_completed_stream_logs_no_disconnect(self) -> None:
        app = create_app(rate_limit="1000/minute", docs_enabled=False)
        app.state.runtime = AsyncMock()

        async def _fake_astream(**_kwargs):
            yield StreamTokenEvent(type="token", text="There are 3 roles.")
            yield StreamMetadataEvent(type="metadata", trace_id=None, trace_url=None)

        app.state.runtime.astream = _fake_astream

        with patch("src.api.routes.query.logger") as mock_logger:
            response = TestClient(app).post(
                "/api/v1/agent/chat/stream",
                json={"query": "list 3 data engineer jobs"},
            )
            self.assertEqual(response.status_code, 200)
            self.assertTrue(
                response.text.rstrip().endswith('event: done\ndata: {"type": "done"}'),
                "the stream must reach its terminal frame for this test to mean "
                "anything",
            )
            disconnect_calls = [
                call
                for call in mock_logger.info.call_args_list
                if call.args and call.args[0] == "stream.client_disconnected"
            ]
            self.assertEqual(
                disconnect_calls,
                [],
                "a stream that sent done must not be logged as a client disconnect",
            )
