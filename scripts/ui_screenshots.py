"""Capture the UI review matrix: three viewports, both colour schemes.

The screenshot review is the step that catches what source review cannot —
hierarchy, wrapping, contrast as rendered, and anything that only breaks at
390px. It is mandatory before declaring a UI change done, and the images are
what you look at.

    # render the static page straight from disk, no server needed
    uv run python scripts/ui_screenshots.py

    # or point it at a running instance
    uv run python scripts/ui_screenshots.py http://127.0.0.1:8000

Writes PNGs to `.playwright-cli/ui/` and prints one path per line, so an agent
can `read` them back and critique the result.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "api" / "static" / "index.html"
OUTPUT = ROOT / ".playwright-cli" / "ui"

VIEWPORTS = [
    ("mobile", "390,860"),
    ("tablet", "768,1000"),
    ("desktop", "1440,1020"),
]
SCHEMES = ["light", "dark"]


def playwright_cli() -> list[str]:
    """Return a working invocation of the Playwright CLI, Windows included.

    On Windows the shim is `npx.cmd`, which a plain `npx` lookup will miss when
    spawning a subprocess without a shell.
    """
    if shutil.which("playwright"):
        return ["playwright"]
    for shim in ("npx.cmd", "npx"):
        if shutil.which(shim):
            return [shim, "--no-install", "playwright"]
    raise SystemExit("playwright CLI not found; install it with `npm i -D playwright`")


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    target = args[0] if args else STATIC.as_uri()
    command = playwright_cli()
    OUTPUT.mkdir(parents=True, exist_ok=True)

    captured: list[Path] = []
    for scheme in SCHEMES:
        for name, size in VIEWPORTS:
            destination = OUTPUT / f"{name}-{scheme}.png"
            result = subprocess.run(
                [
                    *command,
                    "screenshot",
                    "--viewport-size", size,
                    "--color-scheme", scheme,
                    "--full-page",
                    "--wait-for-timeout", "600",
                    target,
                    str(destination),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0 or not destination.exists():
                print(f"failed: {name}-{scheme}", file=sys.stderr)
                print(result.stderr.strip(), file=sys.stderr)
                return 1
            captured.append(destination)

    for path in captured:
        print(path.relative_to(ROOT).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
