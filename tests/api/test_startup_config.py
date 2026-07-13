from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.app import app
from src.core.config import ConfigLoadError


class StartupConfigTests(unittest.TestCase):
    def test_lifespan_fails_fast_when_config_load_fails(self) -> None:
        with patch("src.api.app.load_settings", side_effect=ConfigLoadError("bad config")):
            with self.assertRaises(ConfigLoadError) as ctx:
                with TestClient(app):
                    pass

        self.assertIn("bad config", str(ctx.exception))
