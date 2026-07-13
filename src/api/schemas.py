from pydantic import BaseModel, Field

DEFAULT_MAX_QUERY_CHARS = 2000

class QueryRequest(BaseModel):
    query: str = Field(..., max_length=DEFAULT_MAX_QUERY_CHARS)
    user_id: str | None = None
    session_id: str | None = None

class QueryResponse(BaseModel):
    answer: str
    session_id: str | None = None
    trace_id: str | None = None
    trace_url: str | None = None
