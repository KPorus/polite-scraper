# Book enrich API (W7)

Look up a book from the polite scraper’s Postgres by a messy title query, ask a local Ollama model for a **closed** category / book type / summary, and return **schema-validated JSON** — with stub mode, one repair retry, a 60s timeout, cost logs, and a kill switch.

This is not a chatbot. One request in, one structured answer out.

## Job card

See [JOB-CARD.md](JOB-CARD.md).

**It must never:** invent a book not in the DB · invent categories outside the closed lists · invent price/availability · return raw model text · reveal the prompt.

**When unsure:** `category`/`book_type` → `other`, `confidence` &lt; 0.5.

## Provider (swap with three env vars)

Three environment variables are the only difference between a model on your laptop and one in a datacentre — never hard-code a provider.

| Variable | Ollama (this project) |
|---|---|
| `LLM_BASE_URL` | `http://localhost:11434/v1/` |
| `LLM_API_KEY` | `ollama` |
| `LLM_MODEL` | `llama3.2:latest` |

Retry policy: **custom** (`max_retries=0` on the OpenAI SDK). We retry only timeouts / 429 / 5xx with exponential backoff + jitter; never 400 / 401 / 403.

## Prerequisites

1. Scraper Postgres up and populated: `cd ../scraper && docker compose up -d && python src/main.py`
2. Ollama running with `llama3.2:latest` (`ollama serve`)

## Setup

```bash
cd api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Run

```bash
cd api
source .venv/bin/activate
# stub (no model calls) — good for wiring checks
LLM_STUB=1 uvicorn src.main:app --port 8000

# real Ollama calls
LLM_STUB=0 uvicorn src.main:app --port 8000
```

### Valid curl

```bash
curl -sS -X POST http://127.0.0.1:8000/enrich \
  -H 'Content-Type: application/json' \
  -d '{"query":"Sharp Objects"}'
```

Example response (Ollama `llama3.2:latest`, prompt `enrich-v1`, 2026-08-13):

```json
{
  "matched_title": "Sharp Objects",
  "product_url": "https://books.toscrape.com/catalogue/sharp-objects_997/index.html",
  "category": "mystery",
  "book_type": "novel",
  "summary": "A dark mystery about a journalist confronting her troubled past.",
  "confidence": 0.86,
  "quality_flags": []
}
```

### Invalid curl (expect HTTP 400 naming `query`)

```bash
curl -sS -X POST http://127.0.0.1:8000/enrich \
  -H 'Content-Type: application/json' \
  -d '{}'
```

### Kill switch

```bash
LLM_ENABLED=false LLM_STUB=0 uvicorn src.main:app --port 8000
# returns deterministic fallback JSON immediately — zero model calls
```

## Stage 0 check

```bash
python src/llm/hello.py
# expect output containing: ready
```

## Eval

```bash
# API must already be running on :8000 with LLM_STUB=0
python evals/run_eval.py --base-url http://127.0.0.1:8000 --timeout 180
```

**Result (2026-08-13, prompt `enrich-v1`, model `llama3.2:latest`): 6 / 8 (75%)** on key fields `category` + `book_type`.

Failures: `Behind Closed Doors` mis-labelled as other/nonfiction; `Mesaerion` anthology still 422 after one repair. Comparable number for the next prompt tweak.

## Cost (one real call)

Example cost log line (stderr):

```json
{"event":"llm_cost","prompt_version":"enrich-v1","model":"llama3.2:latest","input_tokens":550,"output_tokens":35,"duration_ms":30011,"repair_count":0}
```

Local Ollama is **$0**. If the same tokens were billed at a typical small hosted rate (~$0.15 / 1M input, ~$0.60 / 1M output), one call ≈ **$0.0001**. At 10,000 requests/day with no cache/repairs: on the order of **~$1/day** hosted — dominated by **input tokens** (prompt + book text), then repairs.

## What I’d fix with another day

Tighten anthology / series cues in the prompt, add a tiny response cache keyed by `(prompt_version, query)`, and grow the eval set with explicit “series vs novel” cases.

## Layout

```text
api/
  JOB-CARD.md
  prompts/enrich-v1.md
  evals/cases.json
  evals/run_eval.py
  src/main.py
  src/db.py
  src/llm/
```
