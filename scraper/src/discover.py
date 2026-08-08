"""Catalogue discovery: follow 'next' across N pages and collect absolute book URLs."""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from config import CATALOGUE_PAGES_LIMIT, CATALOGUE_START
from fetch import catalogue_cache_path, fetch_with_retry


def parse_book_links(html: str, page_url: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    links: list[str] = []
    for a in soup.select("article.product_pod h3 a"):
        href = a.get("href")
        if not href:
            continue
        links.append(urljoin(page_url, href))
    return links


def find_next_catalogue_url(html: str, page_url: str) -> str | None:
    soup = BeautifulSoup(html, "lxml")
    next_a = soup.select_one("li.next a")
    if not next_a or not next_a.get("href"):
        return None
    return urljoin(page_url, next_a["href"])


def discover_catalogue(
    session: requests.Session,
    stats: dict[str, Any],
) -> tuple[list[str], dict[str, str]]:
    """Return (unique book urls, book_url -> catalogue source page url)."""
    book_urls: list[str] = []
    source_by_book: dict[str, str] = {}
    page_url = CATALOGUE_START
    pages = 0

    while pages < CATALOGUE_PAGES_LIMIT and page_url:
        pages += 1
        cache_file = catalogue_cache_path(pages)
        html = fetch_with_retry(
            session, page_url, cache_file=cache_file, stats=stats
        )
        links = parse_book_links(html, page_url)
        for link in links:
            if link not in source_by_book:
                book_urls.append(link)
                source_by_book[link] = page_url
        next_url = find_next_catalogue_url(html, page_url)
        page_url = next_url if pages < CATALOGUE_PAGES_LIMIT else None

    unique: list[str] = list(dict.fromkeys(book_urls))
    print(
        f"catalogue_pages={pages}  discovered={len(book_urls)}  "
        f"unique_urls={len(unique)}"
    )
    return unique, source_by_book
