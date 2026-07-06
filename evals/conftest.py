"""Redirect the agent's DB access to the fixture database before src.core loads.

``src/core/config.py`` instantiates a module-level ``Settings()`` (reading
``DATABASE_URL`` from the environment) the moment it is imported, and
``src/services/query/executor.py`` binds its SQLAlchemy session factory to
that value at import time too. Pytest imports conftest.py before any test
module, so setting the env var here — read straight from the YAML, not via
the settings singleton (that would import src.core.config and freeze
DATABASE_URL to whatever's already in the environment first) — is what makes
the harness hit the seeded fixture DB instead of prod.
"""

import os
from pathlib import Path

import yaml

_cfg = yaml.safe_load(Path("config/settings.yaml").read_text(encoding="utf-8"))
os.environ["DATABASE_URL"] = _cfg["eval"]["fixture"]["database_url"]
