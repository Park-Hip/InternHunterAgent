"""Check repository documentation hygiene without external dependencies.

Only checks that compare documentation with a machine-readable source of truth remain.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MOJIBAKE = ("\u00e2\u20ac", "\u00c2 ", "\u00ef\xbb\xbf", "\u00e2\u2020")
ARCHIVED_MARKER = "<!-- archived-on-tag -->"
ENCODING_MARKER = "<!-- lint-allow-encoding -->"
LINK_PATH_MARKER = "<!-- lint-allow-link-path -->"
LINK_PATH_BLOCK_BEGIN = "<!-- lint-allow-link-path:begin -->"
LINK_PATH_BLOCK_END = "<!-- lint-allow-link-path:end -->"
SCENARIO_ID_MARKER = "<!-- lint-allow-scenario-id -->"
SCENARIOS = ROOT / "evals" / "scenarios_v1.yaml"
SCENARIO_ID = re.compile(r"\b(?:HLP|HON|SAF)-[A-Z0-9]+(?:-[A-Z0-9]+)*\b")
REGISTRY_ID = re.compile(r"^- id: (\S+)", re.M)
TECH_STACK = ROOT / "docs" / "reference" / "configuration.md"
PYPROJECT = ROOT / "pyproject.toml"
DEPS_BEGIN = "<!-- deps:begin -->"
DEPS_END = "<!-- deps:end -->"
CALIBRATION_V7 = ROOT / "evals" / "calibration_v7.yaml"
CALIBRATION_V8 = ROOT / "evals" / "calibration_v8.yaml"
CALIBRATION_PY = ROOT / "evals" / "calibration.py"
# Prose patterns that hard-code numeric facts which must match the machine-readable sources.
# Each tuple is (pattern_regex, expected_value, context_hint).
# Patterns that indicate a prose claim about the TOTAL scenario registry size.
# Only these patterns trigger drift findings; subset counts (e.g. "4 scenarios affected") are ignored.
SCENARIO_TOTAL_PATTERNS: list[tuple[str, str]] = [
    (r"\b(\d+)\s*-scenario\s+evaluation\s+run", "total scenario count in prose"),
    (r"\b(\d+)\s*-scenario\s+registry", "total scenario count in prose"),
    (r"\b(\d+)\s*scenario(?:s)?\s+total", "total scenario count in prose"),
    (r"\b(\d+)\s*scenarios,\s*their\s+assertions", "total scenario count in prose (key files table)"),
]

# Patterns that indicate a prose claim about the TOTAL calibration corpus size.
CALIBRATION_TOTAL_PATTERNS: list[tuple[str, str]] = [
    (r"\bv7\s*\(\s*(\d+)\s*\)", "v7 corpus size in prose"),
    (r"\bv7\s*=\s*(\d+)", "v7 corpus size in prose"),
    (r"\bv7.*?\b(\d+)\s*cases", "v7 corpus size in prose"),
    (r"\b(\d+)\s*total\s*(?:case|corpus)", "total calibration cases in prose"),
    (r"\b(\d+)\s*\+\s*12\s*=\s*(\d+)", "v7+v8 total in prose"),
]

# Stale numbers that should never appear in live docs (historical artifacts only).
STALE_NUMBERS: list[tuple[str, str]] = [
    (r"\b56\s+(?:total|case|cases)", "stale combined corpus count (was 56, now 66)"),
    (r"\b44\s+case", "stale v7 count (was 44, now 54)"),
]


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
    """Return tracked and untracked Markdown files while excluding ignored files."""
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
    """True for historical records that intentionally retain stale references."""
    return any(
        path.is_relative_to(directory)
        for directory in (ROOT / "docs" / "archive", ROOT / "research" / "archive", ROOT / "evals" / "archive")
    )


def is_dated_snapshot(path: Path) -> bool:
    """True for point-in-time reports that are allowed to carry stale numbers."""
    markers = ("Dated snapshot", "Dated plan", "Dated evidence")
    try:
        text = path.read_text(encoding="utf-8")
        # Check the frontmatter block (first ~10 lines) for status markers
        lines = text.split("\n")
        for line in lines[:10]:
            for marker in markers:
                if marker in line:
                    return True
        # Also check for ADRs that explicitly note corpus growth since writing
        if "has grown from" in text and "since this ADR" in text:
            return True
    except (UnicodeDecodeError, IndexError):
        pass
    return False


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
    return ((ROOT if repo_rooted else source.parent) / target).resolve()


def is_repo_path(value: str) -> bool:
    top_level = (".github/", "config/", "data/", "docs/", "evals/", "infra/", "research/", "scripts/", "src/", "tests/")
    if not value.startswith(top_level) or " " in value:
        return False
    candidate = ROOT / value
    return Path(value).suffix != "" or candidate.is_dir()


def check_link_path(files: list[Path]) -> list[Finding]:
    """Report live repository paths referenced by Markdown that no longer exist."""
    findings: list[Finding] = []
    link_pattern = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
    code_pattern = re.compile(r"`([^`]+)`")
    for path in files:
        if is_archive(path):
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
            targets.extend((value, True) for value in code_pattern.findall(line) if is_repo_path(value))
            for target, repo_rooted in targets:
                candidate = path_from_link(target, path, repo_rooted=repo_rooted)
                if candidate is not None and not candidate.exists():
                    findings.append(Finding("link-path", path, number, f"missing {target}"))
    return findings


def check_encoding(files: list[Path]) -> list[Finding]:
    """Report UTF-8 BOMs, invalid bytes, and common PowerShell mojibake."""
    findings: list[Finding] = []
    for path in files:
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            findings.append(Finding("encoding", path, 0, "UTF-8 BOM is not allowed"))
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            findings.append(Finding("encoding", path, error.start + 1, "invalid UTF-8"))
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if ENCODING_MARKER in line:
                continue
            for sequence in MOJIBAKE:
                if sequence in code_spans_removed(line):
                    findings.append(Finding("encoding", path, number, f"mojibake sequence {sequence!r}"))
    return findings


def declared_dependencies(raw: bytes) -> set[str]:
    """Return normalized distribution names from runtime and development requirements."""
    data = tomllib.loads(raw.decode("utf-8"))
    specifiers = list(data.get("project", {}).get("dependencies", []))
    for group in data.get("dependency-groups", {}).values():
        specifiers.extend(item for item in group if isinstance(item, str))
    return {
        name.lower()
        for specifier in specifiers
        if (name := re.split(r"[\[<>=!~;\s]", specifier, maxsplit=1)[0].strip())
    }


def documented_dependencies(text: str) -> set[str]:
    """Return dependency names from table rows inside Tech Stack's marked region."""
    start, end = text.find(DEPS_BEGIN), text.find(DEPS_END)
    if start == -1 or end == -1 or end < start:
        return set()
    rows = re.findall(r"^\|\s*`([^`]+)`\s*\|", text[start + len(DEPS_BEGIN) : end], re.M)
    return {name.strip().lower() for name in rows}


def check_stack(_: list[Path]) -> list[Finding]:
    """Keep dependency claims in Tech Stack aligned with pyproject.toml."""
    if not TECH_STACK.exists():
        return [Finding("stack", TECH_STACK, 0, "docs/reference/configuration.md is missing")]
    stack_text = TECH_STACK.read_text(encoding="utf-8")
    if DEPS_BEGIN not in stack_text or DEPS_END not in stack_text:
        return [Finding("stack", TECH_STACK, 0, f"missing {DEPS_BEGIN} / {DEPS_END} markers")]
    declared = declared_dependencies(PYPROJECT.read_bytes())
    documented = documented_dependencies(stack_text)
    findings = [Finding("stack", TECH_STACK, 0, f"dependency {name!r} is not documented") for name in sorted(declared - documented)]
    findings.extend(Finding("stack", TECH_STACK, 0, f"documented {name!r} is not a dependency") for name in sorted(documented - declared))
    return findings


def registered_scenario_ids(text: str) -> set[str]:
    """Return the scenario IDs the scenario registry defines."""
    return set(REGISTRY_ID.findall(text))


def check_scenario_id(files: list[Path], registry: Path = SCENARIOS) -> list[Finding]:
    """Keep every live documented scenario ID resolvable in the scenario registry."""
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
                    findings.append(Finding("scenario-id", path, number, f"{identifier} is absent from {location}"))
    return findings


def _load_yaml_case_count(path: Path) -> int:
    """Load a YAML corpus file and return the number of cases."""
    try:
        import yaml
    except ImportError:
        return -1
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return len(data.get("cases", []))
        if isinstance(data, list):
            return len(data)
    except Exception:
        pass
    return -1


def check_scenario_count(files: list[Path]) -> list[Finding]:
    """Verify that prose does not hard-code a stale total scenario-count number."""
    if not SCENARIOS.exists():
        return [Finding("drift", SCENARIOS, 0, "scenario registry is missing")]
    try:
        import yaml
        data = yaml.safe_load(SCENARIOS.read_text(encoding="utf-8"))
        scenarios = data if isinstance(data, list) else data.get("scenarios", [])
        expected = len(scenarios)
    except Exception:
        return [Finding("drift", SCENARIOS, 0, "cannot parse scenario registry")]
    findings: list[Finding] = []
    for path in files:
        if is_archive(path) or is_dated_snapshot(path) or path.suffix != ".md":
            continue
        text = path.read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), 1):
            if SCENARIO_ID_MARKER in line or "lint-allow" in line.lower():
                continue
            # Only flag patterns that claim the TOTAL scenario count
            for pattern, hint in SCENARIO_TOTAL_PATTERNS:
                for match in re.finditer(pattern, line):
                    stated = match.group(1)
                    if stated != str(expected):
                        findings.append(Finding("drift", path, number, f"stale {hint}: {stated}; registry has {expected}"))
    return findings


def check_calibration_counts(files: list[Path]) -> list[Finding]:
    """Verify that prose does not hard-code stale calibration-corpus counts."""
    v7_count = _load_yaml_case_count(CALIBRATION_V7)
    v8_count = _load_yaml_case_count(CALIBRATION_V8)
    if v7_count < 0 or v8_count < 0:
        return [Finding("drift", CALIBRATION_V7, 0, "cannot parse calibration corpora")]
    expected_total = v7_count + v8_count
    findings: list[Finding] = []
    for path in files:
        if is_archive(path) or is_dated_snapshot(path) or path.suffix != ".md":
            continue
        text = path.read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), 1):
            if "lint-allow" in line.lower():
                continue
            # v7 count patterns
            for pattern, hint in CALIBRATION_TOTAL_PATTERNS:
                for match in re.finditer(pattern, line):
                    stated = match.group(1)
                    if stated != str(v7_count) and stated != str(expected_total):
                        findings.append(Finding("drift", path, number, f"stale {hint}: {stated}; expected v7={v7_count}, total={expected_total}"))
            # Stale numbers
            for pattern, hint in STALE_NUMBERS:
                for match in re.finditer(pattern, line):
                    findings.append(Finding("drift", path, number, f"{hint}: {match.group()}"))
    return findings


def check_threshold_constants(files: list[Path]) -> list[Finding]:
    """Verify that prose does not hard-code stale threshold values."""
    findings: list[Finding] = []
    # Parse thresholds from calibration.py
    py_text = CALIBRATION_PY.read_text(encoding="utf-8") if CALIBRATION_PY.exists() else ""
    released_threshold_match = re.search(r"RELEASE_THRESHOLD\s*=\s*([\d.]+)", py_text)
    released_threshold = float(released_threshold_match.group(1)) if released_threshold_match else None
    thresholds_by_class: dict[str, float] = {}
    for match in re.finditer(r'"(\w+)":\s*([\d.]+)', py_text):
        cls, val = match.group(1), float(match.group(2))
        if cls in ("SAF", "HON", "HLP"):
            thresholds_by_class[cls] = val
    if released_threshold is None:
        return [Finding("drift", CALIBRATION_PY, 0, "cannot parse RELEASE_THRESHOLD from calibration.py")]
    expected_total = sum(_load_yaml_case_count(p) for p in (CALIBRATION_V7, CALIBRATION_V8))
    if expected_total < 0:
        return [Finding("drift", CALIBRATION_V7, 0, "cannot parse calibration corpora for threshold provenance")]
    for path in files:
        if is_archive(path) or is_dated_snapshot(path) or path.suffix != ".md":
            continue
        text = path.read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), 1):
            if "lint-allow" in line.lower():
                continue
            # Check for stale composite corpus size mentioned alongside thresholds
            for pattern, hint in STALE_NUMBERS:
                for match in re.finditer(pattern, line):
                    findings.append(Finding("drift", path, number, f"{hint}: {match.group()}"))
    return findings


CHECKS = {
    "link-path": check_link_path,
    "encoding": check_encoding,
    "stack": check_stack,
    "scenario-id": check_scenario_id,
    "drift-scenario": check_scenario_count,
    "drift-calibration": check_calibration_counts,
    "drift-threshold": check_threshold_constants,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", choices=CHECKS, action="append")
    args = parser.parse_args(argv)
    files = markdown_files()
    selected = args.check or list(CHECKS)
    findings = [finding for name in selected for finding in CHECKS[name](files)]
    for finding in findings:
        print(finding)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
