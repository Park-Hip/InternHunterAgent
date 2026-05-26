from pydantic import BaseModel

class QueryRequest(BaseModel):
    query: str
    user_id: str | None = None
    session_id: str | None = None

class QueryResponse(BaseModel):
    answer: str
    session_id: str | None = None
    trace_id: str | None = None
    trace_url: str | None = None