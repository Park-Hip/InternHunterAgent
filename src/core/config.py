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
    # Two providers can serve and a third judges, so no single key is required to boot:
    # requiring one would break a checkout that holds only the selected provider's key.
    # See D-045 in docs/Decision_Log.md.
    GROQ_API_KEY: str | None = None
    GOOGLE_API_KEY: str | None = None
    DEEPSEEK_API_KEY: str | None = None
    DATABASE_URL: str = Field(..., min_length=1)
    HEALTHCHECKS_URL: str | None = None

    LANGFUSE_SECRET_KEY: str
    LANGFUSE_PUBLIC_KEY: str
    LANGFUSE_BASE_URL: str = "http://localhost:3000"

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
