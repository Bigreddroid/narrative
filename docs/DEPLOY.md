# Deploy Guide — The Narrative (beta)

Turnkey deploy: **backend → Railway**, **frontend → Vercel**. Everything in the repo
is prepped; this guide is the checklist once you create the accounts. The frontend
calls the API at the relative path `/api/v1`, and Vercel rewrites that to Railway
(`vercel.json`), so the browser sees one origin — no CORS to fight.

---

## 0. Gather secrets first
The pipeline runs free/local by default (Ollama + fastembed) — no AI keys required.
See `docs/COST.md`. The keys below are **optional** unless you opt into paid providers.
- **LLM is local-only** — `LLM_PROVIDER` accepts `ollama` (local/free) or `off`. There is
  no paid LLM provider (Anthropic was removed); no LLM API key exists or is needed. See
  §1.3 for the cloud posture, since Railway has no local Ollama.
- **Voyage** API key (`VOYAGE_API_KEY`) — optional; the only opt-in paid provider, used
  for embeddings solely when `PAID_APIS_ENABLED=true` and `EMBEDDINGS_PROVIDER=voyage`.
- The world map needs no token (d3/topojson).
- **Stripe** (test mode is fine to start): `STRIPE_SECRET_KEY`, a recurring **Price ID**
  (`STRIPE_PRICE_ID`), and later `STRIPE_WEBHOOK_SECRET`.
- A long random `SECRET_KEY` (JWT signing): `python -c "import secrets;print(secrets.token_urlsafe(48))"`.
- Optional: `AISHUB_USERNAME` (live ships), Sentry DSN.

---

## 1. Backend → Railway

1. **New Project → Deploy from GitHub repo** (this repo). Railway reads `railway.toml`
   (Dockerfile build; services: `api`, `scheduler`, + 11 pipeline workers).
2. **Add a Postgres with pgvector.** The schema runs `CREATE EXTENSION vector` + `pg_trgm`
   (migration `001`), so the DB image **must include pgvector** — use Railway's
   *Postgres (pgvector)* template/image, not vanilla Postgres. **Add Redis** too.
3. **Set variables** on the project (shared by all services) — see `.env.example`:
   - `DATABASE_URL` = the Railway Postgres URL, but with the async driver:
     `postgresql+asyncpg://USER:PASS@HOST:PORT/DB` (swap `postgresql://` →
     `postgresql+asyncpg://`).
   - `REDIS_URL`, `VOYAGE_API_KEY` (optional), `SECRET_KEY`.
   - `APP_ENV=production`, `APP_BASE_URL=https://<your-vercel-domain>`,
     `ALLOWED_ORIGINS=https://<your-vercel-domain>`.
   - Stripe: `STRIPE_SECRET_KEY`, `STRIPE_PRICE_ID` (webhook secret added in step 4).
   - **AI paths in the cloud (no local Ollama on Railway):** the LLM is local-only, so
     the default `LLM_PROVIDER=ollama` pointing at `localhost:11434` cannot reach a model
     in the cloud. Two supported postures:
     - **Ship without the local-LLM features (simplest, $0):** set `LLM_PROVIDER=off`.
       Every LLM-touching path degrades honestly rather than erroring — the Analyst chat
       returns a templated answer (flagged `degraded`), the agentic operator falls back to
       the deep reasoner, and IMINT/geolocate return `{available: false, reason}`. **No
       endpoint 500s** with the LLM off (verified across analyst, operator, imint,
       geolocate, reasoner). Everything else — feeds, map, exposure, scoring — is
       unaffected.
     - **Enable the full AI stack:** run Ollama as its own reachable service (a separate
       Railway service on the `ollama/ollama` image, or an external host) with the models
       pulled (`llama3.2` for text, `llava` for vision), then point `OLLAMA_BASE_URL` at
       it. Leave `LLM_PROVIDER=ollama`.
     Either way leave `EMBEDDINGS_PROVIDER=local` to keep embeddings free (fastembed).
   - **Live-news channels (optional iptv-org expansion):** the in-app player ships
     a curated set of **official** broadcaster streams by default (publisher HLS +
     official YouTube-live embeds — reliable, $0, keyless). The per-country *local*
     coverage already pulls from iptv-org on demand. To also expand the paid-tier
     channel list with iptv-org's bulk keyless HLS catalog, set
     `LIVE_NEWS_USE_IPTV_ORG=true` (default `false`). Note these are aggregated
     **unofficial restreams** (copyright/geo/uptime risk) — the curated officials
     always win on de-dupe, and a failed iptv-org fetch degrades gracefully to the
     curated set.
4. **Deploy.** The `api` service runs `alembic ... upgrade head` then gunicorn, and
   exposes `/health` for the healthcheck. First boot auto-migrates the DB, and every
   redeploy applies any new migrations automatically (migrations `008`+ are all guarded
   idempotent DDL, so re-running is safe).
   - **Upgrading an already-live prod (schema-drift heal):** if this prod was last
     deployed before mid-July 2026 it is at migration `011`; the deploy will apply `012`
     (`int_discipline` on events) and `013` (`disciplines[]` on users) on boot — no manual
     step. **But** a known prior drift left `osint_triage_decisions` (migration `009`)
     *missing while alembic-version was already past it*. Because that table's DDL is
     `CREATE TABLE IF NOT EXISTS`, `upgrade head` will **not** re-create it. If the OSINT
     triage table is absent in prod, heal it by running its idempotent DDL directly once
     (safe no-op if it already exists):
     ```sql
     CREATE TABLE IF NOT EXISTS osint_triage_decisions (
       id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
       external_id TEXT NOT NULL, source TEXT NOT NULL, kept BOOLEAN NOT NULL,
       reason TEXT NOT NULL, method TEXT NOT NULL, category TEXT,
       confidence DOUBLE PRECISION, importance INTEGER, title TEXT,
       created_at TIMESTAMPTZ NOT NULL DEFAULT now()
     );
     ```
     Check with `SELECT to_regclass('osint_triage_decisions');` (NULL ⇒ run the DDL above).
5. **Workers (cost control):** the `scheduler` runs the full pipeline — including the
   consequence **mapping** worker, which now uses the **local LLM** (Ollama, $0), not a
   paid provider. With `LLM_PROVIDER=off` (the cloud default when no Ollama is reachable)
   the mapping worker skips cleanly (`skipped: no_llm`) — events still ingest, cluster and
   score; they just don't get an LLM-written consequence chain. The only optionally-paid
   worker is embedding, and only if you set `EMBEDDINGS_PROVIDER=voyage`. For a lean beta
   you can **pause** the heavy worker services in Railway and keep only `api` (+ a
   free-feed loop) running — the live free feeds (quakes/storms/launches/market) still
   flow via the `hazard_ingest`/`market_ingest` steps.
6. Note the public API URL, e.g. `https://narrative-api-production.up.railway.app`.

---

## 2. Frontend → Vercel

1. **Import the same GitHub repo.** Vercel reads `vercel.json` (build `cd web && npm
   install && npm run build`, output `web/dist`, SPA fallback).
2. **Check `vercel.json`** → the `/api/(.*)` rewrite `destination` already points at
   the live Railway API host (`narrative-production-2a1c.up.railway.app`). If you
   deploy the backend to a different host, update that host here (no scheme) and commit.
3. **Env / secrets:** the frontend needs no map token (the world map is d3/topojson).
   - `VITE_DEMO_MODE=false` (real beta — never `true` in prod).
   - `VITE_AISSTREAM_KEY` = your free AISStream key (live ship tracking; without it
     the Maritime layer shows a clearly-badged simulated fleet).
   - `VITE_AIS_GLOBAL=true` to stream **all** active vessels worldwide (the memory
     cap auto-scales to ~15000; the canvas layer renders the full fleet). Leave
     unset/`false` to focus only on the maritime chokepoints the consequence model
     watches (lighter, smoother globe).
4. **Deploy.** You get `https://<project>.vercel.app` (add a custom domain if desired).

---

## 3. Connect the two
- Set Railway `APP_BASE_URL` and `ALLOWED_ORIGINS` to the final Vercel URL (custom
  domain if you added one), then redeploy `api`.
- Smoke test: open the Vercel URL → **Sign Up** with a fresh email + password → you
  should land authenticated on live data (map full of events, Exposure populated).

---

## 4. Stripe (payments)
1. In Stripe (test mode), create a **Product + recurring Price**; put the price id in
   `STRIPE_PRICE_ID`.
2. **Webhook:** add an endpoint pointing at
   `https://<your-vercel-domain>/api/v1/stripe/webhook` (it proxies to Railway), or
   directly at the Railway API. Subscribe to `checkout.session.completed`,
   `customer.subscription.updated`, `customer.subscription.deleted`,
   `invoice.payment_failed`. Copy the signing secret → `STRIPE_WEBHOOK_SECRET` on
   Railway; redeploy `api`.
3. Test: Settings → **Upgrade — Full Access** → Stripe Checkout (use test card
   `4242 4242 4242 4242`) → on success the webhook flips your tier free→paid and you
   return to `/settings?upgraded=1`.

> Until real Stripe keys are set, the Upgrade button shows
> *"Payments aren't enabled yet"* (the `/stripe/checkout` route returns 503) — the
> rest of the app is unaffected.

---

## 5. PWA / Add to Home Screen
The manifest, icon, service worker and meta tags are in place (`web/public/` +
`web/index.html`). On a deployed HTTPS URL: **iPhone Safari → Share → Add to Home
Screen**; Android/desktop Chrome shows an install prompt.

Optional polish: the icon is an SVG (`web/public/icon.svg`). For the crispest iOS
home-screen icon, drop in a `180×180` `apple-touch-icon.png` (and 192/512 PNGs) and
add them to `manifest.webmanifest` + the `apple-touch-icon` link.

---

## 6. Post-deploy checklist
- [ ] `https://<api>/health` returns `{"status":"ok"}`.
- [ ] Sign up / sign in works on the live site (real account, not dev).
- [ ] Map + feed + Exposure show **live** data (not the demo fallback).
- [ ] Stripe test checkout upgrades the tier.
- [ ] App installs to the iPhone home screen and launches standalone.
</content>
