"""Shared path constants for the evals package.

Centralises ``ROOT`` so that every module points at the project root without
repeating ``Path(__file__).resolve().parents[1]``.  New modules should import
from here instead of computing the path themselves.
"""

from __future__ import annotations

from pathlib import Path

EVALS_ROOT = Path(__file__).resolve().parent
ROOT = EVALS_ROOT.parent
