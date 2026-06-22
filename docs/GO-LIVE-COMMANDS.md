# Narrative — Go-Live Commands (Railway + Vercel)

Ordered, copy-paste runbook to take the stack live. Steps marked **[dashboard]** must be done
in the web UI (account/billing/plugins); everything else is CLI. Companion to `docs/Deploy.pdf`
(the why) — this is the how. Backend → Railway (`api` + `scheduler` + Postgres + Redis);
frontend → Vercel.

> **Three traps this runbook is built to avoid** (verified against the code):
> 1. The app's engine needs the **`+asyncpg`** driver. Railway emits plain `postgresql://`,
>    but `backend/config.py` now normalizes any `postgresql://`/`postgres://` to
>    `postgresql+asyncpg://` automatically, so either form boots cleanly.
> 2. Postgres must have **pgvector** (`CREATE EXTENSION vector` runs in migrations + the dump).
> 3. `vercel.json` no longer carries the Mapbox token — set it as a **Vercel env var**.

## Prerequisites (one-time)
```bash
npm i -g @railway/cli vercel      # Railway + Vercel CLIs
railway --version && vercel --version
# Postgres client tools (pg_restore) — e.g. Postgres.app / apt install postgresql-client / choco install postgresql
pg_restore --version
```
Rotate the **Anthropic** and **Voyage** keys at their consoles first — the old ones leaked via
`.env`. Keep the new values handy (Railway only; never commit them).

## Step 1 — Fresh data snapshot (local)
```bash
cd "<repo root>"
bash scripts/dump_for_railway.sh        # writes scripts/narrative.dump (gitignored)
```

## Step 2 — Railway project + managed data stores  **[dashboard]**
- New Project → **Deploy from GitHub repo** → pick `Bigreddroid/narrative`. It builds from the
  `Dockerfile` per `railway.toml` (two services: `api`, `scheduler`).
- **New → Database → Postgres**, and **New → Database → Redis**.
- Confirm the Postgres has **pgvector**: open its shell and run `CREATE EXTENSION IF NOT EXISTS vector;`
  (current Railway Postgres images include it). If it errors, redeploy Postgres from Railway's
  **pgvector** template and reattach.

## Step 3 — Service variables (set on BOTH `api` and `scheduler`)  **[dashboard]**
Variables tab → Raw editor. The DB URL is **composed** (do not paste the plugin's plain URL):
```
DATABASE_URL=postgresql+asyncpg://${{Postgres.PGUSER}}:${{Postgres.PGPASSWORD}}@${{Postgres.RAILWAY_PRIVATE_DOMAIN}}:5432/${{Postgres.PGDATABASE}}
REDIS_URL=${{Redis.REDIS_URL}}
APP_ENV=production
SECRET_KEY=<paste: openssl rand -hex 32>
ALLOWED_ORIGINS=https://<your-app>.vercel.app
APP_BASE_URL=https://<your-app>.vercel.app
ANTHROPIC_API_KEY=<rotated>
VOYAGE_API_KEY=<rotated>
```
(Use the placeholder Vercel domain for now; correct it in Step 8 once the real domain exists.)
Optional vars — Stripe / Supabase / Sentry / SMTP / R2 — from `.env.production.example`; all
degrade gracefully if blank. **Enable Sentry** (`SENTRY_DSN`) if you have it.

## Step 4 — Deploy the API (migrations run automatically)
The `api` start command is `alembic -c backend/alembic.ini upgrade head && gunicorn …`, so the
first deploy creates the schema at head `006`.
```bash
railway link            # select the project + environment
railway up --service api
railway logs --service api      # watch: "alembic … running upgrade … 006", then gunicorn boot
```

## Step 5 — Load the real data
Copy the Postgres **public** connection string from the dashboard (Postgres → Connect →
`postgresql://…@<proxy>.rlwy.net:<port>/railway`; note: **plain** scheme, not `+asyncpg`).
```bash
pg_restore --no-owner --no-acl --clean --if-exists \
  -d "postgresql://USER:PASS@<proxy>.rlwy.net:PORT/railway" \
  scripts/narrative.dump
```
`--clean --if-exists` swaps the freshly-migrated empty schema for the real one; the dump carries
`alembic_version=006`, so the version stays consistent. (If `CREATE EXTENSION vector` errors here,
finish Step 2's pgvector fix and rerun.)

## Step 6 — Verify the API
```bash
API_BASE="https://<railway-api-host>" bash scripts/smoke_test.sh
# expect: /health 200 (env=production), /docs 404, /api/v1/events/ reachable
```

## Step 7 — Start the scheduler  (only AFTER key rotation — it spends Claude/Voyage credits)
```bash
railway up --service scheduler
railway logs --service scheduler        # workers tick: scrape → embed → cluster → map → exposure
```

## Step 8 — Frontend on Vercel
```bash
vercel link                              # repo root; creates the project
vercel env add VITE_MAPBOX_TOKEN production     # paste your Mapbox public token (pk.…)
# Do NOT set VITE_DEMO_MODE (unset = real data only).
```
Edit `vercel.json` → replace `__RAILWAY_API_HOST__` in the `/api/(.*)` rewrite with the Railway
`api` public host (no scheme), e.g. `narrative-api-production.up.railway.app`. Commit + push (CI
runs), then:
```bash
vercel --prod
```

## Step 9 — Close the CORS loop
Set the real Vercel domain into the Railway `api` (and `scheduler`) vars from Step 3:
```
ALLOWED_ORIGINS=https://<real-vercel-domain>
APP_BASE_URL=https://<real-vercel-domain>
```
Railway redeploys `api` on save.

## Step 10 — Full smoke test (API + frontend through the rewrite)
```bash
API_BASE="https://<railway-api-host>" \
WEB_BASE="https://<real-vercel-domain>" \
bash scripts/smoke_test.sh
# expect: SMOKE TEST PASSED
```

---
### Rollback / notes
- **App boots but DB errors** → `DATABASE_URL` is missing `+asyncpg` (Step 3). Migrations passing
  while the app fails is the tell (Alembic self-converts; the app doesn't).
- **`vector` type errors** → Postgres lacks pgvector (Step 2).
- **CORS errors in the browser** → `ALLOWED_ORIGINS` doesn't match the Vercel domain (Step 9).
- **Mapbox blank** → `VITE_MAPBOX_TOKEN` not set in Vercel *before* the build (it's build-time).
- Re-running Steps 4/7 (`railway up`) redeploys; data persists in the Postgres plugin across
  redeploys. Re-run Step 5 only to refresh the dataset (`--clean` makes it idempotent).
