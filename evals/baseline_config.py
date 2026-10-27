"""Read and validate the baseline run controls from ``config/settings.yaml``.

The repeat counts live in configuration because they change the evidence a run
collects. They are read by the generators and recorded in the run lineage, not
consulted again while scoring: a committed run has to re-score with the repeat
count it actually ran, even after the setting moves.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

SETTINGS_PATH = Path(__file__).resolve().parents[1] / "config" / "settings.yaml"


class BaselineConfigError(ValueError):
    """The ``eval.baseline`` section is missing or malformed."""


@dataclass(frozen=True)
class BaselineSettings:
    layer1_repeats: int
    agent_repeats: int
    agent_max_rows: int


def _positive_int(value: Any, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise BaselineConfigError(
            f"{name} must be a positive integer in config/settings.yaml"
        )
    return value


def load_baseline_settings(path: Path = SETTINGS_PATH) -> BaselineSettings:
    """Return the validated baseline repeats, refusing anything a run cannot use."""
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except OSError as exc:
        raise BaselineConfigError(f"cannot read {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise BaselineConfigError(f"invalid YAML in {path}: {exc}") from exc

    eval_cfg = payload.get("eval") if isinstance(payload, dict) else None
    baseline_cfg = eval_cfg.get("baseline") if isinstance(eval_cfg, dict) else None
    if not isinstance(baseline_cfg, dict):
        raise BaselineConfigError(
            "missing 'eval.baseline' section in config/settings.yaml"
        )
    agent_cfg = payload.get("agent") if isinstance(payload, dict) else None
    query_cfg = agent_cfg.get("query") if isinstance(agent_cfg, dict) else None
    max_rows = query_cfg.get("max_rows") if isinstance(query_cfg, dict) else None
    return BaselineSettings(
        layer1_repeats=_positive_int(
            baseline_cfg.get("layer1_repeats"), name="eval.baseline.layer1_repeats"
        ),
        agent_repeats=_positive_int(
            baseline_cfg.get("agent_repeats"), name="eval.baseline.agent_repeats"
        ),
        agent_max_rows=_positive_int(max_rows, name="agent.query.max_rows"),
    )
