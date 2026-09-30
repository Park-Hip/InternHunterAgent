"""The typed result of a governed query.

One result type serves search and analytics, so a percentage and a list cannot
drift apart in how they report what was matched and what was withheld. The
fields below are the ones the answer depends on: the state, the criteria that
were actually applied, the full matching total, the rows that were displayed, and
the exclusions that make a number honest.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.services.query.plan import FilterField, QueryShape


class QueryState(str, Enum):
    """The outcome of one governed query.

    ``ANSWERED`` and ``EMPTY`` are both data answers; the rest are refusals to
    answer without inventing. They are separate states so a caller can never
    render an error the way it renders a zero.
    """

    ANSWERED = "answered"
    EMPTY = "empty"
    UNSUPPORTED = "unsupported"
    AMBIGUOUS = "ambiguous"
    ERROR = "error"


class AppliedCriterion(BaseModel):
    """One restriction as it was applied, after vocabulary resolution.

    ``side`` is the comparison side the criterion belongs to, and None for a
    single-set request, so a comparison can report each side's own criteria
    rather than one merged list.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    field: FilterField
    values: tuple[Any, ...]
    basis: str
    side: int | None = None


class GroupRow(BaseModel):
    """One recorded value and how many rows carry it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    value: str
    count: int


class SalaryAggregate(BaseModel):
    """One currency's figure, with the rows it was computed from."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    currency: str
    rows: int
    with_salary_min: int
    value: float | None
    excluded_no_salary: int


class ShareResult(BaseModel):
    """A share with its denominator and its excluded count."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    numerator: int
    denominator: int
    excluded_null_field: int
    percent: float | None


class QueryResult(BaseModel):
    """Everything an answer needs, and nothing that invents it."""

    model_config = ConfigDict(extra="forbid")

    state: QueryState
    shape: QueryShape
    # A request the model can fix by re-asking, as opposed to a failure it
    # cannot. The tool renders the two differently so a repairable rejection
    # never reads as a dead end.
    repairable: bool = False
    applied: list[AppliedCriterion] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    # The full matching set, always computed before any display limit.
    match_total: int | None = None
    displayed_count: int = 0
    truncated: bool = False
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    count: int | None = None
    groups: list[GroupRow] = Field(default_factory=list)
    # The two counts of a comparison, side 0 and side 1, in that order.
    compare_sides: list[int] = Field(default_factory=list)
    aggregate: list[SalaryAggregate] = Field(default_factory=list)
    share: ShareResult | None = None
    # Rows excluded from a ranking because the ranked field was empty.
    skipped_unranked: int | None = None
    # A sentence for the model to use when there are no rows to show.
    message: str | None = None

    @property
    def is_data_answer(self) -> bool:
        return self.state in (QueryState.ANSWERED, QueryState.EMPTY)
