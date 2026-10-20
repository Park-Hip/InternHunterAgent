"""Framework-neutral failures the job-query tools raise at the MCP boundary.

The behavior modules never write user-facing sentences for a failure. They
raise one of these, the MCP wrapper translates it to a ``ToolError``, and the
model receives a ``status="error"`` tool message whose detail is a short,
English, model-facing string. All user-facing wording lives in the system
prompt (#702).
"""

from typing import Literal

#: The closed set of failure kinds a job-query tool can report.
#:
#: ``rejected`` is a deterministic refusal the model can act on: the
#: validator's shape check, the database's syntax refusal, the executor's
#: offset-order check, or the database's column grant. ``unknown_column`` is a
#: column the schema does not have, ``timeout`` the server cancelling a slow
#: statement, ``too_large`` the byte budget refusing an oversized result, and
#: ``unavailable`` any other database failure.
FailureKind = Literal[
    "rejected", "unknown_column", "timeout", "too_large", "unavailable"
]


class ToolFailure(Exception):
    """A model-facing tool failure: a kind and a short English detail.

    The kind is stable and machine-readable, so the system prompt can name the
    one case that needs wording of its own (``unknown_column``). The detail is
    for the model, never for the reader, and never carries a raw driver
    message: those can name the database host.
    """

    def __init__(self, kind: FailureKind, detail: str) -> None:
        super().__init__(f"{kind}: {detail}")
        self.kind = kind
        self.detail = detail
