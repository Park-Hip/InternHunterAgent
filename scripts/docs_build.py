"""Render the derived documentation registers from the per-ticket entry files.

Three registers that every ticket used to hand-edit now carry generated regions marked
`<!-- generated:<name>:begin -->` and `<!-- generated:<name>:end -->`. The sole source is one file
per ticket under `docs/entries/`, so a ticket branch writes a file no other branch owns. A merge
conflict inside a generated region is resolved by running this script, never by hand.

Only the regions are generated. Everything outside them stays hand-written, which is what lets a
register carry years of history that predates `docs/entries/` alongside the entries it now folds.

Since T0031.3 the same machinery derives `docs/Repo_Current_State.md`, whose regions come from the
tree rather than from the entries: milestone status from `roadmap.yaml`, dependencies from
`pyproject.toml`, and the maintenance-script inventory from `scripts/`. Those three are pure
functions of the committed tree, so the linter gates them exactly like the entry-fed regions.

The `snapshot` region is the deliberate exception. Branch, baseline commit, open branches, and
worktrees are facts about a clone rather than about a commit, so they differ between a developer
machine and CI and can never be gated by a check that must pass on both. `--snapshot` writes them
and `stale()` ignores them; the integration step is what runs it. Build status stays hand-written:
it is the result of running commands, not a reading of `git`, `roadmap.yaml`, or `pyproject.toml`.

The script keeps the no-dependency contract that `scripts/docs_lint.py` holds: the entry
frontmatter is flat scalars only and is parsed here rather than through a YAML library, and
`roadmap.yaml` is read by the same flat-scalar rule rather than by pulling in PyYAML.
"""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
import textwrap
import tomllib
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
ENTRIES = DOCS / "entries"
STATE = DOCS / "Repo_Current_State.md"
ROADMAP = DOCS / "roadmap.yaml"
PYPROJECT = ROOT / "pyproject.toml"
SCRIPTS = ROOT / "scripts"
ENTRY_NAME = re.compile(r"^T\d{4}(?:\.\d+)?$")
REGION = "<!-- generated:{name}:{edge} -->"
SECTION = re.compile(r"^## +(?P<title>.+?)\s*$", re.M)
ISSUE_ID = re.compile(r"\bKI-\d{4}-\d{2}-\d{2}-[a-z0-9-]+\b")
SEVERITY = re.compile(r"\[(HIGH|MED|LOW)\s*[·|-]\s*(OPEN|BLOCKED|DECISION)\]")
LINE_LIMIT = 100  # The limit scripts/docs_lint.py enforces; generated lines have to meet it too.
MILESTONE_ID = re.compile(r"^  - id: +(?P<id>M\d+)\s*$")
MILESTONE_FIELD = re.compile(r"^    (?P<key>[a-z_]+): +(?P<value>.+?)\s*$")
STATUSES = ("complete", "in-progress", "next", "planned", "paused")
MILESTONE_ORDER = ("in-progress", "claimed", "planned", "complete")
SEVERITIES = ("HIGH", "MED", "LOW")
STATES = ("OPEN", "BLOCKED", "DECISION")
REPORT_FIELDS = ("Summary", "Files", "Commands", "Build and test", "Risks", "Follow-ups", "Docs")


@dataclass(frozen=True)
class Entry:
    """One ticket's cradle-to-grave record, the sole source for every generated region."""

    path: Path
    meta: dict[str, str]
    sections: dict[str, str]

    @property
    def ticket(self) -> str:
        return self.meta.get("ticket", self.path.stem)

    @property
    def title(self) -> str:
        return self.meta.get("title", self.ticket)

    @property
    def status(self) -> str:
        return self.meta.get("status", "planned")

    @property
    def date(self) -> str:
        return self.meta.get("date", "")

    @property
    def is_complete(self) -> bool:
        return self.status == "complete"

    @property
    def checklist_is_open(self) -> bool:
        return self.meta.get("verified", "no") != "yes"

    def section(self, title: str) -> str:
        return self.sections.get(title, "").strip()

    def sort_key(self) -> tuple[int, ...]:
        digits = re.findall(r"\d+", self.ticket)
        return tuple(int(value) for value in digits)


class BuildError(RuntimeError):
    """A source entry or a target register is malformed in a way rendering cannot resolve."""


def read(path: Path) -> str:
    """Return the file's text with line endings normalised, so CRLF checkouts compare equal."""
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def parse_frontmatter(text: str, path: Path) -> tuple[dict[str, str], str]:
    """Split flat `key: value` frontmatter from the body. Nested YAML is deliberately unsupported."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        raise BuildError(f"{path.name}: must open with a --- frontmatter block")
    try:
        closing = lines.index("---", 1)
    except ValueError as exc:
        raise BuildError(f"{path.name}: frontmatter block is never closed") from exc
    meta: dict[str, str] = {}
    for number, line in enumerate(lines[1:closing], 2):
        if not line.strip():
            continue
        key, separator, value = line.partition(":")
        if not separator:
            raise BuildError(f"{path.name}:{number}: frontmatter needs `key: value`")
        meta[key.strip()] = value.strip()
    return meta, "\n".join(lines[closing + 1 :])


def parse_sections(body: str) -> dict[str, str]:
    """Return the `## Heading` sections of an entry body, keyed by heading text."""
    sections: dict[str, str] = {}
    matches = list(SECTION.finditer(body))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        sections[match.group("title")] = body[match.end() : end].strip("\n")
    return sections


def load_entries(entries_dir: Path = ENTRIES) -> list[Entry]:
    """Load every ticket entry, ordered by ticket number."""
    if not entries_dir.is_dir():
        return []
    loaded: list[Entry] = []
    for path in sorted(entries_dir.glob("*.md")):
        if not ENTRY_NAME.match(path.stem):
            continue
        meta, body = parse_frontmatter(read(path), path)
        for required in ("ticket", "title", "status", "date"):
            if required not in meta:
                raise BuildError(f"{path.name}: frontmatter is missing `{required}`")
        if meta["status"] not in STATUSES:
            raise BuildError(f"{path.name}: unknown status {meta['status']!r}")
        loaded.append(Entry(path=path, meta=meta, sections=parse_sections(body)))
    return sorted(loaded, key=Entry.sort_key)


def strip_generated(text: str) -> str:
    """Return the text with every generated region removed, leaving only hand-written content."""
    pattern = re.compile(
        r"<!-- generated:(?P<name>[a-z-]+):begin -->\n.*?<!-- generated:(?P=name):end -->", re.S
    )
    return pattern.sub("", text)


def render_reports(entries: list[Entry]) -> str:
    """Completion reports for finished tickets, oldest first.

    The register is append-only and reads chronologically, so a generated report lands where a
    hand-written one would have: at the end, under the reports that shipped before it.
    """
    blocks = []
    for entry in entries:
        if not entry.is_complete:
            continue
        parts = [f"## {entry.ticket} - {entry.title}", f"*Completed {entry.date}.*"]
        for field in REPORT_FIELDS:
            content = entry.section(field)
            if content:
                parts.append(f"**{field}**\n\n{content}")
        blocks.append("\n\n".join(parts))
    return "\n\n---\n\n".join(blocks)


def render_checklists(entries: list[Entry]) -> str:
    """Manual-verification checklists that have not been marked verified.

    A checklist leaves this region when its entry sets `verified: yes`, which is the guide's
    stated eviction rule expressed as code rather than as a habit.
    """
    blocks = []
    for entry in reversed(entries):
        checklist = entry.section("Manual verification")
        if not checklist or not entry.checklist_is_open:
            continue
        blocks.append(f"### {entry.ticket}: {entry.title}\n\n{checklist}")
    return "\n\n".join(blocks)


def render_registered(entries: list[Entry], register: str) -> str:
    """Issues raised by tickets that a maintainer has not yet filed into a topic section.

    Membership is decided by the issue id: paste an entry into a topic section keeping its id and
    it leaves this region on the next build, with no edit to the ticket entry and no way for the
    two copies to drift. A bullet with no id is never inboxed, which is what keeps the register's
    pre-M31 history out of it.
    """
    filed = set(ISSUE_ID.findall(strip_generated(register)))
    blocks = []
    for entry in entries:
        issues = entry.section("Known issues")
        if not issues:
            continue
        for block in re.split(r"\n(?=- )", issues):
            identifiers = set(ISSUE_ID.findall(block))
            if identifiers and not identifiers & filed:
                blocks.append(block.strip())
    return "\n\n".join(blocks)


def render_triage(register: str) -> str:
    """Severity and state counts, derived from the register instead of hand-tallied."""
    counts: dict[tuple[str, str], int] = {}
    for severity, state in SEVERITY.findall(register):
        counts[(severity, state)] = counts.get((severity, state), 0) + 1
    lines = ["| Severity | Open | Blocked | Decision |", "|---|---:|---:|---:|"]
    for severity in SEVERITIES:
        cells = " | ".join(str(counts.get((severity, state), 0)) for state in STATES)
        lines.append(f"| {severity} | {cells} |")
    return "\n".join(lines)


def parse_milestones(text: str) -> list[dict[str, str]]:
    """Return each milestone's flat scalar fields from `roadmap.yaml`, in file order.

    Only the `  - id:` / `    key: value` shape is read. Block scalars and nested lists indent
    further, so they fall through without a YAML parser having to understand them.
    """
    milestones: list[dict[str, str]] = []
    for line in text.split("\n"):
        identifier = MILESTONE_ID.match(line)
        if identifier:
            milestones.append({"id": identifier.group("id")})
            continue
        field = MILESTONE_FIELD.match(line)
        if field and milestones:
            milestones[-1].setdefault(field.group("key"), field.group("value"))
    return milestones


def compress_ids(identifiers: list[str]) -> str:
    """Collapse consecutive milestone numbers into ranges, so 30 ids read as a short line."""
    numbers = sorted(int(value.lstrip("M")) for value in identifiers)
    if not numbers:
        return "none"
    spans: list[list[int]] = [[numbers[0], numbers[0]]]
    for number in numbers[1:]:
        if number == spans[-1][1] + 1:
            spans[-1][1] = number
        else:
            spans.append([number, number])
    return ", ".join(f"M{low}" if low == high else f"M{low}-M{high}" for low, high in spans)


def render_milestones(roadmap: str) -> str:
    """Milestone status, taken from the registry that already owns milestone identity.

    Complete milestones compress to one line because their detail lives in the completion
    reports; the ones still moving get a row each, because those are what a reader is here for.
    """
    milestones = parse_milestones(roadmap)
    done = [entry["id"] for entry in milestones if entry.get("status") == "complete"]
    open_entries = [entry for entry in milestones if entry.get("status") != "complete"]
    lines = [
        f"Complete: {compress_ids(done)} - {len(done)} of {len(milestones)} milestones.",
        "",
        "| Milestone | Title | Status |",
        "|---|---|---|",
    ]
    order = {status: index for index, status in enumerate(MILESTONE_ORDER)}
    for entry in sorted(open_entries, key=lambda item: order.get(item.get("status", ""), 99)):
        lines.append(f"| {entry['id']} | {entry.get('title', '')} | {entry.get('status', '')} |")
    return "\n".join(lines)


def wrap(text: str, indent: str = "") -> str:
    """Wrap to the documentation line limit.

    Hyphen breaking is off because these lines are almost entirely hyphenated package names and
    branch names inside backticks; letting `textwrap` split one produces a broken code span.
    """
    lines = textwrap.wrap(
        text,
        width=LINE_LIMIT,
        subsequent_indent=indent,
        break_long_words=False,
        break_on_hyphens=False,
    )
    return "\n".join(lines)


def wrap_names(label: str, names: list[str]) -> str:
    """Render a dependency group as wrapped prose, which costs a fifth of the lines a table does."""
    if not names:
        return f"{label} (0): none."
    body = ", ".join(f"`{name}`" for name in names)
    return wrap(f"{label} ({len(names)}): {body}")


def render_dependencies(raw: bytes) -> str:
    """Declared dependencies, read from the file that declares them.

    Versions are deliberately omitted: `pyproject.toml` is the authority on the specifier, and
    copying it here would create a second place for it to be wrong.
    """
    data = tomllib.loads(raw.decode("utf-8"))
    runtime = [distribution(item) for item in data.get("project", {}).get("dependencies", [])]
    development: list[str] = []
    for group in data.get("dependency-groups", {}).values():
        development.extend(distribution(item) for item in group if isinstance(item, str))
    runtime_block = wrap_names("Runtime", sorted(runtime))
    return f"{runtime_block}\n\n{wrap_names('Development', sorted(development))}"


def distribution(specifier: str) -> str:
    """Strip extras, version, and marker from a requirement: `psycopg[binary]>=3.2` -> `psycopg`."""
    return re.split(r"[\[<>=!~;\s]", specifier, maxsplit=1)[0].strip()


def render_scripts(scripts: Path = SCRIPTS) -> str:
    """The `scripts/` inventory, each entry summarised by the first line of its own docstring."""
    lines = []
    for path in sorted(scripts.glob("*.py")):
        try:
            docstring = ast.get_docstring(ast.parse(read(path))) or ""
        except SyntaxError:
            docstring = ""
        summary = docstring.strip().split("\n", 1)[0].strip() or "No module docstring."
        # Source docstrings predate the documentation style, which spells this dash as a hyphen.
        summary = summary.replace("—", "-").replace("–", "-")
        lines.append(wrap(f"- `scripts/{path.name}` - {summary}", indent="  "))
    return "\n".join(lines)


def git(*args: str) -> str:
    """Run a read-only git command, returning empty output rather than raising outside a clone."""
    try:
        result = subprocess.run(
            ("git", *args),
            cwd=ROOT,
            capture_output=True,
            # Explicit UTF-8: a commit subject with a non-ASCII character otherwise crashes the
            # snapshot on a Windows locale, where `text=True` decodes as cp1252.
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if result.returncode != 0 or result.stdout is None:
        return ""
    return result.stdout.strip()


def render_snapshot() -> str:
    """Clone-local git facts: the part of this file that a commit alone cannot answer."""
    head = git("rev-parse", "--short", "HEAD")
    if not head:
        return "- Git is unavailable, so branch and commit facts could not be derived."
    subject = git("log", "-1", "--format=%s")
    stamped = git("log", "-1", "--format=%cs")
    unmerged = [
        name
        for name in git("branch", "--format=%(refname:short)", "--no-merged", "main").split("\n")
        if name
    ]
    trees = [
        line.removeprefix("worktree ")
        for line in git("worktree", "list", "--porcelain").split("\n")
        if line.startswith("worktree ")
    ]
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    names = ", ".join(f"`{name}`" for name in sorted(unmerged))
    lines = [
        wrap(f"- Checked out: `{branch}` at `{head}` - {subject} ({stamped}).", indent="  "),
        wrap(
            f"- Branches not merged into `main`: {len(unmerged)}"
            + (f" - {names}." if unmerged else "."),
            indent="  ",
        ),
        f"- Worktrees: {len(trees)}.",
    ]
    return "\n".join(lines)


def replace_region(text: str, name: str, body: str, path: Path) -> str:
    """Replace one generated region, leaving every hand-written line untouched."""
    begin = REGION.format(name=name, edge="begin")
    end = REGION.format(name=name, edge="end")
    start, stop = text.find(begin), text.find(end)
    if start == -1 or stop == -1 or stop < start:
        raise BuildError(f"{path.name}: missing {begin} / {end} markers")
    payload = f"{body}\n" if body else ""
    return f"{text[: start + len(begin)]}\n{payload}{text[stop:]}"


def build(
    entries_dir: Path = ENTRIES,
    docs: Path = DOCS,
    roadmap: Path = ROADMAP,
    pyproject: Path = PYPROJECT,
    scripts: Path = SCRIPTS,
) -> dict[Path, str]:
    """Return the rendered text of every register that carries a generated region."""
    entries = load_entries(entries_dir)
    reports = docs / "Completion_Reports.md"
    checks = docs / "Manual_Verification_Guide.md"
    issues = docs / "Known_Issues.md"

    # The triage counts tally the whole register, so the inbox has to be rendered first and
    # counted alongside the hand-filed sections; otherwise an unfiled issue is invisible to it.
    register = read(issues)
    registered = render_registered(entries, register)
    updated = replace_region(register, "registered", registered, issues)
    counted = strip_generated(updated) + registered
    rendered = {issues: replace_region(updated, "triage", render_triage(counted), issues)}

    rendered[reports] = replace_region(
        read(reports), "reports", render_reports(entries), reports
    )
    rendered[checks] = replace_region(
        read(checks), "checklists", render_checklists(entries), checks
    )

    # The state snapshot's tree-derived regions only. `snapshot` is written by --snapshot and is
    # absent here on purpose, so a check that must pass on every clone never reads a clone's git.
    state = docs / "Repo_Current_State.md"
    text = replace_region(read(state), "milestones", render_milestones(read(roadmap)), state)
    text = replace_region(text, "dependencies", render_dependencies(pyproject.read_bytes()), state)
    rendered[state] = replace_region(text, "scripts", render_scripts(scripts), state)
    return rendered


def stale(
    entries_dir: Path = ENTRIES,
    docs: Path = DOCS,
    roadmap: Path = ROADMAP,
    pyproject: Path = PYPROJECT,
    scripts: Path = SCRIPTS,
) -> list[Path]:
    """Return the registers whose generated regions no longer match their sources."""
    rendered = build(entries_dir, docs, roadmap, pyproject, scripts)
    return [path for path, text in rendered.items() if read(path) != text]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Report stale registers without writing them."
    )
    parser.add_argument(
        "--snapshot",
        action="store_true",
        help="Also refresh the clone-local git region of Repo_Current_State.md.",
    )
    args = parser.parse_args(argv)
    if args.check and args.snapshot:
        parser.error("--check cannot verify --snapshot: the git region differs between clones")
    try:
        rendered = build()
        if args.snapshot:
            rendered[STATE] = replace_region(
                rendered[STATE], "snapshot", render_snapshot(), STATE
            )
    except BuildError as error:
        print(f"docs-build: {error}")
        return 1
    changed = [path for path, text in rendered.items() if read(path) != text]
    for path in changed:
        location = path.relative_to(ROOT).as_posix()
        if args.check:
            print(f"{location}: generated regions are stale; run scripts/docs_build.py")
        else:
            path.write_text(rendered[path], encoding="utf-8", newline="\n")
            print(f"rebuilt {location}")
    if args.check:
        return 1 if changed else 0
    if not changed:
        print("docs-build: every generated region is already current")
    return 0


if __name__ == "__main__":
    sys.exit(main())
