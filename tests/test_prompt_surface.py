"""Guard the model-facing text surface, which is now only the prompt and the tools.

Since #702 a tool returns typed facts and raises a kind with a detail, so the
only places a written sentence reaches the model are:

1. the three prompt surfaces declared in ``config/prompts.yaml``, and
2. the four descriptions the MCP server advertises for its two tools.

The inventory below is that closed list. The first test compares it against the
text the real server actually serves, so a new tool, a renamed argument, or a
changed description cannot reach the model unrecorded. The last tests guard the
other half of the change: a behavior module must not return a written sentence,
and the deleted caveat machinery must not creep back into the config.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml
from fastmcp import Client

from src.agents.mcp.job_server import (
    GET_JOB_DETAILS_TOOL,
    IDS_ARGUMENT_DESCRIPTION,
    QUERY_CLEAN_JOBS_DESCRIPTION,
    QUERY_CLEAN_JOBS_TOOL,
    REQUEST_ARGUMENT_DESCRIPTION,
    create_job_mcp_server,
    job_details_description,
)


ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIRECTORY = ROOT / "src" / "agents" / "tools"
JOB_SERVER_PATH = "src/agents/mcp/job_server.py"

#: The behavior modules. They return facts or raise, never a sentence.
BEHAVIOR_MODULES = ("query_clean_jobs.py", "get_job_details.py")


@dataclass(frozen=True)
class PromptSurface:
    path: str
    symbol: str
    text: str
    visibility: str


INVENTORY = frozenset(
    {
        PromptSurface(
            path="config/prompts.yaml",
            symbol="prompts.system_prompt",
            text="",
            visibility="model-visible",
        ),
        PromptSurface(
            path="config/prompts.yaml",
            symbol="prompts.schema_context",
            text="",
            visibility="model-visible",
        ),
        PromptSurface(
            path="config/prompts.yaml",
            symbol="prompts.sql_generation",
            text="",
            visibility="model-visible",
        ),
        PromptSurface(
            path=JOB_SERVER_PATH,
            symbol="QUERY_CLEAN_JOBS_DESCRIPTION",
            text=QUERY_CLEAN_JOBS_DESCRIPTION,
            visibility="model-visible",
        ),
        PromptSurface(
            path=JOB_SERVER_PATH,
            symbol="REQUEST_ARGUMENT_DESCRIPTION",
            text=REQUEST_ARGUMENT_DESCRIPTION,
            visibility="model-visible",
        ),
        PromptSurface(
            path=JOB_SERVER_PATH,
            symbol="GET_JOB_DETAILS_DESCRIPTION",
            text=job_details_description(),
            visibility="model-visible",
        ),
        PromptSurface(
            path=JOB_SERVER_PATH,
            symbol="IDS_ARGUMENT_DESCRIPTION",
            text=IDS_ARGUMENT_DESCRIPTION,
            visibility="model-visible",
        ),
    }
)


def load_prompts_config() -> dict:
    return yaml.safe_load((ROOT / "config" / "prompts.yaml").read_text(encoding="utf-8"))


def config_surfaces() -> set[PromptSurface]:
    prompts = load_prompts_config()["prompts"]

    assert set(prompts) == {
        "system_prompt",
        "schema_context",
        "sql_generation",
    }

    return {
        PromptSurface("config/prompts.yaml", f"prompts.{name}", "", "model-visible")
        for name in prompts
    }


async def advertised_surfaces() -> set[PromptSurface]:
    """The descriptions the MCP server serves, as a client reads them."""
    async with Client(create_job_mcp_server()) as client:
        by_name = {tool.name: tool for tool in await client.list_tools()}

    query = by_name[QUERY_CLEAN_JOBS_TOOL]
    details = by_name[GET_JOB_DETAILS_TOOL]
    return {
        PromptSurface(
            JOB_SERVER_PATH,
            "QUERY_CLEAN_JOBS_DESCRIPTION",
            str(query.description),
            "model-visible",
        ),
        PromptSurface(
            JOB_SERVER_PATH,
            "REQUEST_ARGUMENT_DESCRIPTION",
            query.input_schema["properties"]["request"]["description"],
            "model-visible",
        ),
        PromptSurface(
            JOB_SERVER_PATH,
            "GET_JOB_DETAILS_DESCRIPTION",
            str(details.description),
            "model-visible",
        ),
        PromptSurface(
            JOB_SERVER_PATH,
            "IDS_ARGUMENT_DESCRIPTION",
            details.input_schema["properties"]["ids"]["description"],
            "model-visible",
        ),
    }


@pytest.mark.asyncio
async def test_the_inventory_gathers_every_model_facing_string() -> None:
    discovered = config_surfaces() | await advertised_surfaces()

    assert discovered == INVENTORY


def test_the_deleted_caveat_machinery_does_not_come_back() -> None:
    """#702 deleted the glossary, its anchors, and the obligation config."""
    config = load_prompts_config()

    assert "behavior_glossary" not in config
    assert "behavior_glossary_anchors" not in config
    assert "evaluation_anchors" not in config

    settings = yaml.safe_load(
        (ROOT / "config" / "settings.yaml").read_text(encoding="utf-8")
    )

    assert "obligations" not in settings["agent"]["query"]


def returned_sentences(path: Path) -> list[str]:
    """The source of every string or f-string one module's functions return."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    offenders: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Return) or node.value is None:
            continue
        is_string = isinstance(node.value, ast.Constant) and isinstance(
            node.value.value, str
        )
        if is_string or isinstance(node.value, ast.JoinedStr):
            offenders.append(
                f"{path.name}:{node.lineno}: "
                f"{ast.get_source_segment(source, node.value)}"
            )

    return offenders


def test_behavior_modules_return_facts_not_a_written_sentence() -> None:
    offenders = [
        offender
        for name in BEHAVIOR_MODULES
        for offender in returned_sentences(TOOLS_DIRECTORY / name)
    ]

    assert offenders == [], (
        "a behavior returns a written sentence; tools return typed facts and the "
        "system prompt owns the wording (#702): " + "; ".join(offenders)
    )


def test_a_returned_sentence_is_detected(tmp_path: Path) -> None:
    tool_path = tmp_path / "tool.py"
    tool_path.write_text(
        'def hits() -> str:\n    return "Tìm thấy 214 kết quả."\n',
        encoding="utf-8",
    )

    assert returned_sentences(tool_path) == ['tool.py:2: "Tìm thấy 214 kết quả."']
