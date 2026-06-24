# Deploy Guide — The Narrative (beta)

Turnkey deploy: **backend → Railway**, **frontend → Vercel**. Everything in the repo
is prepped; this guide is the checklist once you create the accounts. The frontend
calls the API at the relative path `/api/v1`, and Vercel rewrites that to Railway
(`vercel.json`), so the browser sees one origin — no CORS to fight.

---

## 0. Gather secrets first
The pipeline runs free/local by default (Ollama + fastembed) — no AI keys required.
See `docs/COST.md`. The keys below are **optional** unless you opt into paid providers.
- **Anthropic** API key (`ANTHROPIC_API_KEY`) — optional; only used when
  `PAID_APIS_ENABLED=true` and `LLM_PROVIDER=anthropic`.
- **Voyage** API key (`VOYAGE_API_KEY`) — optional; only used when
  `PAID_APIS_ENABLED=true` and `EMBEDDINGS_PROVIDER=voyage`.
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
   - `REDIS_URL`, `ANTHROPIC_API_KEY`, `VOYAGE_API_KEY`, `SECRET_KEY`.
   - `APP_ENV=production`, `APP_BASE_URL=https://<your-vercel-domain>`,
     `ALLOWED_ORIGINS=https://<your-vercel-domain>`.
   - Stripe: `STRIPE_SECRET_KEY`, `STRIPE_PRICE_ID` (webhook secret added in step 4).
4. **Deploy.** The `api` service runs `alembic ... upgrade head` then gunicorn, and
   exposes `/health` for the healthcheck. First boot auto-migrates the DB.
5. **Workers (cost control):** the full `scheduler` runs the paid mapping (Claude) +
   embedding (Voyage) workers. For a cheap beta, you can **pause** the heavy worker
   services in Railway and keep only `api` (+ optionally a free-feed loop) running —
   the live free feeds (quakes/storms/launches/market) still flow via the
   `hazard_ingest`/`market_ingest` steps.
6. Note the public API URL, e.g. `https://narrative-api-production.up.railway.app`.

---

## 2. Frontend → Vercel

1. **Import the same GitHub repo.** Vercel reads `vercel.json` (build `cd web && npm
   install && npm run build`, output `web/dist`, SPA fallback).
2. **Edit `vercel.json`** → replace `__RAILWAY_API_HOST__` in the `/api/(.*)` rewrite
   `destination` with your real Railway API host (no scheme), e.g.
   `narrative-api-production.up.railway.app`. Commit.
3. **Env / secrets:** the frontend needs no map token (the world map is d3/topojson).
   Leave `VITE_DEMO_MODE` unset/false for a real beta.
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
