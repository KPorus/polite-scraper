#!/usr/bin/env python3
"""Stage 0: prove one call to the local Ollama model works."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def main() -> None:
    base_url = os.environ["LLM_BASE_URL"]
    api_key = os.environ["LLM_API_KEY"]
    model = os.environ["LLM_MODEL"]

    client = OpenAI(base_url=base_url, api_key=api_key)
    res = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Reply with exactly the word: ready"}],
    )
    text = res.choices[0].message.content or ""
    print(text)
    if "ready" not in text.lower():
        sys.exit(1)


if __name__ == "__main__":
    main()
