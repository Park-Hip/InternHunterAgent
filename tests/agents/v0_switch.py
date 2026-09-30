"""Flip the served bundle for one test, in memory.

The cutover is one config key, and the tests that describe the other bundle need to
say so explicitly. This edits the loaded settings dict rather than the file, so a
test cannot leave the working tree modified and no settings reload is needed.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def agent_v0(value: bool) -> Iterator[None]:
    """Run the block with `agent.agent_v0` set to `value`, then restore it."""
    from src.core.config import settings

    agent = settings.config_yaml["agent"]
    original = agent["agent_v0"]
    agent["agent_v0"] = value
    try:
        yield
    finally:
        agent["agent_v0"] = original
