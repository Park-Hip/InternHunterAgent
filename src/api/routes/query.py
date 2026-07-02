from fastapi import APIRouter, HTTPException, Request
from src.api.schemas import QueryRequest, QueryResponse
from src.core.logger import logger
from src.agents.service import generate_agent_response

router = APIRouter()


@router.post("/agent/chat", response_model=QueryResponse)
async def query_agent(payload: QueryRequest, request: Request):
    try:
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

    except Exception as e:
        logger.error(
            "query.failed",
            session_id=payload.session_id,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail="Failed to process query")

