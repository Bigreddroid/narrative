# The Narrative — Setup Guide

## Phase 1: Engine Core

### Prerequisites
- Docker + Docker Compose
- Python 3.11
- Node.js 18+

---

### Step 1 — Environment

```bash
cp .env.example .env
# Fill in ANTHROPIC_API_KEY and VOYAGE_API_KEY at minimum
```

---

### Step 2 — Start infrastructure

```bash
docker-compose up postgres redis -d
```

Wait for both to be healthy:
```bash
docker-compose ps
```

---

### Step 3 — Install Python deps

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate     # Windows
# source .venv/bin/activate  # Mac/Linux
pip install -r requirements.txt
```

---

### Step 4 — Run migrations

```bash
# From repo root
alembic -c backend/alembic.ini upgrade head
```

Verify:
```bash
docker exec -it narrative_postgres_1 psql -U narrative -c "\dt"
# Should list all 12 tables
```

---

### Step 5 — Start the API

```bash
uvicorn backend.main:app --reload --port 8000
```

Verify:
```bash
curl http://localhost:8000/health
# {"status":"ok","env":"development"}
```

API docs (dev only):
```
http://localhost:8000/docs
```

---

### Step 6 — Run pipeline manually (test)

In separate terminals:

```bash
# Seed sources + scrape
python -m backend.workers.scrape_worker

# Embed articles (needs VOYAGE_API_KEY)
python -m backend.workers.embed_worker

# Cluster into events
python -m backend.workers.cluster_worker

# Score importance
python -m backend.workers.importance_worker

# Map with Claude (needs ANTHROPIC_API_KEY, costs ~$0.01-0.15 total)
python -m backend.workers.mapping_worker

# Connect graph
python -m backend.workers.graph_worker
```

---

### Step 7 — Start the scheduler (runs everything automatically)

```bash
python -m backend.scheduler
```

---

### Step 8 — Start the web frontend

```bash
cd web
npm install
cp .env.example .env  # Add VITE_MAPBOX_TOKEN
npm run dev
# → http://localhost:5173
```

---

### Step 9 — Full Docker stack

```bash
docker-compose up
# API: http://localhost:8000
# Web: http://localhost:5173 (run npm dev separately)
# pgAdmin: http://localhost:5050
```

---

## Verify Pipeline Works

After running scrape + embed + cluster + importance + mapping:

```bash
curl http://localhost:8000/api/v1/events/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Should return mapped events with consequence chains.

World graph:
```bash
curl http://localhost:8000/api/v1/graph/world \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## Cost Control

Mapping worker limits: 20 events per run (configurable).
Claude calls: 1 per cluster only.
Check costs: http://localhost:8000/api/v1/admin/costs (admin token).

Set budget alerts in .env:
```
CLAUDE_DAILY_COST_ALERT_USD=20
CLAUDE_MONTHLY_BUDGET_USD=200
```

---

## Phase 2 checklist (after Phase 1 runs clean)
- [ ] graph_worker connections computed
- [ ] evolution_worker detecting drift
- [ ] alert_worker sending FCM
- [ ] outcome_worker evaluating predictions
- [ ] archive_worker running

Phase 3: Web frontend (WorldMap awe moment)
Phase 4: Admin panel
Phase 5: Stripe payments
Phase 6: Mobile (React Native)
