"""Structured cost / latency log for each model call."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any


def log_cost(
    *,
    prompt_version: str,
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
    duration_ms: int,
    repair_count: int,
    extra: dict[str, Any] | None = None,
) -> None:
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": "llm_cost",
        "prompt_version": prompt_version,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "duration_ms": duration_ms,
        "repair_count": repair_count,
    }
    if extra:
        row.update(extra)
    print(json.dumps(row, ensure_ascii=False), file=sys.stderr, flush=True)
