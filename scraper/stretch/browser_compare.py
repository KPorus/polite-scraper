#!/usr/bin/env python3
"""Stretch: compare plain HTTP vs Playwright on a JS-rendered sandbox page."""

from __future__ import annotations

import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

QUOTE_JS_URL = "https://quotes.toscrape.com/js"
USER_AGENT = (
    "FlyRankInternship-A9/1.0 "
    "(+https://github.com/KPorus/polite-scraper)"
)
QUOTE_SELECTOR = ".quote"


def rss_mb() -> float:
    """Current process RSS in MiB (best-effort)."""
    try:
        import psutil

        return psutil.Process().memory_info().rss / (1024 * 1024)
    except Exception:
        pass
    try:
        status = Path("/proc/self/status").read_text(encoding="utf-8")
        for line in status.splitlines():
            if line.startswith("VmRSS:"):
                # kB
                kb = int(line.split()[1])
                return kb / 1024
    except Exception:
        pass
    return -1.0


def count_quotes_http() -> tuple[int, float, float]:
    headers = {"User-Agent": USER_AGENT}
    before = rss_mb()
    t0 = time.perf_counter()
    resp = requests.get(QUOTE_JS_URL, headers=headers, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    count = len(soup.select(QUOTE_SELECTOR))
    elapsed = time.perf_counter() - t0
    after = rss_mb()
    mem = max(before, after) if before >= 0 and after >= 0 else after
    return count, elapsed, mem


def count_quotes_playwright() -> tuple[int, float, float]:
    from playwright.sync_api import sync_playwright

    before = rss_mb()
    t0 = time.perf_counter()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=USER_AGENT)
        page.goto(QUOTE_JS_URL, wait_until="networkidle", timeout=30_000)
        page.wait_for_selector(QUOTE_SELECTOR, timeout=15_000)
        count = page.locator(QUOTE_SELECTOR).count()
        browser.close()
    elapsed = time.perf_counter() - t0
    after = rss_mb()
    mem = max(before, after) if before >= 0 and after >= 0 else after
    return count, elapsed, mem


def main() -> int:
    http_count, http_s, http_mb = count_quotes_http()
    print(
        f"HTTP       quotes={http_count}  time_s={http_s:.3f}  rss_mib={http_mb:.1f}"
    )

    try:
        pw_count, pw_s, pw_mb = count_quotes_playwright()
    except Exception as exc:
        print(f"PLAYWRIGHT failed: {exc}")
        print(
            "Install with: pip install playwright && playwright install chromium"
        )
        return 1

    print(
        f"PLAYWRIGHT quotes={pw_count}  time_s={pw_s:.3f}  rss_mib={pw_mb:.1f}"
    )
    print(
        f"SUMMARY http_quotes={http_count} playwright_quotes={pw_count} "
        f"http_s={http_s:.3f} playwright_s={pw_s:.3f} "
        f"http_mib={http_mb:.1f} playwright_mib={pw_mb:.1f}"
    )
    print(
        "Conclusion: quotes are injected by JS, so plain HTTP sees none; "
        "Books to Scrape needs no browser because its data is already in the HTML."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
