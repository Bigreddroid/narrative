# The Narrative — Current State

*Canonical status of the project. Supersedes the older vision notes in
`build-status.html` / `.grok/AGENTS.md` where they conflict.*

## What it is
Consequence-intelligence platform — "we tell you how the world's next shock will
hit your life, before it does, with the evidence." Reads world news across
sources, maps the causal chain from an event to its real-world impact (with a
fact/inference/speculation label + evidence at each node), scores a prediction,
and keeps a track record of whether predictions came true. Consumer-mission-first,
enterprise-funded. See `MISSION.md` + `PITCH.md`.

## Status: real and working (locally)
- **Backend** (FastAPI + SQLAlchemy async + Postgres/pgvector + Redis) serves
  **993 real events**, 107 consequence maps, 39 event connections.
- **Engine** (`backend/consequence_engine/`): scrape → embed → cluster → importance
  → consequence-map (Claude, evidence-grounded) → graph → outcome. Wired into
  `scheduler.py` (importance/mapping/outcome included).
- **Track record** (the make-or-break): real evidence-grounded `outcome_worker`
  (replaced a fake placeholder). First honest grading via independent web ground
  truth: **6/7 short-horizon predictions materialized, mean Brier 0.094** (vs 0.25
  coin-flip). Encouraging signal; small/short-horizon — not yet proof.
- **Web** (Vite/React): world globe + consequence rail, intelligence feed, event
  detail with consequence chain + related events, live landing teaser, admin.
- **Tests**: 19 passing (API auth/feed/search/graph + engine scoring/connection units).

## How to run
- **One command (needs Docker):** `docker compose up` → http://localhost:8080,
  sign in with any email. Bundled real data auto-loads. See `QUICKSTART.md`.
- **Dev (this machine):** Postgres+Redis run in WSL; backend runs in a WSL
  **python3.12** venv (system 3.14 can't build the pinned wheels); web runs on
  Windows via `npm run dev`. WSL2↔Windows reaches the backend on `127.0.0.1`
  (mirrored networking). Details in the project memory / `LOCAL_DEV.md`.

## Architecture
- `backend/api/routes/` — feed, events, graph, follows, search, users, auth, admin, stripe
- `backend/workers/` — pipeline stages; `backend/consequence_engine/` — the IP
- `backend/models/` — NarrativeEvent, EventConsequenceMap, EventConnection,
  PredictionOutcome (the track-record table), Article, Source, User
- `web/src/` — pages (Landing, WorldView, EventDetail, Following, Settings, Auth),
  components/graph (WorldMap, EventGraph), hooks, admin

## What's left (and what it needs)
| Item | Blocker |
|---|---|
| Public URL (shareable) | cloud logins (Vercel + Railway + Neon) |
| Grow the track record | a valid `ANTHROPIC_API_KEY` + pipeline running over time |
| Refresh stale data (newest ~Jun 10) | valid Anthropic key (mapping step) |
| Backfill tags on 82 low-importance events | valid Anthropic key (deep re-map) |
| Real auth (replace dev-login) | Supabase project |
| Monetization | Stripe keys |
| Verify `docker compose up` end-to-end | Docker Desktop installed |

**Note:** the `ANTHROPIC_API_KEY` currently in `.env` returns `401` — any
engine/pipeline work is blocked until a working key is in place.
