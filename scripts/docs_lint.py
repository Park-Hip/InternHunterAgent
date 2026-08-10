"""Check repository documentation hygiene without external dependencies."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path


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
    return path.is_relative_to(ROOT / "docs" / "archive")


def is_line_length_exempt(line: str, in_fence: bool) -> bool:
    stripped = line.strip()
    return (
        in_fence
        or stripped.startswith("|")
        or (stripped.startswith("`") and stripped.endswith("`") and " " not in stripped)
        or re.fullmatch(r"<?https?://\S+>?", stripped) is not None
    )


def check_line_length(files: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in files:
        if is_archive(path):
            continue
        in_fence = False
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
            if len(line) > LINE_LIMIT and not is_line_length_exempt(line, in_fence):
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
    return value.startswith(top_level) and " " not in value


def check_link_path(files: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    link_pattern = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
    code_pattern = re.compile(r"`([^`]+)`")
    for path in files:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if ARCHIVED_MARKER in line:
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


CHECKS = {
    "line-length": check_line_length,
    "link-path": check_link_path,
    "encoding": check_encoding,
    "agent-parity": check_agent_parity,
}


def reflow_line_length(files: list[Path]) -> list[Path]:
    changed: list[Path] = []
    for path in files:
        if is_archive(path):
            continue
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        result: list[str] = []
        in_fence = False
        modified = False
        for line in lines:
            content = line.rstrip("\r\n")
            if content.lstrip().startswith("```"):
                in_fence = not in_fence
            if len(content) > LINE_LIMIT and not is_line_length_exempt(content, in_fence):
                indent = content[: len(content) - len(content.lstrip())]
                wrapped = textwrap.wrap(
                    content.strip(),
                    width=LINE_LIMIT - len(indent),
                    break_long_words=False,
                    break_on_hyphens=False,
                )
                if len(wrapped) > 1:
                    result.extend(f"{indent}{part}\n" for part in wrapped)
                    modified = True
                    continue
            result.append(line if line.endswith(("\n", "\r")) else f"{line}\n")
        if modified:
            path.write_text("".join(result), encoding="utf-8", newline="\n")
            changed.append(path)
    return changed


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
    findings = [finding for name in selected for finding in CHECKS[name](files)]
    for finding in findings:
        print(finding)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
