"""Shared path constants for the evals package.

Centralises ``ROOT`` so that every module points at the project root without
repeating ``Path(__file__).resolve().parents[1]``.  New modules should import
from here instead of computing the path themselves.
"""

from __future__ import annotations

from pathlib import Path

EVALS_ROOT = Path(__file__).resolve().parent
ROOT = EVALS_ROOT.parent

# Versioned calibration corpora. Extend this dict when a new calibration version
# is produced; callers in evals.calibration read the keys they need.
CALIBRATION_VERSIONS: dict[str, Path] = {
    "v7": EVALS_ROOT / "calibration_v7.yaml",
    "v8": EVALS_ROOT / "calibration_v8.yaml",
}

# Release gate configuration for the live evaluation pipeline.
RELEASE_GATE_PATH = EVALS_ROOT / "calibration_release_gate.yaml"
