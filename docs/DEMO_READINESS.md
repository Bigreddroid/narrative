# Demo readiness — prod topology, pre-demo checklist, and verified posture

The operator-facing companion to [`CALIBRATION.md`](./CALIBRATION.md) (what the engine can *prove*)
and [`DEPLOY.md`](./DEPLOY.md) (how it ships). This page answers: *is the live product complete and
safe to demo, and what do I check in the five minutes before I present it?*

---

## 1. Production topology

| Layer | Host | Notes |
|---|---|---|
| **Frontend** | **Vercel** (from `main`) | React + Vite static build; sets its own edge TLS/HSTS. |
| **API** | **Railway** — web service | FastAPI + Gunicorn (`--workers 2`); `/health` returns 200. |
| **Scheduler** | **Railway** — background worker | Persistent worker (feeds + CPE `outcome_worker`). This worker is *why* the app needs a stateful host, not serverless. |
| **Database** | **Railway Postgres** (pgvector) | Embeddings + the `prediction_outcomes` calibration set. |
| **Cache / limits** | **Railway Redis** | Shared rate-limit store across the 2 workers (exact limits). |
| **Standby** | **Render** (`render.yaml`, **undeployed**) | Parity blueprint — the only non-downgrade peer with a native background-worker type. Activate only if Railway is unavailable. |

**LLM posture in prod:** `LLM_PROVIDER=off` on Railway (no Ollama in the cloud). Every LLM-backed
surface therefore runs in **honest-degraded** mode in prod — see §3. Local Docker bundles Ollama and
runs the LLM paths live at $0.

---

## 2. Before-a-live-demo checklist

1. **Frontend is current.** Confirm Vercel prod is deployed from the latest `main` commit.
2. **API is up.** `curl -s https://<railway-api-domain>/health` → `{"status":"ok",...}` (200).
   - If demoing against the local Docker stack, the API is `:8001`; **restart web after any `git pull`**
     — Vite-in-Docker doesn't see OneDrive-bind-mount changes until `docker compose restart web`.
3. **Relight the demo corpus** (the `/wipro` + `/int` fusion strips). The 72h corroboration gate reads
   `first_detected_at`; seeds age out. Re-run the seeder so it **stamps `first_detected_at` +
   `last_updated_at` = now** on its `wipro_demo*` rows (`scripts/seed_scenario.py`) — this is the
   documented relight step, verified to bring the strip back.
4. **Sign in.** Beta creds `enterprise@narrative.dev` / `betatest1` (provisioned on demand; in prod
   they work only when `beta_accounts_enabled` is set — see §4).
5. **Smoke the surfaces:** map/feed/exposure populate → analyst + operator respond (honest-degraded if
   no cloud LLM) → `/wipro` deck renders → no console errors.

---

## 3. The degraded-path guarantee (verified)

With `LLM_PROVIDER=off`, **every** LLM surface must return an honest "unavailable/templated" result and
**never a 500**. Audited and confirmed for all five:

| Surface | Degrade behavior | Test lock |
|---|---|---|
| **analyst** | templated grounded answer, `degraded:true` | `analyst_test` (+ broad `except`) |
| **operator** | falls back to the deep reasoner, then templated | `operator_test` |
| **reasoner** (deep) | stops the OODA chain, returns templated | **`reasoner_test`** (added — was untested) |
| **imint** | `{available:false, reason, scope}` | `imint_test` |
| **geolocate** | `{available:false, reason}` | `geolocate_test` |

Locked in CI by the backend suite (**24 modules** including the new `reasoner_test`).

---

## 4. Security posture (verified — no open code issue)

- **Auth throttling is live and wired.** `slowapi` `Limiter` is registered in `main.py`
  (`app.state.limiter` + exception handler + `SlowAPIMiddleware`), keyed by **hashed** bearer token
  (never the raw secret) with an IP fallback, backed by **Redis** so the limit is exact across both
  Gunicorn workers. `/login` and `/signup` carry `@limiter.limit("10/minute")`; the default is
  `120/minute`; `/health` is exempt.
- **Privileged endpoints are prod-gated.** `/dev-login` returns 403 when `APP_ENV=production`; the
  hard-coded beta accounts only authenticate in prod when `beta_accounts_enabled` is explicitly set
  (non-prod always allows them for local demos).
- **Secret hygiene.** `secret_key` has an insecure-default guard that fails startup in production;
  the rate-limit key hashes tokens rather than logging them.
- **Security headers** on every response: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: no-referrer`, `X-XSS-Protection: 0`.

**Documented follow-ups (deliberate, not defects):**
- **HSTS / CSP are delegated to the TLS edge** (Railway/Vercel) by design (`main.py` comment). ✅
  **Verify** the edge actually emits `Strict-Transport-Security` on the **API** domain; if Railway does
  not, add it at the app layer as the fallback. A tailored CSP for the Mapbox/React app is a good
  future hardening but must be browser-tested before shipping (it can silently break the map/tiles).
- **AISStream key is client-side** (`useVesselFeed.js` opens the AIS WebSocket from the browser, so
  `VITE_AISSTREAM_KEY` is baked into the bundle). This is architectural (direct browser→AIS streaming)
  and a low-value free-tier key — acceptable for now; proxy it through the API if a higher-value key is
  ever used.

---

## 5. Verify commands

```bash
# Frontend production build (vite is not on PATH — invoke it directly)
node web/node_modules/vite/bin/vite.js build      # run from web/

# Full backend suite (24 modules)
bash scripts/run_backend_tests.sh

# Calibration pipeline proof (offline, deterministic)
python scripts/validate_calibration.py --report calibration_report.txt

# Prod liveness
curl -s https://<railway-api-domain>/health
```
