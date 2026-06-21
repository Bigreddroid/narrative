# The Narrative

A world-consequence intelligence platform: it ingests real events from open
feeds (news RSS, USGS, GDACS, launches, cyber, markets, AIS/air traffic),
clusters them into narrative events, maps each event's consequence chain, and
runs a deterministic **Consequence Propagation Engine (CPE)** to score how
exposed each sector/region is — with full driver attribution.

## Stack

- **Backend** — FastAPI (`backend/`), SQLAlchemy + Alembic, Postgres + **pgvector**,
  Redis. A single async **scheduler** (`backend/scheduler.py`) runs all pipeline
  workers (scrape → embed → cluster → score → map → graph → exposure).
- **CPE** — deterministic, server-side only (`backend/consequence_engine/`). No
  LLM at serving time; the only paid LLM step is the budget-capped `mapping_worker`.
- **Frontend** — React + Vite (`web/`), D3 globe, exposure panels, tier-gated UI.
- **Mobile** — React Native scaffold (`mobile/`).

## Local development

Requires Postgres (with the `vector` extension) and Redis running, plus a Python
3.12 env and Node.

```bash
# 1. Postgres + Redis (Docker is the documented path; see SETUP.md for native)
docker-compose up postgres redis -d

# 2. Backend
pip install -r backend/requirements.txt
cp .env.example .env            # fill in ANTHROPIC_API_KEY, VOYAGE_API_KEY, etc.
alembic -c backend/alembic.ini upgrade head
uvicorn backend.main:app --reload          # http://localhost:8000  (/health, /docs)

# 3. Scheduler (optional — ingests live data continuously; spends API credits)
python -m backend.scheduler

# 4. Frontend
cd web && npm install && npm run dev        # http://localhost:5173
```

Sign in with a dev account (e.g. `enterprise@narrative.dev`, any password) — dev
login is enabled when `APP_ENV != production`.

### Real data vs. demo

By default the app shows **real backend data only**; if the API is unreachable it
shows an honest empty/error state — never fabricated data. To run a self-contained
offline demo with sample events, build with `VITE_DEMO_MODE=true npm run dev`.

## Tests

```bash
# Backend engine (no framework needed)
python -m pytest backend/consequence_engine backend/feeds
# Frontend lib property tests
node web/src/lib/propagation.test.mjs
```

## Deploy

Backend → **Railway** (consolidated to `api` + `scheduler` services + managed
Postgres/Redis; see `railway.toml` and `.env.production.example`). Frontend →
**Vercel** (`vercel.json`; set the API rewrite target + `VITE_MAPBOX_TOKEN`).
Full steps in `docs/DEPLOY.md`.

## Security notes

- Secrets live in `.env` (gitignored). Never commit real keys.
- The API enforces per-user/per-IP rate limiting (`backend/api/rate_limit.py`).
- Production (`APP_ENV=production`) disables `/docs` and runs under gunicorn.
