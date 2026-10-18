from pydantic import BaseModel, Field, TypeAdapter

from src.agents.models import StreamEvent

DEFAULT_MAX_QUERY_CHARS = 2000


class QueryRequest(BaseModel):
    query: str = Field(..., max_length=DEFAULT_MAX_QUERY_CHARS)
    user_id: str | None = None
    # Omit session_id on the first demo turn: the server mints an unguessable uuid4,
    # returns it, and the UI reuses it so visitors do not share one conversation.
    session_id: str | None = None

class QueryResponse(BaseModel):
    answer: str
    session_id: str | None = None
    trace_id: str | None = None
    trace_url: str | None = None


#: The published SSE contract: the six event models, discriminated on `type`.
#: The models themselves live in the agents package, because the runtime and the
#: service produce them and a service must not import from the API layer (#679).
STREAM_EVENT_SCHEMA = TypeAdapter(StreamEvent).json_schema()
