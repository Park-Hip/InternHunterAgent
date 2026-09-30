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
            symbol="run_get_job_details.__doc__",
            text="Return safe Vietnamese job details for the given posting ids.",
            visibility="model-visible",
        ),
        PromptSurface(
            path="src/agents/tools/query_clean_jobs.py",
            symbol="run_query_clean_jobs.__doc__",
            text="Return safe Vietnamese clean_jobs search results for one question.",
            visibility="model-visible",
        ),
        PromptSurface(
            path="src/agents/tools/query_clean_jobs.py",
            symbol="generate_sql.__doc__",
            text="Generate SQL for one question with an explicit traceable generation.",
            visibility="model-visible",
        ),
        PromptSurface(
            path="src/agents/tools/get_job_details.py",
            symbol="run_get_job_details",
            text=(
                "Vui lòng chỉ định mã tin tuyển dụng bạn muốn xem chi tiết hoặc tìm kiếm "
                "trước bằng query_clean_jobs."
            ),
            visibility="model-visible",
        ),
        PromptSurface(
            path="src/agents/tools/get_job_details.py",
            symbol="run_get_job_details",
            text="Tôi không thể truy xuất dữ liệu do lỗi cơ sở dữ liệu. Vui lòng thử lại sau.",
            visibility="model-visible",
        ),
        PromptSurface(
            path="src/agents/tools/query_clean_jobs.py",
            symbol="run_query_clean_jobs",
            text='f"Tôi không thể chạy truy vấn đó: {validation.reason}"',
            visibility="model-visible",
        ),
        PromptSurface(
            path="src/agents/tools/query_clean_jobs.py",
            symbol="run_query_clean_jobs",
            text="Tôi không thể truy xuất dữ liệu do lỗi cơ sở dữ liệu. Vui lòng thử lại sau.",
            visibility="model-visible",
        ),
        PromptSurface(
            path="src/agents/tools/v0_query_jobs.py",
            symbol="_repair_message",
            text='"INVALID REQUEST\\n"\n        f"{details}\\n"\n        f"Allowed shapes: {\', \'.join(shape.value for shape in QueryShape)}\\n"\n        f"Allowed metrics: {\', \'.join(metric.value for metric in Metric)}\\n"\n        f"Allowed filter fields: {\', \'.join(field.value for field in FilterField)}"',
            visibility="model-visible",
        ),
        PromptSurface(
            path="src/agents/tools/v0_query_jobs.py",
            symbol="_repair_message.__doc__",
            text="A repairable rejection, so the model can re-ask instead of failing.",
            visibility="model-visible",
        ),
        PromptSurface(
            path="src/agents/tools/v0_query_jobs.py",
            symbol="_row_lines.__doc__",
            text="Render rows as key=value pairs.\n\nA list drops a null field rather than printing it 20 times, and a detail\nrow keeps it, because the contract requires an absent field on a specific\nposting to be named rather than left as a gap.",
            visibility="model-visible",
        ),
        PromptSurface(
            path="src/agents/tools/v0_query_jobs.py",
            symbol="_value_text",
            text="(không có)",
            visibility="model-visible",
        ),
        PromptSurface(
            path="src/agents/tools/v0_query_jobs.py",
            symbol="render_result",
            text='f"AMBIGUOUS\\n{result.message}"',
            visibility="model-visible",
        ),
        PromptSurface(
            path="src/agents/tools/v0_query_jobs.py",
            symbol="render_result",
            text='f"ERROR\\n{result.message}"',
            visibility="model-visible",
        ),
        PromptSurface(
            path="src/agents/tools/v0_query_jobs.py",
            symbol="render_result",
            text='f"UNSUPPORTED\\n{result.message}"',
            visibility="model-visible",
        ),
        PromptSurface(
            path="src/agents/tools/v0_query_jobs.py",
            symbol="render_result.__doc__",
            text="Render a result as the facts an answer must be built from.",
            visibility="model-visible",
        ),
        PromptSurface(
            path="src/agents/tools/v0_query_jobs.py",
            symbol="run_query_jobs.__doc__",
            text="Answer one typed request and return the evidence as text.",
            visibility="model-visible",
        ),
        # The governed v0 system prompt is model-facing from the cutover onwards.
        PromptSurface(
            path="config/prompts.yaml",
            symbol="prompts.system_prompt_v0",
            text="",
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

    assert set(prompts) == {
        "system_prompt",
        "system_prompt_v0",
        "schema_context",
        "sql_generation",
    }
    assert all(isinstance(prompts[name], str) for name in prompts)
    assert isinstance(config["behavior_glossary"], dict)

    return {
        PromptSurface("config/prompts.yaml", "prompts.system_prompt", "", "model-visible"),
        PromptSurface("config/prompts.yaml", "prompts.schema_context", "", "model-visible"),
        PromptSurface("config/prompts.yaml", "prompts.sql_generation", "", "model-visible"),
        PromptSurface("config/prompts.yaml", "behavior_glossary", "", "model-visible"),
        PromptSurface("config/prompts.yaml", "prompts.system_prompt_v0", "", "model-visible"),
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
