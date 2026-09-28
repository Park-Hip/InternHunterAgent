"""Bind the fixture database before any ``src`` import freezes ``Settings()``.

The runner calls this before importing any production module.
Settings cache database URLs on first access, so a late bind could point a
live capture at the serving database instead of the frozen fixture.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from evals.fixtures.loader import fixture_database_url

ROOT = Path(__file__).resolve().parents[1]


def _git_sha() -> str:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
            )
            .strip()
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def bind_fixture_environment() -> None:
    """Set the two database URLs and tracing environment before any ``src`` import.

    Call before any production import or Settings access.
    """
    url = fixture_database_url()
    os.environ["DATABASE_URL"] = url
    os.environ["AGENT_DATABASE_URL"] = url
    os.environ["LANGFUSE_TRACING_ENVIRONMENT"] = "evaluation"
    os.environ.setdefault("LANGFUSE_ENABLED", "true")
    os.environ.setdefault("LANGFUSE_RELEASE", _git_sha())
