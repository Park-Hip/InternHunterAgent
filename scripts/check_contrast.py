"""Check that every declared design token clears its WCAG contrast floor.

The UI is served as static CSS, so there is no bundler to catch a token that
silently drops below AA. This script parses `src/api/static/tokens.css`, resolves
the light and dark blocks, and asserts each pair listed in `PAIRS`.

Run it directly, or let `scripts/docs_lint.py`-style CI call it:

    uv run python scripts/check_contrast.py

Exit code 0 when every pair passes, 1 otherwise. When you add or retune a token,
add its pair in the same commit, otherwise the new colour is unenforced.
"""

from __future__ import annotations

import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOKENS = ROOT / "src" / "api" / "static" / "tokens.css"

# (foreground, background, minimum ratio, note)
# 4.5 is WCAG 2.2 AA for normal text; 3.0 is AA for large text and for the
# 3:1 non-text contrast that meaningful boundaries and focus rings need.
PAIRS: list[tuple[str, str, float, str]] = [
    ("--ink", "--paper", 4.5, "body text"),
    ("--ink-soft", "--paper", 4.5, "secondary reading ink"),
    ("--muted", "--paper", 4.5, "labels and captions"),
    ("--faint", "--paper", 4.5, "lowest-emphasis text"),
    ("--faint", "--surface-2", 4.5, "captions on a raised surface"),
    ("--ink", "--user-fill", 4.5, "text on the reader's own words"),
    ("--ink-soft", "--user-fill", 4.5, "the reader's own words"),
    ("--accent-ink", "--paper", 4.5, "links and citation marks"),
    ("--accent-ink", "--surface-2", 4.5, "links on a raised surface"),
    ("--accent", "--paper", 3.0, "the vermilion rule, a non-text boundary"),
    ("--on-ink", "--ink", 4.5, "the send button label"),
    ("--ok", "--paper", 4.5, "status text"),
    ("--warn", "--paper", 4.5, "status text"),
    ("--bad", "--paper", 4.5, "status text"),
]

# (background, minimum ratio against --paper, note) for non-text surfaces.
SURFACES: list[tuple[str, float, str]] = [
    ("--surface", 1.03, "a card must be distinguishable from the page"),
    ("--surface-2", 1.04, "a raised fill must be distinguishable"),
    ("--user-fill", 1.06, "the reader's own words must be distinguishable"),
    ("--hairline", 1.18, "a hairline border must be visible as a boundary"),
]

THEMES = ("light", "dark")

DECLARATION = re.compile(r"(--[a-z0-9-]+)\s*:\s*(.+?);", re.IGNORECASE)
OKLCH = re.compile(
    r"oklch\(\s*([\d.]+)%\s+([\d.]+)\s+([\d.]+)\s*(?:/\s*([\d.]+)\s*%?)?\s*\)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Failure:
    theme: str
    description: str
    measured: float
    required: float

    def __str__(self) -> str:
        return (
            f"{self.theme}: {self.description} is {self.measured:.2f}:1, "
            f"needs {self.required:.2f}:1"
        )


def _srgb_to_linear(channel: float) -> float:
    if channel <= 0.04045:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def _linear_to_srgb(channel: float) -> float:
    if channel <= 0.0031308:
        return 12.92 * channel
    return 1.055 * channel ** (1 / 2.4) - 0.055


def oklch_to_srgb(lightness: float, chroma: float, hue: float) -> tuple[float, float, float]:
    """Convert OKLCH to sRGB in 0..1, clipping out-of-gamut channels."""
    radians = math.radians(hue)
    a = chroma * math.cos(radians)
    b = chroma * math.sin(radians)

    l_ = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (lightness - 0.0894841775 * a - 1.2914855480 * b) ** 3

    red = 4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_
    green = -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_
    blue = -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_

    return tuple(
        min(1.0, max(0.0, _linear_to_srgb(channel))) for channel in (red, green, blue)
    )


def relative_luminance(rgb: tuple[float, float, float]) -> float:
    red, green, blue = (_srgb_to_linear(channel) for channel in rgb)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(first: tuple[float, float, float], second: tuple[float, float, float]) -> float:
    a, b = relative_luminance(first), relative_luminance(second)
    lighter, darker = max(a, b), min(a, b)
    return (lighter + 0.05) / (darker + 0.05)


def parse_themes(text: str) -> dict[str, dict[str, str]]:
    """Split the light `:root` block from the dark `prefers-color-scheme` block."""
    themes: dict[str, dict[str, str]] = {name: {} for name in THEMES}
    current = "light"
    depth = 0
    for line in text.splitlines():
        stripped = line.strip()
        if "prefers-color-scheme: dark" in stripped:
            current = "dark"
        for name, value in DECLARATION.findall(line):
            if OKLCH.search(value):
                themes[current][name] = value
    # A token only declared once belongs to the theme that declared it; carry it
    # into the other theme so a shared value is still checked.
    for name, value in list(themes["light"].items()):
        themes["dark"].setdefault(name, value)
    for name, value in list(themes["dark"].items()):
        themes["light"].setdefault(name, value)
    del depth
    return themes


def resolve(themes: dict[str, dict[str, str]], theme: str, name: str) -> tuple[float, float, float]:
    match = OKLCH.search(themes[theme][name])
    if match is None:
        raise KeyError(f"{name} is not an oklch token in the {theme} theme")
    lightness, chroma, hue = (float(match.group(index)) for index in (1, 2, 3))
    return oklch_to_srgb(lightness / 100, chroma, hue)


def main() -> int:
    if not TOKENS.exists():
        print(f"{TOKENS.relative_to(ROOT)} is missing", file=sys.stderr)
        return 1

    themes = parse_themes(TOKENS.read_text(encoding="utf-8"))
    failures: list[Failure] = []
    checked = 0

    for theme in THEMES:
        for foreground, background, minimum, note in PAIRS:
            try:
                first = resolve(themes, theme, foreground)
                second = resolve(themes, theme, background)
            except KeyError as error:
                print(f"{theme}: {error}", file=sys.stderr)
                return 1
            ratio = contrast(first, second)
            checked += 1
            status = "ok" if ratio >= minimum else "FAIL"
            print(f"  [{status}] {theme:5} {foreground} on {background} = {ratio:5.2f}:1  ({note})")
            if ratio < minimum:
                failures.append(Failure(theme, f"{foreground} on {background}", ratio, minimum))

        paper = resolve(themes, theme, "--paper")
        for surface, minimum, note in SURFACES:
            ratio = contrast(resolve(themes, theme, surface), paper)
            checked += 1
            status = "ok" if ratio >= minimum else "FAIL"
            print(f"  [{status}] {theme:5} {surface} vs --paper = {ratio:5.2f}:1  ({note})")
            if ratio < minimum:
                failures.append(Failure(theme, f"{surface} vs --paper", ratio, minimum))

    print()
    if failures:
        print(f"{len(failures)} of {checked} token pairs fail:")
        for failure in failures:
            print(f"  {failure}")
        return 1
    print(f"All {checked} token pairs meet their contrast floor in both themes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
