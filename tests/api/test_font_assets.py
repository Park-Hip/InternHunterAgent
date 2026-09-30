"""Guard the self-hosted typeface wiring.

The deep glyph check lives in `scripts/check_font_coverage.py` and needs
fontTools. This file is the cheap, dependency-free guard that runs in the normal
suite: it proves the fonts are declared, referenced by files that exist, and
split into the subsets a Vietnamese page actually needs.

It exists because the failure mode is silent. A missing `woff2` or a dropped
Vietnamese `unicode-range` does not raise; the browser simply falls back
mid-paragraph, which is exactly the defect the typeface change set out to remove.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "src" / "api" / "static"
TOKENS = STATIC / "tokens.css"
FONT_DIR = STATIC / "vendor" / "fonts"

FACE = re.compile(
    r"@font-face\s*\{(?P<body>[^}]*)\}", re.DOTALL
)
URL = re.compile(r'url\(\s*"(?P<path>[^"]+)"\s*\)')
UNICODE_RANGE = re.compile(r"unicode-range:\s*(?P<range>[^;]+);")
FONT_WEIGHT = re.compile(r"font-weight:\s*(?P<weight>\d+)")
FONT_STYLE = re.compile(r"font-style:\s*(?P<style>\w+)")


class FontAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = TOKENS.read_text(encoding="utf-8")
        cls.faces = [match.group("body") for match in FACE.finditer(cls.text)]

    def test_tokens_declare_font_faces(self) -> None:
        self.assertTrue(self.faces, "tokens.css declares no @font-face rules")

    def test_every_referenced_font_file_exists(self) -> None:
        for body in self.faces:
            match = URL.search(body)
            self.assertIsNotNone(match, "a @font-face has no src url")
            relative = match.group("path")
            path = (STATIC / relative).resolve()
            self.assertTrue(path.is_file(), f"referenced font is missing: {relative}")

    def test_vietnamese_is_a_declared_subset_for_every_weight_and_style(self) -> None:
        """Each shipped weight needs both subsets: base Latin from `latin`, the
        Vietnamese block from `vietnamese`. A page loads their union, so losing
        either one silently breaks rendering."""
        declared: set[tuple[str, str, str]] = set()
        for body in self.faces:
            path = URL.search(body).group("path")
            weight = FONT_WEIGHT.search(body).group("weight")
            style = FONT_STYLE.search(body).group("style")
            for subset in ("latin", "latin-ext", "vietnamese"):
                if f"be-vietnam-pro-{subset}-" in path:
                    declared.add((weight, style, subset))

        for weight, style in (("400", "normal"), ("600", "normal"), ("700", "normal"), ("400", "italic")):
            for subset in ("latin", "vietnamese"):
                self.assertIn(
                    (weight, style, subset),
                    declared,
                    f"no {subset} subset declared for {weight} {style}",
                )

    def test_vietnamese_unicode_range_covers_the_vietnamese_block(self) -> None:
        """U+1EA0-1EF9 is the Vietnamese-specific block. Without it in the range
        the browser never fetches the Vietnamese subset for Vietnamese text."""
        for body in self.faces:
            path = URL.search(body).group("path")
            if "be-vietnam-pro-vietnamese-" not in path:
                continue
            ranges = UNICODE_RANGE.search(body)
            self.assertIsNotNone(ranges, f"vietnamese subset has no unicode-range: {path}")
            self.assertIn(
                "U+1EA0-1EF9",
                ranges.group("range"),
                f"the Vietnamese block is not claimed by {path}",
            )

    def test_no_third_party_font_cdn(self) -> None:
        """A CDN font is a third party on the critical path and a source of
        layout shift. The typeface is self-hosted by policy."""
        for path in STATIC.rglob("*"):
            if path.suffix not in {".css", ".html", ".js"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            self.assertNotIn(
                "fonts.googleapis.com", text, f"{path.name} loads fonts from a CDN"
            )
            self.assertNotIn(
                "fonts.gstatic.com", text, f"{path.name} loads fonts from a CDN"
            )

    def test_typography_rules_survive(self) -> None:
        """The Vietnamese typography floor, as executable assertions.

        Short failure messages on purpose: dumping a whole stylesheet into an
        assertion failure makes the failure unreadable.
        """
        styles = (STATIC / "styles.css").read_text(encoding="utf-8")
        index = (STATIC / "index.html").read_text(encoding="utf-8")
        self.assertIn("Be Vietnam Pro", self.text, "the self-hosted family is not declared")
        self.assertNotIn("Times New Roman", styles, "the old system serif default is back")
        self.assertIn('"ccmp" 1', styles, "composed Vietnamese diacritics are not requested")
        self.assertIn("prefers-reduced-motion", styles, "the motion floor is gone")
        self.assertIn("aria-busy", index, "the stream live region lost its busy flag")


if __name__ == "__main__":
    unittest.main()
