from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.agents.service import FALLBACK_ANSWER, stream_agent_response
from src.agents.tracing import langfuse


@pytest.mark.asyncio
async def test_langfuse_observation_records_fallback_as_the_first_visible_token() -> (
    None
):
    async def empty_stream(**_kwargs):
        if False:  # pragma: no cover - keeps this an async generator
            yield {}

    client = MagicMock()
    runtime = MagicMock()
    runtime.astream = MagicMock(side_effect=empty_stream)

    with patch.object(langfuse, "get_langfuse_client", return_value=client):
        events = [
            event
            async for event in stream_agent_response(
                query="find internships",
                runtime=runtime,
                session_id="stream-fallback",
                stream_observation_factory=langfuse.create_langfuse_stream_observation,
            )
        ]

    assert {"type": "token", "text": FALLBACK_ANSWER} in events
    metadata = client.update_current_span.call_args.kwargs["metadata"]
    assert metadata["user_visible_ttft_ms"] is not None
    assert metadata["outcome"] == "success"


def test_langfuse_observation_records_cancellation() -> None:
    client = MagicMock()
    observation = langfuse.create_langfuse_stream_observation()

    with patch.object(langfuse, "get_langfuse_client", return_value=client):
        observation.complete("cancelled")

    metadata = client.update_current_span.call_args.kwargs["metadata"]
    assert metadata["user_visible_ttft_ms"] is None
    assert metadata["outcome"] == "cancelled"
