# The Narrative — Quickstart (plug & play)

One command. No Python, no database setup, no config. Real data included.

## Run it

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) (one-time).
2. In this folder:
   ```bash
   docker compose up
   ```
3. Open **http://localhost:8080**
4. Sign in with **any email + any password** (one-click demo auth).

That's it. You're looking at the real terminal: a world of events, each mapped
to its downstream consequences with evidence, on real data (~993 events).

- Web app:    http://localhost:8080
- API + docs: http://localhost:8000/docs

## What's running

`docker compose up` starts four things and wires them together:

| Service  | What it is                                        |
|----------|---------------------------------------------------|
| postgres | Database — auto-loads the bundled real data on first boot |
| redis    | Cache / queue                                     |
| api      | FastAPI backend (consequence engine + endpoints)  |
| web      | The terminal UI (nginx; proxies `/api` to the backend) |

The first boot takes a minute (builds images, loads the seed). Later boots are fast.

## Optional: run the live pipeline

To continuously ingest news and generate fresh consequence maps + predictions,
add real keys to `.env.docker` (`ANTHROPIC_API_KEY`, `VOYAGE_API_KEY`) and run:

```bash
docker compose --profile pipeline up
```

## Reset

```bash
docker compose down -v   # wipes the database volume; next `up` reloads the seed
```
