#!/usr/bin/env python3
"""FastAPI app — POST /enrich with schema validation, repair, timeout, kill switch."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow `uvicorn src.main:app` from the api/ directory without installing a package.
_API_ROOT = Path(__file__).resolve().parents[1]
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from openai import APITimeoutError
from pydantic import ValidationError

from src.db import find_book_by_query
from src.llm.client import (
    PROMPT_VERSION,
    chat_completion,
    load_system_prompt,
    llm_enabled,
    llm_stub_enabled,
)
from src.llm.cost import log_cost
from src.llm.parse import parse_and_validate, quarantine, validation_error_text
from src.llm.schema import EnrichRequest, EnrichResponse, LlmEnrichment, STUB_LLM

ROOT = _API_ROOT
load_dotenv(ROOT / ".env")

app = FastAPI(title="Book Enrich API", version="0.4.0")

FALLBACK_LLM = LlmEnrichment(
    category=STUB_LLM.category,
    book_type=STUB_LLM.book_type,
    summary="LLM disabled — deterministic fallback (no model call).",
    confidence=0.0,
    quality_flags=[],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request, exc: RequestValidationError):
    errors = exc.errors()
    field = "body"
    if errors:
        loc = errors[0].get("loc", ())
        parts = [str(p) for p in loc if p != "body"]
        if parts:
            field = ".".join(parts)
    return JSONResponse(
        status_code=400,
        content={"detail": f"Invalid input: field '{field}' failed validation", "errors": errors},
    )


def _merge_response(book: dict, llm_fields: LlmEnrichment) -> EnrichResponse:
    return EnrichResponse(
        matched_title=book["title"],
        product_url=str(book["product_url"]),
        category=llm_fields.category,
        book_type=llm_fields.book_type,
        summary=llm_fields.summary,
        confidence=llm_fields.confidence,
        quality_flags=list(llm_fields.quality_flags),
    )


def _user_payload(book: dict) -> str:
    desc = book.get("description")
    if isinstance(desc, str) and len(desc) > 200:
        desc = desc[:200] + "…"
    payload = {
        "title": book["title"],
        "description": desc,
        "price_gbp": book.get("price_gbp"),
        "rating_text": book.get("rating_text"),
    }
    # JSON-encode untrusted catalogue text so it cannot break out of quotes.
    return json.dumps(payload, ensure_ascii=False)


def _enrich_with_model(book: dict) -> LlmEnrichment:
    system = load_system_prompt()
    user = _user_payload(book)
    repair_count = 0
    raw = ""
    try:
        raw, meta = chat_completion(system=system, user=user)
        try:
            result = parse_and_validate(raw)
            log_cost(
                prompt_version=PROMPT_VERSION,
                model=meta["model"],
                input_tokens=meta.get("input_tokens"),
                output_tokens=meta.get("output_tokens"),
                duration_ms=meta["duration_ms"],
                repair_count=0,
            )
            return result
        except (ValueError, ValidationError, json.JSONDecodeError) as first_err:
            repair_count = 1
            repair_user = (
                f"{user}\n\n"
                f"Your previous answer was rejected for this reason:\n"
                f"{validation_error_text(first_err)}\n\n"
                f"Previous answer:\n{raw}\n\n"
                "Return only corrected JSON matching the schema."
            )
            raw2, meta2 = chat_completion(system=system, user=repair_user)
            raw = raw2
            try:
                result = parse_and_validate(raw2)
                log_cost(
                    prompt_version=PROMPT_VERSION,
                    model=meta2["model"],
                    input_tokens=meta2.get("input_tokens"),
                    output_tokens=meta2.get("output_tokens"),
                    duration_ms=meta2["duration_ms"],
                    repair_count=1,
                )
                return result
            except (ValueError, ValidationError, json.JSONDecodeError) as second_err:
                quarantine(
                    input_payload={"title": book["title"], "user": user},
                    raw_output=raw2,
                    error=validation_error_text(second_err),
                    prompt_version=PROMPT_VERSION,
                )
                log_cost(
                    prompt_version=PROMPT_VERSION,
                    model=meta2["model"],
                    input_tokens=meta2.get("input_tokens"),
                    output_tokens=meta2.get("output_tokens"),
                    duration_ms=meta2["duration_ms"],
                    repair_count=1,
                    extra={"quarantined": True},
                )
                raise HTTPException(
                    status_code=422,
                    detail="Model output failed schema validation after one repair attempt",
                ) from second_err
    except HTTPException:
        raise
    except APITimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail=f"Model call timed out after {60}s",
        ) from exc


@app.post("/enrich", response_model=EnrichResponse)
def enrich(body: EnrichRequest) -> EnrichResponse:
    book = find_book_by_query(body.query)
    if book is None:
        raise HTTPException(status_code=404, detail=f"No book matched query: {body.query!r}")

    if llm_stub_enabled():
        return _merge_response(book, STUB_LLM)

    if not llm_enabled():
        return _merge_response(book, FALLBACK_LLM)

    try:
        llm_fields = _enrich_with_model(book)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Model call failed: {exc}") from exc

    return _merge_response(book, llm_fields)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
