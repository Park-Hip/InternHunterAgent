from __future__ import annotations

import re
from pathlib import Path

import yaml

from src.services.ingestion.models import CleanJob


ROOT = Path(__file__).resolve().parents[1]
PROMPTS_PATH = ROOT / "config" / "prompts.yaml"
NON_AGENT_VISIBLE_COLUMNS = frozenset(
    {
        "source",
        "external_id",
        "posted_date",
        "is_active",
        "first_seen_at",
        "last_seen_at",
    }
)


def prompts() -> dict[str, str]:
    config = yaml.safe_load(PROMPTS_PATH.read_text(encoding="utf-8"))
    prompt_blocks = config["prompts"]
    return {name: prompt_blocks[name] for name in ("system_prompt", "schema_context", "sql_generation")}


def comma_separated_columns(value: str) -> set[str]:
    return {column.strip() for column in value.split(",")}


def schema_context_columns(prompt: str) -> set[str]:
    return set(re.findall(r"^\s*-\s+([a-z_]+)\s+\(", prompt, re.MULTILINE))


def sql_generation_columns(prompt: str) -> set[str]:
    match = re.search(r"Reference only real columns:\s*(.+?)\.\s+Never invent", prompt, re.DOTALL)
    assert match is not None, "sql_generation is missing its real-column list"
    columns = comma_separated_columns(match.group(1))
    assert "always SELECT id as the first column" in prompt
    return columns | {"id"}


def agent_visible_model_columns() -> set[str]:
    model_columns = {column.name for column in CleanJob.__table__.columns}
    assert NON_AGENT_VISIBLE_COLUMNS <= model_columns
    return model_columns - NON_AGENT_VISIBLE_COLUMNS


def test_sql_prompt_column_list_matches_schema_context() -> None:
    prompt_blocks = prompts()
    column_sets = {
        "schema_context": schema_context_columns(prompt_blocks["schema_context"]),
        "sql_generation": sql_generation_columns(prompt_blocks["sql_generation"]),
    }

    assert len({frozenset(columns) for columns in column_sets.values()}) == 1, column_sets


def test_prompt_column_lists_match_the_agent_visible_model_columns() -> None:
    prompt_blocks = prompts()
    expected_columns = agent_visible_model_columns()

    assert schema_context_columns(prompt_blocks["schema_context"]) == expected_columns
    assert sql_generation_columns(prompt_blocks["sql_generation"]) == expected_columns
