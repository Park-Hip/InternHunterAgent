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
            "AGENT_DATABASE_URL": "postgresql+psycopg://internhunter_agent:internhunter@localhost:5433/internhunter",
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
            "Missing required environment variables: AGENT_DATABASE_URL, DATABASE_URL",
            str(ctx.exception),
        )

    def test_load_settings_boots_with_only_the_selected_providers_key(self) -> None:
        """No provider key is required at boot; the selected branch validates its own."""
        selected_provider_env = {
            "DATABASE_URL": "postgresql+psycopg://internhunter:internhunter@localhost:5433/internhunter",
            "AGENT_DATABASE_URL": "postgresql+psycopg://internhunter_agent:internhunter@localhost:5433/internhunter",
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
        self.assertIsNone(settings.GOOGLE_API_KEY)
        self.assertIsNone(settings.OPENROUTER_API_KEY)

    def test_load_settings_allows_missing_langfuse_credentials(self) -> None:
        required_env = {
            "DATABASE_URL": "postgresql+psycopg://internhunter:internhunter@localhost:5433/internhunter",
            "AGENT_DATABASE_URL": "postgresql+psycopg://internhunter_agent:internhunter@localhost:5433/internhunter",
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

    def test_configured_secret_prefers_environment_over_dotenv(self) -> None:
        environment_variable = "TEST_CONFIGURED_PROVIDER_KEY"
        with tempfile.TemporaryDirectory() as tmp_dir:
            dotenv_path = Path(tmp_dir) / ".env"
            dotenv_path.write_text(
                f"{environment_variable}=dotenv-key\n", encoding="utf-8"
            )
            config_module.Settings.model_config = SettingsConfigDict(
                env_file=str(dotenv_path),
                env_file_encoding="utf-8",
                extra="ignore",
            )

            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(
                    config_module.get_configured_secret(environment_variable),
                    "dotenv-key",
                )
                with patch.dict(
                    os.environ, {environment_variable: "process-key"}, clear=False
                ):
                    self.assertEqual(
                        config_module.get_configured_secret(environment_variable),
                        "process-key",
                    )

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

    def test_api_config_rejects_nonpositive_stream_heartbeat(self) -> None:
        config = {"api": {"stream_heartbeat_seconds": 0}}

        with self.assertRaisesRegex(
            config_module.ConfigLoadError, "stream_heartbeat_seconds"
        ):
            config_module._validate_api_config(config)

    def test_api_config_rejects_nonfinite_stream_heartbeat(self) -> None:
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                config = {"api": {"stream_heartbeat_seconds": value}}
                with self.assertRaisesRegex(
                    config_module.ConfigLoadError, "stream_heartbeat_seconds"
                ):
                    config_module._validate_api_config(config)

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


class DuplicateKeyTests(unittest.TestCase):
    """A repeated YAML key is a contradiction, not a merge."""

    def _write(self, body: str) -> Path:
        path = Path(tempfile.mkdtemp()) / "prompts.yaml"
        path.write_text(body, encoding="utf-8")
        return path

    def test_duplicate_key_in_the_same_mapping_is_refused(self) -> None:
        path = self._write("prompts:\n  system_prompt_v0: |\n  system_prompt_v0: |\n    first\n    second\n")
        with self.assertRaisesRegex(config_module.ConfigLoadError, "duplicate key 'system_prompt_v0'"):
            config_module._load_yaml_file(path)

    def test_duplicate_key_names_the_line_it_appears_on(self) -> None:
        path = self._write("a: 1\nb: 2\na: 3\n")
        with self.assertRaisesRegex(config_module.ConfigLoadError, "line 3"):
            config_module._load_yaml_file(path)

    def test_nested_duplicate_key_is_refused(self) -> None:
        path = self._write("prompts:\n  system: |\n    text\n  system: |\n    text\n")
        with self.assertRaisesRegex(config_module.ConfigLoadError, "duplicate key 'system'"):
            config_module._load_yaml_file(path)

    def test_repeated_value_under_distinct_keys_is_fine(self) -> None:
        path = self._write("prompts:\n  system: |\n    same text\n  system_prompt_v0: |\n    same text\n")
        self.assertEqual(config_module._load_yaml_file(path)["prompts"]["system"], "same text\n")

    def test_shipped_config_files_have_no_duplicate_keys(self) -> None:
        """The file that carried the defect must not be able to acquire another."""
        for path in sorted((config_module.CONFIG_DIR).rglob("*.yaml")):
            with self.subTest(config=path.name):
                self.assertIsInstance(config_module._load_yaml_file(path), dict)
