"""Attach eval scores to the Langfuse trace produced by the same run.

Harness-owned, eval-time path (T0011.4) — deliberately separate from
`src/agents/tracing/langfuse.py`, whose accessors this module only reuses.
Never touches the request-path tracing handler.
"""

from __future__ import annotations

from langfuse.api import NotFoundError

from src.agents.tracing.langfuse import get_langfuse_client, get_langfuse_handler
from src.core.logger import logger

# A trace id in a capture artifact is not evidence that the trace was ingested.
# The 2026-08-21 probe recorded five non-null ids against an export target that
# was refusing connections, so every one of them pointed at nothing. This module
# resolves one of them against Langfuse before anyone reads the run as traced.


def write_scores(
    trace_id: str | None,
    results: dict[str, dict],
    *,
    dataset_run_id: str | None = None,
) -> int:
    """Write every non-None metric score in `results` onto the Langfuse trace
    `trace_id`. Returns the number of scores written; no-ops (returns 0, never
    raises) when `trace_id` is None or Langfuse is disabled (missing creds)."""
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
                    dataset_run_id=dataset_run_id,
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


def verify_ingestion(
    trace_id: str | None, *, dataset_run_id: str | None = None
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
        lf.api.trace.get(trace_id)
    except NotFoundError:
        record["ingested"] = False
        record["detail"] = "Langfuse has no trace with this id"
        logger.warning("Langfuse trace was never ingested", trace_id=trace_id)
    except Exception as exc:  # noqa: BLE001 - an unreachable Langfuse is not a verdict
        record["detail"] = str(exc)
        logger.warning(
            "Langfuse trace verification failed", trace_id=trace_id, error=str(exc)
        )
    else:
        record["ingested"] = True
        record["detail"] = "resolved in Langfuse"

    return record
