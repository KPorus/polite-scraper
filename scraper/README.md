# The polite scraper

Python scraper for the public **Books to Scrape** practice sandbox. It fetches the first three catalogue pages, visits 60 book detail pages, normalizes and schema-validates records, skips broken pages, and writes an honest run report.

## Target classification

| | |
|---|---|
| **Site** | [Books to Scrape](https://books.toscrape.com/) (`books.toscrape.com`) |
| **Why** | [toscrape.com](https://toscrape.com/) describes it as a fictional bookstore that *desperately wants to be scraped* — a sandbox for learning and validating scrapers. |
| **How much** | First **3** catalogue pages only → **60** book detail pages |
| **What data** | Title, product URL, price (raw + numeric GBP), availability, star rating text, description (nullable), provenance (`source_page`, `fetched_at`) |
| **Appropriate?** | Yes: the operator built this site for practice scraping; we collect only catalogue product fields within the stated three-page scope. |

**robots.txt check** (requested once for this classification): `GET https://books.toscrape.com/robots.txt` returned **HTTP 404**. Per the assignment: **no robots file found**. A missing file is not permission — it is just a missing file. Permission here comes from the sandbox’s own statement that the site is for practising scraping.

> I will not reuse this code on another site without checking its rules and terms first.

## Lane

Python 3.10+ · Requests · Beautiful Soup · Pydantic · stdlib `json`

## Install

```bash
cd scraper
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
cd scraper
python src/main.py              # default: 3 detail workers
python src/main.py --workers 1  # serial detail fetch
```

First run hits the network (with delays). Later runs mostly print `CACHE HIT` and read `cache/`.

Outputs:

- `output/books.json` — validated unique records (expect 60)
- `output/errors.json` — schema failures with reasons
- `output/run-report.json` — counts, failures, cache hits, duration
- `output/enrichment.json` — optional Ollama opinions (separate from scraped facts)

## Record schema

```json
{
  "title": "string",
  "product_url": "https://...",
  "price_text": "£51.77",
  "price_gbp": 51.77,
  "availability_text": "In stock (22 available)",
  "rating_text": "Three",
  "description": "string or null",
  "source_page": "https://...",
  "fetched_at": "2026-08-08T00:00:00Z"
}
```

Identity / idempotency key: absolute `product_url`. Reruns update the same 60 records; they do not grow to 120.

## Politeness rules

- **User-Agent:** `FlyRankInternship-A9/1.0 (+https://github.com/flyrank-internship/polite-scraper)` — honest name + contact link
- **Timeout:** 10 seconds per request
- **Delay:** at least 500 ms between real network requests (cache hits do not wait)
- **Status check:** only HTTP 200 is treated as HTML to parse
- **Cache:** HTML saved under `cache/` (gitignored) so development does not re-hammer the site
- **Retries:** one retry on timeout or 5xx; never retry 403 or 404
- **Failure isolation:** one broken URL is logged and skipped; the rest of the run continues

## Why no browser?

Books to Scrape puts product data in the HTML the server sends. A headless browser would only add time and memory without changing what we can extract. (JS-rendered sandboxes like `quotes.toscrape.com/js` are a different story — that is a Stretch exercise.)

## Ethics

Prefer an official API when one exists. Do not bypass logins, paywalls, or blocks. Collect only what you need for the stated scope. This project only targets a public practice sandbox.

## Sample run report

From a real local run (mostly cache hits after the first fetch):

```json
{
  "started_at": "2026-08-08T00:02:53Z",
  "duration_seconds": 3.466,
  "catalogue_pages": 3,
  "discovered_urls": 60,
  "unique_urls": 60,
  "pages_fetched": 0,
  "cache_hits": 63,
  "valid_records": 60,
  "invalid_records": 0,
  "failed_pages": 1,
  "failed_urls": [
    {
      "url": "https://books.toscrape.com/catalogue/this-book-does-not-exist-zzzz_0/index.html",
      "error": "HTTP 404 for https://books.toscrape.com/catalogue/this-book-does-not-exist-zzzz_0/index.html"
    }
  ],
  "output": {
    "books": "output/books.json",
    "errors": "output/errors.json"
  }
}
```

## Limitation

Catalogue discovery follows the site’s own “next” link for exactly three pages. Broader crawls, JS-rendered pages, and production retry/backoff are out of scope for this assignment.

## Stretch

### Browser cost comparison

```bash
cd scraper
pip install playwright psutil
playwright install chromium
python stretch/browser_compare.py
```

Target: [quotes.toscrape.com/js](https://quotes.toscrape.com/js) — quotes are injected by JavaScript (View Source shows none).

Example local measurements:

Browser stretch is done.

| Method | Quotes | Time | RSS |
|--------|--------|------|-----|
| HTTP | **0** | 1.7 s | 36.3 MiB |
| Playwright | **10** | 7.6 s | 45.4 MiB |

Conclusion: quotes are injected by JS, so plain HTTP sees none; Books to Scrape needs no browser because its data is already in the HTML.

**Why the core assignment needed no browser:** Books to Scrape embeds product fields in the HTML the server sends. A browser would only add time and memory. `quotes.toscrape.com/js` needs a browser because the quotes are not in the raw response.

### Parser tests

```bash
cd scraper
pip install pytest
pytest tests/ -q
```

Five offline tests cover price normalization, relative→absolute URLs, missing description, duplicate URL idempotency, and malformed price.

### Background detail jobs (not a cron)

Detail pages run as queued jobs in a `ThreadPoolExecutor` with a concurrency cap. This overlaps HTTP waits across workers (GIL means this is I/O concurrency, not multi-core CPU parallel Python). A shared rate limiter still spaces **network request starts** by ≥500 ms.

```bash
python src/main.py --workers 3   # default
python src/main.py --workers 1   # serial (debug)
```

Writes stay **idempotent** by absolute `product_url`. One failed job does not cancel the pool.

### AI enrichment (local Ollama)

Scraped facts stay in `output/books.json`. Model opinions go to a separate file:

```bash
# requires Ollama running locally with a pulled model, e.g. llama3.2
ollama serve
ollama pull llama3.2
python src/enrich.py --limit 5
# → output/enrichment.json  keyed by product_url: {category, summary}
```

Schema-forced via Pydantic. Enrichment failures skip that book only; they never rewrite scraped fields.
