#!/usr/bin/env python3
"""FlyRank Internship A9 — polite scraper for Books to Scrape (sandbox)."""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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
from db import upsert_books


def ensure_dirs() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def process_detail_page(
    product_url: str,
    source_page: str,
    stats: dict[str, Any],
) -> tuple[str, dict[str, Any] | None, dict[str, Any] | None, Exception | None]:
    """
    Fetch → extract → normalize → validate one book URL.

    Returns (product_url, book_or_None, error_or_None, fail_exc_or_None).
    Each worker uses its own Session (requests.Session is not thread-safe).
    """
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    try:
        cache_file = detail_cache_path(product_url)
        html = fetch_with_retry(
            session, product_url, cache_file=cache_file, stats=stats
        )
        fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        raw = extract_raw_book(
            html,
            product_url=product_url,
            source_page=source_page,
            fetched_at=fetched_at,
        )
        normalized = normalize_record(raw)
        try:
            record = BookRecord.model_validate(normalized)
        except ValidationError as ve:
            return (
                product_url,
                None,
                {
                    "product_url": product_url,
                    "reason": ve.errors(),
                    "raw": normalized,
                },
                None,
            )
        return product_url, json.loads(record.model_dump_json()), None, None
    except Exception as exc:
        return product_url, None, None, exc


def run(workers: int = 3, *, skip_db: bool = False) -> int:
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
        "workers": workers,
    }

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    book_urls, source_by_book = discover_catalogue(session, stats)

    # Stage 5: inject one made-up URL so failure handling is proven locally.
    urls_to_fetch = list(book_urls) + [FAKE_BOOK_URL]
    source_by_book[FAKE_BOOK_URL] = CATALOGUE_START

    books_by_url: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, Any]] = []
    result_lock = threading.Lock()
    printed_sample = False

    print(f"detail_workers={workers}")

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = [
            pool.submit(
                process_detail_page,
                url,
                source_by_book.get(url, CATALOGUE_START),
                stats,
            )
            for url in urls_to_fetch
        ]
        for fut in as_completed(futures):
            product_url, book, err, fail_exc = fut.result()
            with result_lock:
                if fail_exc is not None:
                    stats["failed_pages"] += 1
                    stats["failed_urls"].append(
                        {"url": product_url, "error": str(fail_exc)}
                    )
                    print(f"SKIP       {product_url}  ({fail_exc})")
                    continue
                if err is not None:
                    stats["invalid_records"] += 1
                    errors.append(err)
                    continue
                if book is not None:
                    if not printed_sample:
                        # Reconstruct a raw-ish sample for the checkpoint.
                        sample = {
                            k: book[k]
                            for k in (
                                "title",
                                "product_url",
                                "price_text",
                                "availability_text",
                                "rating_text",
                                "description",
                                "source_page",
                                "fetched_at",
                            )
                        }
                        print("sample_raw_record=")
                        print(json.dumps(sample, indent=2, ensure_ascii=False))
                        printed_sample = True
                    # Idempotent: canonical product_url overwrites, never duplicates.
                    books_by_url[str(book["product_url"])] = book

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

    db_upserted = 0
    if not skip_db:
        try:
            db_upserted = upsert_books(books)
            print(f"DB upserted={db_upserted} → PostgreSQL")
        except Exception as exc:
            print(f"DB upsert failed: {exc}", file=sys.stderr)
            # JSON already written; fail the run so broken storage is noticed.
            duration_s = round(time.perf_counter() - t0, 3)
            report = {
                "started_at": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "duration_seconds": duration_s,
                "catalogue_pages": CATALOGUE_PAGES_LIMIT,
                "discovered_urls": len(book_urls),
                "unique_urls": len(book_urls),
                "workers": workers,
                "pages_fetched": stats["pages_fetched"],
                "cache_hits": stats["cache_hits"],
                "valid_records": stats["valid_records"],
                "invalid_records": stats["invalid_records"],
                "failed_pages": stats["failed_pages"],
                "failed_urls": stats["failed_urls"],
                "db_upserted": 0,
                "db_error": str(exc),
                "output": {
                    "books": str(books_path.relative_to(ROOT)),
                    "errors": str(errors_path.relative_to(ROOT)),
                },
            }
            report_path.write_text(
                json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            return 1

    duration_s = round(time.perf_counter() - t0, 3)
    report = {
        "started_at": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duration_seconds": duration_s,
        "catalogue_pages": CATALOGUE_PAGES_LIMIT,
        "discovered_urls": len(book_urls),
        "unique_urls": len(book_urls),
        "workers": workers,
        "pages_fetched": stats["pages_fetched"],
        "cache_hits": stats["cache_hits"],
        "valid_records": stats["valid_records"],
        "invalid_records": stats["invalid_records"],
        "failed_pages": stats["failed_pages"],
        "failed_urls": stats["failed_urls"],
        "db_upserted": db_upserted if not skip_db else None,
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
        f"failed_pages={stats['failed_pages']} workers={workers} "
        f"db_upserted={db_upserted if not skip_db else 'skipped'} duration_s={duration_s}"
    )
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Polite Books to Scrape pipeline")
    parser.add_argument(
        "--workers",
        type=int,
        default=3,
        help="ThreadPool workers for detail pages (default 3; use 1 for serial)",
    )
    parser.add_argument(
        "--skip-db",
        action="store_true",
        help="Write JSON only; do not upsert into PostgreSQL",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    try:
        args = parse_args()
        raise SystemExit(
            run(workers=max(1, args.workers), skip_db=args.skip_db)
        )
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        raise SystemExit(130)
