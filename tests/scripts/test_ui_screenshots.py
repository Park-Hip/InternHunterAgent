from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).parents[2] / "scripts" / "ui_screenshots.py"
SPEC = importlib.util.spec_from_file_location("ui_screenshots", SCRIPT_PATH)
assert SPEC and SPEC.loader
screenshots = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = screenshots
SPEC.loader.exec_module(screenshots)

FIXTURE_SSE = re.compile(r'const FIXTURE_SSE = ("(?:[^"\\]|\\.)*");')


def _fixture_events(harness: "screenshots.Harness") -> list[dict[str, object]]:
    match = FIXTURE_SSE.search(harness.html)
    assert match, f"{harness.name} does not embed an SSE fixture"

    sse = json.loads(match.group(1))
    events: list[dict[str, object]] = []
    for block in sse.split("\n\n"):
        if not block.strip():
            continue
        events.append(json.loads(block.split("data: ", 1)[1]))
    return events


def _harness(name: str) -> "screenshots.Harness":
    return next(
        harness for harness in screenshots.build_harnesses() if harness.name == name
    )


def test_harness_covers_an_early_zero_followed_by_a_match() -> None:
    """The #725 scenario: an early zero must not leave the card up (#725).

    The fixture has two completed query calls, zero then two rows. Its selector
    requires the rendered answer and forbids the no-answer card, so a stale
    `zeroResult` makes the capture wait and fail instead of passing on a
    misleading image.
    """
    harness = _harness("late-match")
    tools = [
        event for event in _fixture_events(harness) if event["type"] == "tool"
    ]

    assert [tool["row_count"] for tool in tools] == [0, 2]
    assert all(tool["status"] == "ok" for tool in tools)
    assert ":not(:has(.turn__nodata))" in harness.selector
    assert ".turn__answer--markdown" in harness.selector


def test_harness_pins_the_latest_retrieval_as_the_turn_outcome() -> None:
    """A match followed by a zero must still show the card, for the latest call.

    This is the other side of the rule: the no-answer state follows the final
    counted result rather than the first one, and the detail line says the
    latest query matched nothing.
    """
    harness = _harness("final-zero")
    tools = [
        event for event in _fixture_events(harness) if event["type"] == "tool"
    ]

    assert [tool["row_count"] for tool in tools] == [2, 0]
    assert all(tool["status"] == "ok" for tool in tools)
    assert "article.turn:has(.turn__nodata)" in harness.selector
    assert ":not(:has(.turn__nodata))" not in harness.selector
