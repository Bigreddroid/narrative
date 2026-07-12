#!/usr/bin/env bash
# ============================================================
#  The Narrative - Local Beta launcher for macOS (plug and play)
#  Double-click this file in Finder. First run downloads Docker
#  images, the sample database, and the local AI models (llama3.2
#  + llava, ~7GB) so the analyst + geolocation work fully offline.
#  That first download can take 10-20 min; later runs are instant.
#
#  If macOS blocks it ("unidentified developer"): right-click ->
#  Open, then click Open. Or run once in Terminal:
#      chmod +x START_BETA_MAC.command
# ============================================================
set -e
cd "$(dirname "$0")"

# --- 0) Boot intro (glitch "hello mithra" uplink theatre). ---
bash scripts/boot_intro.sh || true

echo "============================================================"
echo "   The Narrative - Local Beta (macOS)"
echo "============================================================"
echo

# --- 1) Ensure Docker Desktop is installed + running ---
if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed. Install Docker Desktop:"
  echo "   https://www.docker.com/products/docker-desktop"
  echo "Then double-click this file again."
  read -n 1 -s -r -p "Press any key to close..."; exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "[1/5] Starting Docker Desktop..."
  open -a Docker
  printf "      waiting for the Docker engine"
  until docker info >/dev/null 2>&1; do printf "."; sleep 2; done
  echo " ready."
else
  echo "[1/5] Docker is running."
fi

# --- 1b) Root .env — the api service references it via `env_file: .env`, so it
#         must exist before any `docker compose` call or compose errors out. ---
[ -f .env ] || cp .env.example .env

# --- 2) Database + cache ---
echo "[2/5] Starting Postgres + Redis..."
docker compose up -d postgres redis
# give Postgres a moment to accept connections
until docker compose exec -T postgres pg_isready -U narrative >/dev/null 2>&1; do sleep 1; done

# --- 3) Load the sample data only if the DB is empty ---
HAS_TABLE=$(docker compose exec -T postgres psql -U narrative -d narrative -tAc "SELECT to_regclass('public.narrative_events') IS NOT NULL;" 2>/dev/null | tr -d '[:space:]' || echo "f")
if [ "$HAS_TABLE" != "t" ]; then
  echo "[3/5] Loading sample data (~8 MB, one time)..."
  docker compose exec -T postgres pg_restore -U narrative -d narrative --no-owner --clean --if-exists < scripts/narrative.dump || true
else
  echo "[3/5] Sample data already loaded."
fi

# --- 4) Backend API (runs DB migrations on boot). On first run Docker also
#        starts Ollama and downloads the local AI models (~7GB) before the API
#        comes up, because the api service waits for the model pull to finish. ---
echo "[4/5] Starting backend API (http://localhost:8000)..."
echo "      FIRST RUN downloads local AI models (~7GB, 10-20 min) - later runs skip this."
docker compose up -d api
printf "      waiting for the backend"
until curl -sf http://localhost:8000/health >/dev/null 2>&1; do printf "."; sleep 2; done
echo " ready."

# --- 5) Frontend (Vite) -> talks to the LOCAL backend ---
echo "[5/5] Starting the app..."
cd web
[ -f .env ] || cp .env.example .env      # blank VITE_API_TARGET => local backend :8000
[ -d node_modules ] || npm install
( sleep 4; open "http://localhost:5173" ) &

echo
echo "============================================================"
echo "   Beta is running. Opening http://localhost:5173"
echo "     Email:    enterprise@narrative.dev"
echo "     Password: betatest1"
echo
echo "   Keep THIS window open. Press Ctrl+C to stop the app."
echo "   To stop everything else later:  docker compose down"
echo "============================================================"
echo

npm run dev -- --port 5173 --strictPort
