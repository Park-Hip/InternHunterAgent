from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "docs_lint.py"
SPEC = importlib.util.spec_from_file_location("docs_lint", SCRIPT)
assert SPEC and SPEC.loader
docs_lint = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = docs_lint
SPEC.loader.exec_module(docs_lint)


def test_is_dated_record_covers_completion_reports_and_archive_dirs() -> None:
    assert docs_lint.is_dated_record(docs_lint.ROOT / "docs" / "Completion_Reports.md")
    assert docs_lint.is_dated_record(docs_lint.ROOT / "docs" / "archive" / "x.md")
    assert docs_lint.is_dated_record(docs_lint.ROOT / "docs" / "entries" / "T0031.1.md")
    assert not docs_lint.is_dated_record(docs_lint.ROOT / "docs" / "Tickets.md")


def test_is_ticket_entry_covers_only_the_entries_directory() -> None:
    assert docs_lint.is_ticket_entry(docs_lint.ROOT / "docs" / "entries" / "T0031.1.md")
    assert docs_lint.is_ticket_entry(docs_lint.ROOT / "docs" / "entries" / "README.md")
    assert not docs_lint.is_ticket_entry(docs_lint.ROOT / "docs" / "Tickets.md")
    assert not docs_lint.is_ticket_entry(docs_lint.ROOT / "docs" / "archive" / "x.md")


def test_ticket_entries_need_no_caps_row_and_no_inbound_link() -> None:
    """A per-ticket file is owned by one branch, so neither shared index applies to it."""
    entry = docs_lint.ROOT / "docs" / "entries" / "README.md"
    tickets = docs_lint.ROOT / "docs" / "Tickets.md"

    managed = docs_lint.managed_documentation_files([entry, tickets])

    assert entry.resolve() not in managed
    assert tickets.resolve() in managed
    assert docs_lint.check_orphan([entry]) == []


def test_archived_on_tag_reference_is_allowed(tmp_path: Path) -> None:
    document = tmp_path / "guide.md"
    document.write_text("See `src/core/event_loop.py`. <!-- archived-on-tag -->\n", encoding="utf-8")

    assert docs_lint.check_link_path([document]) == []


def test_measured_link_path_block_is_allowed(tmp_path: Path) -> None:
    document = tmp_path / "audit.md"
    document.write_text(
        "<!-- lint-allow-link-path:begin -->\n"
        "Measured `src/missing.py`.\n"
        "<!-- lint-allow-link-path:end -->\n",
        encoding="utf-8",
    )

    assert docs_lint.check_link_path([document]) == []


def test_markdown_link_in_fenced_example_is_not_checked(tmp_path: Path) -> None:
    document = tmp_path / "guide.md"
    document.write_text("```markdown\n[example](not-a-real-file.md)\n```\n", encoding="utf-8")

    assert docs_lint.check_link_path([document]) == []


def test_mojibake_in_code_span_is_allowed(tmp_path: Path) -> None:
    document = tmp_path / "guide.md"
    sequence = "\u00e2\u20ac"
    document.write_text(f"The bad signature is `{sequence}`.\n", encoding="utf-8")

    assert docs_lint.check_encoding([document]) == []


def test_mojibake_outside_code_span_is_reported(tmp_path: Path) -> None:
    document = tmp_path / "guide.md"
    sequence = "\u00e2\u20ac"
    document.write_text(f"Bad encoding: {sequence}.\n", encoding="utf-8")

    findings = docs_lint.check_encoding([document])

    assert len(findings) == 1
    assert findings[0].check == "encoding"


def test_dagger_mojibake_is_reported(tmp_path: Path) -> None:
    document = tmp_path / "guide.md"
    document.write_text("Bad encoding: \u00e2\u2020.\n", encoding="utf-8")

    findings = docs_lint.check_encoding([document])

    assert len(findings) == 1
    assert findings[0].check == "encoding"


def test_completion_reports_encoding_is_clean() -> None:
    report = SCRIPT.parents[1] / "docs" / "Completion_Reports.md"

    assert docs_lint.check_encoding([report]) == []


def test_shared_skill_instructions_match() -> None:
    root = SCRIPT.parents[1]
    codex_skill = root / "skills" / "generate-ticket-prompt" / "SKILL.md"
    claude_skill = root / ".claude" / "skills" / "generate-ticket-prompt" / "SKILL.md"

    if not claude_skill.exists():
        pytest.skip(".claude/ is gitignored, so the Claude Code copy is local-only")

    # Compare lines, not bytes. The tracked copy is newline-normalized on checkout when
    # core.autocrlf is set, while the untracked .claude/ copy is never touched by git.
    codex_lines = codex_skill.read_text(encoding="utf-8").splitlines()
    claude_lines = claude_skill.read_text(encoding="utf-8").splitlines()

    assert codex_lines == claude_lines


def test_reflow_preserves_blockquote_prefix(tmp_path: Path) -> None:
    document = tmp_path / "guide.md"
    document.write_text(f"> {'word ' * 30}\n", encoding="utf-8")

    docs_lint.reflow_line_length([document])

    assert all(line.startswith("> ") for line in document.read_text(encoding="utf-8").splitlines())


def test_reflow_preserves_list_content_columns(tmp_path: Path) -> None:
    cases = (("- ", "  "), ("  - ", "    "), ("1. ", "   "))
    for number, (prefix, continuation) in enumerate(cases):
        document = tmp_path / f"guide-{number}.md"
        document.write_text(f"{prefix}{'word ' * 30}\n", encoding="utf-8")

        docs_lint.reflow_line_length([document])

        lines = document.read_text(encoding="utf-8").splitlines()
        assert lines[0].startswith(prefix)
        assert all(line.startswith(continuation) for line in lines[1:])


def test_reflow_does_not_touch_yaml_frontmatter(tmp_path: Path) -> None:
    document = tmp_path / "guide.md"
    frontmatter = f"description: {'word ' * 30}\n"
    document.write_text(f"---\n{frontmatter}---\n", encoding="utf-8")

    assert docs_lint.reflow_line_length([document]) == []
    assert frontmatter in document.read_text(encoding="utf-8")


def test_link_only_code_path_with_punctuation_is_line_length_exempt() -> None:
    line = "`tests/services/test_example.py::Example::test_a_very_long_name_for_regression_coverage`."

    assert docs_lint.is_line_length_exempt(line, in_fence=False)


def test_link_only_markdown_reference_is_line_length_exempt() -> None:
    line = "> [A deliberately long reference](../research/archive/agent-behavior-question-bank.md)"

    assert docs_lint.is_line_length_exempt(line, in_fence=False)


def test_missing_repo_path_is_reported(tmp_path: Path) -> None:
    document = tmp_path / "guide.md"
    document.write_text("See `src/missing.py`.\n", encoding="utf-8")

    findings = docs_lint.check_link_path([document])

    assert len(findings) == 1
    assert findings[0].check == "link-path"


def test_branch_name_is_not_treated_as_a_missing_repo_path(tmp_path: Path) -> None:
    document = tmp_path / "guide.md"
    document.write_text("Use branch `docs/some-branch`.\n", encoding="utf-8")

    assert docs_lint.check_link_path([document]) == []


PYPROJECT_SAMPLE = b"""
[project]
dependencies = ["fastapi>=0.136.3", "psycopg[binary,pool]>=3.2"]

[dependency-groups]
dev = ["ruff>=0.15.20"]
"""


def test_extras_and_specifiers_are_stripped_from_dependency_names() -> None:
    """`psycopg[binary,pool]>=3.2` must resolve to `psycopg`, not swallow the group."""
    assert docs_lint.declared_dependencies(PYPROJECT_SAMPLE) == {"fastapi", "psycopg", "ruff"}


def test_documented_dependencies_reads_table_rows_only() -> None:
    """Prose inside the marked region may use backticks without registering as a dependency."""
    text = (
        f"{docs_lint.DEPS_BEGIN}\n"
        "| Package | Role |\n|---|---|\n"
        "| `fastapi` | HTTP layer. |\n"
        "Configured in `config/settings.yaml` under `agent`.\n"
        f"{docs_lint.DEPS_END}\n"
    )

    assert docs_lint.documented_dependencies(text) == {"fastapi"}


def test_stack_check_reports_both_directions() -> None:
    declared = docs_lint.declared_dependencies(PYPROJECT_SAMPLE)
    documented = docs_lint.documented_dependencies(
        f"{docs_lint.DEPS_BEGIN}\n| `fastapi` | x |\n| `tenacity` | x |\n{docs_lint.DEPS_END}\n"
    )

    assert declared - documented == {"psycopg", "ruff"}  # added but undocumented
    assert documented - declared == {"tenacity"}  # documented but removed


def test_tech_stack_matches_pyproject() -> None:
    """The shipped Tech_Stack.md must agree with the real pyproject.toml."""
    assert docs_lint.check_stack([]) == []


def test_stamp_check_reports_missing_stamp(tmp_path: Path) -> None:
    document = tmp_path / "current-state.md"
    document.write_text("# Current State\n", encoding="utf-8")

    findings = docs_lint.check_stamps((document,))

    assert len(findings) == 1
    assert findings[0].check == "stamp"


def test_required_living_documents_have_stamps() -> None:
    assert docs_lint.check_stamps() == []


def write_caps_map(tmp_path: Path, capped_body: str, cap: int = 10) -> tuple[Path, Path]:
    docs = tmp_path / "docs"
    docs.mkdir()
    document = docs / "capped.md"
    document.write_text(capped_body, encoding="utf-8")
    map_path = docs / "README.md"
    map_path.write_text(
        f"{docs_lint.CAPS_BEGIN}\n"
        "| Doc | Owns | Tier | Cap | Reader |\n"
        "|---|---|---:|---:|---|\n"
        "| [Map](README.md) | Map | T3 | Uncapped | Maintainers |\n"
        f"| [Capped](capped.md) | Test | T3 | {cap} | Maintainers |\n"
        f"{docs_lint.CAPS_END}\n",
        encoding="utf-8",
    )
    return map_path, document


def test_documented_caps_parses_the_marked_table(tmp_path: Path) -> None:
    map_path, document = write_caps_map(tmp_path, "one\n")

    entries = docs_lint.documented_caps(map_path.read_text(encoding="utf-8"), map_path)

    assert entries[document.resolve()].cap == 10
    assert entries[map_path.resolve()].cap is None


def test_size_cap_reports_an_overage_and_an_unindexed_document(tmp_path: Path) -> None:
    map_path, document = write_caps_map(tmp_path, "one\ntwo\n", cap=1)

    findings = docs_lint.check_size_cap([map_path, document], map_path)

    assert any(finding.path == document and "exceeds cap" in finding.message for finding in findings)

    document.write_text("one\n", encoding="utf-8")
    assert docs_lint.check_size_cap([map_path, document], map_path) == []

    map_path.write_text(
        map_path.read_text(encoding="utf-8").replace(
            "| [Capped](capped.md) | Test | T3 | 1 | Maintainers |\n", ""
        ),
        encoding="utf-8",
    )
    findings = docs_lint.check_size_cap([map_path, document], map_path)

    assert any("missing from caps table" in finding.message for finding in findings)


def test_eviction_rule_reports_a_missing_header_and_accepts_one(tmp_path: Path) -> None:
    map_path, document = write_caps_map(tmp_path, "# Capped\n")

    findings = docs_lint.check_eviction_rule([], map_path)

    assert len(findings) == 1
    document.write_text("# Capped\n\n> **Eviction:** Test content leaves when retired.\n", encoding="utf-8")
    assert docs_lint.check_eviction_rule([], map_path) == []


def test_amendment_reports_a_phrase_and_allows_a_marked_exception(tmp_path: Path) -> None:
    map_path, document = write_caps_map(tmp_path, "This is no longer accurate.\n")

    findings = docs_lint.check_amendment([], map_path)

    assert len(findings) == 1
    document.write_text(
        "This is no longer accurate. <!-- lint-allow-amendment -->\n", encoding="utf-8"
    )
    assert docs_lint.check_amendment([], map_path) == []


def write_scenario_registry(tmp_path: Path, *ids: str) -> Path:
    registry = tmp_path / "scenarios.yaml"
    registry.write_text(
        "".join(f"- id: {identifier}\n  input: ask something\n" for identifier in ids),
        encoding="utf-8",
    )
    return registry


def test_registered_scenario_ids_reads_registry_entries_only() -> None:
    text = "- id: HLP-COUNT-1\n  expected: mentions id: not-an-entry\n- id: SAF-INJECTION-REFUSAL-1\n"

    assert docs_lint.registered_scenario_ids(text) == {"HLP-COUNT-1", "SAF-INJECTION-REFUSAL-1"}


def test_scenario_id_reports_an_id_the_registry_does_not_define(tmp_path: Path) -> None:
    registry = write_scenario_registry(tmp_path, "HLP-COUNT-1")
    document = tmp_path / "guide.md"
    document.write_text("`HLP-COUNT-1` passes but HLP-RENAMED-1 does not.\n", encoding="utf-8")

    findings = docs_lint.check_scenario_id([document], registry)

    assert len(findings) == 1
    assert findings[0].check == "scenario-id"
    assert "HLP-RENAMED-1" in findings[0].message


def test_scenario_id_accepts_a_marked_example(tmp_path: Path) -> None:
    registry = write_scenario_registry(tmp_path, "HLP-COUNT-1")
    document = tmp_path / "guide.md"
    document.write_text("Try HLP-NOT-A-SCENARIO-9. <!-- lint-allow-scenario-id -->\n", encoding="utf-8")

    assert docs_lint.check_scenario_id([document], registry) == []


def test_scenario_id_reports_a_missing_registry(tmp_path: Path) -> None:
    findings = docs_lint.check_scenario_id([], tmp_path / "absent.yaml")

    assert len(findings) == 1
    assert findings[0].check == "scenario-id"


def test_documented_scenario_ids_all_exist() -> None:
    """Every scenario named in the shipped documentation must resolve in the registry."""
    assert docs_lint.check_scenario_id(docs_lint.markdown_files()) == []


def test_orphan_reports_an_unlinked_document_and_clears_after_linking(tmp_path: Path) -> None:
    entry = tmp_path / "entry.md"
    index = tmp_path / "index.md"
    orphan = tmp_path / "orphan.md"
    entry.write_text("[Index](index.md)\n", encoding="utf-8")
    index.write_text("[Entry](entry.md)\n", encoding="utf-8")
    orphan.write_text("# Orphan\n", encoding="utf-8")

    findings = docs_lint.check_orphan([entry, index, orphan])

    assert [finding.path for finding in findings] == [orphan]
    index.write_text("[Entry](entry.md)\n[Orphan](orphan.md)\n", encoding="utf-8")
    assert docs_lint.check_orphan([entry, index, orphan]) == []


def test_generated_check_reports_a_stale_register(monkeypatch: pytest.MonkeyPatch) -> None:
    """The check owns no rendering: it reports whatever docs_build says has drifted."""
    stale = docs_lint.ROOT / "docs" / "Known_Issues.md"
    monkeypatch.setattr(docs_lint.docs_build, "stale", lambda: [stale])

    findings = docs_lint.check_generated([])

    assert [finding.path for finding in findings] == [stale]
    assert "docs_build" in findings[0].message


def test_generated_check_reports_an_unbuildable_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    def explode() -> list[Path]:
        raise docs_lint.docs_build.BuildError("T9999.md: frontmatter is missing `ticket`")

    monkeypatch.setattr(docs_lint.docs_build, "stale", explode)

    findings = docs_lint.check_generated([])

    assert len(findings) == 1
    assert "cannot run" in findings[0].message


def test_the_committed_generated_regions_are_current() -> None:
    assert docs_lint.check_generated([]) == []
