"""Polite HTTP fetch with disk cache, timeout, status checks, and one retry."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from config import (
    CACHE_DIR,
    MIN_DELAY_S,
    REQUEST_TIMEOUT_S,
)


class HTTPStatusError(Exception):
    def __init__(self, status: int, url: str) -> None:
        self.status = status
        self.url = url
        super().__init__(f"HTTP {status} for {url}")


def catalogue_cache_path(page_num: int) -> Path:
    return CACHE_DIR / f"catalogue-page-{page_num}.html"


def detail_cache_path(product_url: str) -> Path:
    parsed = urlparse(product_url)
    parts = [p for p in parsed.path.split("/") if p]
    name = "__".join(parts) if parts else "book.html"
    return CACHE_DIR / f"book__{name}"


def polite_get(
    session: requests.Session,
    url: str,
    *,
    cache_file: Path,
    stats: dict[str, Any],
) -> tuple[str, int | None]:
    """Return (html, status_or_None). Uses disk cache when present."""
    if cache_file.exists():
        html = cache_file.read_text(encoding="utf-8", errors="replace")
        html = html.replace("Â£", "£")
        stats["cache_hits"] = stats.get("cache_hits", 0) + 1
        print(f"CACHE HIT  {cache_file.name}  size={len(html)} bytes")
        return html, None

    time.sleep(MIN_DELAY_S)
    stats["pages_fetched"] = stats.get("pages_fetched", 0) + 1
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT_S)
    except requests.Timeout:
        raise
    except requests.RequestException as exc:
        raise RuntimeError(f"request failed for {url}: {exc}") from exc

    status = resp.status_code
    if status != 200:
        raise HTTPStatusError(status, url)

    resp.encoding = resp.apparent_encoding or "utf-8"
    if "£" not in resp.text and "Â£" in resp.text:
        try:
            html = resp.content.decode("utf-8")
        except UnicodeDecodeError:
            html = resp.text
    else:
        html = resp.text.replace("Â£", "£")

    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(html, encoding="utf-8")
    print(
        f"FETCH      {url}  status={status}  size={len(html)} bytes → {cache_file.name}"
    )
    return html, status


def fetch_with_retry(
    session: requests.Session,
    url: str,
    *,
    cache_file: Path,
    stats: dict[str, Any],
) -> str:
    """Fetch once; retry once on timeout or 5xx. Do not retry 403/404."""
    try:
        html, _ = polite_get(session, url, cache_file=cache_file, stats=stats)
        return html
    except requests.Timeout:
        print(f"RETRY      timeout on {url}")
        time.sleep(1.0)
        html, _ = polite_get(session, url, cache_file=cache_file, stats=stats)
        return html
    except HTTPStatusError as exc:
        if 500 <= exc.status <= 599:
            print(f"RETRY      HTTP {exc.status} on {url}")
            time.sleep(1.0)
            if cache_file.exists():
                cache_file.unlink()
            html, _ = polite_get(session, url, cache_file=cache_file, stats=stats)
            return html
        raise
