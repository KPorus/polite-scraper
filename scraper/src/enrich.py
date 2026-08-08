#!/usr/bin/env python3
"""Stretch: local Ollama enrichment — AI opinions stay separate from scraped facts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import requests
from pydantic import BaseModel, ValidationError

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"
DEFAULT_BOOKS = OUTPUT_DIR / "books.json"
DEFAULT_OUT = OUTPUT_DIR / "enrichment.json"
OLLAMA_URL = "http://localhost:11434/api/chat"
DEFAULT_MODEL = "llama3.2"


class Enrichment(BaseModel):
    category: str
    summary: str


def build_prompt(title: str, description: str | None) -> str:
    desc = description or "(no description)"
    return (
        "You classify bookstore catalogue entries. "
        "Respond with JSON only, keys: category (short genre label), "
        "summary (one or two sentences).\n\n"
        f"Title: {title}\n"
        f"Description: {desc}\n"
    )


def call_ollama(title: str, description: str | None, *, model: str) -> Enrichment:
    payload = {
        "model": model,
        "stream": False,
        "format": "json",
        "messages": [
            {
                "role": "user",
                "content": build_prompt(title, description),
            }
        ],
    }
    resp = requests.post(OLLAMA_URL, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    content = data.get("message", {}).get("content", "")
    parsed = json.loads(content)
    return Enrichment.model_validate(parsed)


def enrich_books(
    books: list[dict[str, Any]],
    *,
    model: str,
    limit: int | None,
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    selected = books if limit is None else books[:limit]
    for book in selected:
        url = book.get("product_url")
        if not url:
            continue
        try:
            enrichment = call_ollama(
                book.get("title") or "",
                book.get("description"),
                model=model,
            )
            out[url] = enrichment.model_dump()
            print(f"ENRICHED   {url}")
        except (requests.RequestException, json.JSONDecodeError, ValidationError, KeyError) as exc:
            print(f"SKIP_AI    {url}  ({exc})")
            continue
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ollama enrichment for books.json")
    parser.add_argument("--books", type=Path, default=DEFAULT_BOOKS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional max books to enrich (for a quick demo)",
    )
    args = parser.parse_args(argv)

    if not args.books.exists():
        print(f"missing books file: {args.books}", file=sys.stderr)
        return 1

    books = json.loads(args.books.read_text(encoding="utf-8"))
    if not isinstance(books, list):
        print("books.json must be a list", file=sys.stderr)
        return 1

    try:
        requests.get("http://localhost:11434/api/tags", timeout=3).raise_for_status()
    except requests.RequestException as exc:
        print(
            f"Ollama not reachable at localhost:11434 ({exc}). "
            "Start Ollama and pull a model, then re-run.",
            file=sys.stderr,
        )
        return 2

    enrichment = enrich_books(books, model=args.model, limit=args.limit)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(enrichment, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(enrichment)} enrichments → {args.out}")
    print("Note: scraped books.json is unchanged; enrichment is AI opinion only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
