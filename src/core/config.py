import math
import os
import re
from pathlib import Path
from typing import Annotated, Any, Dict, Literal, TypeVar

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PrivateAttr,
    StrictBool,
    StrictInt,
    StringConstraints,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, DotEnvSettingsSource, SettingsConfigDict
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"


class ConfigLoadError(Exception):
    """Raised when runtime settings or YAML config cannot be loaded."""


AGENT_PROFILES = frozenset({"react", "sql_generation"})
ENVIRONMENT_VARIABLE_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")
# The LiteLLM provider token: the model prefix LiteLLM routes on, and the
# provider identity everything downstream reads. Lowercase only.
PROVIDER_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

_NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


def _require_a_number(value: Any) -> Any:
    """Refuse what a numeric field must never coerce.

    Python's ``bool`` is an ``int`` subclass, so a lax float field would read
    ``temperature: true`` as ``1.0``, and a lax float would also read numeric
    strings. YAML writes numbers as numbers, so both are refused here; the
    range and finiteness checks stay in the fields' ``Field`` constraints.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("must be a number")
    return value


_NonNegativeFiniteFloat = Annotated[
    float, BeforeValidator(_require_a_number), Field(ge=0, allow_inf_nan=False)
]
_PositiveFiniteFloat = Annotated[
    float, BeforeValidator(_require_a_number), Field(gt=0, allow_inf_nan=False)
]


class ProviderOptions(BaseModel):
    """One vendor's explicit serving-option contract.

    The same model validates a profile's options and translates them for
    LiteLLM, so validation and translation cannot drift apart; an option the
    model does not declare is refused at load instead of passed to the vendor.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    def to_model_kwargs(self) -> dict[str, Any]:
        """Translate the validated options into LiteLLM's request shape."""
        raise NotImplementedError


class DeepSeekOptions(ProviderOptions):
    """DeepSeek's serving options: one thinking switch, off by default."""

    thinking: Literal["disabled", "enabled"] = "disabled"

    @model_validator(mode="before")
    @classmethod
    def _refuse_unknown_options(cls, data: Any) -> Any:
        if isinstance(data, dict):
            unknown = sorted(set(data) - {"thinking"})
            if unknown:
                raise ValueError(f"unsupported DeepSeek options: {unknown}")
        return data

    def to_model_kwargs(self) -> dict[str, Any]:
        if self.thinking == "disabled":
            return {"extra_body": {"thinking": {"type": "disabled"}}}
        return {}


class EmptyProviderOptions(ProviderOptions):
    """A provider without an option contract; only empty options are accepted."""

    def to_model_kwargs(self) -> dict[str, Any]:
        return {}


_OPTION_CONTRACTS: dict[str, type[ProviderOptions]] = {
    "deepseek": DeepSeekOptions,
}


class Deployment(BaseModel):
    """One trusted deployment in the serving allowlist.

    The provider is derived from the model prefix rather than stated a second
    time: LiteLLM routes on that prefix, so a separate key could only disagree
    with it.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    model: _NonEmptyString
    api_key_env: _NonEmptyString

    @property
    def provider(self) -> str:
        """The LiteLLM provider, read from the model prefix."""
        return self.model.split("/", 1)[0]

    @field_validator("model")
    @classmethod
    def _model_is_provider_qualified(cls, value: str) -> str:
        provider, _, model_name = value.partition("/")
        if not model_name or PROVIDER_NAME.fullmatch(provider) is None:
            raise ValueError(
                "must be a provider-qualified LiteLLM model, "
                "like 'deepseek/deepseek-flash'"
            )
        return value

    @field_validator("api_key_env")
    @classmethod
    def _names_an_environment_variable(cls, value: str) -> str:
        if ENVIRONMENT_VARIABLE_NAME.fullmatch(value) is None:
            raise ValueError("must name an environment variable")
        return value


class Profile(BaseModel):
    """One agent profile: a deployment name plus portable generation settings."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    deployment: _NonEmptyString
    temperature: _NonNegativeFiniteFloat
    max_tokens: StrictInt = Field(gt=0)
    timeout: _PositiveFiniteFloat
    # Counts attempts, not retries: the provider feeds it to tenacity's
    # stop_after_attempt, so 1 is one request and 0 could never happen.
    max_attempts: StrictInt = Field(gt=0)
    streaming: StrictBool
    provider_options: dict[str, Any] = Field(default_factory=dict)


class ResolvedDeployment(BaseModel):
    """One profile's deployment and settings, resolved once at load."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    model: str
    api_key_env: str
    options: ProviderOptions
    profile: Profile

    @property
    def provider(self) -> str:
        """The LiteLLM provider, read from the model prefix."""
        return self.model.split("/", 1)[0]


class MemorySettings(BaseModel):
    """The session memory bound: one cap measured in complete turns."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_turns: StrictInt = Field(gt=0)


class AgentSettings(BaseModel):
    """The agent section validated and resolved once at load.

    ``deployments`` holds one resolved deployment per profile in
    ``AGENT_PROFILES``, so runtime code reads attributes instead of walking
    raw YAML.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    deployments: dict[str, ResolvedDeployment]
    stream_turn_timeout_seconds: StrictInt = Field(gt=0)
    max_turns: StrictInt = Field(gt=0)

    def deployment_for(self, profile: str) -> ResolvedDeployment:
        """Return the profile's deployment, refusing an unknown profile."""
        deployment = self.deployments.get(profile)
        if deployment is None:
            raise ValueError(f"Unsupported agent model profile: {profile}")
        return deployment


class Settings(BaseSettings):
    # No serving provider key is declared here: serving reads each selected
    # deployment's key by name through `get_configured_secret`, and the serving
    # lifespan validates the deployment each served profile selects before the
    # pool opens. The declared keys below are read by the evaluation judge
    # (evals/judge.py), so no single key is required to load settings: a
    # checkout that holds only the keys it needs still runs. See
    # docs/decisions/adr-0045-deepseek-serves-the-agent.md.
    GROQ_API_KEY: str | None = None
    GOOGLE_API_KEY: str | None = None
    OPENROUTER_API_KEY: str | None = None
    DATABASE_URL: str = Field(..., min_length=1)
    AGENT_DATABASE_URL: str = Field(..., min_length=1)
    HEALTHCHECKS_URL: str | None = None

    # Tracing is optional at boot. The tracing layer emits a non-fatal startup
    # diagnostic when these are absent or invalid.
    LANGFUSE_SECRET_KEY: str | None = None
    LANGFUSE_PUBLIC_KEY: str | None = None
    # No default, per ADR-0029: the previous "http://localhost:3000" made a missing
    # value fail toward a local address that nothing serves, so a capture recorded
    # trace IDs for traces that were never ingested. Absent, tracing is disabled by
    # name instead. See docs/decisions/adr-0029-langfuse-cloud-hobby-japan.md.
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

    # The resolved agent section is a private attribute rather than a field: it
    # is built by `load_settings` and never parsed from the environment, and a
    # field named `agent` would match an unrelated AGENT variable and refuse
    # boot. The property is the attribute runtime code reads (#656).
    _agent: AgentSettings | None = PrivateAttr(default=None)

    @property
    def agent(self) -> AgentSettings | None:
        return self._agent

    @agent.setter
    def agent(self, value: AgentSettings | None) -> None:
        self._agent = value


_settings_cache: Settings | None = None


def _config_error(message: str) -> ConfigLoadError:
    return ConfigLoadError(f"Invalid agent configuration: {message}")


def _agent_config_error(exc: ValidationError, *, path: str) -> ConfigLoadError:
    """Name the first pydantic refusal with its YAML path."""
    first = exc.errors()[0]
    location = ".".join(str(part) for part in first.get("loc", ()))
    message = str(first.get("msg", "invalid value"))
    full_path = f"{path}.{location}" if location else path
    return _config_error(f"'{full_path}': {message}")


_ModelT = TypeVar("_ModelT", bound=BaseModel)


def _validate_agent_model(model: type[_ModelT], data: Any, *, path: str) -> _ModelT:
    """Validate one typed model, refusing with the YAML path on error."""
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise _agent_config_error(exc, path=path) from exc


def _resolve_provider_options(
    provider: str, options: dict[str, Any], *, path: str
) -> ProviderOptions:
    """Validate a profile's options against its vendor's contract."""
    contract = _OPTION_CONTRACTS.get(provider)
    if contract is None:
        if options:
            raise _config_error(
                f"'{path}' is not supported for provider '{provider}'. "
                "Add an explicit contract first"
            )
        return EmptyProviderOptions()
    return _validate_agent_model(contract, options, path=path)


def get_configured_secret(environment_variable: str) -> str | None:
    """Read one validated secret reference without recording its value."""

    if ENVIRONMENT_VARIABLE_NAME.fullmatch(environment_variable) is None:
        raise ValueError("Invalid environment variable reference")
    value = os.getenv(environment_variable)
    if value is not None:
        return value.strip() or None

    dotenv_source = DotEnvSettingsSource(Settings)
    dotenv_key = (
        environment_variable if dotenv_source.case_sensitive else environment_variable.lower()
    )
    value = dotenv_source().get(dotenv_key)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _build_agent_settings(config: dict[str, Any]) -> AgentSettings:
    """Validate and resolve the whole agent section once, at load.

    Every refusal names the YAML path, so a malformed section refuses boot
    with the entry to fix instead of failing later at the first question.
    """

    agent = config.get("agent")
    if not isinstance(agent, dict):
        raise _config_error("missing 'agent' section")

    providers = agent.get("providers")
    if not isinstance(providers, dict) or not providers:
        raise _config_error("'agent.providers' must be a nonempty mapping")

    deployments: dict[str, Deployment] = {}
    for deployment_name, raw_deployment in providers.items():
        if not isinstance(deployment_name, str) or not deployment_name.strip():
            raise _config_error("'agent.providers' names must be nonempty strings")
        if not isinstance(raw_deployment, dict):
            raise _config_error(f"'agent.providers.{deployment_name}' must be a mapping")
        deployments[deployment_name] = _validate_agent_model(
            Deployment, raw_deployment, path=f"agent.providers.{deployment_name}"
        )

    resolved: dict[str, ResolvedDeployment] = {}
    for profile in AGENT_PROFILES:
        raw_profile = agent.get(profile)
        if not isinstance(raw_profile, dict):
            raise _config_error(f"missing 'agent.{profile}' section")
        profile_settings = _validate_agent_model(
            Profile, raw_profile, path=f"agent.{profile}"
        )
        deployment = deployments.get(profile_settings.deployment)
        if deployment is None:
            raise _config_error(
                f"'agent.{profile}.deployment' references unknown deployment "
                f"'{profile_settings.deployment}'"
            )
        resolved[profile] = ResolvedDeployment(
            name=profile_settings.deployment,
            model=deployment.model,
            api_key_env=deployment.api_key_env,
            options=_resolve_provider_options(
                deployment.provider,
                profile_settings.provider_options,
                path=f"agent.{profile}.provider_options",
            ),
            profile=profile_settings,
        )

    memory = agent.get("memory")
    if not isinstance(memory, dict):
        raise _config_error("missing 'agent.memory' section")
    memory_settings = _validate_agent_model(
        MemorySettings, memory, path="agent.memory"
    )

    raw_agent_settings: dict[str, Any] = {
        "deployments": resolved,
        "max_turns": memory_settings.max_turns,
    }
    if "stream_turn_timeout_seconds" in agent:
        raw_agent_settings["stream_turn_timeout_seconds"] = agent[
            "stream_turn_timeout_seconds"
        ]
    return _validate_agent_model(AgentSettings, raw_agent_settings, path="agent")


def _config_path(filename: str) -> Path:
    return CONFIG_DIR / filename


def _no_duplicate_keys(loader: yaml.SafeLoader, node: yaml.Node, deep: bool = False) -> dict:
    """Build a mapping, refusing a key that is already present.

    ``yaml.safe_load`` is last-wins on a repeated key, so a duplicated entry in
    a config file is silently discarded and the file still loads. That is how a
    managed prompt was once declared twice in ``prompts.yaml`` and served
    correctly by accident. A config file is a declaration, and a declaration
    that contradicts itself should stop the process rather than pick a winner.
    """
    mapping: dict = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                None, None,
                f"duplicate key {key!r} at line {key_node.start_mark.line + 1}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


class _StrictLoader(yaml.SafeLoader):
    """SafeLoader that refuses duplicate mapping keys."""


_StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_duplicate_keys)


def _load_yaml_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigLoadError(f"Missing config file: {path}")

    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.load(f, Loader=_StrictLoader) or {}
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
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item for item in value)
    ):
        raise ConfigLoadError(f"Invalid '{name}' configuration")
    if len(value) != len(set(value)):
        raise ConfigLoadError(f"Duplicate values in '{name}' configuration")
    return value


def _validate_prompt_config(config: dict[str, Any]) -> None:
    agent = config.get("agent")
    prompts = agent.get("prompts") if isinstance(agent, dict) else None
    if not isinstance(prompts, dict):
        raise ConfigLoadError("Missing 'agent.prompts' configuration")
    label = prompts.get("deployment_label")
    if label not in {"candidate", "production"}:
        raise ConfigLoadError(
            "agent.prompts.deployment_label must be candidate or production"
        )
    cache_ttl_seconds = prompts.get("cache_ttl_seconds")
    if (
        isinstance(cache_ttl_seconds, bool)
        or not isinstance(cache_ttl_seconds, int)
        or cache_ttl_seconds < 0
    ):
        raise ConfigLoadError(
            "agent.prompts.cache_ttl_seconds must be a non-negative integer"
        )


def _validate_database_config(config: dict[str, Any]) -> None:
    """Reject a malformed connect bound before any engine can be built.

    The bound must never be absent: libpq's own default is to wait forever, and
    that is what left uvicorn at "Waiting for application startup." on an
    unreachable database (#642).
    """
    database = config.get("database")
    if not isinstance(database, dict):
        raise ConfigLoadError("Missing 'database' section in config/settings.yaml")

    connect_timeout = database.get("connect_timeout_seconds")
    if (
        isinstance(connect_timeout, bool)
        or not isinstance(connect_timeout, int)
        or connect_timeout <= 0
    ):
        raise ConfigLoadError(
            "database.connect_timeout_seconds must be a positive integer "
            "in config/settings.yaml"
        )


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
        raise ConfigLoadError(
            "Missing 'observability.langfuse' section in config/settings.yaml"
        )

    environments = langfuse.get("environments")
    if not isinstance(environments, dict) or not isinstance(
        environments.get("default"), str
    ):
        raise ConfigLoadError(
            "Invalid 'observability.langfuse.environments' configuration"
        )
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
        raise ConfigLoadError(
            "Missing 'observability.langfuse.tag_taxonomy' configuration"
        )
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
            "Missing required environment variables: " + ", ".join(unique_fields)
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
    _validate_database_config(settings.config_yaml)
    _validate_api_config(settings.config_yaml)
    _validate_prompt_config(settings.config_yaml)
    _validate_observability_config(settings.config_yaml)
    settings.agent = _build_agent_settings(settings.config_yaml)
    settings.prompts_yaml = _load_yaml_file(_config_path("prompts.yaml"))
    settings.ingestion_yaml = _load_yaml_file(_config_path("ingestion.yaml"))
    settings.tech_vocabulary_yaml = _load_yaml_file(
        _config_path("tech_vocabulary.yaml")
    )

    _settings_cache = settings
    return settings


class _SettingsProxy:
    def __getattr__(self, name: str) -> Any:
        return getattr(load_settings(), name)

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(load_settings(), name, value)


settings = _SettingsProxy()
