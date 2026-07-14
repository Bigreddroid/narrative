# The Narrative — Install Guide (Mac & Windows)

Run the whole intelligence platform locally on one machine, with one command.
Live event feed, AI analyst, world map, personalized exposure — all self-contained.
Runs at **$0 — no API keys, no accounts** (the AI is local).

---

## Fastest path — the `mithrasayshello` command

Install Docker Desktop first (see Requirements below). Then, from a terminal:

**macOS / Linux** — clone and run in one go:
```bash
git clone https://github.com/Bigreddroid/narrative.git && cd narrative && ./mithrasayshello
```
Or straight from the internet (it clones itself):
```bash
curl -fsSL https://raw.githubusercontent.com/Bigreddroid/narrative/main/mithrasayshello | bash
```

**Windows** (PowerShell or CMD):
```powershell
git clone https://github.com/Bigreddroid/narrative.git ; cd narrative ; .\mithrasayshello.cmd
```

`mithrasayshello` checks Docker is running, clones the project if you don't have it
yet, then brings the whole stack up. First run downloads images + the local AI
models (once). When it settles, open **http://localhost:5173**.

---

## What you're installing

A complete local stack (no cloud account, no API keys):

- **Live event pipeline** that auto-refreshes every ~5 minutes from free public feeds.
- **Local AI** (runs on your machine, offline) — the analyst, embeddings, and vision model.
- **Web app** at `http://localhost:5173`, backed by an API at `http://localhost:8000`.
- **Postgres + Redis** for storage; data persists across restarts.

---

## Requirements (Mac & Windows are the same)

| | Requirement |
|---|---|
| **Software** | [Docker Desktop](https://www.docker.com/products/docker-desktop/) — that's the only install. Works on Apple Silicon (M1/M2/M3), Intel Mac, and Windows. |
| **RAM for Docker** | **≥ 10–12 GB** — Docker Desktop → Settings → Resources → Memory. The AI models load into memory; too little RAM and the pipeline gets killed. |
| **Disk** | **~23 GB free.** (~18 GB if you skip the vision model.) |
| **Internet** | Needed on first run (downloads) and for live event updates. The AI itself runs offline. |
| **Free ports** | 5173, 8000, 5432, 6379, 5050 |

---

## Install — macOS

1. **Install Docker Desktop for Mac** from the link above. Open it once; wait for the whale icon in the menu bar to go steady (Docker is running).
2. **Give it enough RAM:** Docker Desktop → **Settings → Resources → Memory → 10–12 GB → Apply & Restart**.
3. **Copy the project folder** onto the Mac (USB, AirDrop, or `git clone`).
4. Open **Terminal**, `cd` into the folder, and run:
   ```bash
   ./start.sh
   ```
   (If it says permission denied: `chmod +x start.sh` then re-run.)
5. Wait for the first-run download (~18 GB of images + AI models — **once**, then cached).
6. Open **http://localhost:5173** and log in.

---

## Install — Windows

1. **Install Docker Desktop for Windows** from the link above. It will enable WSL2 if needed (follow its prompt, reboot if asked).
2. **Give it enough RAM:** Docker Desktop → **Settings → Resources → Memory → 10–12 GB → Apply & Restart**.
3. **Copy the project folder** onto the PC.
4. Open **PowerShell**, `cd` into the folder, and run:
   ```powershell
   .\start.cmd
   ```
   (or `docker compose up`)
5. Wait for the first-run download (~18 GB — once, then cached).
6. Open **http://localhost:5173** and log in.

---

## Logging in

| Email | Password | Tier |
|---|---|---|
| `enterprise@narrative.dev` | `betatest1` | Enterprise (full features) |
| `enterprise.b@narrative.dev` | `betatest1` | Enterprise |
| `enterprise.ultra@narrative.dev` | `betatest1` | Enterprise |
| `enterprise.c@narrative.dev` | `betatest1` | Enterprise |

---

## What to expect

- **First boot is the slow one** (~10–20 min): images + AI models download. Later boots start in a minute or two — everything is cached in Docker volumes.
- **The feed starts nearly empty and fills in live.** The scheduler ingests, embeds, links, and ranks events every ~5–10 minutes. Give it 10–15 minutes to build a rich feed, then it keeps updating on its own.
- **The AI analyst is slow on the first question** (~90 s while the model loads into memory), then fast (~10 s) while it stays warm.
- **Lenses** (top bar) re-scope the whole app to a point of view — EU Logistics, Gulf Energy, Asia Tech, **Indo-Pak**, **Southeast Asia**.
- **Data persists.** Stop with `Ctrl+C` (or `docker compose down`); your events and models are kept. `docker compose up` again resumes.

---

## Terminal analyst (optional)

Ask the local AI from the command line while the stack is up:

```bash
./analyst.sh "biggest risk to shipping right now"      # mac/linux
analyst.cmd "biggest risk to shipping right now"       # windows
./analyst.sh --deep "how could a Hormuz closure hit me"
```

---

## Is my code safe when I share this?

**Be aware:** this full local package includes the **backend source code**. Anyone you
give the folder to can read it. That's fine for **running it yourself** or sharing with
**people you trust**. If you need to demo to someone **without exposing your code**, use
the separate *frontend-only* distribution instead (a ~200 MB package that talks to a
hosted backend, so the source never leaves your server).

---

## Troubleshooting

- **Feed stays empty** → give it 10–15 min; confirm the machine has internet.
- **Pipeline seems stuck / a container exited** → `docker compose up -d` restarts it; the scheduler also auto-restarts itself.
- **Analyst says AI is off** → the local model is still loading; wait ~90 s and retry.
- **Port already in use** → close whatever is using 5173/8000/5432/6379/5050, or stop other Docker projects.
- **Out of memory / container killed** → raise Docker Desktop's RAM to 12 GB.
