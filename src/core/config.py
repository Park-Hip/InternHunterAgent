import math
from pathlib import Path
from typing import Any, Dict

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"


class ConfigLoadError(Exception):
    """Raised when runtime settings or YAML config cannot be loaded."""


class Settings(BaseSettings):
    # Every provider key is optional here, and validated by the branch that needs it.
    # Two providers can serve (deepseek, groq) and a third hosts the judge (OpenRouter),
    # so no single key is required to boot: requiring one would break a checkout that
    # holds only the selected provider's key. See D-045 in docs/Decision_Log.md.
    GROQ_API_KEY: str | None = None
    GOOGLE_API_KEY: str | None = None
    OPENROUTER_API_KEY: str | None = None
    DEEPSEEK_API_KEY: str | None = None
    DATABASE_URL: str = Field(..., min_length=1)
    HEALTHCHECKS_URL: str | None = None

    # Tracing is optional at boot. The tracing layer emits a non-fatal startup
    # diagnostic when these are absent or invalid.
    LANGFUSE_SECRET_KEY: str | None = None
    LANGFUSE_PUBLIC_KEY: str | None = None
    # No default, per D-029 and R3.1: the previous "http://localhost:3000" made a
    # missing value fail toward a local address that nothing serves, so a capture
    # recorded trace IDs for traces that were never ingested. Absent, tracing is
    # disabled by name instead.
    LANGFUSE_BASE_URL: str | None = None

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    config_yaml: Dict[str, Any] = {}
    prompts_yaml: Dict[str, Any] = {}
    ingestion_yaml: Dict[str, Any] = {}
    tech_vocabulary_yaml: Dict[str, Any] = {}


_settings_cache: Settings | None = None
DEFAULT_STREAM_TURN_TIMEOUT_SECONDS = 120


def get_stream_turn_timeout_seconds(config: dict[str, Any]) -> int:
    """Return the configured bounded SSE turn deadline or its safe fallback."""

    agent_config = config.get("agent")
    if not isinstance(agent_config, dict):
        return DEFAULT_STREAM_TURN_TIMEOUT_SECONDS

    timeout_seconds = agent_config.get("stream_turn_timeout_seconds")
    if isinstance(timeout_seconds, int) and not isinstance(timeout_seconds, bool) and timeout_seconds > 0:
        return timeout_seconds
    return DEFAULT_STREAM_TURN_TIMEOUT_SECONDS


def _config_path(filename: str) -> Path:
    return CONFIG_DIR / filename


def _load_yaml_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigLoadError(f"Missing config file: {path}")

    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as exc:
        raise ConfigLoadError(f"Invalid YAML in {path}: {exc}") from exc
    except OSError as exc:
        raise ConfigLoadError(f"Failed to read config file {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigLoadError(
            f"Invalid YAML structure in {path}: expected a mapping/object"
        )

    return data


def _validate_string_list(value: Any, *, name: str) -> list[str]:
    if not isinstance(value, list) or not value or not all(
        isinstance(item, str) and item for item in value
    ):
        raise ConfigLoadError(f"Invalid '{name}' configuration")
    if len(value) != len(set(value)):
        raise ConfigLoadError(f"Duplicate values in '{name}' configuration")
    return value


def _validate_api_config(config: dict[str, Any]) -> None:
    """Reject an invalid stream heartbeat before the application starts."""
    api = config.get("api")
    if not isinstance(api, dict):
        raise ConfigLoadError("Missing 'api' section in config/settings.yaml")

    heartbeat_seconds = api.get("stream_heartbeat_seconds")
    if (
        isinstance(heartbeat_seconds, bool)
        or not isinstance(heartbeat_seconds, (int, float))
        or not math.isfinite(heartbeat_seconds)
        or heartbeat_seconds <= 0
    ):
        raise ConfigLoadError(
            "api.stream_heartbeat_seconds must be a positive finite number in config/settings.yaml"
        )


def _validate_observability_config(config: dict[str, Any]) -> None:
    """Reject malformed closed Langfuse taxonomy before serving requests."""
    observability = config.get("observability")
    if not isinstance(observability, dict):
        raise ConfigLoadError("Missing 'observability' section in config/settings.yaml")
    langfuse = observability.get("langfuse")
    if not isinstance(langfuse, dict):
        raise ConfigLoadError("Missing 'observability.langfuse' section in config/settings.yaml")

    environments = langfuse.get("environments")
    if not isinstance(environments, dict) or not isinstance(
        environments.get("default"), str
    ):
        raise ConfigLoadError("Invalid 'observability.langfuse.environments' configuration")
    allowed_environments = _validate_string_list(
        environments.get("allowed"),
        name="observability.langfuse.environments.allowed",
    )
    if environments["default"] not in allowed_environments:
        raise ConfigLoadError(
            "The default Langfuse environment must be in the allowed environments"
        )

    taxonomy = langfuse.get("tag_taxonomy")
    if not isinstance(taxonomy, dict):
        raise ConfigLoadError("Missing 'observability.langfuse.tag_taxonomy' configuration")
    _validate_string_list(
        taxonomy.get("entry_points"),
        name="observability.langfuse.tag_taxonomy.entry_points",
    )


def _format_validation_error(exc: ValidationError) -> str:
    missing_fields: list[str] = []
    invalid_fields: list[str] = []

    for error in exc.errors():
        loc = ".".join(str(part) for part in error.get("loc", ()))
        if error.get("type") == "missing":
            missing_fields.append(loc)
            continue

        message = error.get("msg", "invalid value")
        invalid_fields.append(f"{loc}: {message}" if loc else message)

    parts: list[str] = []
    if missing_fields:
        unique_fields = sorted(set(missing_fields))
        parts.append(
            "Missing required environment variables: "
            + ", ".join(unique_fields)
        )
    if invalid_fields:
        parts.append("Invalid settings: " + "; ".join(invalid_fields))

    if not parts:
        parts.append(str(exc))

    return "Failed to load runtime settings. " + " ".join(parts)


def load_settings(*, force_reload: bool = False) -> Settings:
    global _settings_cache

    if _settings_cache is not None and not force_reload:
        return _settings_cache

    try:
        settings = Settings()
    except ValidationError as exc:
        raise ConfigLoadError(_format_validation_error(exc)) from exc

    settings.config_yaml = _load_yaml_file(_config_path("settings.yaml"))
    _validate_api_config(settings.config_yaml)
    _validate_observability_config(settings.config_yaml)
    settings.prompts_yaml = _load_yaml_file(_config_path("prompts.yaml"))
    settings.ingestion_yaml = _load_yaml_file(_config_path("ingestion.yaml"))
    settings.tech_vocabulary_yaml = _load_yaml_file(_config_path("tech_vocabulary.yaml"))

    _settings_cache = settings
    return settings


class _SettingsProxy:
    def __getattr__(self, name: str) -> Any:
        return getattr(load_settings(), name)

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(load_settings(), name, value)


settings = _SettingsProxy()
