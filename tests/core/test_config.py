from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from collections.abc import Callable
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
        """No provider key is needed to load settings; the serving boot guard validates the selected deployment's key."""
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

        self.assertIsNone(settings.GROQ_API_KEY)
        self.assertIsNone(settings.GOOGLE_API_KEY)
        self.assertIsNone(settings.OPENROUTER_API_KEY)
        agent = settings.agent
        assert agent is not None
        react = agent.deployment_for("react")
        self.assertEqual(react.name, "deepseek_flash")
        self.assertEqual(react.model, "deepseek/deepseek-flash")
        self.assertEqual(react.api_key_env, "DEEPSEEK_API_KEY")
        self.assertEqual(agent.stream_turn_timeout_seconds, 120)

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
                    "tag_taxonomy": {
                        "entry_points": ["api:chat-stream", "api:chat-stream"]
                    },
                }
            }
        }

        with self.assertRaisesRegex(config_module.ConfigLoadError, "Duplicate values"):
            config_module._validate_observability_config(config)

    def test_database_config_rejects_missing_section(self) -> None:
        with self.assertRaisesRegex(config_module.ConfigLoadError, "database"):
            config_module._validate_database_config({})

    def test_database_config_rejects_malformed_connect_timeout(self) -> None:
        for value in (0, -1, True, "5", 5.0):
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    config_module.ConfigLoadError, "connect_timeout_seconds"
                ):
                    config_module._validate_database_config(
                        {"database": {"connect_timeout_seconds": value}}
                    )


def _agent_section() -> dict:
    """A minimal valid agent section that tests mutate one field at a time."""

    return {
        "agent": {
            "providers": {
                "deepseek_flash": {
                    "model": "deepseek/deepseek-flash",
                    "api_key_env": "DEEPSEEK_API_KEY",
                },
            },
            "stream_turn_timeout_seconds": 120,
            "react": {
                "deployment": "deepseek_flash",
                "temperature": 0.2,
                "max_tokens": 2048,
                "timeout": 30,
                "max_attempts": 2,
                "streaming": True,
                "provider_options": {"thinking": "disabled"},
            },
            "sql_generation": {
                "deployment": "deepseek_flash",
                "temperature": 0.0,
                "max_tokens": 1024,
                "timeout": 30,
                "max_attempts": 2,
                "streaming": False,
                "provider_options": {"thinking": "disabled"},
            },
            "memory": {"max_turns": 6},
        }
    }


class AgentSectionTests(unittest.TestCase):
    """The agent section is validated and resolved once, at load (#656)."""

    def test_resolves_one_typed_deployment_per_profile(self) -> None:
        agent = config_module._build_agent_settings(_agent_section())

        react = agent.deployment_for("react")
        self.assertEqual(react.name, "deepseek_flash")
        self.assertEqual(react.provider, "deepseek")
        self.assertEqual(react.model, "deepseek/deepseek-flash")
        self.assertEqual(react.api_key_env, "DEEPSEEK_API_KEY")
        self.assertIsInstance(react.options, config_module.DeepSeekOptions)
        self.assertEqual(
            react.options.to_model_kwargs(),
            {"extra_body": {"thinking": {"type": "disabled"}}},
        )
        self.assertEqual(react.profile.max_tokens, 2048)
        self.assertEqual(agent.stream_turn_timeout_seconds, 120)
        self.assertEqual(agent.max_turns, 6)
        self.assertEqual(set(agent.deployments), {"react", "sql_generation"})

    def test_provider_is_derived_from_the_model_prefix(self) -> None:
        config = _agent_section()
        config["agent"]["react"]["provider_options"] = {}
        config["agent"]["sql_generation"]["provider_options"] = {}
        config["agent"]["providers"]["deepseek_flash"]["model"] = (
            "anthropic/claude-sonnet-4-5"
        )

        agent = config_module._build_agent_settings(config)

        deployment = agent.deployment_for("react")
        self.assertEqual(deployment.provider, "anthropic")
        self.assertEqual(deployment.model, "anthropic/claude-sonnet-4-5")

    def test_uncontracted_provider_accepts_only_empty_options(self) -> None:
        config = _agent_section()
        config["agent"]["providers"]["deepseek_flash"]["model"] = "openai/gpt-5"
        config["agent"]["react"]["provider_options"] = {}
        config["agent"]["sql_generation"]["provider_options"] = {}

        agent = config_module._build_agent_settings(config)
        deployment = agent.deployment_for("react")
        self.assertEqual(deployment.provider, "openai")
        self.assertEqual(deployment.options.to_model_kwargs(), {})

        config["agent"]["react"]["provider_options"] = {"reasoning_effort": "low"}
        with self.assertRaisesRegex(
            config_module.ConfigLoadError, "not supported for provider 'openai'"
        ):
            config_module._build_agent_settings(config)

    def test_missing_agent_section_is_refused(self) -> None:
        with self.assertRaisesRegex(
            config_module.ConfigLoadError, "missing 'agent' section"
        ):
            config_module._build_agent_settings({})

    def test_empty_provider_allowlist_is_refused(self) -> None:
        config = _agent_section()
        config["agent"]["providers"] = {}

        with self.assertRaisesRegex(
            config_module.ConfigLoadError, "nonempty mapping"
        ):
            config_module._build_agent_settings(config)

    def test_stream_turn_timeout_refuses_missing_or_invalid_values(self) -> None:
        for value in ("missing", None, 0, -5, True, "120", 120.5):
            with self.subTest(value=value):
                config = _agent_section()
                if value == "missing":
                    del config["agent"]["stream_turn_timeout_seconds"]
                else:
                    config["agent"]["stream_turn_timeout_seconds"] = value
                with self.assertRaises(config_module.ConfigLoadError) as ctx:
                    config_module._build_agent_settings(config)
                self.assertIn(
                    "agent.stream_turn_timeout_seconds", str(ctx.exception)
                )

    def test_memory_max_turns_refuses_missing_or_invalid_values(self) -> None:
        for value in ("missing", None, 0, -1, True, "6", 6.0):
            with self.subTest(value=value):
                config = _agent_section()
                if value == "missing":
                    del config["agent"]["memory"]["max_turns"]
                else:
                    config["agent"]["memory"]["max_turns"] = value
                with self.assertRaises(config_module.ConfigLoadError) as ctx:
                    config_module._build_agent_settings(config)
                self.assertIn("agent.memory.max_turns", str(ctx.exception))

    def test_memory_rejects_a_leftover_compaction_section(self) -> None:
        config = _agent_section()
        config["agent"]["memory"]["compaction"] = {
            "trigger_messages": 48,
            "keep_messages": 12,
        }

        with self.assertRaises(config_module.ConfigLoadError) as ctx:
            config_module._build_agent_settings(config)

        self.assertIn("agent.memory.compaction", str(ctx.exception))

    def test_missing_memory_section_is_refused(self) -> None:
        config = _agent_section()
        del config["agent"]["memory"]

        with self.assertRaisesRegex(
            config_module.ConfigLoadError, "missing 'agent.memory' section"
        ):
            config_module._build_agent_settings(config)

    def test_malformed_agent_sections_refuse_with_the_yaml_path(self) -> None:
        cases: list[tuple[str, Callable[[dict], None], list[str]]] = [
            (
                "unknown deployment",
                lambda config: config["agent"]["react"].update(
                    {"deployment": "missing"}
                ),
                ["agent.react.deployment", "unknown deployment"],
            ),
            (
                "unqualified model",
                lambda config: config["agent"]["providers"][
                    "deepseek_flash"
                ].update({"model": "deepseek-flash"}),
                ["agent.providers.deepseek_flash.model", "provider-qualified"],
            ),
            (
                "mis-cased provider prefix",
                lambda config: config["agent"]["providers"][
                    "deepseek_flash"
                ].update({"model": "DeepSeek/deepseek-flash"}),
                ["agent.providers.deepseek_flash.model", "provider-qualified"],
            ),
            (
                "secret pasted as the key reference",
                lambda config: config["agent"]["providers"][
                    "deepseek_flash"
                ].update({"api_key_env": "sk-secret"}),
                [
                    "agent.providers.deepseek_flash.api_key_env",
                    "must name an environment variable",
                ],
            ),
            (
                "removed provider key",
                lambda config: config["agent"]["providers"][
                    "deepseek_flash"
                ].update({"provider": "deepseek"}),
                [
                    "agent.providers.deepseek_flash.provider",
                    "Extra inputs are not permitted",
                ],
            ),
            (
                "unknown profile knob",
                lambda config: config["agent"]["react"].update({"rety": 1}),
                ["agent.react.rety", "Extra inputs are not permitted"],
            ),
            (
                "boolean temperature",
                lambda config: config["agent"]["react"].update(
                    {"temperature": True}
                ),
                ["agent.react.temperature", "must be a number"],
            ),
            (
                "string temperature",
                lambda config: config["agent"]["react"].update(
                    {"temperature": "0.2"}
                ),
                ["agent.react.temperature", "must be a number"],
            ),
            (
                "negative temperature",
                lambda config: config["agent"]["react"].update(
                    {"temperature": -0.1}
                ),
                ["agent.react.temperature", "greater than or equal to 0"],
            ),
            (
                "infinite temperature",
                lambda config: config["agent"]["react"].update(
                    {"temperature": float("inf")}
                ),
                ["agent.react.temperature", "finite"],
            ),
            (
                "boolean max_tokens",
                lambda config: config["agent"]["react"].update({"max_tokens": True}),
                ["agent.react.max_tokens", "valid integer"],
            ),
            (
                "zero max_tokens",
                lambda config: config["agent"]["react"].update({"max_tokens": 0}),
                ["agent.react.max_tokens", "greater than 0"],
            ),
            (
                "missing timeout",
                lambda config: config["agent"]["react"].pop("timeout"),
                ["agent.react.timeout", "Field required"],
            ),
            (
                "boolean timeout",
                lambda config: config["agent"]["react"].update({"timeout": True}),
                ["agent.react.timeout", "must be a number"],
            ),
            (
                "missing max_attempts",
                lambda config: config["agent"]["react"].pop("max_attempts"),
                ["agent.react.max_attempts", "Field required"],
            ),
            (
                "zero max_attempts",
                lambda config: config["agent"]["react"].update(
                    {"max_attempts": 0}
                ),
                ["agent.react.max_attempts", "greater than 0"],
            ),
            (
                "negative max_attempts",
                lambda config: config["agent"]["react"].update(
                    {"max_attempts": -1}
                ),
                ["agent.react.max_attempts", "greater than 0"],
            ),
            (
                "boolean max_attempts",
                lambda config: config["agent"]["react"].update(
                    {"max_attempts": True}
                ),
                ["agent.react.max_attempts", "valid integer"],
            ),
            (
                "string streaming",
                lambda config: config["agent"]["react"].update({"streaming": "true"}),
                ["agent.react.streaming", "valid boolean"],
            ),
            (
                "non-mapping provider options",
                lambda config: config["agent"]["react"].update(
                    {"provider_options": ["thinking"]}
                ),
                ["agent.react.provider_options", "valid dictionary"],
            ),
            (
                "unsupported DeepSeek option",
                lambda config: config["agent"]["react"].update(
                    {"provider_options": {"reasoning_effort": "low"}}
                ),
                ["agent.react.provider_options", "unsupported DeepSeek options"],
            ),
        ]
        for name, mutate, fragments in cases:
            with self.subTest(case=name):
                config = _agent_section()
                mutate(config)
                with self.assertRaises(config_module.ConfigLoadError) as ctx:
                    config_module._build_agent_settings(config)
                message = str(ctx.exception)
                for fragment in fragments:
                    self.assertIn(fragment, message)


class DuplicateKeyTests(unittest.TestCase):
    """A repeated YAML key is a contradiction, not a merge."""

    def _write(self, body: str) -> Path:
        path = Path(tempfile.mkdtemp()) / "prompts.yaml"
        path.write_text(body, encoding="utf-8")
        return path

    def test_duplicate_key_in_the_same_mapping_is_refused(self) -> None:
        path = self._write(
            "prompts:\n  sql_generation: |\n  sql_generation: |\n    first\n    second\n"
        )
        with self.assertRaisesRegex(
            config_module.ConfigLoadError, "duplicate key 'sql_generation'"
        ):
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
        path = self._write(
            "prompts:\n  system: |\n    same text\n  sql_generation: |\n    same text\n"
        )
        self.assertEqual(config_module._load_yaml_file(path)["prompts"]["system"], "same text\n")

    def test_shipped_config_files_have_no_duplicate_keys(self) -> None:
        """The file that carried the defect must not be able to acquire another."""
        for path in sorted((config_module.CONFIG_DIR).rglob("*.yaml")):
            with self.subTest(config=path.name):
                self.assertIsInstance(config_module._load_yaml_file(path), dict)
