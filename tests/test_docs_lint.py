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

    assert codex_skill.read_bytes() == claude_skill.read_bytes()


def test_missing_repo_path_is_reported(tmp_path: Path) -> None:
    document = tmp_path / "guide.md"
    document.write_text("See `src/missing.py`.\n", encoding="utf-8")

    findings = docs_lint.check_link_path([document])

    assert len(findings) == 1
    assert findings[0].check == "link-path"
