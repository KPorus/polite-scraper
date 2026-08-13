# Book enrich API (W7)

Given a messy book title query, this API looks up the matching catalogue row in the polite scraper’s Postgres database, asks a local Ollama model for a closed category / book type / summary, and returns schema-validated JSON.

**Provider swap:** three environment variables are the only difference between a model on your laptop (Ollama) and one in a datacentre — never hard-code a provider.

```text
LLM_BASE_URL · LLM_API_KEY · LLM_MODEL
```

## Prerequisites

1. Scraper Postgres running and populated (`cd ../scraper && docker compose up -d && python src/main.py`)
2. Ollama with `llama3.2:latest` pulled and `ollama serve` running

## Setup

```bash
cd api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Stage 0 check

```bash
python src/llm/hello.py
# expect output containing: ready
```
