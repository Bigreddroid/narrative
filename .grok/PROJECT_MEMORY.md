# Project Memory — Narrative v5 (The Narrative)

**Focus**: Turn sophisticated but disconnected backend pipeline into a real, usable consequence intelligence product. Prioritize the beta minimum items from build-status.html.

## Current Tech Stack
- Backend: FastAPI (async), SQLAlchemy, Postgres (pgvector expected), Redis, Alembic.
- Pipeline: 11 workers (scrape, embed/Voyage, cluster, graph, importance, feed, outcome, archive, alert, mapping, evolution) + consequence_engine (clusterer, embedder, etc.).
- AI: Claude (Sonnet for core, Opus for deep), Voyage embeddings.
- Frontend: Mobile (React Native/Expo — WorldMap, Event, Following, etc. — mostly mock). Legacy web in v2.
- Other: Docker, GitHub Actions (intended), Stripe skeleton, tier system in UI/models.

## Key Files
- `build-status.html` — Authoritative current state and remaining work list (use this as source of truth for priorities).
- `backend/main.py`, `config.py`, `database.py`.
- Workers in `backend/workers/`.
- Consequence engine in `backend/consequence_engine/`.
- Models in `backend/models/` (NarrativeEvent, EventConsequenceMap, etc.).
- Mobile in `mobile/src/`.
- Legacy disaster: `Narrative v2/` (do not expand; plan cleanup).

## Open Tasks & Priorities (from build-status + code)
**Beta Minimum (must do before sending to friends):**
1. Mobile layout (zero responsive today).
2. Deploy config (no FE Dockerfile, no public URL, env setup).
3. Real data (backend not connected to frontend; everything mock).
4-8. Admin wiring, Stripe/checkout, beta invites, real search, iOS.

**High Priority Flaws to Fix First:**
- Disconnect between pipeline and UI (feed.py exists but uses mocks in practice).
- Legacy v2 bloat (massive node_modules, duplicate code).
- Overly complex architecture for zero live output.
- No tests, incomplete error handling in workers.
- Hardcoded dev secrets/mocks in dev_server.py.

**Architecture Decisions**
- Keep the worker + consequence model (it's the strength), but make the smallest slice (scrape → embed → simple feed) work end-to-end first.
- Mobile-first. Do not invest in new web UI until mobile + data is solid.
- Use segment/personalized feeds (already in feed.py).
- Clean up v2 only after v5 has a working core loop.

## User Preferences for This Project
- Be ruthless about removing mocks.
- Small, verifiable changes over big refactors.
- Update build-status.html after any significant progress.
- Follow clean-code: no fluff comments, direct implementations.
- GAIA hybrid: For any architectural decisions or reviews, prepare clean handoff blocks.

## Gotchas
- Workers run on intervals; test via `python -m backend.workers.scrape_worker` etc.
- Many __pycache__ and legacy files — ignore for source work.
- Cost control is already in config (claude budgets) — respect it.
- The "Narrative" vision is powerful, but current delivered value is near zero. Focus on shipping one useful slice.

**Last updated**: SuperGrok setup session. Read this + .grok/AGENTS.md + build-status.html at start of any work on this project.