# Narrative — Run the Beta Locally (macOS)

This guide gets the Narrative beta running on a Mac. There are two ways:

- **Path A — Frontend only, against the LIVE backend (recommended, ~5 min).**
  Needs only Node + Git. No Docker, no database, no Python. You get real, live data.
- **Path B — Full local stack (offline / development).**
  Runs the backend, Postgres, and Redis on your machine with Docker, plus sample data.

Start with **Path A** unless you specifically need to run the backend yourself.

---

## 1. Install prerequisites

Install [Homebrew](https://brew.sh) if you don't have it, then:

```bash
# Node.js 20+ and Git (needed for both paths)
brew install node git

# Docker Desktop — only needed for Path B
brew install --cask docker
```

After installing Docker Desktop, **open it once** so the engine starts (Path B only).

Check versions:

```bash
node --version   # should be v20 or newer
git --version
```

## 2. Get the code

```bash
git clone https://github.com/Bigreddroid/narrative.git
cd narrative
```

---

## Path A — Frontend against the live backend (recommended)

### A1. Configure the frontend

```bash
cd web
cp .env.example .env
```

Open `web/.env` and set these two lines:

```
VITE_API_TARGET=https://narrative-production-2a1c.up.railway.app
VITE_DEMO_MODE=false
```

That points the local app at the live production backend. (Optional: add
`VITE_AISSTREAM_KEY=<key>` for live ship tracking — see the bottom section.)

### A2. Install and run

```bash
npm install
npm run dev
```

Open **http://localhost:5173** in your browser.

### A3. Log in

Use the beta account:

- **Email:** `enterprise@narrative.dev`
- **Password:** `betatest1`

You should see live events, the world map, the consequence graph, and the analyst.
That's it — you're on the beta.

---

## Path B — Full local stack (offline / development)

This runs everything on your Mac and loads a sample database so the app isn't empty.

### B1. Create the backend env file

The backend container reads a `.env` at the repo root. A blank one is fine for local
dev (the compose file already sets the database, Redis, and `APP_ENV=development`):

```bash
touch .env
```

### B2. Start the database, cache, and API

```bash
docker compose up postgres redis -d
```

Load the sample data (~8 MB dump of real events):

```bash
docker compose exec -T postgres pg_restore -U narrative -d narrative \
  --no-owner --clean --if-exists < scripts/narrative.dump
```

Then start the API (it runs database migrations automatically on boot):

```bash
docker compose up api -d
```

Confirm it's healthy:

```bash
curl http://localhost:8000/health      # -> {"status":"ok",...}
```

### B3. Run the frontend

Leave `VITE_API_TARGET` **empty** so the app talks to your local backend on :8000:

```bash
cd web
cp .env.example .env      # keep VITE_API_TARGET blank, VITE_DEMO_MODE=false
npm install
npm run dev
```

Open **http://localhost:5173** and log in with the same beta account as Path A.

### B4. Stop everything

```bash
docker compose down          # stop containers (keeps data)
docker compose down -v       # also delete the local database volume
```

---

## Optional — live ship tracking (Maritime layer)

Both paths show a simulated fleet by default. For real vessels, get a free key at
[aisstream.io](https://aisstream.io) and add to `web/.env`:

```
VITE_AISSTREAM_KEY=<your-key>
VITE_AIS_GLOBAL=true
```

Restart `npm run dev` (Vite bakes this in at start-up).

---

## Troubleshooting

- **`docker: command not found` / containers won't start** — Docker Desktop isn't
  running. Open the Docker app and wait for the whale icon to settle (Path B only).
- **Port already in use (5173 or 8000)** — something else is using it. Stop that
  process, or change the port (`npm run dev -- --port 5174`).
- **App loads but no data (Path B)** — you skipped the `pg_restore` step in B2. A fresh
  local database is empty until you load the sample dump.
- **App loads but no data (Path A)** — check `VITE_API_TARGET` in `web/.env` is exactly
  the URL above and restart `npm run dev`; the target is read only at start-up.
- **Login fails** — use `enterprise@narrative.dev` / `betatest1` exactly (case-sensitive).
