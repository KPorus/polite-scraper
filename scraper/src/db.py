"""PostgreSQL upsert for validated book records."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

# Load scraper/.env if present (simple KEY=VALUE, no export required).
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def _load_dotenv(path: Path = _ENV_PATH) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        os.environ.setdefault(key, value)


_load_dotenv()

DEFAULT_DATABASE_URL = "postgresql://scraper:scraper@localhost:5432/books"

UPSERT_SQL = """
INSERT INTO books (
    product_url,
    title,
    price_text,
    price_gbp,
    availability_text,
    rating_text,
    description,
    source_page,
    fetched_at,
    updated_at
) VALUES (
    %(product_url)s,
    %(title)s,
    %(price_text)s,
    %(price_gbp)s,
    %(availability_text)s,
    %(rating_text)s,
    %(description)s,
    %(source_page)s,
    %(fetched_at)s,
    %(updated_at)s
)
ON CONFLICT (product_url) DO UPDATE SET
    title = EXCLUDED.title,
    price_text = EXCLUDED.price_text,
    price_gbp = EXCLUDED.price_gbp,
    availability_text = EXCLUDED.availability_text,
    rating_text = EXCLUDED.rating_text,
    description = EXCLUDED.description,
    source_page = EXCLUDED.source_page,
    fetched_at = EXCLUDED.fetched_at,
    updated_at = EXCLUDED.updated_at
"""


def database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def _parse_fetched_at(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _row_params(book: dict[str, Any]) -> dict[str, Any]:
    return {
        "product_url": str(book["product_url"]),
        "title": book["title"],
        "price_text": book["price_text"],
        "price_gbp": book["price_gbp"],
        "availability_text": book["availability_text"],
        "rating_text": book["rating_text"],
        "description": book.get("description"),
        "source_page": str(book["source_page"]),
        "fetched_at": _parse_fetched_at(book["fetched_at"]),
        "updated_at": datetime.now(timezone.utc),
    }


def upsert_books(books: list[dict[str, Any]], *, dsn: str | None = None) -> int:
    """Upsert books by product_url. Returns number of rows written."""
    if not books:
        return 0
    url = dsn or database_url()
    rows = [_row_params(b) for b in books]
    with psycopg.connect(url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS books (
                    product_url       TEXT PRIMARY KEY,
                    title             TEXT NOT NULL,
                    price_text        TEXT NOT NULL,
                    price_gbp         NUMERIC(10, 2) NOT NULL,
                    availability_text TEXT NOT NULL,
                    rating_text       TEXT NOT NULL,
                    description       TEXT,
                    source_page       TEXT NOT NULL,
                    fetched_at        TIMESTAMPTZ NOT NULL,
                    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS books_title_idx ON books (title)"
            )
            cur.executemany(UPSERT_SQL, rows)
        conn.commit()
    return len(rows)
