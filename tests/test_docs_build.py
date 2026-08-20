from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "docs_build.py"
SPEC = importlib.util.spec_from_file_location("docs_build", SCRIPT)
assert SPEC and SPEC.loader
docs_build = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = docs_build
SPEC.loader.exec_module(docs_build)


STATE = """# Repository Current State

## Current branch

<!-- generated:snapshot:begin -->
<!-- generated:snapshot:end -->

## Milestones

<!-- generated:milestones:begin -->
<!-- generated:milestones:end -->

## Dependencies

<!-- generated:dependencies:begin -->
<!-- generated:dependencies:end -->

## Available scripts

<!-- generated:scripts:begin -->
<!-- generated:scripts:end -->
"""

ROADMAP = """version: 1

milestones:
  - id: M1
    title: A finished milestone
    status: complete
  - id: M2
    title: A second finished milestone
    status: complete
  - id: M3
    title: A milestone in flight
    status: in-progress
    scope:
      - docs/roadmap.yaml
    note: >-
      A block scalar indents further than a field, so it must not be read as one.
  - id: M5
    title: A milestone with no scope yet
    status: planned
"""

PYPROJECT = """[project]
name = "example"
dependencies = ["fastapi>=0.1", "psycopg[binary,pool]>=3.2"]

[dependency-groups]
dev = ["pytest>=9.1"]
"""


@pytest.fixture
def docs(tmp_path: Path) -> Path:
    root = tmp_path / "docs"
    root.mkdir()
    (root / "Repo_Current_State.md").write_text(STATE, encoding="utf-8")
    (root / "roadmap.yaml").write_text(ROADMAP, encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    return root


def built(docs: Path, scripts: Path) -> dict[Path, str]:
    return docs_build.build(docs, docs / "roadmap.yaml", docs.parent / "pyproject.toml", scripts)


def test_milestone_status_comes_from_the_registry(docs: Path, tmp_path: Path) -> None:
    text = built(docs, tmp_path)[docs / "Repo_Current_State.md"]

    assert "Complete: M1-M2 - 2 of 4 milestones." in text
    assert "| M3 | A milestone in flight | in-progress |" in text
    assert "| M5 | A milestone with no scope yet | planned |" in text
    assert "| M1 |" not in text


def test_the_registry_reader_ignores_nested_blocks() -> None:
    milestones = docs_build.parse_milestones(ROADMAP)

    assert [entry["id"] for entry in milestones] == ["M1", "M2", "M3", "M5"]
    assert milestones[2]["title"] == "A milestone in flight"
    assert "A block scalar" not in str(milestones)


def test_milestone_ranges_skip_a_gap() -> None:
    assert docs_build.compress_ids(["M1", "M2", "M3", "M7"]) == "M1-M3, M7"
    assert docs_build.compress_ids(["M4"]) == "M4"
    assert docs_build.compress_ids([]) == "none"


def test_dependencies_are_named_without_versions(docs: Path, tmp_path: Path) -> None:
    text = built(docs, tmp_path)[docs / "Repo_Current_State.md"]

    assert "Runtime (2): `fastapi`, `psycopg`" in text
    assert "Development (1): `pytest`" in text
    assert ">=" not in text.split("generated:dependencies:begin -->")[1].split("<!-- gen")[0]


def test_a_long_dependency_name_is_never_split(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    names = [f"langgraph-checkpoint-postgres-{index}" for index in range(12)]
    pyproject.write_text(f"[project]\ndependencies = [{', '.join(f'\"{name}>=1.0\"' for name in names)}]\n", encoding="utf-8")

    text = docs_build.render_dependencies(pyproject.read_bytes())

    assert all(len(line) <= docs_build.LINE_LIMIT for line in text.split("\n"))
    assert all(f"`{name}`" in text for name in names)


def test_scripts_are_summarised_by_their_own_docstring(tmp_path: Path) -> None:
    (tmp_path / "with_doc.py").write_text('"""Do a thing.\n\nMore."""\n', encoding="utf-8")
    (tmp_path / "no_doc.py").write_text("import os\n", encoding="utf-8")
    (tmp_path / "broken.py").write_text("def (\n", encoding="utf-8")

    text = docs_build.render_scripts(tmp_path)

    assert "- `scripts/with_doc.py` - Do a thing." in text
    assert "- `scripts/no_doc.py` - No module docstring." in text
    assert "- `scripts/broken.py` - No module docstring." in text


def test_building_twice_changes_nothing_and_ignores_snapshot(docs: Path, tmp_path: Path) -> None:
    state = docs / "Repo_Current_State.md"
    for path, text in built(docs, tmp_path).items():
        path.write_text(text, encoding="utf-8", newline="\n")
    state.write_text(state.read_text(encoding="utf-8").replace("<!-- generated:snapshot:begin -->", "<!-- generated:snapshot:begin -->\n- Checked out: another clone."), encoding="utf-8")

    assert docs_build.stale(docs, docs / "roadmap.yaml", docs.parent / "pyproject.toml", tmp_path) == []


def test_a_missing_state_marker_is_an_error(docs: Path, tmp_path: Path) -> None:
    (docs / "Repo_Current_State.md").write_text("# State\n", encoding="utf-8")

    with pytest.raises(docs_build.BuildError, match="missing"):
        built(docs, tmp_path)


def test_check_refuses_to_verify_the_git_region() -> None:
    with pytest.raises(SystemExit):
        docs_build.main(["--check", "--snapshot"])


def test_the_committed_state_regions_are_current() -> None:
    assert docs_build.stale() == []
