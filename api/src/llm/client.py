"""LLM client helpers — stub mode for Stage 1; real calls wired in later stages."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

PROMPT_VERSION = "enrich-v1"


def env_flag(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def llm_stub_enabled() -> bool:
    return env_flag("LLM_STUB", "0")


def llm_enabled() -> bool:
    return env_flag("LLM_ENABLED", "true")
