"""Regression coverage for the generated AGENTS.md contract."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_agent_instructions_are_current() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/sync_agent_instructions.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
