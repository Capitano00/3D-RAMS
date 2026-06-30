from __future__ import annotations

import json
import logging
import time
from typing import Any


logger = logging.getLogger("3d-rams")
logger.setLevel(logging.INFO)


def log_event(event: str, **fields: Any) -> None:
    safe_fields = {
        key: value
        for key, value in fields.items()
        if key not in {"accessCode", "prompt", "message", "uploadUrl", "rawText"}
    }
    logger.info(json.dumps({"event": event, **safe_fields}, default=str, separators=(",", ":")))


def now_ms() -> int:
    return int(time.time() * 1000)
