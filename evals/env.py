"""Bind the fixture database before any ``src`` import freezes ``Settings()``.

The runner calls this before importing any production module.
Settings cache database URLs on first access, so a late bind could point a
live capture at the serving database instead of the frozen fixture.

The serving DSN stays on the fixture owner, which is also what the loader uses
to build and seed the schema. The agent DSN is the fixture reader role, whose
column grants mirror production's ``internhunter_agent`` boundary (#730).
"""

from __future__ import annotations

import os
import subprocess

from evals._paths import ROOT
from evals.fixtures.loader import fixture_database_url, fixture_reader_database_url


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
    os.environ["DATABASE_URL"] = fixture_database_url()
    os.environ["AGENT_DATABASE_URL"] = fixture_reader_database_url()
    os.environ["LANGFUSE_TRACING_ENVIRONMENT"] = "evaluation"
    os.environ.setdefault("LANGFUSE_ENABLED", "true")
    os.environ.setdefault("LANGFUSE_RELEASE", _git_sha())
