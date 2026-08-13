"""LLM client — timeout, selective retries, stub, kill switch."""

from __future__ import annotations

import os
import random
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI, RateLimitError

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

PROMPT_VERSION = "enrich-v1"
PROMPT_PATH = ROOT / "prompts" / f"{PROMPT_VERSION}.md"
# Assignment: explicit timeout ≤ 60s (SDK default is ~10 minutes).
CLIENT_TIMEOUT_S = 60.0
MAX_RETRIES = 2  # additional attempts after the first (timeouts / 429 / 5xx only)


def env_flag(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def llm_stub_enabled() -> bool:
    return env_flag("LLM_STUB", "0")


def llm_enabled() -> bool:
    return env_flag("LLM_ENABLED", "true")


def load_system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def get_client() -> OpenAI:
    # max_retries=0: we own retry policy so a 401 never burns extra calls.
    return OpenAI(
        base_url=os.environ["LLM_BASE_URL"],
        api_key=os.environ["LLM_API_KEY"],
        timeout=CLIENT_TIMEOUT_S,
        max_retries=0,
    )


def _should_retry(exc: Exception) -> bool:
    if isinstance(exc, (APITimeoutError, APIConnectionError, RateLimitError)):
        return True
    if isinstance(exc, APIStatusError):
        code = exc.status_code
        if code == 429 or code >= 500:
            return True
        # Never retry 400 / 401 / 403
        return False
    return False


def _backoff_seconds(attempt: int, exc: Exception) -> float:
    if isinstance(exc, APIStatusError):
        ra = exc.response.headers.get("retry-after") if exc.response is not None else None
        if ra:
            try:
                return float(ra)
            except ValueError:
                pass
    base = 2**attempt  # 1, 2, 4…
    return base + random.uniform(0, 0.25)


def chat_completion(
    *,
    system: str,
    user: str,
    messages: list[dict[str, str]] | None = None,
) -> tuple[str, dict[str, Any]]:
    """
    Call the model with timeout + selective retries.
    Returns (text, meta) where meta has model, usage, duration_ms, attempts.
    """
    client = get_client()
    model = os.environ["LLM_MODEL"]
    if messages is None:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    last_exc: Exception | None = None
    attempts = 0
    t0 = time.perf_counter()
    for attempt in range(MAX_RETRIES + 1):
        attempts = attempt + 1
        try:
            res = client.chat.completions.create(
                model=model,
                temperature=0.2,
                max_tokens=120,
                response_format={"type": "json_object"},
                messages=messages,
            )
            text = (res.choices[0].message.content or "").strip()
            usage = res.usage
            meta = {
                "model": model,
                "input_tokens": getattr(usage, "prompt_tokens", None) if usage else None,
                "output_tokens": getattr(usage, "completion_tokens", None) if usage else None,
                "duration_ms": int((time.perf_counter() - t0) * 1000),
                "attempts": attempts,
            }
            return text, meta
        except Exception as exc:
            last_exc = exc
            if attempt >= MAX_RETRIES or not _should_retry(exc):
                raise
            time.sleep(_backoff_seconds(attempt, exc))
    assert last_exc is not None
    raise last_exc
