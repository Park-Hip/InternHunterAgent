from langchain.messages import SystemMessage

from src.core.config import settings


def load_prompt_version() -> str:
    prompt_version = settings.prompts_yaml.get("prompt_version")
    if not isinstance(prompt_version, str) or not prompt_version.strip():
        raise ValueError("Missing or empty top-level 'prompt_version' in config/prompts.yaml")

    return prompt_version.strip()


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
