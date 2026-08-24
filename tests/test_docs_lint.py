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


def write_scenario_registry(tmp_path: Path, *ids: str) -> Path:
    registry = tmp_path / "scenarios.yaml"
    registry.write_text("".join(f"- id: {identifier}\n  input: ask something\n" for identifier in ids), encoding="utf-8")
    return registry


def test_registered_scenario_ids_reads_registry_entries_only() -> None:
    text = "- id: HLP-COUNT-1\n  expected: mentions id: not-an-entry\n- id: SAF-INJECTION-REFUSAL-1\n"

    assert docs_lint.registered_scenario_ids(text) == {"HLP-COUNT-1", "SAF-INJECTION-REFUSAL-1"}


def test_scenario_id_reports_an_unknown_id_and_allows_marked_examples(tmp_path: Path) -> None:
    registry = write_scenario_registry(tmp_path, "HLP-COUNT-1")
    document = tmp_path / "guide.md"
    document.write_text("`HLP-COUNT-1` passes but HLP-RENAMED-1 does not.\n", encoding="utf-8")

    findings = docs_lint.check_scenario_id([document], registry)

    assert len(findings) == 1
    assert "HLP-RENAMED-1" in findings[0].message
    document.write_text("Try HLP-NOT-A-SCENARIO-9. <!-- lint-allow-scenario-id -->\n", encoding="utf-8")
    assert docs_lint.check_scenario_id([document], registry) == []


def test_scenario_id_reports_a_missing_registry_and_skips_archives(tmp_path: Path) -> None:
    assert docs_lint.check_scenario_id([], tmp_path / "absent.yaml")[0].check == "scenario-id"
    archive = docs_lint.ROOT / "docs" / "archive" / "old.md"
    assert docs_lint.is_archive(archive)


def test_documented_scenario_ids_all_exist() -> None:
    assert docs_lint.check_scenario_id(docs_lint.markdown_files()) == []


def test_the_committed_documentation_is_clean() -> None:
    files = docs_lint.markdown_files()

    assert docs_lint.check_link_path(files) == []
    assert docs_lint.check_encoding(files) == []
    assert docs_lint.check_stack(files) == []
