"""Capture the UI review matrix: three viewports, both colour schemes.

The screenshot review is the step that catches what source review cannot -
hierarchy, wrapping, contrast as rendered, and anything that only breaks at
390px. It is mandatory before declaring a UI change done, and the images are
what you look at.

    # render the static page straight from disk, no server needed
    uv run python scripts/ui_screenshots.py

    # or point it at a running instance
    uv run python scripts/ui_screenshots.py http://127.0.0.1:8000

A second phase replays one canned server sequence per fixture through the real
page and the real app.js, with fetch() stubbed, so the error turn and the
empty-answer turn - states that need a failing server to produce - are captured
for review as well. The fixture payloads are built from the server's own
constants, so they cannot drift from the copy the wire carries.

Writes PNGs to `.playwright-cli/ui/` and prints one path per line, so an agent
can `read` them back and critique the result.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "src" / "api" / "static"
INDEX = STATIC_DIR / "index.html"
OUTPUT = ROOT / ".playwright-cli" / "ui"

VIEWPORTS = [
    ("mobile", "390,860"),
    ("tablet", "768,1000"),
    ("desktop", "1440,1020"),
]
SCHEMES = ["light", "dark"]

# One question, so the harness turns read like a real conversation.
HARNESS_QUESTION = "Vị trí thực tập AI Engineer ở Đà Nẵng có mức lương bao nhiêu?"

ASSET_REF = re.compile(r'(?P<attribute>href|src)="\./(?P<asset>[^"]+)"')
APP_SCRIPT = '<script src="./app.js"></script>'


@dataclass(frozen=True)
class Harness:
    """A canned stream plus the selector whose arrival means it rendered."""

    name: str
    selector: str
    html: str


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


def capture(
    command: list[str],
    *,
    target: str,
    destination: Path,
    viewport: str,
    scheme: str,
    selector: str | None = None,
) -> bool:
    """Capture one PNG and report whether it was written."""
    args = [
        *command,
        "screenshot",
        "--viewport-size",
        viewport,
        "--color-scheme",
        scheme,
        "--full-page",
    ]
    if selector is not None:
        # A fixture that never renders should fail the run, not hang it.
        args += ["--wait-for-selector", selector, "--timeout", "15000"]
    args += ["--wait-for-timeout", "600", target, str(destination)]

    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    if result.returncode != 0 or not destination.exists():
        print(f"failed: {destination.name}", file=sys.stderr)
        print(result.stderr.strip(), file=sys.stderr)
        return False
    return True


def build_harnesses() -> list[Harness]:
    """The error and empty-answer turns, replayed from the server's own copy."""
    sys.path.insert(0, str(ROOT))
    from src.agents.service import FALLBACK_ANSWER
    from src.core.errors import BUSY_MESSAGE, PROVIDER_BUSY_ERROR_CODE

    session = {"session_id": "screenshot-harness"}
    return [
        Harness(
            name="error-turn",
            selector=".turn__agent.is-error",
            html=_harness_html(
                [
                    ("session", session),
                    (
                        "error",
                        {
                            "message": BUSY_MESSAGE,
                            "code": PROVIDER_BUSY_ERROR_CODE,
                            "retryable": True,
                        },
                    ),
                    ("done", {}),
                ]
            ),
        ),
        Harness(
            name="empty-answer",
            selector=".turn__nodata",
            html=_harness_html(
                [
                    ("session", session),
                    ("token", {"text": FALLBACK_ANSWER}),
                    ("metadata", {"trace_id": None, "trace_url": None}),
                    ("done", {}),
                ]
            ),
        ),
    ]


def _harness_html(events: list[tuple[str, dict[str, object]]]) -> str:
    page = INDEX.read_text(encoding="utf-8")
    if APP_SCRIPT not in page:
        raise SystemExit("index.html no longer loads ./app.js as expected")
    stub = _stub_script(_sse(events))
    page = page.replace(APP_SCRIPT, f"{stub}\n    {APP_SCRIPT}")
    # The harness page lives outside the static directory, so every relative
    # asset reference becomes an absolute file:// URI.
    return ASSET_REF.sub(_absolute_asset, page)


def _absolute_asset(match: re.Match[str]) -> str:
    asset = (STATIC_DIR / match.group("asset")).as_uri()
    return f'{match.group("attribute")}="{asset}"'


def _sse(events: list[tuple[str, dict[str, object]]]) -> str:
    """Encode the fixture the way the route does, `type` included."""
    blocks = []
    for event, payload in events:
        data = {"type": event, **payload}
        blocks.append(f"event: {event}\ndata: {json.dumps(data)}\n\n")
    return "".join(blocks)


def _stub_script(sse: str) -> str:
    question = json.dumps(HARNESS_QUESTION)
    return "\n".join(
        [
            "<script>",
            "// Screenshot harness from scripts/ui_screenshots.py: fetch() is",
            "// stubbed to replay one canned server sequence, so a rendered error",
            "// or empty-answer turn can be reviewed as an image without a server.",
            f"const FIXTURE_SSE = {json.dumps(sse)};",
            "const fixtureResponse = () => {",
            "  const bytes = new TextEncoder().encode(FIXTURE_SSE);",
            "  let sent = false;",
            "  return {",
            "    ok: true,",
            "    body: { getReader: () => ({ read: async () => {",
            "      if (sent) return { done: true };",
            "      sent = true;",
            "      return { done: false, value: bytes };",
            "    } }) },",
            "  };",
            "};",
            "window.fetch = async (url) =>",
            '  String(url).includes("/ready") ? { ok: false } : fixtureResponse();',
            'window.addEventListener("load", () => {',
            f'  document.getElementById("query").value = {question};',
            '  document.getElementById("composer").requestSubmit();',
            "});",
            "</script>",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    target = args[0] if args else INDEX.as_uri()
    command = playwright_cli()
    OUTPUT.mkdir(parents=True, exist_ok=True)

    captured: list[Path] = []
    for scheme in SCHEMES:
        for name, size in VIEWPORTS:
            destination = OUTPUT / f"{name}-{scheme}.png"
            if not capture(
                command,
                target=target,
                destination=destination,
                viewport=size,
                scheme=scheme,
            ):
                return 1
            captured.append(destination)

    for harness in build_harnesses():
        harness_path = OUTPUT / f"harness-{harness.name}.html"
        harness_path.write_text(harness.html, encoding="utf-8")
        for scheme in SCHEMES:
            for name, size in VIEWPORTS:
                destination = OUTPUT / f"{harness.name}-{name}-{scheme}.png"
                if not capture(
                    command,
                    target=harness_path.as_uri(),
                    destination=destination,
                    viewport=size,
                    scheme=scheme,
                    selector=harness.selector,
                ):
                    return 1
                captured.append(destination)

    for path in captured:
        print(path.relative_to(ROOT).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
