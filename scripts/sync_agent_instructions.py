"""Keep AGENTS.md byte-for-byte identical to CLAUDE.md."""

from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "CLAUDE.md"
TARGET = ROOT / "AGENTS.md"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail when AGENTS.md differs.")
    args = parser.parse_args(argv)
    source = SOURCE.read_bytes()
    if args.check:
        if TARGET.read_bytes() != source:
            print("stale: AGENTS.md does not match CLAUDE.md")
            return 1
        return 0
    TARGET.write_bytes(source)
    print("updated: AGENTS.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
