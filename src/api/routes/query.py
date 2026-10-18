import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent
from starlette.types import Receive

from src.agents.models import (
    InternalStreamError,
    StreamDoneEvent,
    StreamEvent,
    StreamSessionEvent,
)
from src.api.schemas import (
    STREAM_EVENT_SCHEMA,
    QueryRequest,
    QueryResponse,
)
from src.core.errors import (
    BUSY_MESSAGE,
    GENERIC_ERROR_MESSAGE,
    InvalidQueryError,
    ProviderBusyError,
)
from src.core.config import settings
from src.core.logger import logger
from src.agents.service import (
    collect_agent_response,
    stream_agent_response,
)
from src.agents.tracing.stream import (
    StreamObservationFactory,
    create_noop_stream_observation,
)


_DISCONNECT_POLL_INTERVAL_SECONDS = 0.05


def _stream_observation_factory(request: Request) -> StreamObservationFactory:
    return getattr(
        request.app.state,
        "stream_observation_factory",
        create_noop_stream_observation,
    )


class _DisconnectLoggingEventSourceResponse(EventSourceResponse):
    def __init__(self, *args, on_disconnect: Callable[[], None], **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._on_disconnect = on_disconnect

    async def listen_for_disconnect(self, receive: Receive) -> None:
        await super().listen_for_disconnect(receive)
        self._on_disconnect()


def create_router(*, limiter=None, rate_limit: str | None = None) -> APIRouter:
    router = APIRouter()
    endpoint = query_agent
    stream_endpoint = stream_query_agent
    if limiter is not None and rate_limit:
        endpoint = limiter.limit(rate_limit)(endpoint)
        stream_endpoint = limiter.limit(rate_limit)(stream_endpoint)
    router.post("/agent/chat", response_model=QueryResponse)(endpoint)
    router.post(
        "/agent/chat/stream",
        responses={
            200: {
                "content": {"text/event-stream": {"schema": STREAM_EVENT_SCHEMA}},
                "description": "Server-Sent Events",
            }
        },
    )(stream_endpoint)
    return router


async def query_agent(payload: QueryRequest, request: Request):
    try:
        if not payload.query or not payload.query.strip():
            raise InvalidQueryError("Query must not be empty.")

        logger.info(
            "query.started",
            session_id=payload.session_id,
            query_length=len(payload.query),
        )

        response = await collect_agent_response(
            query=payload.query,
            session_id=payload.session_id,
            user_id=payload.user_id,
            runtime=request.app.state.runtime,
            stream_observation_factory=_stream_observation_factory(request),
        )

        logger.info(
            "query.succeeded",
            session_id=response["session_id"],
            has_trace_id=bool(response["trace_id"]),
        )

        return QueryResponse(
            answer=response['answer'],
            session_id=response["session_id"],
            trace_id=response["trace_id"],
            trace_url=response["trace_url"],
        )

    except HTTPException:
        raise
    except InvalidQueryError:
        raise HTTPException(status_code=400, detail="Query must not be empty.")
    except ProviderBusyError as e:
        logger.warning(
            "query.provider_busy",
            session_id=payload.session_id,
            status_code=e.status_code,
        )
        raise HTTPException(status_code=e.status_code, detail=BUSY_MESSAGE) from e
    except Exception as e:
        logger.error(
            "query.failed",
            session_id=payload.session_id,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=GENERIC_ERROR_MESSAGE) from e


async def stream_query_agent(payload: QueryRequest, request: Request):
    if not payload.query or not payload.query.strip():
        raise HTTPException(status_code=400, detail="Query must not be empty.")

    disconnect_logged = False
    # The service mints a session id when the caller omits one (a first turn),
    # so the route learns the id the turn belongs to from the `session` event
    # rather than from the request (#674).
    session_id: str | None = payload.session_id
    # `done` is the terminal event. A client that goes away after it is ending a
    # completed SSE stream, which the transport reports the same way as a client
    # that leaves mid-turn: once the response is complete, the ASGI receive
    # channel answers with `http.disconnect`. The route is the only layer that
    # knows the turn finished, so it suppresses the log from here (#674).
    done_emitted = False

    def _log_client_disconnected() -> None:
        nonlocal disconnect_logged
        if disconnect_logged or done_emitted:
            return
        logger.info("stream.client_disconnected", session_id=session_id)
        disconnect_logged = True

    async def _event_source():
        nonlocal done_emitted, session_id
        stream = stream_agent_response(
            query=payload.query,
            session_id=payload.session_id,
            user_id=payload.user_id,
            runtime=request.app.state.runtime,
            stream_observation_factory=_stream_observation_factory(request),
        )
        try:
            async for item in _with_heartbeats(
                stream,
                heartbeat_seconds=float(
                    settings.config_yaml["api"]["stream_heartbeat_seconds"]
                ),
                is_disconnected=request.is_disconnected,
                on_disconnect=_log_client_disconnected,
            ):
                if isinstance(item, str):
                    yield item
                    continue
                if isinstance(item, StreamSessionEvent):
                    session_id = item.session_id
                if isinstance(item, StreamDoneEvent):
                    done_emitted = True
                # Every public frame carries `type`, including the terminal ones.
                # The published STREAM_EVENT_SCHEMA is a union discriminated on
                # `type`, so every variant lists it as required; a client that
                # builds a validator from /openapi.json rejects a frame without it.
                # The SSE `event:` line stays the authoritative name, so this is
                # additive for readers that already parse by key.
                frame = (
                    item.as_public_event()
                    if isinstance(item, InternalStreamError)
                    else item
                )
                yield _server_sent_event(event=frame.type, data=frame.model_dump())
        finally:
            await stream.aclose()

    return _DisconnectLoggingEventSourceResponse(
        _event_source(),
        on_disconnect=_log_client_disconnected,
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _next_stream_event(events: AsyncIterator[StreamEvent]) -> StreamEvent:
    return await events.__anext__()


async def _with_heartbeats(
    events: AsyncIterator[StreamEvent],
    *,
    heartbeat_seconds: float,
    is_disconnected: Callable[[], Awaitable[bool]] | None = None,
    on_disconnect: Callable[[], None] | None = None,
) -> AsyncIterator[StreamEvent | str]:
    """Pass events through while polling disconnects and commenting during idle periods."""
    next_event: asyncio.Task[StreamEvent] | None = None
    try:
        while True:
            if is_disconnected is not None and await is_disconnected():
                if on_disconnect is not None:
                    on_disconnect()
                return

            next_event = asyncio.create_task(_next_stream_event(events))
            next_heartbeat_at = asyncio.get_running_loop().time() + heartbeat_seconds
            while not next_event.done():
                now = asyncio.get_running_loop().time()
                timeout = min(
                    _DISCONNECT_POLL_INTERVAL_SECONDS,
                    max(0, next_heartbeat_at - now),
                )
                await asyncio.wait({next_event}, timeout=timeout)

                if is_disconnected is not None and await is_disconnected():
                    if on_disconnect is not None:
                        on_disconnect()
                    return

                now = asyncio.get_running_loop().time()
                if not next_event.done() and now >= next_heartbeat_at:
                    # SSE comments are ignored by compliant clients, unlike named events.
                    yield ": ping\n\n"
                    next_heartbeat_at = now + heartbeat_seconds

            try:
                yield next_event.result()
            except StopAsyncIteration:
                return
    finally:
        if next_event is not None and not next_event.done():
            next_event.cancel()
            await asyncio.gather(next_event, return_exceptions=True)


def _server_sent_event(*, event: str, data: dict[str, Any]) -> str:
    payload = ServerSentEvent(event=event, data=data)
    encoded_data = json.dumps(payload.data)
    return f"event: {payload.event}\ndata: {encoded_data}\n\n"


router = create_router()
