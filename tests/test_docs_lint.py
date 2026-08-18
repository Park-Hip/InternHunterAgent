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


# --- T0031.4: the protocol checks -------------------------------------------------------------

ROADMAP_TEXT = """version: 1

frozen:
  - docs/Tickets.md
  - docs/Known_Issues.md

milestones:
  - id: M0
    title: Foundation through Hardening (M0-M5)
    status: complete
    tickets: [T0000, T0003]
  - id: M6
    title: A milestone
    status: complete
    tickets: [T0006]
  - id: M7
    title: Another milestone
    status: in-progress
    tickets: [T0007.1]
    scope:
      - scripts/docs_lint.py
      - docs/entries/
    note: >-
      A block scalar must not be read as a scope entry.
"""


def test_parse_roadmap_reads_the_nested_lists() -> None:
    milestones, frozen = docs_lint.parse_roadmap(ROADMAP_TEXT)

    assert frozen == ["docs/Tickets.md", "docs/Known_Issues.md"]
    assert [item["id"] for item in milestones] == ["M0", "M6", "M7"]
    assert milestones[2]["scope"] == ["scripts/docs_lint.py", "docs/entries/"]
    assert milestones[2]["tickets"] == ["T0007.1"]
    # The block scalar under note: indents past a field and must not land in scope.
    assert milestones[0]["scope"] == []


def test_an_aggregate_milestone_covers_its_titled_range() -> None:
    """M0 stands for six milestones, so M1-M5 are accounted for rather than skipped."""
    milestones, _ = docs_lint.parse_roadmap(ROADMAP_TEXT)

    assert docs_lint.covered_numbers(milestones[0]) == {0, 1, 2, 3, 4, 5}
    assert docs_lint.covered_numbers(milestones[1]) == {6}


def test_within_scope_matches_files_exactly_and_directories_by_prefix() -> None:
    scope = ["scripts/docs_lint.py", "docs/entries/"]

    assert docs_lint.within_scope("scripts/docs_lint.py", scope)
    assert docs_lint.within_scope("docs/entries/T0007.1.md", scope)
    assert not docs_lint.within_scope("scripts/docs_build.py", scope)
    # A prefix that is not a directory boundary must not match.
    assert not docs_lint.within_scope("docs/entries-old.md", scope)


def test_the_registry_check_passes_on_the_committed_roadmap() -> None:
    """The gate itself: this repository's own registry must satisfy the rule it now enforces."""
    assert docs_lint.check_registry([]) == []


def write_roadmap(root: Path, text: str) -> None:
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "roadmap.yaml").write_text(text, encoding="utf-8")


def test_registry_reports_gaps_duplicates_and_misfiled_tickets(tmp_path: Path) -> None:
    broken = ROADMAP_TEXT.replace(
        "  - id: M6\n    title: A milestone\n", "  - id: M8\n    title: A milestone\n"
    ).replace("tickets: [T0007.1]", "tickets: [T0009.1]")
    write_roadmap(tmp_path, broken)

    messages = [
        finding.message
        for finding in docs_lint.check_registry([], tmp_path / "docs" / "roadmap.yaml")
    ]

    # M0 covers 0-5 and the renamed entry claims 8, so 6 is the number nothing accounts for.
    assert any("M6 is skipped" in message for message in messages)
    assert any("T0009.1 sits under M7" in message for message in messages)


def git(root: Path, *args: str) -> None:
    import subprocess

    subprocess.run(("git", *args), cwd=root, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A miniature repository with a main branch, a roadmap, and a ticket branch off it."""
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "Test")
    write_roadmap(root, ROADMAP_TEXT)
    (root / "scripts").mkdir()
    (root / "scripts" / "docs_lint.py").write_text("# lint\n", encoding="utf-8")
    (root / "docs" / "Tickets.md").write_text(
        "# Tickets\n\n<!-- generated:reports:begin -->\nold\n<!-- generated:reports:end -->\n\ntail\n",
        encoding="utf-8",
    )
    git(root, "add", "-A")
    git(root, "commit", "-qm", "base")
    git(root, "checkout", "-qb", "feature/t0007.1-thing")
    return root


def test_scope_accepts_a_declared_path_and_rejects_an_undeclared_one(repo: Path) -> None:
    (repo / "scripts" / "docs_lint.py").write_text("# changed\n", encoding="utf-8")

    assert docs_lint.check_scope([], "main", repo) == []

    (repo / "scripts" / "other.py").write_text("# stray\n", encoding="utf-8")
    git(repo, "add", "-A")
    findings = docs_lint.check_scope([], "main", repo)

    assert [finding.path.name for finding in findings] == ["other.py"]
    assert "M7" in findings[0].message


def test_scope_allows_a_change_confined_to_a_generated_region(repo: Path) -> None:
    """A ticket branch that runs the mandatory generator must not be rejected for the result.

    `check_frozen` already exempts these bytes. Without the same exemption here, a branch that
    adds a docs/entries/ file deadlocks: the `generated` check fails if it does not rebuild the
    registers, and this check fails if it does.
    """
    tickets = repo / "docs" / "Tickets.md"
    tickets.write_text(
        tickets.read_text(encoding="utf-8").replace("old", "regenerated"), encoding="utf-8"
    )
    git(repo, "add", "-A")

    assert docs_lint.check_scope([], "main", repo) == []


def test_scope_still_rejects_a_hand_edit_to_an_undeclared_register(repo: Path) -> None:
    """The exemption is the generated region and nothing wider."""
    tickets = repo / "docs" / "Tickets.md"
    tickets.write_text(tickets.read_text(encoding="utf-8") + "a hand edit\n", encoding="utf-8")
    git(repo, "add", "-A")

    findings = docs_lint.check_scope([], "main", repo)

    assert [finding.path.name for finding in findings] == ["Tickets.md"]


def test_scope_reports_nothing_when_no_base_resolves(repo: Path) -> None:
    """A clone with no comparable base has no change set to judge, so the check is silent."""
    assert docs_lint.check_scope([], "no/such/ref", repo) == []


def test_frozen_rejects_a_hand_edit_to_a_register(repo: Path) -> None:
    tickets = repo / "docs" / "Tickets.md"
    tickets.write_text(tickets.read_text(encoding="utf-8") + "a hand edit\n", encoding="utf-8")
    git(repo, "add", "-A")

    findings = docs_lint.check_frozen([], "main", repo)

    assert [finding.path.name for finding in findings] == ["Tickets.md"]


def test_frozen_allows_a_change_confined_to_a_generated_region(repo: Path) -> None:
    """The generator writes those bytes, and the `generated` check makes running it mandatory.

    This is the rule that lets a ticket branch carry a rebuilt register, which is what every
    M31 ticket has had to do since T0031.2.
    """
    tickets = repo / "docs" / "Tickets.md"
    tickets.write_text(
        tickets.read_text(encoding="utf-8").replace("old", "regenerated"), encoding="utf-8"
    )
    git(repo, "add", "-A")

    assert docs_lint.check_frozen([], "main", repo) == []


def test_frozen_allows_the_integration_commit(repo: Path) -> None:
    tickets = repo / "docs" / "Tickets.md"
    tickets.write_text(tickets.read_text(encoding="utf-8") + "published\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "docs(integration): publish the entry")

    assert docs_lint.check_frozen([], "main", repo) == []


def test_frozen_ignores_paths_that_are_not_frozen(repo: Path) -> None:
    (repo / "scripts" / "docs_lint.py").write_text("# changed\n", encoding="utf-8")
    git(repo, "add", "-A")

    assert docs_lint.check_frozen([], "main", repo) == []


def test_frozen_allows_a_register_the_milestone_declared_in_its_scope(repo: Path) -> None:
    """Declaring a frozen path in `scope:` is the decision made in the open that the rule wants.

    M31 is the standing case: it is the milestone that installs the marked regions and the caps
    rows into these registers, so the check it adds must not forbid the work that adds it.
    """
    roadmap = repo / "docs" / "roadmap.yaml"
    roadmap.write_text(
        ROADMAP_TEXT.replace(
            "      - scripts/docs_lint.py\n", "      - scripts/docs_lint.py\n      - docs/Tickets.md\n"
        ),
        encoding="utf-8",
    )
    tickets = repo / "docs" / "Tickets.md"
    tickets.write_text(tickets.read_text(encoding="utf-8") + "a declared edit\n", encoding="utf-8")
    git(repo, "add", "-A")

    assert docs_lint.check_frozen([], "main", repo) == []


def test_git_text_decodes_utf8_regardless_of_platform_locale(repo: Path) -> None:
    """`git show` on these registers returns UTF-8; the platform locale must not decode it."""
    path = repo / "docs" / "Tickets.md"
    path.write_text("# Tickets\n\nA middot \u00b7 and an em dash \u2014 survive.\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "unicode")

    shown = docs_lint.git_text("show", "HEAD:docs/Tickets.md", root=repo)

    assert shown is not None
    assert "\u00b7" in shown and "\u2014" in shown


def test_scope_sees_an_untracked_file(repo: Path) -> None:
    """A new file is untracked until someone stages it, which is before the mistake is permanent."""
    (repo / "scripts" / "stray.py").write_text("# stray\n", encoding="utf-8")

    findings = docs_lint.check_scope([], "main", repo)

    assert [finding.path.name for finding in findings] == ["stray.py"]
