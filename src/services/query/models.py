from pydantic import BaseModel


class TableArtifact(BaseModel):
    columns: list[str]
    rows: list[list[object]]
    row_count: int


class QueryRefusal(BaseModel):
    reason: str


class QueryToolResult(BaseModel):
    answer: str
    table: TableArtifact | None = None
    refusal: QueryRefusal | None = None
