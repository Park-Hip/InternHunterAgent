from typing import Literal

from pydantic import BaseModel, Field

#: What a validated SELECT's result rows represent, as classified by
#: ``result_shape.classify_result_shape``. ``rows`` enumerates matching records,
#: ``match_count`` is a single count of them, and ``summary`` is any other
#: aggregation whose rows are figures rather than matches.
ResultShape = Literal["rows", "match_count", "summary"]


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
