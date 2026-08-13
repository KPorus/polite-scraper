#!/usr/bin/env python3
"""FastAPI app — POST /enrich (Stage 1: validation + stub, no model yet)."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from src.db import find_book_by_query
from src.llm.client import llm_stub_enabled
from src.llm.schema import EnrichRequest, EnrichResponse, STUB_LLM

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

app = FastAPI(title="Book Enrich API", version="0.1.0")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request, exc: RequestValidationError):
    errors = exc.errors()
    field = "body"
    if errors:
        loc = errors[0].get("loc", ())
        # skip "body"
        parts = [str(p) for p in loc if p != "body"]
        if parts:
            field = ".".join(parts)
    return JSONResponse(
        status_code=400,
        content={"detail": f"Invalid input: field '{field}' failed validation", "errors": errors},
    )


def _merge_response(book: dict, llm_fields) -> EnrichResponse:
    return EnrichResponse(
        matched_title=book["title"],
        product_url=str(book["product_url"]),
        category=llm_fields.category,
        book_type=llm_fields.book_type,
        summary=llm_fields.summary,
        confidence=llm_fields.confidence,
        quality_flags=list(llm_fields.quality_flags),
    )


@app.post("/enrich", response_model=EnrichResponse)
def enrich(body: EnrichRequest) -> EnrichResponse:
    book = find_book_by_query(body.query)
    if book is None:
        raise HTTPException(status_code=404, detail=f"No book matched query: {body.query!r}")

    if not llm_stub_enabled():
        raise HTTPException(
            status_code=503,
            detail="Model path not wired yet. Set LLM_STUB=1 for Stage 1, or wait for Stage 2.",
        )

    return _merge_response(book, STUB_LLM)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
