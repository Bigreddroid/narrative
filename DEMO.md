# The Narrative — Plug-and-Play Demo

Run the whole app on your machine with **one command**. No API keys, no config,
no accounts to sign up for. It starts with an **empty, clean database** and builds
itself **live** — with internet, the workers scrape real feeds, embed and cluster
them locally, and the feed/map fill in with fresh real data within a few minutes.
Nothing is pre-baked or stale.

## Requirements

- **[Docker Desktop](https://www.docker.com/products/docker-desktop/)** (Windows, macOS, or Linux) — that's it. Works on Apple Silicon (arm64) and Intel.
- **Give Docker ≥10–12 GB RAM** (Docker Desktop → Settings → Resources). The local
  models (llava vision + bge-large embeddings) load into memory alongside the
  scheduler's workers; with too little RAM the scheduler can get OOM-killed. The
  scheduler now auto-restarts and caches the embedding model, but 10–12 GB is the
  comfortable floor now that ingest refreshes every ~5 minutes.
- **~20 GB free disk.** Measured footprint: Docker images ~11 GB (the Ollama image
  alone is ~8 GB) + volumes ~7 GB (pulled AI models) + build cache. The AI models
  (~7 GB) download once on first run and are cached in named volumes thereafter.
- These ports free on your machine: **5173, 8000, 5432, 6379, 5050**.
- Internet on first boot (to pull images + models). First boot is the slow one
  (~10–20 min on a normal connection); after that it runs offline too.
- Heads-up: the AI analyst runs **locally on CPU** ($0, no keys), so answers take
  roughly **10 seconds** (longer on the first, cold call). That's expected.

## Run it

From the project folder, use the launcher — it plays the intro, then brings the
whole stack up:

- **Windows** (CMD — double-click it, or run in a terminal):
  ```
  start.cmd
  ```
- **macOS / Linux** (terminal):
  ```bash
  ./start.sh
  ```

Prefer plain Docker? `docker compose up` does the same thing without the intro.

First boot takes a few minutes — it downloads Postgres, Redis, the Ollama LLM
runtime, and the `llama3.2` + `llava` models, then creates a fresh database.
**Wait until you see the API and web logs settle**, then open:

| What | URL |
|------|-----|
| **The app (start here)** | http://localhost:5173 |
| API docs | http://localhost:8000/docs |
| Database admin (pgAdmin) | http://localhost:5050 |

### Log in

On the login screen use:

- **Email:** `enterprise@narrative.dev`
- **Password:** `betatest1`

That's an enterprise-tier demo account — you'll see the full feature set.

## What you're looking at

- **Feed / "For You"** — real events with grounded consequence chains.
- **World map** — live hotspots (d3 + topojson, no map token needed).
- **Analyst** — ask questions; answered by the **local** LLM (Ollama), $0.
- **Exposure / lens** — re-scope the whole app to a region.

## It's fully live — nothing pre-baked

The database starts **empty**. In the background the **scheduler** runs 17 workers
that scrape keyless feeds (GDELT, GDACS, weather, RSS, …), embed them **locally**
(fastembed, no key), cluster them into events, and map consequences with the
**local** LLM. So within a few minutes of first boot the feed and map populate with
**real, fresh** data — and keep growing as long as it has internet.

The first couple of minutes the feed may look sparse while the first scrape +
embed + cluster cycle completes — that's expected. Watch it happen with
`docker compose logs -f scheduler`.

Everything runs at **$0** — no paid API keys are used. (Paid providers like
Anthropic/Voyage are strictly opt-in and off by default.)

## Talk to the analyst from your terminal

You can ask the same AI analyst straight from a terminal — no browser needed. The
stack must be up.

```bash
./analyst.sh "biggest risk to shipping right now"     # mac/linux
analyst.cmd "biggest risk to shipping right now"      # windows

./analyst.sh --deep "how could a Strait of Hormuz closure hit me"
./analyst.sh --image ./photo.jpg                      # geolocate a photo (vision model)
```

It shows a live "thinking…" spinner while the local model works, then prints the
grounded answer with its sources. Text questions use the text model; `--image` uses
the vision model — routed by use case, $0, no keys.

## Handy commands

```bash
docker compose up -d          # run in the background
docker compose logs -f api    # follow the API logs
docker compose logs -f scheduler   # watch live data collection
docker compose down           # stop (keeps the database + models)
docker compose down -v        # stop and wipe everything (fresh start next time)
```

## Notes / troubleshooting

- **First run is the slow one** — model downloads (~2 GB) and the local embedding
  model (~1.3 GB) are cached in Docker volumes, so later boots are fast.
- **Port already in use?** Something else is on `5173`, `8000`, `5432`, `6379`,
  or `11434`. Stop it, or edit the `ports:` in `docker-compose.yml`.
- **Restarting keeps your data** — `docker compose down` then `up` resumes with
  everything the workers have collected so far. Use `docker compose down -v` for a
  clean slate (empty DB again, and it rebuilds live from zero).
- This is a **local demo** build (`APP_ENV=development`). Don't expose it to the
  internet as-is — it uses a public dev signing key by design.
