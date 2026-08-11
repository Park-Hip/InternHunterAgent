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
