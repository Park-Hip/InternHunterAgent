from fastapi import APIRouter, HTTPException
from src.api.schemas import QueryRequest, QueryResponse
from src.core.logger import logger
from src.agents.service import generate_agent_response

router = APIRouter()


@router.post("/agent/query", response_model=QueryResponse)
async def query_agent(request: QueryRequest):
    try:
        logger.info(
            "query.started",
            session_id=request.session_id,
            query_length=len(request.query),
        )

        response = await generate_agent_response(
            query=request.query,
            session_id=request.session_id,
            user_id=request.user_id,
        )

        logger.info(
            "query.succeeded",
            session_id=request.session_id,
            has_trace_id=bool(response["trace_id"]),
        )

        return QueryResponse(
            answer=response['answer'],
            session_id=request.session_id,
            trace_id=response["trace_id"],
            trace_url=response["trace_url"],
        )
    
    except Exception as e:
        logger.error(
            "query.failed",
            session_id=request.session_id,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail="Failed to process query")

