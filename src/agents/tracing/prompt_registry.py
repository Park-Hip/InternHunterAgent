"""Stable Langfuse prompt identifiers for the git-authoritative prompt file."""

from typing import Final


LANGFUSE_PROMPT_NAMES: Final = {
    "system_prompt": "resumi-system",
    "schema_context": "resumi-schema-context",
    "sql_generation": "resumi-sql-generation",
}
SQL_GENERATION_PROMPT_NAME: Final = LANGFUSE_PROMPT_NAMES["sql_generation"]
