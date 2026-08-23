"""Data models owned by the evaluation instrument."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class SemanticJudgeResult:
    """A persisted diagnostic result from DeepEval semantic grading."""

    status: str
    score: float | None
    confidence: float | None
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
