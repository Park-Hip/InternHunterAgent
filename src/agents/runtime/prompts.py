from langchain.messages import SystemMessage

from src.core.config import settings

SYSTEM_PROMPT_SURFACE = "system"
SCHEMA_CONTEXT_PROMPT_SURFACE = "schema_context"
SQL_GENERATION_PROMPT_SURFACE = "sql_generation"
PROMPT_SURFACES = (
    SYSTEM_PROMPT_SURFACE,
    SCHEMA_CONTEXT_PROMPT_SURFACE,
    SQL_GENERATION_PROMPT_SURFACE,
)


def load_system_prompt() -> SystemMessage:
    prompts_root = settings.prompts_yaml.get("prompts")
    if not isinstance(prompts_root, dict):
        raise ValueError("Missing 'prompts' section in config/prompts.yaml")

    system_prompt = prompts_root.get("system_prompt")
    if not isinstance(system_prompt, str) or not system_prompt.strip():
        raise ValueError("Missing or empty 'prompts.system_prompt' in config/prompts.yaml")

    return SystemMessage(content=system_prompt.strip())


def load_schema_context() -> str:
    prompts_root = settings.prompts_yaml.get("prompts")
    if not isinstance(prompts_root, dict):
        raise ValueError("Missing 'prompts' section in config/prompts.yaml")

    schema_context = prompts_root.get("schema_context")
    if not isinstance(schema_context, str) or not schema_context.strip():
        raise ValueError("Missing or empty 'prompts.schema_context' in config/prompts.yaml")

    return schema_context.strip()


def load_sql_generation_prompt() -> str:
    prompts_root = settings.prompts_yaml.get("prompts")
    if not isinstance(prompts_root, dict):
        raise ValueError("Missing 'prompts' section in config/prompts.yaml")

    sql_generation_prompt = prompts_root.get("sql_generation")
    if not isinstance(sql_generation_prompt, str) or not sql_generation_prompt.strip():
        raise ValueError("Missing or empty 'prompts.sql_generation' in config/prompts.yaml")

    return sql_generation_prompt.strip()


def load_prompt_versions() -> dict[str, str]:
    """Return the independently versioned prompt lineage surfaces.

    Captures persist this mapping directly. A single aggregate version would make a
    system-only change look like a schema-context or SQL-generation change too.
    """
    prompt_versions = settings.prompts_yaml.get("prompt_versions")
    if not isinstance(prompt_versions, dict) or set(prompt_versions) != set(
        PROMPT_SURFACES
    ):
        raise ValueError(
            "config/prompts.yaml must declare exactly these prompt_versions: "
            + ", ".join(PROMPT_SURFACES)
        )
    if not all(
        isinstance(prompt_versions[surface], str)
        and prompt_versions[surface].strip()
        for surface in PROMPT_SURFACES
    ):
        raise ValueError("Every prompt_versions value must be a non-empty string")

    return {surface: prompt_versions[surface].strip() for surface in PROMPT_SURFACES}


def load_behavior_glossary() -> dict[str, str]:
    """Canonical hedge and refusal phrasings, keyed by token.

    Machine source of truth for the phrasings the behavior spec records in prose. These
    are reference strings: nothing here reaches the model until an obligation resolves one
    of them at runtime.
    """
    glossary = settings.prompts_yaml.get("behavior_glossary")
    if not isinstance(glossary, dict) or not glossary:
        raise ValueError("Missing or empty 'behavior_glossary' in config/prompts.yaml")

    for token, phrasing in glossary.items():
        if not isinstance(token, str) or not token.strip():
            raise ValueError("Every 'behavior_glossary' token must be a non-empty string")
        if not isinstance(phrasing, str) or not phrasing.strip():
            raise ValueError(f"Empty 'behavior_glossary' phrasing for token: {token}")

    return {token: phrasing.strip() for token, phrasing in glossary.items()}
