"""Extract raw book fields from a product detail page."""

from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup

RATING_MAP = {
    "One": "One",
    "Two": "Two",
    "Three": "Three",
    "Four": "Four",
    "Five": "Five",
}


def extract_rating(soup: BeautifulSoup) -> str:
    p = soup.select_one("p.star-rating")
    if not p:
        return ""
    for cls in p.get("class", []):
        if cls != "star-rating" and cls in RATING_MAP:
            return RATING_MAP[cls]
    return ""


def extract_raw_book(
    html: str,
    product_url: str,
    source_page: str,
    fetched_at: str,
) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    product = soup.select_one("div.product_main") or soup

    title_el = product.select_one("h1")
    title = title_el.get_text(strip=True) if title_el else ""

    price_el = product.select_one("p.price_color")
    price_text = price_el.get_text(strip=True) if price_el else ""
    price_text = price_text.replace("Â£", "£")

    avail_el = product.select_one("p.availability")
    availability_text = (
        " ".join(avail_el.get_text(strip=True).split()) if avail_el else ""
    )

    rating_text = extract_rating(product) or extract_rating(soup)

    description: str | None = None
    desc_header = soup.select_one("#product_description")
    if desc_header:
        sibling = desc_header.find_next_sibling("p")
        if sibling:
            text = sibling.get_text(strip=True)
            description = text if text else None

    return {
        "title": title,
        "product_url": product_url,
        "price_text": price_text,
        "availability_text": availability_text,
        "rating_text": rating_text,
        "description": description,
        "source_page": source_page,
        "fetched_at": fetched_at,
    }
