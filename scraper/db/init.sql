-- Books table for scraped catalogue records (idempotent on product_url).
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
);

CREATE INDEX IF NOT EXISTS books_title_idx ON books (title);
