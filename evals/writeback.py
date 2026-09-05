"""Attach eval scores to the Langfuse trace produced by the same run.

Harness-owned, eval-time path (T0011.4) — deliberately separate from
`src/agents/tracing/langfuse.py`, whose accessors this module only reuses.
Never touches the request-path tracing handler.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from langfuse.api import NotFoundError

from src.agents.tracing.langfuse import get_langfuse_client, get_langfuse_handler
from src.core.config import settings
from src.core.logger import logger

# A trace id in a capture artifact is not evidence that the trace was ingested.
# The 2026-08-21 probe recorded five non-null ids against an export target that
# was refusing connections, so every one of them pointed at nothing. This module
# resolves one of them against Langfuse before anyone reads the run as traced.

# Export is asynchronous and batched, and Cloud ingestion is not synchronous with
# the API accepting the batch. A capture of two scenarios finishes in seconds, well
# inside that window, so the probe flushes first and then retries: without this it
# reports a healthy run as un-ingested. The ladder is short because the question is
# "did this arrive at all", not "how fast".
def _ingestion_retry_delays() -> tuple[float, ...]:
    cfg = (settings.config_yaml.get("eval") or {}).get("writeback")
    if isinstance(cfg, dict):
        delays = cfg.get("ingestion_retry_delays")
        if isinstance(delays, list) and all(isinstance(d, (int, float)) for d in delays):
            return tuple(float(d) for d in delays)
    return (0.0, 2.0, 5.0)


_INGESTION_RETRY_DELAYS = _ingestion_retry_delays()


def write_scores(trace_id: str | None, results: dict[str, dict]) -> int:
    """Write every non-None metric score in `results` onto the Langfuse trace
    `trace_id`. Returns the number of scores written; no-ops (returns 0, never
    raises) when `trace_id` is None or Langfuse is disabled (missing creds).

    A score names its trace and nothing else. Langfuse rejects a score carrying
    both `traceId` and `datasetRunId` - "provide exactly one of the following" -
    with a 400 the SDK reports asynchronously, so passing both silently wrote
    nothing at all. The dataset run still gets these scores: its run item links
    this trace, so scoring the trace is what puts them under the run.
    """
    if trace_id is None or get_langfuse_handler() is None:
        return 0

    lf = get_langfuse_client()
    if lf is None:
        return 0

    written = 0
    for seam_name, metric_scores in results.items():
        for metric_name, payload in metric_scores.items():
            score = payload.get("score")
            if score is None:
                continue
            try:
                lf.create_score(
                    name=f"{seam_name}/{metric_name}",
                    value=score,
                    trace_id=trace_id,
                    data_type="NUMERIC",
                    score_id=f"{trace_id}-{seam_name}-{metric_name}",
                    comment=payload.get("reason"),
                )
                written += 1
            except Exception as exc:  # noqa: BLE001 - a Langfuse hiccup must not break scoring
                logger.warning(
                    "Langfuse score writeback failed",
                    metric=f"{seam_name}/{metric_name}",
                    error=str(exc),
                )

    try:
        lf.flush()
    except Exception as exc:  # noqa: BLE001 - export draining must not break an eval capture
        logger.warning("Langfuse score flush failed", error=str(exc))
    return written


def sample_verification_target(
    artifact: dict[str, Any],
) -> tuple[str | None, str | None]:
    """Pick the trace to probe this capture through, with the run it was linked into.

    The most recently captured turn, not the first. Sampling one turn is sound
    because every turn exports through the same client to the same host - but that
    holds only within a single process. A `--resume` continues an artifact whose
    earlier turns were exported by a previous run, possibly against a host that has
    since changed, so probing the first id verifies the interrupted session and
    reports the new traces as ingested when they went nowhere. Scenarios are walked
    in registry order and turns are appended, so the last id recorded is the newest.
    """
    trace_id: str | None = None
    dataset_run_id: str | None = None
    for record in artifact.get("scenarios", {}).values():
        for repeat in record.get("repeats", []):
            for turn in repeat.get("turns", []):
                recorded = turn.get("seams", {}).get("trace_id")
                if recorded is not None:
                    trace_id = recorded
                    dataset_run_id = repeat.get("dataset_run_id")
    return trace_id, dataset_run_id


def verify_ingestion(
    trace_id: str | None,
    *,
    dataset_run_id: str | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, object]:
    """Report whether `trace_id` actually resolves in Langfuse.

    `ingested` is True when the trace is there, False when Langfuse answered that
    it is not, and None when the question could not be asked - tracing disabled,
    no trace id recorded, or the lookup itself failed. None is deliberately not
    False: "we did not check" and "it is not there" are different findings, and
    collapsing them is how the probe's dead export target went unnoticed.
    """
    record: dict[str, object] = {
        "trace_id": trace_id,
        "dataset_run_id": dataset_run_id,
        "ingested": None,
        "detail": None,
    }

    if trace_id is None:
        record["detail"] = "no trace id recorded"
        return record
    if get_langfuse_handler() is None:
        record["detail"] = "tracing disabled"
        return record

    lf = get_langfuse_client()
    if lf is None:
        record["detail"] = "tracing disabled"
        return record

    try:
        lf.flush()
    except Exception as exc:  # noqa: BLE001 - a failed drain is reported, not raised
        logger.warning("Langfuse flush before verification failed", error=str(exc))

    for attempt, delay in enumerate(_INGESTION_RETRY_DELAYS):
        if delay:
            sleep(delay)
        try:
            lf.api.trace.get(trace_id)
        except NotFoundError:
            record["ingested"] = False
            record["detail"] = "Langfuse has no trace with this id"
            continue
        except Exception as exc:  # noqa: BLE001 - unreachable Langfuse is no verdict
            record["ingested"] = None
            record["detail"] = str(exc)
            logger.warning(
                "Langfuse trace verification failed",
                trace_id=trace_id,
                attempt=attempt + 1,
                error=str(exc),
            )
            break
        record["ingested"] = True
        record["detail"] = "resolved in Langfuse"
        break

    if record["ingested"] is False:
        logger.warning("Langfuse trace was never ingested", trace_id=trace_id)

    return record


def count_trace_scores(trace_id: str | None) -> int | None:
    """Count the scores Langfuse actually holds for `trace_id`, or None if unasked.

    `write_scores` returns how many scores it *enqueued*. The SDK batches and
    reports rejections asynchronously on its own logger, so a run can enqueue
    fourteen scores, have every one refused, and still report fourteen. This is
    the only cheap check that distinguishes those two outcomes.
    """
    if trace_id is None or get_langfuse_handler() is None:
        return None
    lf = get_langfuse_client()
    if lf is None:
        return None
    try:
        return len(lf.api.scores.get_many(trace_id=trace_id).data)
    except Exception as exc:  # noqa: BLE001 - an unreachable Langfuse is not a count
        logger.warning("Langfuse score count failed", trace_id=trace_id, error=str(exc))
        return None
