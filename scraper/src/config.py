"""Shared paths and politeness settings for the Books to Scrape pipeline."""

from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "cache"
OUTPUT_DIR = ROOT / "output"

BASE_URL = "https://books.toscrape.com/"
CATALOGUE_START = urljoin(BASE_URL, "index.html")
CATALOGUE_PAGES_LIMIT = 3
REQUEST_TIMEOUT_S = 10
MIN_DELAY_S = 0.5
USER_AGENT = (
    "FlyRankInternship-A9/1.0 "
    "(+https://github.com/flyrank-internship/polite-scraper)"
)

# Intentionally broken URL (Stage 5) — never hammer the live site to test failure.
FAKE_BOOK_URL = (
    "https://books.toscrape.com/catalogue/this-book-does-not-exist-zzzz_0/index.html"
)
