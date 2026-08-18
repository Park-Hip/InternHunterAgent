"""Check repository documentation hygiene without external dependencies."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import textwrap
import tomllib
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import docs_build  # noqa: E402  - sibling script, imported after the path is set

ROOT = Path(__file__).resolve().parents[1]
LINE_LIMIT = 100
AGENT_FILES = (ROOT / "AGENTS.md", ROOT / "CLAUDE.md")
MOJIBAKE = (
    "\u00e2\u20ac",
    "\u00c2 ",
    "\u00ef\u00bb\u00bf",
    "\u00e2\u2020",
)
ARCHIVED_MARKER = "<!-- archived-on-tag -->"
ENCODING_MARKER = "<!-- lint-allow-encoding -->"
LINK_PATH_MARKER = "<!-- lint-allow-link-path -->"
LINK_PATH_BLOCK_BEGIN = "<!-- lint-allow-link-path:begin -->"
LINK_PATH_BLOCK_END = "<!-- lint-allow-link-path:end -->"
AMENDMENT_MARKER = "<!-- lint-allow-amendment -->"
SCENARIO_ID_MARKER = "<!-- lint-allow-scenario-id -->"
SCENARIOS = ROOT / "evals" / "scenarios_v1.yaml"
SCENARIO_ID = re.compile(r"\b(?:HLP|HON|SAF)-[A-Z0-9]+(?:-[A-Z0-9]+)*\b")
REGISTRY_ID = re.compile(r"^- id: (\S+)", re.M)
TECH_STACK = ROOT / "docs" / "Tech_Stack.md"
DOCS_MAP = ROOT / "docs" / "README.md"
CAPS_BEGIN = "<!-- caps:begin -->"
CAPS_END = "<!-- caps:end -->"
EVICTION_RULE = re.compile(r"^> \*\*Eviction:\*\* \S.+")
AMENDMENT_PHRASES = (
    "no longer",
    "read every",
    "correcting an earlier",
    "superseded above",
)
ORPHAN_EXEMPTIONS = frozenset({ROOT / "README.md", ROOT / "AGENTS.md", ROOT / "CLAUDE.md"})
STAMPED_DOCS = (
    ROOT / "docs" / "Repo_Current_State.md",
    ROOT / "docs" / "Known_Issues.md",
    ROOT / "docs" / "Tickets.md",
    ROOT / "docs" / "Operations.md",
)
LAST_VERIFIED = re.compile(r"^> \*\*Last verified:\*\* \d{4}-\d{2}-\d{2}(?:\b|$)")
PYPROJECT = ROOT / "pyproject.toml"
ROADMAP = ROOT / "docs" / "roadmap.yaml"
DEPS_BEGIN = "<!-- deps:begin -->"
DEPS_END = "<!-- deps:end -->"
REFLOW_TARGETS = frozenset(
    {
        "AGENTS.md",
        "CLAUDE.md",
        ".claude/skills/generate-ticket-prompt/SKILL.md",
        "docs/Agent_Behavior_Spec.md",
        "docs/Completion_Reports.md",
        "docs/README.md",
        "docs/Full_Design_Document.md",
        "docs/Known_Issues.md",
        "docs/MVP_Spec.md",
        "docs/MVP_Technical_Design.md",
        "docs/Manual_Verification_Guide.md",
        "docs/Resolved_Issues.md",
        "docs/T0020.4_Cron_Activation_Runbook.md",
        "docs/Tickets.md",
        "research/docs-hygiene-and-system-plan.md",
        "research/honesty-enforcement-design.md",
        "research/v1-release-readiness-plan.md",
        "skills/generate-ticket-prompt/SKILL.md",
    }
)
BLOCK_PREFIX = re.compile(r"^(?P<indent>[ \t]*)(?P<marker>>[ \t]*|[-*+][ \t]+|\d+[.)][ \t]+)(?P<body>\S.*)$")


@dataclass(frozen=True)
class Finding:
    check: str
    path: Path
    line: int
    message: str

    def __str__(self) -> str:
        try:
            location = self.path.relative_to(ROOT).as_posix()
        except ValueError:
            location = self.path.as_posix()
        suffix = f":{self.line}" if self.line else ""
        return f"{location}{suffix}: {self.check}: {self.message}"


@dataclass(frozen=True)
class CapEntry:
    path: Path
    tier: str
    cap: int | None


def markdown_files(root: Path = ROOT) -> list[Path]:
    """Return the tracked Markdown files, excluding virtual environments and caches."""
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", "*.md"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return sorted(
        path for name in result.stdout.decode().split("\0") if name
        if (path := root / Path(name)).exists()
    )


def is_archive(path: Path) -> bool:
    return (
        path.is_relative_to(ROOT / "docs" / "archive")
        or path.is_relative_to(ROOT / "research" / "archive")
        or path.is_relative_to(ROOT / "evals" / "archive")
    )


DATED_RECORDS = frozenset({ROOT / "docs" / "Completion_Reports.md"})
TICKET_ENTRIES = ROOT / "docs" / "entries"


def is_ticket_entry(path: Path) -> bool:
    """Per-ticket write surface: one file per ticket, owned by exactly one branch.

    These files are exempt from the caps table and the orphan check because neither applies
    to them. A caps row is a shared table row, which is the conflict this directory exists to
    remove, and an inbound link per entry would be the same shared edit under another name.
    The directory is indexed as a group in docs/README.md instead. Entries still owe the
    line-length, encoding, and scenario-id checks."""
    return path.is_relative_to(TICKET_ENTRIES)


def is_dated_record(path: Path) -> bool:
    """Link-path exemption for a living file whose entries name paths as they were on the day
    they shipped, not as a live index. Deliberately narrower than is_archive(): unlike a true
    archive, docs/Completion_Reports.md still owes the line-length, reflow, orphan, and
    scenario-id checks - only its historical links get a pass. Ticket entries carry the same
    dated-evidence property for the same reason."""
    return is_archive(path) or is_ticket_entry(path) or path in DATED_RECORDS


def is_line_length_exempt(line: str, in_fence: bool, in_frontmatter: bool = False) -> bool:
    stripped = line.strip()
    return (
        in_fence
        or in_frontmatter
        or stripped.startswith("|")
        or re.fullmatch(r"`[^`]+`[.,;:]?", stripped) is not None
        or re.fullmatch(r">?\s*\[[^\]]+\]\([^)]+\)", stripped) is not None
        or ARCHIVED_MARKER in line
        or LINK_PATH_MARKER in line
        or SCENARIO_ID_MARKER in line
        or re.fullmatch(r"<?https?://\S+>?", stripped) is not None
        or re.search(r"https?://\S{100,}", line) is not None
    )


def check_line_length(files: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in files:
        if is_archive(path):
            continue
        in_fence = False
        in_frontmatter = False
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if number == 1 and line.strip() == "---":
                in_frontmatter = True
                continue
            if in_frontmatter:
                if line.strip() in {"---", "..."}:
                    in_frontmatter = False
                continue
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
            if len(line) > LINE_LIMIT and not is_line_length_exempt(
                line, in_fence, in_frontmatter
            ):
                findings.append(Finding("line-length", path, number, f"{len(line)} characters"))
    return findings


def code_spans_removed(line: str) -> str:
    return re.sub(r"`[^`]*`", "", line)


def path_from_link(target: str, source: Path, *, repo_rooted: bool = False) -> Path | None:
    target = target.strip().split(maxsplit=1)[0].strip("<>")
    target = target.split("#", 1)[0].split("?", 1)[0]
    target = re.split(r"(?:::|:\d)", target, maxsplit=1)[0]
    if not target or target.startswith(("http://", "https://", "mailto:", "#")):
        return None
    if any(character in target for character in "*[]{}"):
        return None
    base = ROOT if repo_rooted else source.parent
    return (base / target).resolve()


def is_repo_path(value: str) -> bool:
    top_level = (
        ".github/",
        "config/",
        "data/",
        "docs/",
        "evals/",
        "infra/",
        "research/",
        "scripts/",
        "src/",
        "tests/",
    )
    if not value.startswith(top_level) or " " in value:
        return False
    candidate = ROOT / value
    return Path(value).suffix != "" or candidate.is_dir()


def check_link_path(files: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    link_pattern = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
    code_pattern = re.compile(r"`([^`]+)`")
    for path in files:
        if is_dated_record(path):
            continue
        in_fence = False
        link_path_allowed = False
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if LINK_PATH_BLOCK_BEGIN in line:
                link_path_allowed = True
                continue
            if LINK_PATH_BLOCK_END in line:
                link_path_allowed = False
                continue
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence or link_path_allowed or ARCHIVED_MARKER in line or LINK_PATH_MARKER in line:
                continue
            targets = [(target, False) for target in link_pattern.findall(line)]
            targets.extend(
                (value, True) for value in code_pattern.findall(line) if is_repo_path(value)
            )
            for target, repo_rooted in targets:
                candidate = path_from_link(target, path, repo_rooted=repo_rooted)
                if candidate is not None and not candidate.exists():
                    findings.append(Finding("link-path", path, number, f"missing {target}"))
    return findings


def check_encoding(files: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in files:
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            findings.append(Finding("encoding", path, 0, "UTF-8 BOM is not allowed"))
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            findings.append(Finding("encoding", path, exc.start + 1, "invalid UTF-8"))
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if ENCODING_MARKER in line:
                continue
            visible = code_spans_removed(line)
            for sequence in MOJIBAKE:
                if sequence in visible:
                    findings.append(
                        Finding("encoding", path, number, f"mojibake sequence {sequence!r}")
                    )
    return findings


def check_agent_parity(_: list[Path]) -> list[Finding]:
    first, second = AGENT_FILES
    if not first.exists() or not second.exists():
        missing = first if not first.exists() else second
        return [Finding("agent-parity", missing, 0, "required instruction file is missing")]
    if min(first.stat().st_size, second.stat().st_size) < 1000:
        return [Finding("agent-parity", first, 0, "instruction files must each be at least 1000 bytes")]
    if first.read_bytes() != second.read_bytes():
        return [Finding("agent-parity", first, 0, "AGENTS.md and CLAUDE.md differ")]
    return []


def check_generated(_: list[Path]) -> list[Finding]:
    """Keep every generated register agreeing with the ticket entries it is built from.

    The same shape as `stack` and `agent-parity`: the check owns no rendering logic, it just
    reports when the committed text and the derivable text have parted company.
    """
    try:
        stale = docs_build.stale()
    except docs_build.BuildError as error:
        return [Finding("generated", DOCS_MAP, 0, f"docs_build cannot run: {error}")]
    return [
        Finding("generated", path, 0, "generated regions are stale; run scripts/docs_build.py")
        for path in stale
    ]


def declared_dependencies(raw: bytes) -> set[str]:
    """Return the distribution names from pyproject's runtime and dev dependency groups."""
    data = tomllib.loads(raw.decode("utf-8"))
    specifiers = list(data.get("project", {}).get("dependencies", []))
    for group in data.get("dependency-groups", {}).values():
        specifiers.extend(item for item in group if isinstance(item, str))
    names = set()
    for specifier in specifiers:
        # Strip extras and any version/marker suffix: "psycopg[binary,pool]>=3.2" -> "psycopg".
        name = re.split(r"[\[<>=!~;\s]", specifier, maxsplit=1)[0].strip()
        if name:
            names.add(name.lower())
    return names


def documented_dependencies(text: str) -> set[str]:
    """Return package names from the first column of tables in the deps-marked region.

    Only table rows count, so ordinary prose in the region may use backticks freely.
    """
    start, end = text.find(DEPS_BEGIN), text.find(DEPS_END)
    if start == -1 or end == -1 or end < start:
        return set()
    region = text[start + len(DEPS_BEGIN) : end]
    rows = re.findall(r"^\|\s*`([^`]+)`\s*\|", region, re.M)
    return {name.strip().lower() for name in rows}


def check_stack(_: list[Path]) -> list[Finding]:
    """Keep Tech_Stack.md and pyproject.toml agreeing on the dependency set."""
    if not TECH_STACK.exists():
        return [Finding("stack", TECH_STACK, 0, "docs/Tech_Stack.md is missing")]
    stack_text = TECH_STACK.read_text(encoding="utf-8")
    if DEPS_BEGIN not in stack_text or DEPS_END not in stack_text:
        return [Finding("stack", TECH_STACK, 0, f"missing {DEPS_BEGIN} / {DEPS_END} markers")]
    declared = declared_dependencies(PYPROJECT.read_bytes())
    documented = documented_dependencies(stack_text)
    findings = [
        Finding("stack", TECH_STACK, 0, f"dependency {name!r} is not documented")
        for name in sorted(declared - documented)
    ]
    findings.extend(
        Finding("stack", TECH_STACK, 0, f"documented {name!r} is not a dependency")
        for name in sorted(documented - declared)
    )
    return findings


def check_stamps(paths: tuple[Path, ...] = STAMPED_DOCS) -> list[Finding]:
    """Require each current-state document to state when it was verified."""
    findings: list[Finding] = []
    for path in paths:
        if not path.exists():
            findings.append(Finding("stamp", path, 0, "required living document is missing"))
            continue
        if not any(LAST_VERIFIED.match(line) for line in path.read_text(encoding="utf-8").splitlines()):
            findings.append(Finding("stamp", path, 0, "missing > **Last verified:** YYYY-MM-DD"))
    return findings


def documented_caps(text: str, source: Path = DOCS_MAP) -> dict[Path, CapEntry]:
    """Return the documented per-file caps from the marked documentation-map table."""
    start, end = text.find(CAPS_BEGIN), text.find(CAPS_END)
    if start == -1 or end == -1 or end < start:
        return {}
    entries: dict[Path, CapEntry] = {}
    for line in text[start + len(CAPS_BEGIN) : end].splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 5 or cells[0] == "Doc" or set(cells[0]) == {"-", ":"}:
            continue
        match = re.fullmatch(r"\[[^]]+\]\(([^)]+)\)", cells[0])
        if match is None:
            continue
        path = path_from_link(match.group(1), source)
        if path is None or path.suffix != ".md":
            continue
        cap_text = cells[3]
        cap = None if cap_text == "Uncapped" else int(cap_text)
        entries[path] = CapEntry(path=path, tier=cells[2], cap=cap)
    return entries


def cap_entries(map_path: Path = DOCS_MAP) -> dict[Path, CapEntry]:
    """Load the documentation-map cap register, or return no entries when it is absent."""
    if not map_path.exists():
        return {}
    return documented_caps(map_path.read_text(encoding="utf-8"), map_path)


def managed_documentation_files(files: list[Path], docs_root: Path = ROOT / "docs") -> set[Path]:
    """Return living documents owned by the documentation map's primary surface."""
    return {
        path.resolve()
        for path in files
        if path.is_relative_to(docs_root) and not is_archive(path) and not is_ticket_entry(path)
    }


def check_size_cap(files: list[Path], map_path: Path = DOCS_MAP) -> list[Finding]:
    """Keep each documentation-map cap current and every managed document indexed."""
    if not map_path.exists():
        return [Finding("size-cap", map_path, 0, "docs/README.md is missing")]
    map_text = map_path.read_text(encoding="utf-8")
    if CAPS_BEGIN not in map_text or CAPS_END not in map_text:
        return [Finding("size-cap", map_path, 0, f"missing {CAPS_BEGIN} / {CAPS_END} markers")]
    entries = documented_caps(map_text, map_path)
    if not entries:
        return [Finding("size-cap", map_path, 0, "caps table has no document rows")]
    findings: list[Finding] = []
    for entry in entries.values():
        if entry.cap is None:
            continue
        if not entry.path.exists():
            findings.append(Finding("size-cap", entry.path, 0, "indexed document is missing"))
            continue
        lines = len(entry.path.read_text(encoding="utf-8").splitlines())
        if lines > entry.cap:
            findings.append(Finding("size-cap", entry.path, 0, f"{lines} lines exceeds cap {entry.cap}"))
    indexed = set(entries)
    for path in sorted(managed_documentation_files(files, map_path.parent) - indexed):
        findings.append(Finding("size-cap", path, 0, "living document is missing from caps table"))
    return findings


def check_eviction_rule(_: list[Path], map_path: Path = DOCS_MAP) -> list[Finding]:
    """Require every capped document to explain which content is removed and when."""
    findings: list[Finding] = []
    for entry in cap_entries(map_path).values():
        if entry.cap is None or not entry.path.exists():
            continue
        header = entry.path.read_text(encoding="utf-8").splitlines()[:20]
        if not any(EVICTION_RULE.match(line) for line in header):
            findings.append(Finding("eviction-rule", entry.path, 0, "missing header eviction rule"))
    return findings


def check_amendment(_: list[Path], map_path: Path = DOCS_MAP) -> list[Finding]:
    """Prevent correction banners in capped living documents."""
    findings: list[Finding] = []
    for entry in cap_entries(map_path).values():
        if entry.tier not in {"T1", "T2", "T3"} or not entry.path.exists():
            continue
        for number, line in enumerate(entry.path.read_text(encoding="utf-8").splitlines(), 1):
            if AMENDMENT_MARKER in line:
                continue
            visible = code_spans_removed(line).lower()
            for phrase in AMENDMENT_PHRASES:
                if phrase in visible:
                    findings.append(
                        Finding("amendment", entry.path, number, f"contains correction phrase {phrase!r}")
                    )
    return findings


def check_orphan(files: list[Path]) -> list[Finding]:
    """Require every living Markdown document to have an inbound documentation link."""
    live = {path.resolve() for path in files if not is_archive(path) and not is_ticket_entry(path)}
    linked: set[Path] = set()
    link_pattern = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
    code_pattern = re.compile(r"`([^`]+)`")
    for source in live:
        in_fence = False
        for line in source.read_text(encoding="utf-8").splitlines():
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            targets = [(target, False) for target in link_pattern.findall(line)]
            targets.extend((value, True) for value in code_pattern.findall(line) if is_repo_path(value))
            for target, repo_rooted in targets:
                candidate = path_from_link(target, source, repo_rooted=repo_rooted)
                if candidate in live and candidate != source:
                    linked.add(candidate)
    return [
        Finding("orphan", path, 0, "living document has no inbound link")
        for path in sorted(live - linked - ORPHAN_EXEMPTIONS)
    ]


def registered_scenario_ids(text: str) -> set[str]:
    """Return the scenario IDs the registry defines.

    Read as text rather than parsed as YAML so this script keeps its no-dependency contract.
    """
    return set(REGISTRY_ID.findall(text))


def check_scenario_id(files: list[Path], registry: Path = SCENARIOS) -> list[Finding]:
    """Keep every scenario ID named in documentation resolvable in the registry that owns it.

    D-041 makes `evals/scenarios_v1.yaml` the sole owner of scenario definitions. Documentation may
    name a scenario, but a name that the registry does not define is a broken reference.
    """
    if not registry.exists():
        return [Finding("scenario-id", registry, 0, "scenario registry is missing")]
    known = registered_scenario_ids(registry.read_text(encoding="utf-8"))
    if not known:
        return [Finding("scenario-id", registry, 0, "scenario registry defines no IDs")]
    try:
        location = registry.relative_to(ROOT).as_posix()
    except ValueError:
        location = registry.as_posix()
    findings: list[Finding] = []
    for path in files:
        if is_archive(path) or path == registry:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if SCENARIO_ID_MARKER in line:
                continue
            for identifier in SCENARIO_ID.findall(line):
                if identifier not in known:
                    findings.append(
                        Finding("scenario-id", path, number, f"{identifier} is absent from {location}")
                    )
    return findings


def parse_roadmap(text: str) -> tuple[list[dict[str, object]], list[str]]:
    """Return the milestones and the frozen path list from `roadmap.yaml`.

    `docs_build.parse_milestones` already reads the flat scalars. This adds the two nested lists
    the protocol checks need - each milestone's `scope:` and the top-level `frozen:` - by the same
    indentation rule, keeping the no-dependency contract both scripts hold.
    """
    milestones: list[dict[str, object]] = []
    frozen: list[str] = []
    collecting: list[str] | None = None
    collecting_indent = 0
    for line in text.split("\n"):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if collecting is not None:
            if stripped.startswith("- ") and indent > collecting_indent:
                collecting.append(stripped[2:].strip())
                continue
            collecting = None
        if line.rstrip() == "frozen:":
            frozen = []
            collecting, collecting_indent = frozen, 0
            continue
        identifier = docs_build.MILESTONE_ID.match(line)
        if identifier:
            milestones.append({"id": identifier.group("id"), "scope": [], "tickets": []})
            continue
        field = docs_build.MILESTONE_FIELD.match(line)
        if field and milestones:
            key, value = field.group("key"), field.group("value")
            if key == "tickets":
                milestones[-1]["tickets"] = [
                    item.strip() for item in value.strip("[]").split(",") if item.strip()
                ]
            elif key not in milestones[-1]:
                milestones[-1][key] = value
            continue
        if milestones and stripped == "scope:":
            collecting = milestones[-1]["scope"]  # type: ignore[assignment]
            collecting_indent = indent
    return milestones, frozen


def covered_numbers(milestone: dict[str, object]) -> set[int]:
    """The milestone numbers an entry accounts for.

    Most entries account for their own number. `M0` is titled "Foundation through Hardening
    (M0-M5)" and genuinely stands for six milestones, so the range in the title is read rather
    than treated as five missing ids. That fact is already recorded; this reads it.
    """
    number = int(str(milestone["id"]).lstrip("M"))
    match = re.search(r"\(M(\d+)\s*-\s*M(\d+)\)", str(milestone.get("title", "")))
    if match:
        low, high = int(match.group(1)), int(match.group(2))
        if low <= number <= high:
            return set(range(low, high + 1))
    return {number}


def check_registry(_: list[Path], roadmap: Path | None = None) -> list[Finding]:
    """Keep every number resolvable in the registry that owns numbers.

    Identity drift is what M31 exists to stop, and it always looked the same: a number that no
    entry claims, or a number two entries claim. Both are decidable from the registry and the
    entry directory alone, so this check reads no git state.
    """
    roadmap = roadmap or ROADMAP
    if not roadmap.exists():
        return [Finding("registry", roadmap, 0, "docs/roadmap.yaml is missing")]
    entries = roadmap.parent / "entries"
    milestones, _frozen = parse_roadmap(docs_build.read(roadmap))
    findings: list[Finding] = []
    if not milestones:
        return [Finding("registry", roadmap, 0, "no milestones found")]

    seen: dict[str, int] = {}
    covered: set[int] = set()
    for milestone in milestones:
        identifier = str(milestone["id"])
        seen[identifier] = seen.get(identifier, 0) + 1
        covered |= covered_numbers(milestone)
    for identifier, count in sorted(seen.items()):
        if count > 1:
            findings.append(Finding("registry", roadmap, 0, f"milestone {identifier} is declared {count} times"))
    missing = sorted(set(range(min(covered), max(covered) + 1)) - covered)
    for number in missing:
        findings.append(Finding("registry", roadmap, 0, f"milestone M{number} is skipped: no entry claims it"))

    tickets: dict[str, str] = {}
    for milestone in milestones:
        identifier = str(milestone["id"])
        owned = covered_numbers(milestone)
        for ticket in milestone["tickets"]:  # type: ignore[union-attr]
            if ticket in tickets:
                findings.append(
                    Finding("registry", roadmap, 0, f"ticket {ticket} is claimed by {tickets[ticket]} and {identifier}")
                )
            tickets[ticket] = identifier
            owner = re.match(r"^T(\d{4})(?:\.\d+)?$", ticket)
            if not owner:
                findings.append(Finding("registry", roadmap, 0, f"ticket {ticket} is not a T#### id"))
            elif int(owner.group(1)) not in owned:
                findings.append(
                    Finding("registry", roadmap, 0, f"ticket {ticket} sits under {identifier}; milestone N owns T00NN.x")
                )

    if entries.is_dir():
        for path in sorted(entries.glob("*.md")):
            if docs_build.ENTRY_NAME.match(path.stem) and path.stem not in tickets:
                findings.append(Finding("registry", path, 0, f"{path.stem} has no entry in docs/roadmap.yaml"))
    return findings


def git_text(*args: str, root: Path = ROOT) -> str | None:
    """Run a read-only git command, returning None when git or the ref is unavailable."""
    try:
        result = subprocess.run(
            ("git", *args),
            cwd=root,
            capture_output=True,
            # These documents are UTF-8 and contain characters cp1252 cannot decode. Without an
            # explicit encoding, `text=True` uses the platform locale and `git show` crashes on
            # Windows against the repository's own registers.
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0 or result.stdout is None:
        return None
    return result.stdout.strip()


def resolve_base(explicit: str | None = None, root: Path = ROOT) -> str | None:
    """Find the ref this branch should be compared against, or None if there is nothing to use.

    A missing base is not a violation. These two checks describe a change set, and a clone with
    no `origin/main` - a shallow CI checkout, an offline copy - has no change set to describe.
    They report nothing there rather than failing, which is the same reason T0031.3 left the
    snapshot region ungated.
    """
    base_ref = os.environ.get("GITHUB_BASE_REF")
    candidates = [
        explicit,
        os.environ.get("DOCS_LINT_DIFF_BASE"),
        f"origin/{base_ref}" if base_ref else None,
        "origin/main",
    ]
    for candidate in candidates:
        if candidate and git_text(
            "rev-parse", "--verify", "--quiet", f"{candidate}^{{commit}}", root=root
        ):
            return candidate
    return None


def changed_paths(base: str, root: Path = ROOT) -> set[str]:
    """Paths this branch changes against `base`: committed, staged, unstaged, or untracked.

    Untracked files count. A ticket adding a brand new file outside its scope is exactly the
    drift these checks exist to catch, and that file is untracked until someone stages it - so
    reading only the diff would stay silent until the moment the mistake became permanent.
    """
    paths: set[str] = set()
    commands = (
        ("diff", "--name-only", f"{base}...HEAD"),
        ("diff", "--name-only", "HEAD"),
        ("ls-files", "--others", "--exclude-standard"),
    )
    for args in commands:
        output = git_text(*args, root=root)
        if output:
            paths |= {line.strip() for line in output.split("\n") if line.strip()}
    return paths


def milestone_for(
    paths: set[str], milestones: list[dict[str, object]], root: Path = ROOT
) -> dict[str, object] | None:
    """Decide which milestone a change set belongs to.

    The entry file is the authority: a ticket writes exactly one, and it names its own number.
    The branch name is the fallback for a change set that has not written its entry yet.
    """
    numbers = {
        match.group(1)
        for path in paths
        if (match := re.match(r"^docs/entries/T(\d{4})(?:\.\d+)?\.md$", path))
    }
    if not numbers:
        branch = git_text("rev-parse", "--abbrev-ref", "HEAD", root=root) or ""
        if match := re.search(r"[tT](\d{4})(?:\.\d+)?", branch):
            numbers = {match.group(1)}
    if len(numbers) != 1:
        return None
    wanted = f"M{int(next(iter(numbers)))}"
    return next((item for item in milestones if str(item["id"]) == wanted), None)


def within_scope(path: str, scope: list[str]) -> bool:
    """A declared path matches itself; a declared directory matches everything beneath it."""
    return any(path == entry or (entry.endswith("/") and path.startswith(entry)) for entry in scope)


def check_scope(
    _: list[Path], explicit: str | None = None, root: Path = ROOT
) -> list[Finding]:
    """Keep a branch inside the paths its milestone declared.

    A rebuilt register is exempt for the reason `check_frozen` already exempts it: the generator
    wrote those bytes and the `generated` check makes running it mandatory, so a ticket branch
    that adds an entry file has no way to be silent about them. Without this, every branch that
    adds a `docs/entries/` file is rejected whether or not it runs `docs_build.py`, and the only
    escape is for a milestone to claim a frozen path in its own `scope:` - which the M31 note in
    docs/roadmap.yaml forbids.
    """
    roadmap = root / "docs" / "roadmap.yaml"
    if not roadmap.exists():
        return []
    base = resolve_base(explicit, root)
    if base is None:
        return []
    paths = changed_paths(base, root)
    if not paths:
        return []
    milestones, _frozen = parse_roadmap(docs_build.read(roadmap))
    milestone = milestone_for(paths, milestones, root)
    if milestone is None:
        return []
    scope = [str(entry) for entry in milestone["scope"]]  # type: ignore[union-attr]
    if not scope:
        return []
    return [
        Finding(
            "scope",
            root / path,
            0,
            f"outside {milestone['id']}'s declared scope; widen scope: in docs/roadmap.yaml or move the change",
        )
        for path in sorted(paths)
        if not within_scope(path, scope) and not only_generated_changed(path, base, root)
    ]


def only_generated_changed(path: str, base: str, root: Path = ROOT) -> bool:
    """True when a frozen register's change is confined to its generated regions.

    This is what lets a ticket branch carry a rebuilt register without being the integration
    step. The generator wrote those bytes, not the agent, and running it is mandatory - the
    `generated` check fails if the branch does not. Stripping the regions from both sides asks
    the only question that matters: did a human touch anything outside them?
    """
    before = git_text("show", f"{base}:{path}", root=root)
    if before is None:
        return False
    current = root / path
    if not current.exists():
        return False
    strip = docs_build.strip_generated
    # `git show` output arrives without its trailing newline; compare the bodies, not the edges.
    return (
        strip(before.replace("\r\n", "\n")).strip() == strip(docs_build.read(current)).strip()
    )


def is_integration(base: str, root: Path = ROOT) -> bool:
    """True when every commit on this branch is an integration commit."""
    subjects = git_text("log", "--format=%s", f"{base}..HEAD", root=root)
    if not subjects:
        return False
    return all(line.startswith("docs(integration)") for line in subjects.split("\n") if line.strip())


def check_frozen(
    _: list[Path], explicit: str | None = None, root: Path = ROOT
) -> list[Finding]:
    """Keep the shared registers writable by the integration step and the generator only."""
    roadmap = root / "docs" / "roadmap.yaml"
    if not roadmap.exists():
        return []
    base = resolve_base(explicit, root)
    if base is None:
        return []
    paths = changed_paths(base, root)
    if not paths or is_integration(base, root):
        return []
    milestones, frozen = parse_roadmap(docs_build.read(roadmap))
    # A milestone that named a frozen path in its own scope: has already made that decision in
    # the open, which is the governance the protocol asks for. M31 is the standing example - it
    # is the milestone that installs the marked regions and the caps rows into these registers,
    # so the check it adds must not forbid the work that adds it.
    declared = milestone_for(paths, milestones, root) or {}
    scope = [str(entry) for entry in declared.get("scope", [])]  # type: ignore[union-attr]
    findings = []
    for path in sorted(paths):
        if not within_scope(path, frozen) or within_scope(path, scope):
            continue
        if only_generated_changed(path, base, root):
            continue
        findings.append(
            Finding(
                "frozen",
                root / path,
                0,
                "frozen register: only the integration step and scripts/docs_build.py write this",
            )
        )
    return findings


CHECKS = {
    "line-length": check_line_length,
    "link-path": check_link_path,
    "encoding": check_encoding,
    "agent-parity": check_agent_parity,
    "stack": check_stack,
    "generated": check_generated,
    "stamp": lambda _: check_stamps(),
    "size-cap": check_size_cap,
    "eviction-rule": check_eviction_rule,
    "amendment": check_amendment,
    "orphan": check_orphan,
    "scenario-id": check_scenario_id,
    "registry": check_registry,
    "scope": check_scope,
    "frozen": check_frozen,
}


def reflow_line_length(files: list[Path]) -> list[Path]:
    changed: list[Path] = []
    for path in files:
        if is_archive(path) or not is_reflow_target(path):
            continue
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        result: list[str] = []
        in_fence = False
        in_frontmatter = False
        modified = False
        for number, line in enumerate(lines, 1):
            content = line.rstrip("\r\n")
            if number == 1 and content.strip() == "---":
                in_frontmatter = True
                result.append(line)
                continue
            if in_frontmatter:
                if content.strip() in {"---", "..."}:
                    in_frontmatter = False
                result.append(line)
                continue
            if content.lstrip().startswith("```"):
                in_fence = not in_fence
            if len(content) > LINE_LIMIT and not is_line_length_exempt(
                content, in_fence, in_frontmatter
            ):
                initial_indent, subsequent_indent, body = reflow_indents(content)
                wrapped = textwrap.wrap(
                    body,
                    width=LINE_LIMIT,
                    initial_indent=initial_indent,
                    subsequent_indent=subsequent_indent,
                    break_long_words=False,
                    break_on_hyphens=False,
                )
                if len(wrapped) > 1:
                    result.extend(f"{part}\n" for part in wrapped)
                    modified = True
                    continue
            result.append(line if line.endswith(("\n", "\r")) else f"{line}\n")
        if modified:
            path.write_text("".join(result), encoding="utf-8", newline="\n")
            changed.append(path)
    return changed


def is_reflow_target(path: Path) -> bool:
    try:
        return path.relative_to(ROOT).as_posix() in REFLOW_TARGETS
    except ValueError:
        return True


def reflow_indents(line: str) -> tuple[str, str, str]:
    match = BLOCK_PREFIX.match(line)
    if match is None:
        indent = line[: len(line) - len(line.lstrip())]
        return indent, indent, line.strip()
    indent = match.group("indent")
    marker = match.group("marker")
    initial_indent = f"{indent}{marker}"
    if marker.startswith(">"):
        return initial_indent, initial_indent, match.group("body")
    return initial_indent, f"{indent}{' ' * len(marker)}", match.group("body")


def print_stat(files: list[Path]) -> None:
    total_bytes = sum(path.stat().st_size for path in files)
    lines = [line for path in files for line in path.read_text(encoding="utf-8").splitlines()]
    print("Documentation baseline")
    print(f"files: {len(files)}")
    print(f"bytes: {total_bytes}")
    print(f"lines >100: {sum(len(line) > 100 for line in lines)}")
    print(f"lines >200: {sum(len(line) > 200 for line in lines)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", choices=CHECKS, action="append")
    parser.add_argument("--stat", action="store_true")
    parser.add_argument("--fix", action="store_true", help="Safely reflow ordinary prose lines only.")
    parser.add_argument(
        "--diff-base",
        help="Ref the scope and frozen checks compare against. Defaults to origin/main; both "
        "checks report nothing when no base resolves.",
    )
    args = parser.parse_args(argv)
    files = markdown_files()
    if args.stat:
        print_stat(files)
        if not args.check and not args.fix:
            return 0
    if args.fix:
        for path in reflow_line_length(files):
            print(f"reflowed {path.relative_to(ROOT).as_posix()}")
    selected = args.check or list(CHECKS)
    diffed = {"scope": check_scope, "frozen": check_frozen}
    findings = [
        finding
        for name in selected
        for finding in (
            diffed[name](files, args.diff_base) if name in diffed else CHECKS[name](files)
        )
    ]
    for finding in findings:
        print(finding)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
