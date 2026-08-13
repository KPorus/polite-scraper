"""Pydantic input/output schemas for POST /enrich."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Category(str, Enum):
    fiction = "fiction"
    mystery = "mystery"
    romance = "romance"
    scifi = "scifi"
    history = "history"
    self_help = "self_help"
    other = "other"


class BookType(str, Enum):
    novel = "novel"
    series = "series"
    nonfiction = "nonfiction"
    young_adult = "young_adult"
    other = "other"


QualityFlag = Literal["missing_description", "thin_copy", "price_outlier"]


class EnrichRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=200)

    @field_validator("query")
    @classmethod
    def strip_query(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("query must not be empty or whitespace")
        return cleaned


class LlmEnrichment(BaseModel):
    """Fields the model is allowed to invent (closed lists)."""

    category: Category
    book_type: BookType
    summary: str = Field(..., min_length=1, max_length=300)
    confidence: float = Field(..., ge=0.0, le=1.0)
    quality_flags: list[QualityFlag] = Field(default_factory=list)


class EnrichResponse(BaseModel):
    matched_title: str
    product_url: str
    category: Category
    book_type: BookType
    summary: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    quality_flags: list[QualityFlag] = Field(default_factory=list)


STUB_LLM = LlmEnrichment(
    category=Category.other,
    book_type=BookType.other,
    summary="Stub enrichment — no model call was made.",
    confidence=0.0,
    quality_flags=[],
)
