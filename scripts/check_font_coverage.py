"""Deep check that the vendored typeface actually covers Vietnamese.

The cheap guard in `tests/api/test_font_assets.py` only proves the font files are
referenced and declared. This reads the `cmap` tables of the shipped `woff2`
files and proves the glyphs are really there, which is the check the typography
work actually hinged on.

It needs `fontTools` and `brotli`, so it is run ephemerally rather than added as
a project dependency:

    uv run --with fonttools --with brotli python scripts/check_font_coverage.py

A Vietnamese page is served by two subsets working together: base Latin letters
come from `latin`, and the Vietnamese-specific block from `vietnamese`. Each
subset is therefore expected to cover only part of the alphabet, and the check
asserts the **union** covers all of it - which is what a browser assembles.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FONT_DIR = ROOT / "src" / "api" / "static" / "vendor" / "fonts"

# Vietnamese is a first-class language here, so the sample is the full
# alphabet in both cases plus the digits and Latin the interface also sets.
SAMPLE = (
    "ÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĐĨŨƠƯẠẢẤẦẨẪẬẮẰẲẴẶẸẺẼỀỀỂỄỆỈỊỌỎỐỒỔỖỘỚỜỞỠỢỤỦỨỪỬỮỰỲỴỶỸ"
    "àáâãèéêìíòóôõùúăđĩũơưạảấầẩẫậắằẳẵặẹẻẽềềểễệỈịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ"
    "ệ ữ ỗ ặ ằ ế"
    "ABCabc0123456789"
)

# The string the typography change was approved against.
TEST_STRING = "ệ ữ ỗ ặ ằ ế"

REQUIRED = [("400", "normal"), ("600", "normal"), ("700", "normal"), ("400", "italic")]
SUBSETS_NEEDED = ("latin", "vietnamese")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        print(
            "fontTools is required: run with\n"
            "  uv run --with fonttools --with brotli python scripts/check_font_coverage.py",
            file=sys.stderr,
        )
        return 2

    if not FONT_DIR.is_dir():
        print(f"{FONT_DIR} is missing; has the vendored font been added?", file=sys.stderr)
        return 1

    def cmap(name: str) -> set[int]:
        font = TTFont(str(FONT_DIR / name))
        points: set[int] = set()
        for table in font["cmap"].tables:
            points |= set(table.cmap)
        return points

    failures: list[str] = []
    for weight, style in REQUIRED:
        subsets = {}
        for subset in SUBSETS_NEEDED:
            path = FONT_DIR / f"be-vietnam-pro-{subset}-{weight}-{style}.woff2"
            if not path.exists():
                failures.append(f"missing file: {path.name}")
                subsets[subset] = set()
                continue
            subsets[subset] = cmap(path.name)

        union = subsets["latin"] | subsets["vietnamese"]
        missing = [c for c in SAMPLE if ord(c) not in union]
        missing_test = [c for c in TEST_STRING if c != " " and ord(c) not in union]

        status = "ok" if not missing else f"{len(missing)} missing"
        print(
            f"[{'ok' if not missing else 'FAIL'}] {weight} {style:<7} "
            f"union of {' + '.join(SUBSETS_NEEDED):<20} {status}"
        )
        if missing:
            failures.append(f"{weight} {style}: missing {''.join(missing)}")
        if missing_test:
            failures.append(f"{weight} {style}: test string missing {''.join(missing_test)}")

    print()
    if failures:
        print(f"{len(failures)} coverage failures:")
        for failure in failures:
            print(f"  {failure}")
        return 1
    print(
        f"Every shipped weight and style covers the full Vietnamese sample through the\n"
        f"latin + vietnamese union, including the approved test string {TEST_STRING!r}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
