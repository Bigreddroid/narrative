# Cost posture — free/local by default

The Narrative runs the **entire pipeline at $0** out of the box. Paid APIs are
opt-in and, when enabled, bounded by **enforced** hard caps. Nothing requires a
paid key to function — when a paid provider is unavailable or over budget, the
affected stage degrades to a free/heuristic path instead of erroring.

## What costs money (and what doesn't)

| Stage | Default (free) | Optional paid upgrade |
|------|----------------|-----------------------|
| Embeddings | `fastembed` / `BAAI/bge-large-en-v1.5` (local, 1024-dim) | Voyage `voyage-3` |
| Consequence mapping | Ollama (`qwen2.5:7b`) | Anthropic Claude |
| Analyst chat | Ollama, else templated grounded answer | Anthropic Claude |
| Outcome eval | Ollama | Anthropic Claude |
| World map | d3 + topojson (no tiles/token) | — |
| Importance, clustering, propagation, calibration, graph, all 14 feeds | always free/heuristic | — |

`bge-large-en-v1.5` is also **1024-dim**, so it's a drop-in for the existing
`Vector(1024)` schema — no migration when switching between local and Voyage.

## The switches (`backend/config.py` / `.env`)

```
PAID_APIS_ENABLED=false        # master kill-switch; false ⇒ ignore ALL paid providers
LLM_PROVIDER=ollama            # ollama | anthropic | off
EMBEDDINGS_PROVIDER=local      # local | voyage

OLLAMA_BASE_URL=http://localhost:11434
LOCAL_LLM_MODEL=llama3.2:latest        # qwen2.5:7b = sharper mapping JSON
LOCAL_EMBEDDING_MODEL=BAAI/bge-large-en-v1.5

# Enforced hard caps (NOT just alerts). 0 ⇒ no paid spend permitted.
CLAUDE_HARD_CAP_DAILY_USD=0
CLAUDE_HARD_CAP_MONTHLY_USD=0
```

A paid call happens **only** when *all* of these hold: `PAID_APIS_ENABLED=true`,
the stage's provider is the paid one, and recorded spend is below the hard cap.
Even if `LLM_PROVIDER=anthropic` is set, leaving `PAID_APIS_ENABLED=false`
downgrades it to local automatically — a stray config can never start spending.

## How enforcement works

- `backend/services/llm.py` — provider-agnostic LLM access (ollama / anthropic / off).
- `backend/services/cost_guard.py` — `claude_allowed(db)` blocks paid calls once
  today's or this-month's `pipeline_metrics.claude_cost_usd` reaches the hard cap.
- Workers (`mapping_worker`, `outcome_worker`) and the analyst check the guard
  first and **degrade gracefully**: mapping leaves events unmapped for a later run,
  outcome eval skips the run, and the analyst returns a templated answer built from
  real retrieved events + exposure.
- `backend/services/cost_alert.py` remains the **soft** layer (email only).

## Running fully free (local)

```bash
# one-time: install Ollama + pull the model (in WSL/Linux/macOS)
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2          # default; or `ollama pull qwen2.5:7b` for sharper mapping
```

`fastembed` downloads its embedding model automatically on first use (~1.3 GB).
With the default `.env` (no keys), start the stack normally — embeddings, mapping,
and analyst chat all run locally for $0.

## Opting a stage into a paid provider

1. Set `PAID_APIS_ENABLED=true`.
2. Point the stage at the paid provider (`LLM_PROVIDER=anthropic` and/or
   `EMBEDDINGS_PROVIDER=voyage`) and set the matching key.
3. Raise `CLAUDE_HARD_CAP_DAILY_USD` / `CLAUDE_HARD_CAP_MONTHLY_USD` to your budget.

Spend is visible at `GET /admin/costs` and in the admin Cost Dashboard.
