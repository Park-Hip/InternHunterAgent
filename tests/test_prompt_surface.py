from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIRECTORY = ROOT / "src" / "agents" / "tools"


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
            path="config/prompts.yaml",
            symbol="behavior_glossary",
            text="",
            visibility="model-visible",
        ),
        PromptSurface(
            path="src/agents/tools/get_job_details.py",
            symbol="get_job_details.__doc__",
            text=(
                "Fetch the full description and details for specific job postings by their id. "
                "Use this only when the user asks to know more about, describe, or compare "
                "specific jobs already shown by query_clean_jobs (which lists jobs with their "
                "id). Pass the id values from that list."
            ),
            visibility="model-visible",
        ),
        PromptSurface(
            path="src/agents/tools/query_clean_jobs.py",
            symbol="query_clean_jobs.__doc__",
            text=(
                "Search AI and data job and internship postings in the clean_jobs table.\n\n"
                "Use this tool for discovery questions before get_job_details, which retrieves "
                "details for\npostings already shown. Pass the user's question with any role, "
                "skill, location, or other\nsearch criteria."
            ),
            visibility="model-visible",
        ),
        PromptSurface(
            path="src/agents/tools/time.py",
            symbol="get_current_time.__doc__",
            text="Return the current UTC time in HH:MM:SS format.",
            visibility="model-visible",
        ),
        PromptSurface(
            path="src/agents/tools/get_job_details.py",
            symbol="get_job_details",
            text=(
                "Please specify which job's id you'd like details for, or run a search "
                "with query_clean_jobs first."
            ),
            visibility="model-visible",
        ),
        PromptSurface(
            path="src/agents/tools/get_job_details.py",
            symbol="get_job_details",
            text="I couldn't retrieve the requested data due to a database error. Please try again later.",
            visibility="model-visible",
        ),
        PromptSurface(
            path="src/agents/tools/query_clean_jobs.py",
            symbol="_build_answer",
            text="I didn't find any postings matching that in the data.",
            visibility="model-visible",
        ),
        PromptSurface(
            path="src/agents/tools/query_clean_jobs.py",
            symbol="query_clean_jobs",
            text='f"I can\'t run that query: {validation.reason}"',
            visibility="model-visible",
        ),
        PromptSurface(
            path="src/agents/tools/query_clean_jobs.py",
            symbol="query_clean_jobs",
            text="I couldn't retrieve the requested data due to a database error. Please try again later.",
            visibility="model-visible",
        ),
    }
)


def tool_surfaces(path: Path) -> set[PromptSurface]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    relative_path = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.name
    surfaces: set[PromptSurface] = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue

        docstring = ast.get_docstring(node, clean=True)
        if docstring is not None:
            surfaces.add(
                PromptSurface(
                    path=relative_path,
                    symbol=f"{node.name}.__doc__",
                    text=docstring,
                    visibility="model-visible",
                )
            )

        for descendant in ast.walk(node):
            if not isinstance(descendant, ast.Return):
                continue
            returned = descendant.value
            if isinstance(returned, ast.Constant) and isinstance(returned.value, str):
                text = returned.value
            elif isinstance(returned, ast.JoinedStr):
                text = ast.get_source_segment(source, returned)
                if text is None:
                    raise AssertionError(f"Could not locate f-string in {relative_path}")
            else:
                continue
            surfaces.add(
                PromptSurface(
                    path=relative_path,
                    symbol=node.name,
                    text=text,
                    visibility="model-visible",
                )
            )

    return surfaces


def config_surfaces() -> set[PromptSurface]:
    config_path = ROOT / "config" / "prompts.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    prompts = config["prompts"]

    assert set(prompts) == {"system_prompt", "schema_context", "sql_generation"}
    assert all(isinstance(prompts[name], str) for name in prompts)
    assert isinstance(config["behavior_glossary"], dict)

    return {
        PromptSurface("config/prompts.yaml", "prompts.system_prompt", "", "model-visible"),
        PromptSurface("config/prompts.yaml", "prompts.schema_context", "", "model-visible"),
        PromptSurface("config/prompts.yaml", "prompts.sql_generation", "", "model-visible"),
        PromptSurface("config/prompts.yaml", "behavior_glossary", "", "model-visible"),
    }


def discovered_surfaces() -> set[PromptSurface]:
    tool_surfaces_found = set().union(
        *(tool_surfaces(path) for path in sorted(TOOLS_DIRECTORY.glob("*.py")))
    )
    return config_surfaces() | tool_surfaces_found


def test_inventory_matches_every_model_facing_tool_string() -> None:
    assert discovered_surfaces() == INVENTORY


def test_unrecorded_return_literal_is_detected(tmp_path: Path) -> None:
    tool_path = tmp_path / "tool.py"
    tool_path.write_text('def example():\n    return "test string"\n', encoding="utf-8")

    found = tool_surfaces(tool_path)

    assert PromptSurface(
        path="tool.py",
        symbol="example",
        text="test string",
        visibility="model-visible",
    ) in found
