"""Recorded provider responses for the Bright Data adapter tests.

Every response here is a reconstruction, not provider output: the bounded observation
retained no bytes. See `fixtures/brightdata/README.md`, and treat
`recorded_evidence.json` as the evidence the scenarios are checked against.

The scenarios are the provider state machine in the shape the observation measured:
the inline branch, the 202 handoff, the declared progress states, an empty delivery, a
partial delivery with provider-reported errors, and the responses a fail-closed adapter
must refuse to interpret.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "brightdata"

SNAPSHOT_ID = "sd_mujknayt1rvg0aadjq"
DATASET_ID = "gd_lpfll7v5hcqtkxl6l"
# The instant the recorded handoff, progress and download states were observed.
OBSERVED_AT = datetime(2026, 9, 27, 8, 44, 34, tzinfo=UTC)
HANDOFF_RETRY_AFTER_SECONDS = 30


def recorded_evidence() -> dict:
    return _load("recorded_evidence.json")


def snapshot_records() -> list[dict]:
    return _load("snapshot_records.json")["records"]


def _load(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def handoff_202(
    *, message: str = "Snapshot is not ready yet, try again in 30s",
    snapshot_id: str = SNAPSHOT_ID, extra: dict | None = None,
) -> dict:
    """The 202 handoff body. `status` is absent because its value was not recorded."""
    return {"message": message, "snapshot_id": snapshot_id, **(extra or {})}


def progress(
    status: str = "ready", *, records: int = 10, errors: int = 0,
    snapshot_id: str = SNAPSHOT_ID, collection_duration_ms: int = 36326,
    extra: dict | None = None,
) -> dict:
    """The progress envelope, with every key the observation recorded."""
    return {
        "avg_duration_per_input": collection_duration_ms,
        "collection_duration": collection_duration_ms,
        "dataset_id": DATASET_ID,
        "errors": errors,
        "records": records,
        "snapshot_id": snapshot_id,
        "status": status,
        **(extra or {}),
    }


def response(status: int, body: Any, headers: dict | None = None) -> dict:
    return {"status": status, "headers": headers or {}, "body": body}


def handoff_run(
    *, statuses: tuple[str, ...] = ("ready",), records: int | None = None,
    errors: int = 0, body: Any = None, download_status: int = 200,
) -> list[dict]:
    """Submit, then one response per declared progress state, then the download.

    The default is the recorded run exactly: a 202 handoff, one `ready` poll, and a
    download of the ten reconstructed records.
    """
    delivered = snapshot_records() if body is None else body
    responses = [
        response(
            202, handoff_202(),
            {"retry-after": str(HANDOFF_RETRY_AFTER_SECONDS),
             "content-type": "application/json; charset=utf-8"},
        )
    ]
    for index, status in enumerate(statuses):
        responses.append(response(200, progress(
            status, records=len(delivered) if records is None else records,
            errors=errors,
        )))
    responses.append(response(download_status, delivered))
    return responses


def inline_run(*, body: Any = None) -> list[dict]:
    """The inline branch: records in the immediate 200 response, no poll at all."""
    return [response(200, snapshot_records() if body is None else body)]


def hostile_handoff_run() -> list[dict]:
    """A handoff that offers a next URL in its body and in a `Location` header.

    Nothing here was observed. It exists so the tests can prove the adapter never
    follows a URL it did not declare.
    """
    next_url = "https://www.linkedin.com/jobs/search/?keywords=AI%20Engineer&page=2"
    return [
        response(
            202,
            handoff_202(
                snapshot_id=SNAPSHOT_ID,
                extra={"next": next_url, "links": {"next": next_url},
                       "snapshot_url": f"https://api.brightdata.com/snapshots/{SNAPSHOT_ID}"},
            ),
            {"retry-after": "30", "location": next_url},
        ),
        response(200, progress()),
        response(200, snapshot_records()),
    ]


def blocked_run(status: int = 400, message: str = "Customer is not active") -> list[dict]:
    """The historical account failure, which the adapter records as a block."""
    return [response(status, {"message": message})]


def failed_progress_run(*, message: str = "No data found in discovery") -> list[dict]:
    """A terminal `failed` state. The message is documented-only, never observed."""
    return [
        response(202, handoff_202(), {"retry-after": "30"}),
        response(200, progress("failed", records=0, errors=1,
                               extra={"error_message": message})),
    ]
