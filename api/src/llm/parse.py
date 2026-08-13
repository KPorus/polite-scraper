"""Parse, validate, one repair retry, and quarantine on failure."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from src.llm.schema import LlmEnrichment

ROOT = Path(__file__).resolve().parents[2]
QUARANTINE_PATH = ROOT / "logs" / "quarantine.jsonl"


def extract_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    fence = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", cleaned, re.IGNORECASE)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no JSON object found in model output")
    data = json.loads(cleaned[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("model output JSON is not an object")
    return data


def parse_and_validate(text: str) -> LlmEnrichment:
    data = extract_json_object(text)
    return LlmEnrichment.model_validate(data)


def quarantine(
    *,
    input_payload: dict[str, Any],
    raw_output: str,
    error: str,
    prompt_version: str,
) -> None:
    QUARANTINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "prompt_version": prompt_version,
        "input": input_payload,
        "raw_output": raw_output,
        "error": error,
    }
    with QUARANTINE_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")


def validation_error_text(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        return exc.json()
    return str(exc)
