"""The serving process's checkpoint-thread retention sweep.

`delete_stale_threads` itself is tested against a real database in
`tests/core/test_checkpointer.py`; these tests pin how the serving lifespan
runs it, what a failed sweep leaves behind, and that shutdown stops it (#673).
"""

from __future__ import annotations

import asyncio
import logging
import threading
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.core.config import settings
from src.serving import composition


async def _wait_for(predicate, *, timeout: float = 5.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not predicate():
        assert loop.time() < deadline, "condition was not reached in time"
        await asyncio.sleep(0.005)


@pytest.mark.asyncio
async def test_a_failed_sweep_is_logged_and_the_loop_keeps_sweeping(
    monkeypatch, caplog
) -> None:
    calls: list[int] = []

    async def delete(_checkpointer: object, *, retention_days: int) -> list[str]:
        calls.append(retention_days)
        if len(calls) == 1:
            raise RuntimeError("database hiccup")
        return []

    monkeypatch.setattr(composition, "delete_stale_threads", delete)
    monkeypatch.setattr(composition, "_RETENTION_SWEEP_INTERVAL_SECONDS", 0.01)

    task = asyncio.create_task(composition._sweep_checkpoint_threads(object()))
    try:
        with caplog.at_level(logging.ERROR):
            await _wait_for(lambda: len(calls) >= 2)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert set(calls) == {settings.agent.retention_days}
    assert any(
        "checkpointer.retention_sweep_failed" in record.getMessage()
        for record in caplog.records
    )


def _boot_dependency_patches(*, sweep):
    """Every lifespan dependency except the sweep, stubbed for the test."""
    pool = MagicMock()
    pool.open = AsyncMock()
    pool.close = AsyncMock()
    return [
        patch("src.serving.composition.assert_serving_schema"),
        patch("src.serving.composition.assert_agent_privileges"),
        patch("src.serving.composition._assert_served_profile_credentials"),
        patch("src.serving.composition.build_checkpointer_pool", return_value=pool),
        patch(
            "src.serving.composition.build_checkpointer",
            new=AsyncMock(return_value=object()),
        ),
        patch("src.serving.composition.init_langfuse"),
        patch(
            "src.serving.composition.prepare_native_prompts_startup", new=AsyncMock()
        ),
        patch("src.serving.composition.list_job_tools", new=AsyncMock(return_value=[])),
        patch("src.serving.composition.AgentRuntime", return_value=object()),
        patch("src.serving.composition.diagnose_langfuse_startup", new=AsyncMock()),
        patch("src.serving.composition.shutdown_langfuse", new=AsyncMock()),
        patch("src.serving.composition._sweep_checkpoint_threads", new=sweep),
    ]


def test_the_lifespan_cancels_a_running_sweep_at_shutdown() -> None:
    started = threading.Event()
    cancelled = threading.Event()

    async def sweep(_checkpointer: object) -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    with ExitStack() as stack:
        for patcher in _boot_dependency_patches(sweep=sweep):
            stack.enter_context(patcher)
        with TestClient(create_app(lifespan=composition.lifespan, docs_enabled=False)):
            assert started.wait(timeout=10)

    assert cancelled.wait(timeout=10)
