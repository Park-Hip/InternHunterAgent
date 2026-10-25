"""Generate one read-only SQL statement from a standalone request.

The model call is injected as a small protocol, so this module depends on no
provider SDK, no LangChain, no prompt registry, and no tracing implementation.
The caller resolves the release text for ``sql_generation`` and
``schema_context`` and owns whatever observability wraps the model call; a test
therefore drives generation with a stub model and no agent runtime.

Prompt assembly stays here because it is part of the query contract: the model
always receives the rules, a blank line, the schema context, a blank line, and
the request. The trace adapter only carries the resulting text to its model.
"""

from __future__ import annotations

from typing import Protocol


class SqlGenerationModel(Protocol):
    """One model client: the assembled prompt in, the raw reply text out."""

    async def complete(self, prompt: str) -> str:
        """Return the model's reply for one assembled prompt."""


def build_prompt(
    *,
    sql_generation: str,
    schema_context: str,
    request: str,
) -> str:
    """Join the two prompt surfaces and the request into the one model message."""
    return f"{sql_generation}\n\n{schema_context}\n\nQuestion: {request}"


async def generate_sql(
    *,
    request: str,
    sql_generation: str,
    schema_context: str,
    model: SqlGenerationModel,
) -> str:
    """Return the stripped statement the injected model wrote for one request.

    An empty reply is returned unchanged: ``validate_sql`` owns the refusal and
    turns it into a ``rejected`` failure the model can act on.
    """
    reply = await model.complete(
        build_prompt(
            sql_generation=sql_generation,
            schema_context=schema_context,
            request=request,
        )
    )
    return reply.strip()
