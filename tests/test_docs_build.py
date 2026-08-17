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


ENTRY = """---
ticket: T9999.1
milestone: M99
title: A throwaway ticket
status: complete
date: 2026-08-17
verified: no
---

## Summary

It changed one thing.

## Manual verification

1. Run the thing.

## Known issues

- `KI-2026-08-17-already-filed` **`[MED · OPEN]` This one a maintainer has filed.**
- `KI-2026-08-17-still-loose` **`[LOW · OPEN]` This one nobody has filed.**
"""

ISSUES = """# Known Issues

## Triage

<!-- generated:triage:begin -->
<!-- generated:triage:end -->

## Raised, not yet filed

<!-- generated:registered:begin -->
<!-- generated:registered:end -->

## Some topic (1)

- `KI-2026-08-17-already-filed` **`[MED · OPEN]` This one a maintainer has filed.**
"""

REPORTS = """# Completion Reports

<!-- generated:reports:begin -->
<!-- generated:reports:end -->
"""

CHECKS = """# Manual Verification Guide

<!-- generated:checklists:begin -->
<!-- generated:checklists:end -->
"""

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
    tickets: [T0001]
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
    """A miniature docs tree: one entry, and the registers it renders into."""
    root = tmp_path / "docs"
    (root / "entries").mkdir(parents=True)
    (root / "entries" / "T9999.1.md").write_text(ENTRY, encoding="utf-8")
    (root / "Known_Issues.md").write_text(ISSUES, encoding="utf-8")
    (root / "Completion_Reports.md").write_text(REPORTS, encoding="utf-8")
    (root / "Manual_Verification_Guide.md").write_text(CHECKS, encoding="utf-8")
    (root / "Repo_Current_State.md").write_text(STATE, encoding="utf-8")
    (root / "roadmap.yaml").write_text(ROADMAP, encoding="utf-8")
    (root.parent / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    return root


def built(docs: Path) -> dict[Path, str]:
    return docs_build.build(
        docs / "entries", docs, docs / "roadmap.yaml", docs.parent / "pyproject.toml"
    )


def rendered(docs: Path, name: str) -> str:
    return built(docs)[docs / name]


def test_a_completed_entry_renders_its_report(docs: Path) -> None:
    text = rendered(docs, "Completion_Reports.md")

    assert "## T9999.1 - A throwaway ticket" in text
    assert "It changed one thing." in text
    # Manual verification and known issues belong to the other two registers, not to this one.
    assert "Run the thing." not in text


def test_an_unfinished_entry_renders_no_report(docs: Path) -> None:
    entry = docs / "entries" / "T9999.1.md"
    entry.write_text(ENTRY.replace("status: complete", "status: in-progress"), encoding="utf-8")

    assert "T9999.1" not in rendered(docs, "Completion_Reports.md")


def test_a_checklist_leaves_when_the_entry_is_marked_verified(docs: Path) -> None:
    """`verified: yes` is the guide's eviction rule, so the region is where it takes effect."""
    entry = docs / "entries" / "T9999.1.md"
    assert "Run the thing." in rendered(docs, "Manual_Verification_Guide.md")

    entry.write_text(ENTRY.replace("verified: no", "verified: yes"), encoding="utf-8")

    assert "Run the thing." not in rendered(docs, "Manual_Verification_Guide.md")


def test_an_issue_leaves_the_inbox_once_its_id_appears_filed(docs: Path) -> None:
    """The id is the dedup key: filing is a paste that keeps it, not an edit to the entry."""
    text = rendered(docs, "Known_Issues.md")
    inbox = text.split("generated:registered:begin -->")[1].split("<!-- generated")[0]

    assert "KI-2026-08-17-still-loose" in inbox
    assert "KI-2026-08-17-already-filed" not in inbox


def test_triage_counts_the_filed_and_the_unfiled_together(docs: Path) -> None:
    text = rendered(docs, "Known_Issues.md")

    # One filed MED · OPEN, one unfiled LOW · OPEN, and nothing else in the register.
    assert "| MED | 1 | 0 | 0 |" in text
    assert "| LOW | 1 | 0 | 0 |" in text
    assert "| HIGH | 0 | 0 | 0 |" in text


def stale(docs: Path) -> list[Path]:
    return docs_build.stale(
        docs / "entries", docs, docs / "roadmap.yaml", docs.parent / "pyproject.toml"
    )


def test_building_twice_changes_nothing(docs: Path) -> None:
    for path, text in built(docs).items():
        path.write_text(text, encoding="utf-8", newline="\n")

    assert stale(docs) == []


def test_a_hand_edit_to_a_region_is_reported_as_stale(docs: Path) -> None:
    for path, text in built(docs).items():
        path.write_text(text, encoding="utf-8", newline="\n")
    reports = docs / "Completion_Reports.md"
    reports.write_text(
        reports.read_text(encoding="utf-8").replace("one thing", "something else"),
        encoding="utf-8",
    )

    assert stale(docs) == [reports]


def test_hand_written_content_outside_a_region_survives(docs: Path) -> None:
    """The registers carry years of history that predates entries; generation must not eat it."""
    text = rendered(docs, "Known_Issues.md")

    assert "## Some topic (1)" in text
    assert text.startswith("# Known Issues")


def test_a_missing_region_marker_is_an_error(docs: Path) -> None:
    reports = docs / "Completion_Reports.md"
    reports.write_text("# Completion Reports\n", encoding="utf-8")

    with pytest.raises(docs_build.BuildError, match="missing"):
        built(docs)


def test_frontmatter_faults_are_reported_against_the_entry(docs: Path) -> None:
    entry = docs / "entries" / "T9999.1.md"
    entry.write_text(ENTRY.replace("status: complete", "status: nonsense"), encoding="utf-8")

    with pytest.raises(docs_build.BuildError, match="unknown status"):
        built(docs)

    entry.write_text(ENTRY.replace("ticket: T9999.1\n", ""), encoding="utf-8")

    with pytest.raises(docs_build.BuildError, match="missing `ticket`"):
        built(docs)


def test_milestone_status_comes_from_the_registry(docs: Path) -> None:
    """`roadmap.yaml` owns milestone identity, so the snapshot reads it rather than restating it."""
    text = rendered(docs, "Repo_Current_State.md")

    assert "Complete: M1-M2 - 2 of 4 milestones." in text
    assert "| M3 | A milestone in flight | in-progress |" in text
    assert "| M5 | A milestone with no scope yet | planned |" in text
    # Complete milestones compress to the one line; they do not also get a row.
    assert "| M1 |" not in text


def test_the_registry_reader_ignores_nested_blocks(docs: Path) -> None:
    """`scope:` lists and `note:` block scalars indent past a field and must not become fields."""
    milestones = docs_build.parse_milestones(ROADMAP)

    assert [entry["id"] for entry in milestones] == ["M1", "M2", "M3", "M5"]
    assert milestones[2]["title"] == "A milestone in flight"
    assert "A block scalar" not in str(milestones)


def test_milestone_ranges_skip_a_gap() -> None:
    assert docs_build.compress_ids(["M1", "M2", "M3", "M7"]) == "M1-M3, M7"
    assert docs_build.compress_ids(["M4"]) == "M4"
    assert docs_build.compress_ids([]) == "none"


def test_dependencies_are_named_without_their_versions(docs: Path) -> None:
    """`pyproject.toml` owns the specifier; copying it here would be a second place to be wrong."""
    text = rendered(docs, "Repo_Current_State.md")

    assert "Runtime (2): `fastapi`, `psycopg`" in text
    assert "Development (1): `pytest`" in text
    assert ">=" not in text.split("generated:dependencies:begin -->")[1].split("<!-- gen")[0]


def test_a_long_dependency_name_is_never_split(tmp_path: Path) -> None:
    """Wrapping on a hyphen would break a backtick span, and these names are all hyphenated."""
    pyproject = tmp_path / "pyproject.toml"
    names = [f"langgraph-checkpoint-postgres-{index}" for index in range(12)]
    listed = ", ".join(f'"{name}>=1.0"' for name in names)
    pyproject.write_text(f"[project]\ndependencies = [{listed}]\n", encoding="utf-8")

    text = docs_build.render_dependencies(pyproject.read_bytes())

    assert all(len(line) <= docs_build.LINE_LIMIT for line in text.split("\n"))
    for name in names:
        assert f"`{name}`" in text


def test_scripts_are_summarised_by_their_own_docstring(tmp_path: Path) -> None:
    (tmp_path / "with_doc.py").write_text('"""Do a thing.\n\nMore."""\n', encoding="utf-8")
    (tmp_path / "no_doc.py").write_text("import os\n", encoding="utf-8")
    (tmp_path / "broken.py").write_text("def (\n", encoding="utf-8")

    text = docs_build.render_scripts(tmp_path)

    assert "- `scripts/with_doc.py` - Do a thing." in text
    assert "- `scripts/no_doc.py` - No module docstring." in text
    # A file that will not parse is reported, not raised: the inventory is not a syntax gate.
    assert "- `scripts/broken.py` - No module docstring." in text


def test_the_git_region_is_not_gated_by_the_check(docs: Path) -> None:
    """The whole reason `snapshot` is separate: it differs per clone, so `stale` must ignore it."""
    for path, text in built(docs).items():
        path.write_text(text, encoding="utf-8", newline="\n")
    state = docs / "Repo_Current_State.md"
    state.write_text(
        state.read_text(encoding="utf-8").replace(
            "<!-- generated:snapshot:begin -->",
            "<!-- generated:snapshot:begin -->\n- Checked out: something else.",
        ),
        encoding="utf-8",
    )

    assert stale(docs) == []


def test_check_refuses_to_verify_the_git_region() -> None:
    with pytest.raises(SystemExit):
        docs_build.main(["--check", "--snapshot"])


def test_the_committed_registers_are_current() -> None:
    """The gate itself: what is committed must equal what the entries render to."""
    assert docs_build.stale() == []
