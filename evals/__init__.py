"""Public API for the ``evals`` package.

Individual submodules are the source of truth; this package re-exports the
symbols that external callers (``driver``, ``score``, tests) depend on most.
"""

from __future__ import annotations

from evals._paths import ROOT, EVALS_ROOT  # noqa: F401 — imported for symmetry

from evals.grader import grade_evidence, summarize  # noqa: F401
from evals.replay import run_replay, run_active_replays  # noqa: F401
from evals.scenarios import load_scenarios  # noqa: F401
