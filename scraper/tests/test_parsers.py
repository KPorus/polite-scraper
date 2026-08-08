"""Offline parser / normalize / idempotency tests (Stretch)."""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from extract import extract_raw_book  # noqa: E402
from models import BookRecord, normalize_price_gbp, normalize_record  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_normalize_price_gbp():
    assert normalize_price_gbp("£51.77") == 51.77
    assert normalize_price_gbp("Â£51.77") == 51.77
    assert normalize_price_gbp("  £1,234.50 ") == 1234.5


def test_relative_to_absolute_url():
    page_url = "https://books.toscrape.com/catalogue/page-2.html"
    href = "a-light-in-the-attic_1000/index.html"
    absolute = urljoin(page_url, href)
    assert absolute == (
        "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"
    )


def test_missing_description_is_none():
    html = (FIXTURES / "missing_description.html").read_text(encoding="utf-8")
    raw = extract_raw_book(
        html,
        product_url="https://books.toscrape.com/catalogue/no-desc_1/index.html",
        source_page="https://books.toscrape.com/catalogue/page-1.html",
        fetched_at="2026-08-08T00:00:00Z",
    )
    assert raw["description"] is None
    assert raw["title"] == "No Description Book"
    record = BookRecord.model_validate(normalize_record(raw))
    assert record.description is None


def test_duplicate_urls_dedupe_by_product_url():
    book = {
        "title": "Same",
        "product_url": "https://books.toscrape.com/catalogue/same_1/index.html",
        "price_text": "£10.00",
        "price_gbp": 10.0,
        "availability_text": "In stock",
        "rating_text": "One",
        "description": None,
        "source_page": "https://books.toscrape.com/index.html",
        "fetched_at": "2026-08-08T00:00:00Z",
    }
    books_by_url: dict[str, dict] = {}
    for _ in range(2):
        record = BookRecord.model_validate(book)
        key = str(record.product_url)
        books_by_url[key] = record.model_dump(mode="json")
    assert len(books_by_url) == 1


def test_malformed_price_fails_validation():
    html = (FIXTURES / "malformed_price.html").read_text(encoding="utf-8")
    raw = extract_raw_book(
        html,
        product_url="https://books.toscrape.com/catalogue/broken_1/index.html",
        source_page="https://books.toscrape.com/catalogue/page-1.html",
        fetched_at="2026-08-08T00:00:00Z",
    )
    with pytest.raises(ValueError, match="cannot parse price"):
        normalize_record(raw)
