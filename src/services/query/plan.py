"""The typed request and the validated plan for the governed query core.

This module is the boundary the model does not cross. A model proposes a
``JobQueryRequest``; this module decides whether the request is well formed,
whether it is a shape v0 can serve, and what the plan actually is. Nothing here
touches a database, a prompt, or an agent.

Three decisions are encoded here rather than left to the model, because each one
was a legacy behavior that failed:

- **Filters are conjunctive; values inside one filter are disjunctive.** A
  multi-technology request is an intersection by default, which is the only
  reading that never returns a posting lacking one of the technologies asked
  for.
- **There is no negation filter.** No ``NOT`` and no "exclude" field exists, so
  a query that subtracts from the corpus cannot be built at all. An
  over-broadening mistake needs an operator to be possible, and none is.
- **A salary filter can be a threshold and can never be a disclosure test.**
  ``has_salary`` is not an allowlisted field, so "only postings that disclose a
  salary" is not expressible.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.core.config import settings

# ---------------------------------------------------------------------------
# Vocabulary of the contract
# ---------------------------------------------------------------------------


class QueryShape(str, Enum):
    """The seven shapes v0 supports. ``DETAIL`` looks up already-listed rows."""

    LIST = "list"
    COUNT = "count"
    GROUP_COUNT = "group_count"
    TOP_N = "top_n"
    AGGREGATE = "aggregate"
    COMPARE = "compare"
    DETAIL = "detail"


class FilterField(str, Enum):
    """Every field a request may filter on.

    This is the allowlist that enforces the 16 agent-visible columns. A field
    that is not here is not a column the agent may reach, and the six hidden
    columns are absent by construction rather than by a later filter.
    """

    ROLE = "role"
    TECHNOLOGY = "technology"
    LOCATION = "location"
    JOB_LEVEL = "job_level"
    COMPANY = "company"
    TITLE = "title"
    IS_INTERNSHIP = "is_internship"
    SALARY_CURRENCY = "salary_currency"
    SALARY_MIN = "salary_min"
    SALARY_MAX = "salary_max"
    HAS_LINK = "has_link"
    FREE_TEXT = "free_text"


class GroupField(str, Enum):
    """The fields a result may be grouped by."""

    ROLE = "role"
    LOCATION = "location"
    JOB_LEVEL = "job_level"
    TECHNOLOGY = "technology"
    COMPANY = "company"
    SALARY_CURRENCY = "salary_currency"
    IS_INTERNSHIP = "is_internship"


class Metric(str, Enum):
    """Every number v0 will compute, and no others."""

    COUNT = "count"
    SHARE = "share"
    AVERAGE_SALARY = "average_salary"
    MEDIAN_SALARY = "median_salary"


class SortField(str, Enum):
    """The fields a top-N request may rank by."""

    SALARY_MIN = "salary_min"
    SALARY_MAX = "salary_max"
    CREATED_ON = "created_on"
    LISTING_EXPIRES_ON = "listing_expires_on"
    POSTING_ID = "id"


class MatchMode(str, Enum):
    """How the values inside one filter combine."""

    ANY = "any"
    ALL = "all"


class QueryRequestError(ValueError):
    """The request is malformed, over budget, or asks for a field v0 hides.

    The caller repairs it and asks again; it is not an answer about the data.
    """


class UnsupportedQueryError(RuntimeError):
    """The request is well formed but names something v0 cannot resolve.

    The result state is ``UNSUPPORTED``, with the closest supported alternative
    named. Never a guess and never a zero.
    """


class AmbiguousQueryError(RuntimeError):
    """The request has no defensible reading and needs one narrow question."""

    def __init__(self, question: str) -> None:
        super().__init__(question)
        self.question = question


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

FilterValue = Union[str, int, float, bool]
Identifier = Annotated[str, Field(min_length=1, max_length=200)]


class Filter(BaseModel):
    """One restriction on the eligible rows.

    ``values`` is a union that excludes null, so a filter cannot smuggle a
    ``None`` past the type check to become an ``IS NULL`` test the contract
    never allows.
    """

    model_config = ConfigDict(extra="forbid")

    field: FilterField
    values: list[FilterValue] = Field(min_length=1)
    mode: MatchMode = MatchMode.ANY


class TopSpec(BaseModel):
    """How many rows, ranked by which recorded field, in which direction."""

    model_config = ConfigDict(extra="forbid")

    n: int = Field(ge=1)
    order_by: SortField
    descending: bool = True


class FilterSet(BaseModel):
    """A base filter, used on its own and as one side of a comparison."""

    model_config = ConfigDict(extra="forbid")

    filters: list[Filter] = Field(default_factory=list)


class ShareSpec(BaseModel):
    """The field and value a share is measured on.

    Kept separate from the base filters on purpose. In "what percentage of AI
    Engineer postings list Python", the base is the AI Engineer role and the
    test is the technology, and folding the test into the base would make the
    denominator exclude exactly the rows the percentage is about.
    """

    model_config = ConfigDict(extra="forbid")

    field: FilterField
    values: list[FilterValue] = Field(min_length=1)


class JobQueryRequest(BaseModel):
    """What the model proposes. One shape, one metric, at most two filter sets."""

    model_config = ConfigDict(extra="forbid")

    shape: QueryShape
    filters: list[Filter] = Field(default_factory=list)
    group_by: GroupField | None = None
    metric: Metric | None = None
    share: ShareSpec | None = None
    top: TopSpec | None = None
    # Exactly two sides for a comparison. The metric applies to both.
    compare: list[FilterSet] = Field(default_factory=list)
    ids: list[int] = Field(default_factory=list)

    @field_validator("ids")
    @classmethod
    def _positive_ids(cls, ids: list[int]) -> list[int]:
        if any(identifier <= 0 for identifier in ids):
            raise ValueError("Posting ids are positive integers")
        return sorted(set(ids))

    @model_validator(mode="after")
    def _shape_is_complete(self) -> JobQueryRequest:
        """Reject a request whose shape is missing the field that shape needs.

        Every rejection names the fix, because this error is handed back to the
        model to repair rather than shown to a user.
        """
        if self.shape is QueryShape.GROUP_COUNT and self.group_by is None:
            raise ValueError(f"shape 'group_count' requires group_by, one of: {_names(GroupField)}")
        if self.shape in (QueryShape.TOP_N,) and self.top is None:
            raise ValueError("shape 'top_n' requires top with n, order_by, and descending")
        if self.shape is QueryShape.AGGREGATE and self.metric is None:
            raise ValueError(f"shape 'aggregate' requires metric, one of: {_names(Metric)}")
        if self.shape is QueryShape.AGGREGATE and self.metric is Metric.SHARE:
            if self.share is None:
                raise ValueError("metric 'share' requires share with the field and the value tested")
            if self.share.field is FilterField.FREE_TEXT:
                raise ValueError("a share cannot be measured on free text; it has no denominator")
        if self.share is not None and self.shape is not QueryShape.AGGREGATE:
            raise ValueError(f"share belongs to an aggregate with metric 'share', not to '{self.shape.value}'")
        if self.shape is QueryShape.COMPARE and len(self.compare) != 2:
            raise ValueError("shape 'compare' requires exactly two filter sets in compare")
        if self.shape is QueryShape.DETAIL and not self.ids:
            raise ValueError("shape 'detail' requires the posting ids in ids")
        if self.shape is not QueryShape.DETAIL and self.ids:
            raise ValueError(f"ids belong to shape 'detail', not '{self.shape.value}'")
        if self.shape is not QueryShape.COMPARE and self.compare:
            raise ValueError(f"compare belongs to shape 'compare', not '{self.shape.value}'")
        return self

    def base_filters(self) -> list[Filter]:
        """The filters that define the eligible set for this shape."""
        if self.shape is QueryShape.COMPARE:
            return []
        return self.filters


def _names(enum_cls: type[Enum]) -> str:
    return ", ".join(member.value for member in enum_cls)


# ---------------------------------------------------------------------------
# The validated plan
# ---------------------------------------------------------------------------


class NormalizedFilter(BaseModel):
    """One restriction after vocabulary resolution.

    ``values`` holds canonical stored values or whole tokens, never the text the
    model typed. ``basis`` records how the filter will be matched, so the answer
    can disclose that a technology match was a token match and that a role match
    fell back to posting text.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    field: FilterField
    values: tuple[Any, ...]
    mode: MatchMode
    basis: Literal["column", "technology_token", "free_text", "fallback"]
    # What the caller asked for, kept for the applied-criteria record.
    requested: tuple[Any, ...] = ()


class QueryPlan(BaseModel):
    """A request that passed validation, in the terms the compiler emits."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    shape: QueryShape
    filters: tuple[NormalizedFilter, ...] = ()
    group_by: GroupField | None = None
    metric: Metric | None = None
    # The filter a share is measured on, held apart from the base filters.
    share: NormalizedFilter | None = None
    top: TopSpec | None = None
    sides: tuple[tuple[NormalizedFilter, ...], ...] = ()
    ids: tuple[int, ...] = ()
    caveats: tuple[str, ...] = ()


def query_limits() -> dict[str, int]:
    """The budgets a request must fit inside, read once per plan."""
    query = settings.config_yaml.get("agent", {}).get("query")
    if not isinstance(query, dict):
        raise ValueError("Missing 'agent.query' section in config/settings.yaml")

    def positive_int(name: str) -> int:
        value = query.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"agent.query.{name} must be a positive integer in config/settings.yaml")
        return value

    return {
        "max_rows": positive_int("max_rows"),
        "max_detail_rows": positive_int("max_detail_ids"),
        "max_filters": positive_int("max_filters"),
        "max_values_per_filter": positive_int("max_values_per_filter"),
        "max_group_values": positive_int("max_group_values"),
        "max_top_n": positive_int("max_top_n"),
    }
