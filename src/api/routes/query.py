import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent
from src.api.schemas import QueryRequest, QueryResponse
from src.core.errors import BUSY_MESSAGE, InvalidQueryError, ProviderBusyError
from src.core.logger import logger
from src.agents.service import generate_agent_response, stream_agent_response


def create_router(*, limiter=None, rate_limit: str | None = None) -> APIRouter:
    router = APIRouter()
    endpoint = query_agent
    stream_endpoint = stream_query_agent
    if limiter is not None and rate_limit:
        endpoint = limiter.limit(rate_limit)(endpoint)
        stream_endpoint = limiter.limit(rate_limit)(stream_endpoint)
    router.post("/agent/chat", response_model=QueryResponse)(endpoint)
    router.post("/agent/chat/stream")(stream_endpoint)
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

        response = await generate_agent_response(
            query=payload.query,
            session_id=payload.session_id,
            user_id=payload.user_id,
            runtime=request.app.state.runtime,
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
        raise HTTPException(status_code=500, detail="Failed to process query")


async def stream_query_agent(payload: QueryRequest, request: Request):
    if not payload.query or not payload.query.strip():
        raise HTTPException(status_code=400, detail="Query must not be empty.")

    async def _event_source():
        async for event in stream_agent_response(
            query=payload.query,
            session_id=payload.session_id,
            user_id=payload.user_id,
            runtime=request.app.state.runtime,
        ):
            event_type = event["type"]
            data = {key: value for key, value in event.items() if key != "type"}
            yield _server_sent_event(event=event_type, data=data)

    return EventSourceResponse(
        _event_source(),
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _server_sent_event(*, event: str, data: dict[str, str | None]) -> str:
    payload = ServerSentEvent(event=event, data=data)
    encoded_data = json.dumps(payload.data)
    return f"event: {payload.event}\ndata: {encoded_data}\n\n"


router = create_router()
