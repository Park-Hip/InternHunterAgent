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
        "first_seen_at",
        "last_seen_at",
    }
)
# The one line that declares which columns the model may reference.
DECLARED_PATTERN = re.compile(
    r"Reference only real columns:\s*(.+?)\.\s+Never invent a column", re.DOTALL
)
# Whole words only, so `source` never matches inside `source_url`.
WORD_PATTERN = re.compile(r"[a-z_][a-z0-9_]*")
# The message the SQL generator actually sends, joined as
# src.agents.tools.query_clean_jobs.generate_sql joins it.
SERVED_SURFACES = ("sql_generation", "schema_context")


def prompts() -> dict[str, str]:
    config = yaml.safe_load(PROMPTS_PATH.read_text(encoding="utf-8"))
    prompt_blocks = config["prompts"]
    return {name: prompt_blocks[name] for name in ("system_prompt", "schema_context", "sql_generation")}


def comma_separated_columns(value: str) -> set[str]:
    return {column.strip() for column in value.split(",")}


def schema_context_columns(prompt: str) -> set[str]:
    return set(re.findall(r"^\s*-\s+([a-z_]+)\s+\(", prompt, re.MULTILINE))


def served_prompt_text(prompt_blocks: dict[str, str]) -> str:
    return "\n\n".join(prompt_blocks[name] for name in SERVED_SURFACES)


def sql_generation_columns(prompt: str) -> set[str]:
    match = DECLARED_PATTERN.search(prompt)
    assert match is not None, "sql_generation is missing its real-column list"
    return comma_separated_columns(match.group(1))


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


def test_the_served_sql_prompt_never_names_an_undeclared_column() -> None:
    """Issue #604: the served prompt ordered `SELECT id` and also said `id` was not
    real.

    Nothing downstream rejects a listing built from the losing half of that
    contradiction, so the answer reads correctly and the follow-up detail request
    cannot chain on an id the reader was never shown.
    """
    prompt_blocks = prompts()
    known_columns = agent_visible_model_columns() | NON_AGENT_VISIBLE_COLUMNS
    used_columns = set(WORD_PATTERN.findall(served_prompt_text(prompt_blocks).lower()))

    undeclared = sorted((used_columns & known_columns) - sql_generation_columns(
        prompt_blocks["sql_generation"]
    ))

    assert undeclared == [], f"prompt names undeclared columns: {undeclared}"


def test_the_prompt_orders_the_chaining_id_first_on_every_listing() -> None:
    """`id` is the chaining key: the list projection carries it and the detail tool
    takes those ids back, so the prompt has to keep naming it."""
    prompt = prompts()["sql_generation"]

    assert "always SELECT id as the first column" in prompt
    assert "id" in sql_generation_columns(prompt)
