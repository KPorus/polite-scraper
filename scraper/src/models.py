"""Normalize raw values and validate records with Pydantic."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, HttpUrl, field_validator


class BookRecord(BaseModel):
    title: str
    product_url: HttpUrl
    price_text: str
    price_gbp: float
    availability_text: str
    rating_text: str
    description: str | None = None
    source_page: HttpUrl
    fetched_at: str

    @field_validator("price_gbp")
    @classmethod
    def price_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("price_gbp must be non-negative")
        return v

    @field_validator("fetched_at")
    @classmethod
    def fetched_at_iso(cls, v: str) -> str:
        datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v


def normalize_price_gbp(price_text: str) -> float:
    """Parse a currency string like '£51.77' (or mojibake 'Â£51.77') to float."""
    text = price_text.replace("Â£", "£").replace(",", "").strip()
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if not match:
        raise ValueError(f"cannot parse price from {price_text!r}")
    return float(match.group(1))


def normalize_record(raw: dict[str, Any]) -> dict[str, Any]:
    out = dict(raw)
    out["price_gbp"] = normalize_price_gbp(raw["price_text"])
    return out
