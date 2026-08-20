"""Render the tree-derived regions of the repository state document.

Only the tree-derived regions in ``docs/Repo_Current_State.md`` remain. Milestone status comes from
``docs/roadmap.yaml``, dependencies from ``pyproject.toml``, and scripts from ``scripts/``.
The snapshot region is clone-local and is deliberately not included in ``stale()``.
"""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
import textwrap
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
STATE = DOCS / "Repo_Current_State.md"
ROADMAP = DOCS / "roadmap.yaml"
PYPROJECT = ROOT / "pyproject.toml"
SCRIPTS = ROOT / "scripts"
REGION = "<!-- generated:{name}:{edge} -->"
LINE_LIMIT = 100
MILESTONE_ID = re.compile(r"^  - id: +(?P<id>M\d+)\s*$")
MILESTONE_FIELD = re.compile(r"^    (?P<key>[a-z_]+): +(?P<value>.+?)\s*$")
MILESTONE_ORDER = ("in-progress", "claimed", "planned", "complete")


class BuildError(RuntimeError):
    """A state document is malformed in a way rendering cannot resolve."""


def read(path: Path) -> str:
    """Return text with normalized line endings so CRLF checkouts compare equal."""
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def parse_milestones(text: str) -> list[dict[str, str]]:
    """Read flat milestone scalars from ``roadmap.yaml`` without a YAML dependency."""
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
    """Collapse consecutive milestone numbers into ranges."""
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
    """Render milestone status from the registry that owns it."""
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
    """Wrap generated prose without splitting package or branch names."""
    return "\n".join(
        textwrap.wrap(
            text,
            width=LINE_LIMIT,
            subsequent_indent=indent,
            break_long_words=False,
            break_on_hyphens=False,
        )
    )


def wrap_names(label: str, names: list[str]) -> str:
    if not names:
        return f"{label} (0): none."
    return wrap(f"{label} ({len(names)}): " + ", ".join(f"`{name}`" for name in names))


def distribution(specifier: str) -> str:
    """Strip extras, version, and markers from a dependency specifier."""
    return re.split(r"[\[<>=!~;\s]", specifier, maxsplit=1)[0].strip()


def render_dependencies(raw: bytes) -> str:
    """Render dependency names from the file that declares them."""
    data = tomllib.loads(raw.decode("utf-8"))
    runtime = [distribution(item) for item in data.get("project", {}).get("dependencies", [])]
    development: list[str] = []
    for group in data.get("dependency-groups", {}).values():
        development.extend(distribution(item) for item in group if isinstance(item, str))
    return f"{wrap_names('Runtime', sorted(runtime))}\n\n{wrap_names('Development', sorted(development))}"


def render_scripts(scripts: Path = SCRIPTS) -> str:
    """Render each script with the first line of its own docstring."""
    lines = []
    for path in sorted(scripts.glob("*.py")):
        try:
            docstring = ast.get_docstring(ast.parse(read(path))) or ""
        except SyntaxError:
            docstring = ""
        summary = docstring.strip().split("\n", 1)[0].strip() or "No module docstring."
        summary = summary.replace(chr(0x2014), "-").replace(chr(0x2013), "-")
        lines.append(wrap(f"- `scripts/{path.name}` - {summary}", indent="  "))
    return "\n".join(lines)


def git(*args: str) -> str:
    """Run a read-only git command, returning an empty result outside a usable clone."""
    try:
        result = subprocess.run(
            ("git", *args), cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace",
            check=False, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 and result.stdout else ""


def render_snapshot() -> str:
    """Render clone-local git facts that cannot be validated by a CI check."""
    head = git("rev-parse", "--short", "HEAD")
    if not head:
        return "- Git is unavailable, so branch and commit facts could not be derived."
    subject = git("log", "-1", "--format=%s")
    stamped = git("log", "-1", "--format=%cs")
    unmerged = [name for name in git("branch", "--format=%(refname:short)", "--no-merged", "main").split("\n") if name]
    worktrees = [line for line in git("worktree", "list", "--porcelain").split("\n") if line.startswith("worktree ")]
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    names = ", ".join(f"`{name}`" for name in sorted(unmerged))
    return "\n".join([
        wrap(f"- Checked out: `{branch}` at `{head}` - {subject} ({stamped}).", indent="  "),
        wrap(f"- Branches not merged into `main`: {len(unmerged)}" + (f" - {names}." if unmerged else "."), indent="  "),
        f"- Worktrees: {len(worktrees)}.",
    ])


def replace_region(text: str, name: str, body: str, path: Path) -> str:
    """Replace one marked region while preserving all hand-written content."""
    begin = REGION.format(name=name, edge="begin")
    end = REGION.format(name=name, edge="end")
    start, stop = text.find(begin), text.find(end)
    if start == -1 or stop == -1 or stop < start:
        raise BuildError(f"{path.name}: missing {begin} / {end} markers")
    payload = f"{body}\n" if body else ""
    return f"{text[: start + len(begin)]}\n{payload}{text[stop:]}"


def build(
    docs: Path = DOCS,
    roadmap: Path = ROADMAP,
    pyproject: Path = PYPROJECT,
    scripts: Path = SCRIPTS,
) -> dict[Path, str]:
    """Return the state document with every tree-derived region refreshed."""
    state = docs / "Repo_Current_State.md"
    text = replace_region(read(state), "milestones", render_milestones(read(roadmap)), state)
    text = replace_region(text, "dependencies", render_dependencies(pyproject.read_bytes()), state)
    return {state: replace_region(text, "scripts", render_scripts(scripts), state)}


def stale(
    docs: Path = DOCS,
    roadmap: Path = ROADMAP,
    pyproject: Path = PYPROJECT,
    scripts: Path = SCRIPTS,
) -> list[Path]:
    """Return state documents whose tree-derived regions no longer match their sources."""
    return [path for path, text in build(docs, roadmap, pyproject, scripts).items() if read(path) != text]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Report stale regions without writing them.")
    parser.add_argument("--snapshot", action="store_true", help="Also refresh clone-local git facts.")
    args = parser.parse_args(argv)
    if args.check and args.snapshot:
        parser.error("--check cannot verify --snapshot: the git region differs between clones")
    try:
        rendered = build()
        if args.snapshot:
            rendered[STATE] = replace_region(rendered[STATE], "snapshot", render_snapshot(), STATE)
    except BuildError as error:
        print(f"docs build: {error}", file=sys.stderr)
        return 1
    stale_paths = [path for path, text in rendered.items() if read(path) != text]
    if args.check:
        for path in stale_paths:
            print(f"stale: {path.relative_to(ROOT).as_posix()}")
        return 1 if stale_paths else 0
    for path, text in rendered.items():
        if path in stale_paths:
            path.write_text(text, encoding="utf-8", newline="\n")
            print(f"updated: {path.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
