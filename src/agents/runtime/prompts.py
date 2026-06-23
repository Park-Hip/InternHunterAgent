from langchain.messages import SystemMessage

from src.core.config import settings


def load_system_prompt() -> SystemMessage:
    prompts_root = settings.prompts_yaml.get("prompts")
    if not isinstance(prompts_root, dict):
        raise ValueError("Missing 'prompts' section in config/prompts.yaml")

    system_prompt = prompts_root.get("system_prompt")
    if not isinstance(system_prompt, str) or not system_prompt.strip():
        raise ValueError("Missing or empty 'prompts.system_prompt' in config/prompts.yaml")

    return SystemMessage(content=system_prompt.strip())


def load_sql_generation_prompt() -> str:
    prompts_root = settings.prompts_yaml.get("prompts")
    if not isinstance(prompts_root, dict):
        raise ValueError("Missing 'prompts' section in config/prompts.yaml")

    sql_generation_prompt = prompts_root.get("sql_generation")
    if not isinstance(sql_generation_prompt, str) or not sql_generation_prompt.strip():
        raise ValueError("Missing or empty 'prompts.sql_generation' in config/prompts.yaml")

    return sql_generation_prompt.strip()