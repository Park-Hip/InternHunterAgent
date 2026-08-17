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


@pytest.fixture
def docs(tmp_path: Path) -> Path:
    """A miniature docs tree: one entry, and the three registers it renders into."""
    root = tmp_path / "docs"
    (root / "entries").mkdir(parents=True)
    (root / "entries" / "T9999.1.md").write_text(ENTRY, encoding="utf-8")
    (root / "Known_Issues.md").write_text(ISSUES, encoding="utf-8")
    (root / "Completion_Reports.md").write_text(REPORTS, encoding="utf-8")
    (root / "Manual_Verification_Guide.md").write_text(CHECKS, encoding="utf-8")
    return root


def rendered(docs: Path, name: str) -> str:
    return docs_build.build(docs / "entries", docs)[docs / name]


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


def test_building_twice_changes_nothing(docs: Path) -> None:
    for path, text in docs_build.build(docs / "entries", docs).items():
        path.write_text(text, encoding="utf-8", newline="\n")

    assert docs_build.stale(docs / "entries", docs) == []


def test_a_hand_edit_to_a_region_is_reported_as_stale(docs: Path) -> None:
    for path, text in docs_build.build(docs / "entries", docs).items():
        path.write_text(text, encoding="utf-8", newline="\n")
    reports = docs / "Completion_Reports.md"
    reports.write_text(
        reports.read_text(encoding="utf-8").replace("one thing", "something else"),
        encoding="utf-8",
    )

    assert docs_build.stale(docs / "entries", docs) == [reports]


def test_hand_written_content_outside_a_region_survives(docs: Path) -> None:
    """The registers carry years of history that predates entries; generation must not eat it."""
    text = rendered(docs, "Known_Issues.md")

    assert "## Some topic (1)" in text
    assert text.startswith("# Known Issues")


def test_a_missing_region_marker_is_an_error(docs: Path) -> None:
    reports = docs / "Completion_Reports.md"
    reports.write_text("# Completion Reports\n", encoding="utf-8")

    with pytest.raises(docs_build.BuildError, match="missing"):
        docs_build.build(docs / "entries", docs)


def test_frontmatter_faults_are_reported_against_the_entry(docs: Path) -> None:
    entry = docs / "entries" / "T9999.1.md"
    entry.write_text(ENTRY.replace("status: complete", "status: nonsense"), encoding="utf-8")

    with pytest.raises(docs_build.BuildError, match="unknown status"):
        docs_build.build(docs / "entries", docs)

    entry.write_text(ENTRY.replace("ticket: T9999.1\n", ""), encoding="utf-8")

    with pytest.raises(docs_build.BuildError, match="missing `ticket`"):
        docs_build.build(docs / "entries", docs)


def test_the_committed_registers_are_current() -> None:
    """The gate itself: what is committed must equal what the entries render to."""
    assert docs_build.stale() == []
