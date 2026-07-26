# Narrative — Architecture (the machine, not the mission)

> Structure, where everything lives, how it runs, and how it goes forward.
> Verified against the code 2026-07-20. Companion to root [`STATUS.md`](../STATUS.md).
> For *what it does / who it's for*, see [`POSITIONING.md`](./POSITIONING.md).

## 1. Runtime topology (`docker-compose.yml` — 7 services)

| Service | Role | Port |
|---|---|---|
| **postgres** | DB with `pgvector` (events, articles, users, predictions, embeddings) | 5432 |
| **redis** | Cache + shared rate-limit store across API workers | 6379 |
| **ollama** | Local LLM runtime (llama3.2 text + llava vision) — the $0 AI | 11434 |
| **api** | FastAPI backend (`backend/main.py`) | 8000 |
| **scheduler** | Continuous background pipeline (`backend/scheduler.py`) | — |
| **web** | React/Vite frontend | 5173 |
| **pgadmin** | DB admin UI (dev only) | 5050 |

Named volumes persist DB, models, node_modules, embedding cache. The **scheduler
is why prod needs a stateful host** (Railway), not serverless.

**Prod:** frontend → Vercel; api + scheduler + Postgres/Redis → Railway
(`railway.toml`); `render.yaml` = undeployed standby. LLM is `off` in prod
(honest-degraded); local Docker runs it live at $0.

## 2. Code tree by subsystem

### `backend/` — the brain
- **`main.py`** FastAPI app (routes, middleware, security, rate-limit) ·
  **`scheduler.py`** worker loop · **`config.py`** all settings/knobs ·
  **`database.py`** · **`taxonomy.py`** categories + INT disciplines (single
  source of truth) · **`geo.py`** · **`mcp_server.py`** (engine-as-MCP for agents)

- **`api/routes/`** — API surface, one file per resource: `events`, `feed`,
  `exposure`, `graph`, `chat`(analyst), `imint`, `geolocate`, `benchmark`,
  `osint`, `search`, `vessels`, `aircraft`, `market`, `auth`, `users`, `follows`,
  `notifications`, `meta`, `admin`, `stripe_routes`. Support: `dependencies.py`,
  `rate_limit.py`.

- **`consequence_engine/`** — **core IP, deterministic, no serving-time LLM:**
  `importance_scorer` (rules-based scoring) · `embedder`+`clusterer`+
  `cluster_logic`+`title_dedup` (articles→deduped events) · `graph_connector`+
  `graph_scoring` (event↔event graph) · `propagation` (consequence math) ·
  `tracer` (chain per event) · `corroboration` (≥2-source gate — **wedge**) ·
  `consensus_mapper` · `evolution_tracker`+`evolution_logic` (narrative drift) ·
  `calibration` (accuracy scoring).

- **`services/`** — LLM-touching + smart services: `llm` (provider-abstracted
  gateway) · `analyst` · `operator_loop`+`operator_tools` (agentic operator) ·
  `reasoner` (deep OODA) · `source_reliability` (Admiralty grading — **wedge**) ·
  `imint`+`imint_event` · `geolocate` · `osint_agent`/`osint_enrich`/
  `osint_extract` · `cost_guard`+`cost_alert` (hard caps) · `runtime_config`.

- **`workers/`** — 16 pipeline stages (see §3): `scrape`, `feed`, `embed`,
  `cluster`, `importance`, `mapping`, `graph`, `exposure_snapshot`,
  `hazard_ingest`, `market_ingest`, `osint_ingest`, `evolution`, `archive`,
  `alert`, `outcome` (grades predictions), `benchmark` (scoreboard).

- **`feeds/`** — keyless sources: `gdelt`, `gdacs`, `usgs`, `weather`, `cyber`,
  `market`, `launches`, `sanctions`, `chokepoints`, `spaceweather`, `rss_osint`,
  `mastodon_osint`, `gdelt_osint`, `osint_threatintel`; `synthesize` (→sectors),
  `_live_check`.
- **`scrapers/`** — `engine`, `rss_parser`, `bs4_scraper`, `playwright_scraper`,
  `sources`.
- **`models/`** — SQLAlchemy tables: `narrative_event`, `article`, `source`,
  `event_connection`, `event_consequence_map`, `event_revision`,
  `exposure_snapshot`, `prediction_outcome`, `benchmark_ledger`,
  `benchmark_runs`, `osint_triage_decision`, `market_snapshot`, `user`,
  `app_config`, `pipeline_metrics`, `segment_feed_cache`, `admin_log`.
- **`migrations/`** — 16 Alembic migrations · **`admin/`** — maintenance scripts.

### `web/` — the frontend (React + Vite)
- **`src/App.jsx`** router · **`main.jsx`** entry · **`index.css`**
- **`pages/`** — `Landing`, `Auth`, `Onboarding`, `WorldView` (map/feed),
  `EventDetail` (chain), `Analyst`, `IntFusion` (`/int`), `GeoLocate`,
  `Following`, `Benchmark` (public scoreboard), `WiproDemo` (`/wipro`), `Settings`.
- **`components/`** — `ExposurePanel`, `HowThisAffectsYou`, `LensSwitcher`,
  `DeckView`, `TierGate`, `InitializingScreen`; `graph/` (`WorldMap`,
  `EventGraph`, `ConsequenceTrace`, `GlobeControls`); `layout/` (`FeedHeader`,
  `MobileNav`); `auth/` (`PrivateRoute`); `ui/`, `livenews/`.
- **`lib/`** — `api`, `propagation`, `taxonomy`, `tiers`, `colors`/`theme`/
  `exposureColor`, `geoAssoc`/`countries`, `vesselData`/`aircraftData`, `bias`,
  `analogs`, `demoMode`/`mockData`.
- **`hooks/`** — `useEventFeed`, `useExposure`, `useConsequenceTrace`,
  `useEventGraph`, `useWorldGraph`, `useVesselFeed`, `useAircraftFeed`,
  `useFollowing`, `useUser`, `useProfile`, `useSearch`, `useTheme`, …
- **`contexts/`** — `FollowingContext`, `ThemeContext` · **`admin/`** —
  `AdminLayout`, `PipelineMonitor`, `CostDashboard` · **`data/wipro/`** — demo data.

### `scripts/` — operational tooling
Benchmark/proof (`benchmark_score`, `external_benchmark`, `backtest_cpe`,
`validate_calibration*`, `publish_ledger`); ops (`analyst`,
`recompute_connections`, `backfill_prediction_outcomes`,
`refresh_osint_framework`, `check_osint_links`); run/test (`run_backend_tests`,
`smoke_test`, `_run_api`, `_wait_ready`); packaging (`package_frontend`,
`dump_for_railway`, `build_*_pdf`, `boot_intro`).

## 3. How data flows (verified)

The scheduler runs **16 workers as independent concurrent asyncio tasks, each on
its own interval** — NOT a strict sequence. Ordering below is the *logical data
dependency* (each stage pulls whatever the prior stage left ready); the timers
just have to be tight enough to keep it flowing:

```
feeds/ + scrapers/  →  workers: scrape → embed → cluster → importance → mapping
                                → graph → exposure_snapshot   (+ hazard/market/osint ingest)
        │                                   │ writes
   consequence_engine/ (the math)  ─────────┤
                                            ▼
                                       models/ (Postgres + pgvector)
                                            ▲ reads
                              api/routes/  ─┘  →  web/ (hooks → pages)

   outcome_worker + benchmark_worker  →  calibration + ledger  →  /benchmark
```

Scheduler drives ingestion on timers; api serves reads on demand; the
deterministic engine is the shared core.

## 4. Design assessment (honest)

**Sound & resilient:** every worker is wrapped in try/except (one crash can't
kill the loop); stages are idempotent (dedup/upsert), so concurrent independent
runs are safe; pull-based staging needs no job queue. Correct for this stage.

**Optimization opportunities (noted, not yet done):**
1. **Startup thundering herd** — all 16 workers fire at once on boot with no
   stagger/jitter → the documented cause of scheduler OOM (137) under <8 GB.
   Fix: stagger initial starts / add jitter.
2. **Stale docstring** — `scheduler.py` says "11 workers"; there are 16.
3. **Latency = sum of intervals** — an event waits for each stage's next tick.
   Fine for this domain; event-driven triggering is the eventual upgrade.
4. Single scheduler process = single point of failure (acceptable for MVP; one
   host owns the ledger by design — see `benchmark_publish_enabled`).

## 5. Taking it forward

### 5a. The platform (one engine, forever)
Growth follows the phased plan
(`~/.claude/plans/get-bak-wi-the-dazzling-umbrella.md`): P1 aim the UI · P2
hygiene · P3 one config-driven dashboard · P4 the Aug-12 proof · P5 gap features
(asset registry → alerting → branded advisories). **Principle: never fork the
engine** — one canonical `consequence_engine/` + thin per-client surfaces.

### 5b. Individual clients (the repeatable motion)
Serving many clients off ONE engine = **multi-tenancy by config + scoping, not
forks.** The model mirrors the incumbents' own onboarding (from the Wipro intel:
vendor provisions an org account + sub-users, configures assets/regions, brands
it, sets the distribution list). A client is a **tenant config layer** over the
shared event corpus:

1. **Provision the tenant** — an org account + role-scoped sub-users
   (`models/user.py`, `api/routes/users.py`, admin/sub-user roles).
2. **Load their world** — their assets/sites + regions + disciplines of interest
   → this is the **exposure lens** scoping (`exposure_snapshot`, `LensSwitcher`,
   `ExposurePanel`). Needs the Phase-5 **asset/location registry**.
3. **Brand + surface** — one **config-driven dashboard** filtered to their lens
   with their logo (Phase 3; `/wipro` becomes a saved config, not a page).
4. **Deliver** — graded advisories pushed to their distribution list (Phase-5
   **alerting**) in their **branded format** (Phase-5 export).
5. **Prove** — the shared `/benchmark` track record backs every client; trust is
   platform-wide, earned once.

The shared event corpus + engine are computed **once** for everyone; per-client
cost is only the scoped view + their alerts. That's the margin story and the
reason not to fork: every new client rides the same proven core.
