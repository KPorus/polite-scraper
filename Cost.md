```
{"ts": "2026-08-13T15:45:28.364869+00:00", "event": "llm_cost", "prompt_version": "enrich-v1", "model": "llama3.2:latest", "input_tokens": 570, "output_tokens": 37, "duration_ms": 108878, "repair_count": 0}
```

That line is a **structured cost/latency log** printed to stderr after each successful LLM path (including after a repair). It comes from [`api/src/llm/cost.py`](api/src/llm/cost.py).

## Purpose

So you can **measure** every model call:

- How long it took  
- How many tokens it used (proxy for money on hosted APIs)  
- Which prompt version / model produced it  
- Whether a repair call was needed  

W7’s point: you can’t manage cost or reliability if you don’t log it. Local Ollama is $0, but the same log answers “what would 10k requests/day cost on a paid API?”

---

## Each property

| Field | Your example | Meaning |
|---|---|---|
| `ts` | `2026-08-13T15:45:28.364869+00:00` | UTC timestamp when the log was written |
| `event` | `llm_cost` | Log type — easy to filter in log systems |
| `prompt_version` | `enrich-v1` | Which prompt file was used (`prompts/enrich-v1.md`). If quality changes, you know which spec was live |
| `model` | `llama3.2:latest` | Which model answered |
| `input_tokens` | `570` | Tokens sent in (system prompt + user book JSON). Usually the **biggest cost driver** |
| `output_tokens` | `37` | Tokens the model generated (the JSON answer) |
| `duration_ms` | `108878` | Wall time for the call (~109 seconds here — slow CPU Ollama) |
| `repair_count` | `0` | `0` = first answer validated; `1` = needed one repair call |

Sometimes you’ll also see `"quarantined": true` when validation failed even after repair.

---

**In one line:** this object is your per-call receipt for “what the LLM did and what it cost in time/tokens,” so you can debug slowness, compare prompt versions, and estimate spend.