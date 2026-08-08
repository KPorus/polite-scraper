#!/usr/bin/env python3
"""FlyRank Internship A9 — polite scraper for Books to Scrape (sandbox)."""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from typing import Any

import requests
from pydantic import ValidationError

from config import (
    CATALOGUE_PAGES_LIMIT,
    CATALOGUE_START,
    FAKE_BOOK_URL,
    OUTPUT_DIR,
    ROOT,
    USER_AGENT,
    CACHE_DIR,
)
from discover import discover_catalogue
from extract import extract_raw_book
from fetch import detail_cache_path, fetch_with_retry
from models import BookRecord, normalize_record


def ensure_dirs() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def run() -> int:
    ensure_dirs()
    started = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    stats: dict[str, Any] = {
        "pages_fetched": 0,
        "cache_hits": 0,
        "valid_records": 0,
        "invalid_records": 0,
        "failed_pages": 0,
        "failed_urls": [],
    }

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    book_urls, source_by_book = discover_catalogue(session, stats)

    # Stage 5: inject one made-up URL so failure handling is proven locally.
    urls_to_fetch = list(book_urls) + [FAKE_BOOK_URL]
    source_by_book[FAKE_BOOK_URL] = CATALOGUE_START

    books_by_url: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, Any]] = []
    printed_sample = False

    for product_url in urls_to_fetch:
        try:
            cache_file = detail_cache_path(product_url)
            html = fetch_with_retry(
                session, product_url, cache_file=cache_file, stats=stats
            )
            fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            raw = extract_raw_book(
                html,
                product_url=product_url,
                source_page=source_by_book.get(product_url, CATALOGUE_START),
                fetched_at=fetched_at,
            )
            if not printed_sample:
                print("sample_raw_record=")
                print(json.dumps(raw, indent=2, ensure_ascii=False))
                printed_sample = True

            normalized = normalize_record(raw)
            try:
                record = BookRecord.model_validate(normalized)
            except ValidationError as ve:
                stats["invalid_records"] += 1
                errors.append(
                    {
                        "product_url": product_url,
                        "reason": ve.errors(),
                        "raw": normalized,
                    }
                )
                continue

            key = str(record.product_url)
            books_by_url[key] = json.loads(record.model_dump_json())
        except Exception as exc:
            stats["failed_pages"] += 1
            stats["failed_urls"].append({"url": product_url, "error": str(exc)})
            print(f"SKIP       {product_url}  ({exc})")
            continue

    books = list(books_by_url.values())
    stats["valid_records"] = len(books)
    print(f"detail_pages={len(book_urls)}  stored={len(books)}")

    books_path = OUTPUT_DIR / "books.json"
    errors_path = OUTPUT_DIR / "errors.json"
    report_path = OUTPUT_DIR / "run-report.json"

    books_path.write_text(
        json.dumps(books, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    errors_path.write_text(
        json.dumps(errors, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    duration_s = round(time.perf_counter() - t0, 3)
    report = {
        "started_at": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duration_seconds": duration_s,
        "catalogue_pages": CATALOGUE_PAGES_LIMIT,
        "discovered_urls": len(book_urls),
        "unique_urls": len(book_urls),
        "pages_fetched": stats["pages_fetched"],
        "cache_hits": stats["cache_hits"],
        "valid_records": stats["valid_records"],
        "invalid_records": stats["invalid_records"],
        "failed_pages": stats["failed_pages"],
        "failed_urls": stats["failed_urls"],
        "output": {
            "books": str(books_path.relative_to(ROOT)),
            "errors": str(errors_path.relative_to(ROOT)),
        },
    }
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"run-report → {report_path}")
    print(
        f"summary valid={stats['valid_records']} invalid={stats['invalid_records']} "
        f"failed_pages={stats['failed_pages']} duration_s={duration_s}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        raise SystemExit(130)
