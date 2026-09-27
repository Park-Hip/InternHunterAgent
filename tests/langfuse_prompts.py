"""Builders for the native prompt objects a managed Langfuse deployment returns.

A resolved managed prompt carries the SDK's own prompt client, and that object
is what `propagate_attributes(prompt=...)` links to a generation. Tests build
the real type so a lockfile or SDK change that breaks prompt linking fails the
suite instead of a live request.
"""

from __future__ import annotations

from collections.abc import Mapping

from langfuse.api.prompts.types import Prompt_Text
from langfuse.model import TextPromptClient

PROMPT_NAME_ATTRIBUTE = "langfuse.observation.prompt.name"
PROMPT_VERSION_ATTRIBUTE = "langfuse.observation.prompt.version"


def prompt_link(
    span_attributes: Mapping[str, object] | None,
) -> tuple[object, object]:
    """Read the prompt name and version a span was linked to."""
    attributes = span_attributes or {}
    return (
        attributes.get(PROMPT_NAME_ATTRIBUTE),
        attributes.get(PROMPT_VERSION_ATTRIBUTE),
    )


def native_prompt_client(
    name: str,
    version: int,
    *,
    text: str = "REMOTE",
    is_fallback: bool = False,
) -> TextPromptClient:
    """Build the object `Langfuse.get_prompt` returns for a managed prompt."""
    return TextPromptClient(
        Prompt_Text(
            type="text",
            prompt=text,
            name=name,
            version=version,
            config={},
            labels=[] if is_fallback else ["production"],
            tags=[],
            commit_message="native prompt fixture" if not is_fallback else None,
        ),
        is_fallback=is_fallback,
    )
