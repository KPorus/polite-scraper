"""Postgres title search against the scraper's books table."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

DEFAULT_DATABASE_URL = "postgresql://scraper:scraper@localhost:5432/books"


def database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


SEARCH_SQL = """
SELECT
    product_url,
    title,
    price_text,
    price_gbp,
    availability_text,
    rating_text,
    description,
    source_page,
    fetched_at
FROM books
WHERE title ILIKE %(pattern)s
ORDER BY
    CASE WHEN lower(title) = lower(%(exact)s) THEN 0 ELSE 1 END,
    length(title) ASC,
    title ASC
LIMIT 1
"""


def find_book_by_query(query: str, *, dsn: str | None = None) -> dict[str, Any] | None:
    """Return the best matching book row, or None."""
    url = dsn or database_url()
    pattern = f"%{query}%"
    with psycopg.connect(url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(SEARCH_SQL, {"pattern": pattern, "exact": query})
            row = cur.fetchone()
    if row is None:
        return None
    # Normalize types for JSON
    out = dict(row)
    if out.get("price_gbp") is not None:
        out["price_gbp"] = float(out["price_gbp"])
    if out.get("fetched_at") is not None:
        out["fetched_at"] = out["fetched_at"].isoformat()
    if out.get("product_url") is not None:
        out["product_url"] = str(out["product_url"])
    return out
