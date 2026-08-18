from pydantic import BaseModel, Field


class TableArtifact(BaseModel):
    columns: list[str]
    rows: list[list[object]]
    row_count: int
    truncated: bool = False


class QueryRefusal(BaseModel):
    reason: str
    glossary_token: str | None = None


class HedgeObligation(BaseModel):
    glossary_token: str


class QueryToolResult(BaseModel):
    answer: str = ""
    table: TableArtifact | None = None
    refusal: QueryRefusal | None = None
    obligations: list[HedgeObligation] = Field(default_factory=list)


class ValidationResult(BaseModel):
    valid: bool
    sql: str
    reason: str = ""
