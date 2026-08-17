"""Render the derived documentation registers from the per-ticket entry files.

Every register that used to be hand-edited by each ticket now carries generated regions marked
`<!-- generated:<name>:begin -->` and `<!-- generated:<name>:end -->`. The sole source is one file
per ticket under `docs/entries/`, so a ticket branch writes a file no other branch owns. A merge
conflict inside a generated region is resolved by running this script, never by hand.

The script keeps the no-dependency contract that `scripts/docs_lint.py` holds: the entry
frontmatter is flat scalars only and is parsed here rather than through a YAML library.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
ENTRIES = DOCS / "entries"
ENTRY_NAME = re.compile(r"^T\d{4}(?:\.\d+)?$")
REGION = "<!-- generated:{name}:{edge} -->"
REGION_ANY = re.compile(
    r"<!-- generated:(?P<name>[a-z-]+):begin -->\n(?P<body>.*?)<!-- generated:(?P=name):end -->",
    re.S,
)
SECTION = re.compile(r"^## +(?P<title>.+?)\s*$", re.M)
TABLE_ROW = re.compile(r"^\|(?P<cells>.+)\|\s*$", re.M)
ISSUE_ID = re.compile(r"\bKI-\d{4}-\d{2}-\d{2}-[a-z0-9-]+\b")
SEVERITY = re.compile(r"\[(HIGH|MED|LOW)\s*[·|-]\s*(OPEN|BLOCKED|DECISION)\]")
STATUS_GLYPH = {
    "complete": "✅",
    "in-progress": "\U0001f528",
    "next": "▶",
    "planned": "\U0001f4cb",
    "paused": "⏸",
}
SEVERITIES = ("HIGH", "MED", "LOW")
STATES = ("OPEN", "BLOCKED", "DECISION")


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
    def milestone(self) -> str:
        return self.meta.get("milestone", "")

    @property
    def title(self) -> str:
        return self.meta.get("title", self.ticket)

    @property
    def status(self) -> str:
        return self.meta.get("status", "planned")

    @property
    def goal(self) -> str:
        return self.meta.get("goal", "")

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
        if meta["status"] not in STATUS_GLYPH:
            raise BuildError(f"{path.name}: unknown status {meta['status']!r}")
        loaded.append(Entry(path=path, meta=meta, sections=parse_sections(body)))
    return sorted(loaded, key=Entry.sort_key)


def newest_date(entries: list[Entry]) -> str:
    return max((entry.date for entry in entries if entry.date), default="")


def strip_generated(text: str) -> str:
    """Return the text with every generated region emptied, leaving only hand-written content."""
    return REGION_ANY.sub("", text)


def table_rows(text: str) -> list[list[str]]:
    """Return the data rows of the first Markdown table in the text."""
    rows: list[list[str]] = []
    for match in TABLE_ROW.finditer(text):
        cells = [cell.strip() for cell in match.group("cells").split("|")]
        if not cells or set("".join(cells)) <= {"-", ":"} or not any(cells):
            continue
        rows.append(cells)
    return rows[1:] if rows else rows


def render_index(entries: list[Entry]) -> str:
    """Milestone index rows, one per ticket entry."""
    lines = []
    for entry in entries:
        glyph = STATUS_GLYPH[entry.status]
        lines.append(
            f"| {entry.milestone} | {entry.ticket} | {entry.title} | {glyph} | {entry.goal} |"
        )
    return "\n".join(lines)


def render_plans(entries: list[Entry]) -> str:
    """Plan bodies for tickets that are not yet complete.

    A completed ticket drops out of this region automatically, which is the eviction rule for
    ticket plans expressed as code rather than as a habit.
    """
    blocks = []
    for entry in entries:
        plan = entry.section("Plan")
        if entry.is_complete or not plan:
            continue
        blocks.append(f"## {entry.ticket}: {entry.title}\n\n{plan}")
    return "\n\n---\n\n".join(blocks)


def render_reports(entries: list[Entry]) -> str:
    """Completion reports for finished tickets, newest first."""
    fields = ("Summary", "Files", "Commands", "Build and test", "Risks", "Follow-ups", "Docs")
    blocks = []
    for entry in reversed(entries):
        if not entry.is_complete:
            continue
        parts = [f"## {entry.ticket} - {entry.title}", f"*Completed {entry.date}.*"]
        for field in fields:
            content = entry.section(field)
            if content:
                parts.append(f"**{field}**\n\n{content}")
        blocks.append("\n\n".join(parts))
    return "\n\n---\n\n".join(blocks)


def render_checklists(entries: list[Entry]) -> str:
    """Manual-verification checklists that have not been marked verified."""
    blocks = []
    for entry in reversed(entries):
        checklist = entry.section("Manual verification")
        if not checklist or not entry.checklist_is_open:
            continue
        blocks.append(f"### {entry.ticket}: {entry.title}\n\n{checklist}")
    return "\n\n".join(blocks)


def render_milestones(entries: list[Entry]) -> str:
    """One paragraph per completed milestone, for the current-state snapshot."""
    lines = []
    for entry in entries:
        if not entry.is_complete:
            continue
        label = f"M{entry.milestone} - " if entry.milestone else ""
        lines.append(f"{label}{entry.title} is complete as of {entry.date} ({entry.ticket}). "
                     f"{entry.goal}".rstrip())
    return "\n\n".join(lines)


def render_tests(entries: list[Entry]) -> str:
    """The build and test table, keeping the newest recorded result for each check.

    A check that no ticket has re-run drops off the table rather than carrying a stale claim
    forward, which is the same honesty rule the rest of this repository applies to measurements.
    """
    latest: dict[str, tuple[str, str]] = {}
    for entry in entries:
        for row in table_rows(entry.section("Build and test")):
            if len(row) < 3:
                continue
            check, result, date = row[0], row[1], row[2]
            if not check:
                continue
            if check not in latest or date >= latest[check][1]:
                latest[check] = (result, date)
    if not latest:
        return "| Check | Most recent recorded result | Date |\n|---|---|---|"
    lines = ["| Check | Most recent recorded result | Date |", "|---|---|---|"]
    for check in sorted(latest):
        result, date = latest[check]
        lines.append(f"| {check} | {result} | {date} |")
    return "\n".join(lines)


def render_registered(entries: list[Entry], register: str) -> str:
    """Issues raised by tickets that a maintainer has not yet filed into a topic section.

    Membership is decided by the issue id: paste an entry into a topic section keeping its id and
    it leaves this region on the next build, with no edit to the ticket entry and no way for the
    two copies to drift.
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


def render_stamp(entries: list[Entry], subject: str) -> str:
    """The verification stamp, dated from the newest entry rather than from the clock."""
    date = newest_date(entries) or "1970-01-01"
    return f"> **Last verified:** {date} against {subject}."


def replace_region(text: str, name: str, body: str, path: Path) -> str:
    """Replace one generated region, leaving every hand-written line untouched."""
    begin = REGION.format(name=name, edge="begin")
    end = REGION.format(name=name, edge="end")
    start, stop = text.find(begin), text.find(end)
    if start == -1 or stop == -1 or stop < start:
        raise BuildError(f"{path.name}: missing {begin} / {end} markers")
    payload = f"{body}\n" if body else ""
    return f"{text[: start + len(begin)]}\n{payload}{text[stop:]}"


def build(entries_dir: Path = ENTRIES, docs: Path = DOCS) -> dict[Path, str]:
    """Return the rendered text of every register that carries a generated region."""
    entries = load_entries(entries_dir)
    tickets = docs / "Tickets.md"
    state = docs / "Repo_Current_State.md"
    reports = docs / "Completion_Reports.md"
    checks = docs / "Manual_Verification_Guide.md"
    issues = docs / "Known_Issues.md"

    rendered: dict[Path, str] = {}
    register = read(issues)
    registered = render_registered(entries, register)
    updated = replace_region(register, "registered", registered, issues)
    rendered[issues] = replace_region(
        updated, "triage", render_triage(strip_generated(updated) + registered), issues
    )

    plan_subject = "the ticket entries under `docs/entries/`"
    for path, regions in (
        (
            tickets,
            {
                "stamp": render_stamp(entries, plan_subject),
                "index": render_index(entries),
                "plans": render_plans(entries),
            },
        ),
        (
            state,
            {
                "stamp": render_stamp(entries, "the ticket entries and the recorded check results"),
                "milestones": render_milestones(entries),
                "tests": render_tests(entries),
            },
        ),
        (reports, {"reports": render_reports(entries)}),
        (checks, {"checklists": render_checklists(entries)}),
    ):
        text = read(path)
        for name, body in regions.items():
            text = replace_region(text, name, body, path)
        rendered[path] = text
    return rendered


def stale(entries_dir: Path = ENTRIES, docs: Path = DOCS) -> list[Path]:
    """Return the registers whose generated regions no longer match their sources."""
    return [path for path, text in build(entries_dir, docs).items() if read(path) != text]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Report stale registers without writing them."
    )
    args = parser.parse_args(argv)
    try:
        rendered = build()
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
