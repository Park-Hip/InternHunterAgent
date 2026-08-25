from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic_settings import SettingsConfigDict

from src.core import config as config_module


class ConfigLoadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_model_config = dict(config_module.Settings.model_config)

    def tearDown(self) -> None:
        config_module.Settings.model_config = SettingsConfigDict(**self.original_model_config)
        config_module.load_settings(force_reload=True)

    def test_load_settings_uses_project_root_when_cwd_changes(self) -> None:
        required_env = {
            "DATABASE_URL": "postgresql+psycopg://internhunter:internhunter@localhost:5433/internhunter",
            "GROQ_API_KEY": "groq-test-key",
            "LANGFUSE_SECRET_KEY": "langfuse-secret",
            "LANGFUSE_PUBLIC_KEY": "langfuse-public",
        }
        config_module.Settings.model_config = SettingsConfigDict(
            env_file=None,
            env_file_encoding="utf-8",
            extra="ignore",
        )

        original_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(os.environ, required_env, clear=False):
                try:
                    os.chdir(tmp_dir)
                    settings = config_module.load_settings(force_reload=True)
                finally:
                    os.chdir(original_cwd)

        self.assertIn("agent", settings.config_yaml)
        self.assertIn("prompts", settings.prompts_yaml)
        self.assertIn("api", settings.ingestion_yaml)
        self.assertTrue(settings.tech_vocabulary_yaml)

    def test_load_settings_raises_clear_error_for_missing_required_env_var(self) -> None:
        required_env = {
            "GROQ_API_KEY": "groq-test-key",
            "LANGFUSE_SECRET_KEY": "langfuse-secret",
            "LANGFUSE_PUBLIC_KEY": "langfuse-public",
        }
        config_module.Settings.model_config = SettingsConfigDict(
            env_file=None,
            env_file_encoding="utf-8",
            extra="ignore",
        )

        with patch.dict(os.environ, required_env, clear=True):
            with self.assertRaises(config_module.ConfigLoadError) as ctx:
                config_module.load_settings(force_reload=True)

        self.assertIn("Failed to load runtime settings.", str(ctx.exception))
        self.assertIn(
            "Missing required environment variables: DATABASE_URL",
            str(ctx.exception),
        )

    def test_load_settings_boots_with_only_the_selected_providers_key(self) -> None:
        """No provider key is required at boot; the selected branch validates its own."""
        selected_provider_env = {
            "DATABASE_URL": "postgresql+psycopg://internhunter:internhunter@localhost:5433/internhunter",
            "DEEPSEEK_API_KEY": "deepseek-test-key",
            "LANGFUSE_SECRET_KEY": "langfuse-secret",
            "LANGFUSE_PUBLIC_KEY": "langfuse-public",
        }
        config_module.Settings.model_config = SettingsConfigDict(
            env_file=None,
            env_file_encoding="utf-8",
            extra="ignore",
        )

        with patch.dict(os.environ, selected_provider_env, clear=True):
            settings = config_module.load_settings(force_reload=True)

        self.assertEqual(settings.DEEPSEEK_API_KEY, "deepseek-test-key")
        self.assertIsNone(settings.GROQ_API_KEY)
        self.assertIsNone(settings.OPENROUTER_API_KEY)

    def test_load_settings_allows_missing_langfuse_credentials(self) -> None:
        required_env = {
            "DATABASE_URL": "postgresql+psycopg://internhunter:internhunter@localhost:5433/internhunter",
            "DEEPSEEK_API_KEY": "deepseek-test-key",
        }
        config_module.Settings.model_config = SettingsConfigDict(
            env_file=None,
            env_file_encoding="utf-8",
            extra="ignore",
        )

        with patch.dict(os.environ, required_env, clear=True):
            settings = config_module.load_settings(force_reload=True)

        self.assertIsNone(settings.LANGFUSE_SECRET_KEY)
        self.assertIsNone(settings.LANGFUSE_PUBLIC_KEY)

    def test_importing_config_module_does_not_validate_env_at_import_time(self) -> None:
        with patch.dict(
            os.environ,
            {
                "PATH": os.environ.get("PATH", ""),
                "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
            },
            clear=True,
        ):
            module = importlib.reload(config_module)

        self.assertTrue(hasattr(module, "settings"))
        self.assertEqual(module.settings.__class__.__name__, "_SettingsProxy")

    def test_observability_taxonomy_rejects_duplicate_entry_points(self) -> None:
        config = {
            "observability": {
                "langfuse": {
                    "environments": {"default": "local", "allowed": ["local"]},
                    "tag_taxonomy": {"entry_points": ["api:chat", "api:chat"]},
                }
            }
        }

        with self.assertRaisesRegex(config_module.ConfigLoadError, "Duplicate values"):
            config_module._validate_observability_config(config)
