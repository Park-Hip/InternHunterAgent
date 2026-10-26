from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


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
    document.write_text("<!-- lint-allow-link-path:begin -->\nMeasured `src/missing.py`.\n<!-- lint-allow-link-path:end -->\n", encoding="utf-8")

    assert docs_lint.check_link_path([document]) == []


def test_link_path_block_markers_on_one_line_do_not_disable_later_checks(tmp_path: Path) -> None:
    document = tmp_path / "audit.md"
    document.write_text(
        "<!-- lint-allow-link-path:begin --><!-- lint-allow-link-path:end -->\n"
        "See `src/missing.py`.\n",
        encoding="utf-8",
    )

    findings = docs_lint.check_link_path([document])

    assert len(findings) == 1
    assert findings[0].check == "link-path"


def test_markdown_link_in_fenced_example_is_not_checked(tmp_path: Path) -> None:
    document = tmp_path / "guide.md"
    document.write_text("```markdown\n[example](not-a-real-file.md)\n```\n", encoding="utf-8")

    assert docs_lint.check_link_path([document]) == []


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


def test_mojibake_in_code_span_is_allowed(tmp_path: Path) -> None:
    document = tmp_path / "guide.md"
    document.write_text("The bad signature is `â€`.\n", encoding="utf-8")

    assert docs_lint.check_encoding([document]) == []


def test_mojibake_outside_code_span_and_bom_are_reported(tmp_path: Path) -> None:
    document = tmp_path / "guide.md"
    document.write_bytes(b"\xef\xbb\xbfBad encoding: \xc3\xa2\xe2\x82\xac.\n")

    findings = docs_lint.check_encoding([document])

    assert {finding.message for finding in findings} == {
        "UTF-8 BOM is not allowed",
        "mojibake sequence 'â€'",
    }


PYPROJECT_SAMPLE = b"""
[project]
dependencies = ["fastapi>=0.136.3", "psycopg[binary,pool]>=3.2"]

[dependency-groups]
dev = ["ruff>=0.15.20"]
"""


def test_dependency_names_are_normalized_and_table_rows_only() -> None:
    assert docs_lint.declared_dependencies(PYPROJECT_SAMPLE) == {"fastapi", "psycopg", "ruff"}
    text = f"{docs_lint.DEPS_BEGIN}\n| Package | Role |\n|---|---|\n| `fastapi` | HTTP layer. |\nConfigured in `config/settings.yaml`.\n{docs_lint.DEPS_END}\n"

    assert docs_lint.documented_dependencies(text) == {"fastapi"}


def test_stack_check_reports_both_directions() -> None:
    declared = docs_lint.declared_dependencies(PYPROJECT_SAMPLE)
    documented = docs_lint.documented_dependencies(f"{docs_lint.DEPS_BEGIN}\n| `fastapi` | x |\n| `tenacity` | x |\n{docs_lint.DEPS_END}\n")

    assert declared - documented == {"psycopg", "ruff"}
    assert documented - declared == {"tenacity"}


def test_tech_stack_matches_pyproject() -> None:
    assert docs_lint.check_stack([]) == []


def test_archives_are_exempt_from_live_paths() -> None:
    archive = docs_lint.ROOT / "docs" / "archive" / "old.md"
    live = docs_lint.ROOT / "docs" / "how-to" / "evaluate.md"

    assert docs_lint.is_archive(archive)
    assert not docs_lint.is_archive(live)


def test_the_committed_documentation_is_clean() -> None:
    files = docs_lint.markdown_files()

    assert docs_lint.check_link_path(files) == []
    assert docs_lint.check_encoding(files) == []
    assert docs_lint.check_stack(files) == []
