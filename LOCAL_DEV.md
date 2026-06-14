# Local Development — Narrative v5

## Quick Start (Recommended)

1. Start the real backend (with DB if possible):
   ```bash
   # Option A: docker (includes postgres + redis)
   docker-compose up --build

   # Option B: local python (assumes you have postgres running)
   uvicorn backend.main:app --reload --port 8000
   ```

2. Mobile (React Native / Expo):
   ```bash
   cd mobile
   npm install
   npx expo start
   ```

   Set the API URL (in your shell or .env):
   ```bash
   export EXPO_PUBLIC_API_URL=http://localhost:8000/api/v1
   ```

   The mobile now defaults to localhost:8000 and calls real endpoints like `/feed`.

3. Test real data flow:
   - The "World" tab (WorldMapScreen) now hits `/feed` and maps canonical fields.
   - Backend must have some NarrativeEvent rows with `is_mapped=true` for the list to populate.

## Current State (Remodel in Progress — New Vision)
- **New Core**: Customer-centric "Bloomberg terminal" for individuals — news + data + analytics + impact tools, simplified, crimson editorial visuals (from mockups: #C80028 crimson, paper backgrounds, globe/map + lists).
- Backend: Simplification started (main.py vision updated, heavy graph/importance workers + connectors marked lean/stretch; cluster/embed already lean). Focus: news/data ingestion + light AI impact/summaries.
- Mobile: Real data wiring started; redesign to terminal feel with crimson/paper style ongoing.
- dev_server.py deprecated.
- Legacy v2: Archived (see notes in AGENTS.md / build-status.html). Do not run or reference for new work.
- Deploy: Mobile EAS ready; backend Docker ready.
- Visuals: Dual light (paper #F5F1EB editorial + crimson) / dark (terminal black + crimson brand + cyan viz) exactly from Mockups/ images (globe hotspots, "How this affects you", Media Bias, dense cards). Mobile uses system Appearance (or toggle in Profile for testing).
- Standalone project (no BigRedDroid ties).

## Next Priorities (All Items)
See updated build-status.html and .grok/AGENTS.md (we are executing the full remodel: core/visuals, backend simplify, mobile UX, cleanup, real data/deploy, product stretch).

Run `cat build-status.html` for the authoritative remaining work list.

## Seeded Real Data (for testing)
After starting backend (docker or uvicorn):
```bash
# Run the seeder (creates realistic NarrativeEvents + articles + maps for feed/graph/mobile)
python -m backend.seed
```

This populates enough for /feed, /graph/world, /graph/event, and mobile World/Following/Event tabs.

For full end-to-end: Run the lean scheduler (core workers only) or individual:
python -m backend.workers.scrape_worker
etc.
Heavy workers are stretch.

## Useful Commands
- Backend health: curl http://localhost:8000/health
- Feed (real): curl "http://localhost:8000/api/v1/feed"
- Graph world: curl "http://localhost:8000/api/v1/graph/world"
- Check workers: python -m backend.workers.scrape_worker (etc.)

## Notes
- The "World" tab in mobile is currently a vertical event list (not the D3 map yet). Map integration via /graph/world is stretch.
- Real consequence maps and predictions come from the EventConsequenceMap table + latest version.
- User tiers affect limits (free gets fewer nodes, no confidence, etc.).

## Mobile Layout / Responsiveness (started)
- Basic: Used flex, padding adjustments, Dimensions if needed in future.
- To improve further: Add Platform.OS checks, scale fonts for small screens, horizontal scroll for pills on tiny devices.
- Current screens (list, following, search, event) use consistent flex containers — test on device/simulator.

## Deploy
- Mobile: `eas build --platform android/ios --profile preview` (or production).
  Set EXPO_PUBLIC_API_URL to your hosted backend.
- Backend: `docker-compose up --build` (dev). For prod: Railway, Fly.io, or similar using the Dockerfile + compose (remove reload/volumes, set production env).
- Health: curl http://localhost:8000/health
- After deploy, update build-status.html with the public URL.
- Seeder + lean scheduler work in prod too (run seed once on fresh DB).

## Next Priorities (beta minimum) — All in progress
See updated build-status.html and .grok/AGENTS.md (we are tackling all: real data wiring complete for list+detail+following+search, mobile layout started, v2 cleanup planned, seeded data added here, deploy config started, admin/stripe as stretch).

Run `cat build-status.html` for the authoritative remaining work list.

## Seeded Real Data (for testing)
After starting backend (docker or uvicorn):
```bash
# Run the seeder (creates realistic NarrativeEvents + articles + maps for feed/graph/mobile)
python -m backend.seed
```

This populates enough for /feed, /graph/world, /graph/event, and mobile World/Following/Event tabs.

For full end-to-end: Run the lean scheduler (core workers only) or individual:
python -m backend.workers.scrape_worker
etc.
Heavy workers are stretch.

## Useful Commands
- Backend health: curl http://localhost:8000/health
- Feed (real): curl "http://localhost:8000/api/v1/feed"
- Graph world: curl "http://localhost:8000/api/v1/graph/world"
- Check workers: python -m backend.workers.scrape_worker (etc.)

## Notes
- The "World" tab in mobile is currently a vertical event list (not the D3 map yet). Map integration via /graph/world is stretch.
- Real consequence maps and predictions come from the EventConsequenceMap table + latest version.
- User tiers affect limits (free gets fewer nodes, no confidence, etc.).

## Mobile Layout / Responsiveness (started)
- Basic: Used flex, padding adjustments, Dimensions if needed in future.
- To improve further: Add Platform.OS checks, scale fonts for small screens, horizontal scroll for pills on tiny devices.
- Current screens (list, following, search, event) use consistent flex containers — test on device/simulator.

## Deploy
- Mobile: `eas build --platform android/ios --profile preview` (or production).
  Set EXPO_PUBLIC_API_URL to your hosted backend.
- Backend: `docker-compose up --build` (dev). For prod: Railway, Fly.io, or similar using the Dockerfile + compose (remove reload/volumes, set production env).
- Health: curl http://localhost:8000/health
- After deploy, update build-status.html with the public URL.
- Seeder + lean scheduler work in prod too (run seed once on fresh DB).
