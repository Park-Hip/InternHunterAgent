"""Attach eval scores to the Langfuse trace produced by the same run.

Harness-owned, eval-time path (T0011.4) — deliberately separate from
`src/agents/tracing/langfuse.py`, whose accessors this module only reuses.
Never touches the request-path tracing handler.
"""

from __future__ import annotations

from src.agents.tracing.langfuse import get_langfuse_client, get_langfuse_handler
from src.core.logger import logger


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
