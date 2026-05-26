from fastapi import APIRouter, HTTPException
from src.api.schemas import QueryRequest, QueryResponse
from src.core.logger import logger
from src.agents.service import generate_agent_response

router = APIRouter()

@router.post("/agent/query", response_model=QueryResponse)
async def query_agent(request: QueryRequest):
    try:
        query = request.query
        response = await generate_agent_response(query)
        return QueryResponse(
            answer=response,
            session_id=request.session_id,
        )
    
    except Exception as e:
        logger.error("Failed to process query", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to process query")

