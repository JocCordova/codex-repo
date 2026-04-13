from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def append_feedback(storage_path: str, payload: dict[str, Any]) -> None:
    """Scaffold for weekly tuning: append human feedback events to JSONL."""
    path = Path(storage_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"ts": datetime.utcnow().isoformat() + "Z", **payload}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    logger.info("Stored feedback event")


def maybe_run_weekly_update(feedback_cfg: dict[str, Any]) -> None:
    """Placeholder extension point for recalibrating topic weights weekly."""
    if not feedback_cfg.get("enabled", False) or not feedback_cfg.get("weekly_update_enabled", False):
        return
    logger.info("Weekly feedback update is enabled, but v1 keeps deterministic static scoring")
