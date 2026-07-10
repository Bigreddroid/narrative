#!/usr/bin/env bash
# ============================================================
#  The Narrative - Beta installer for macOS (Path A)
#  Runs a thin local frontend pointed at the LIVE hosted
#  backend. No Docker, no Python, no database - just Node.
#
#  Double-click in Finder. If macOS blocks it ("unidentified
#  developer"): right-click -> Open, then click Open. Or run:
#      chmod +x INSTALL_BETA_MAC.command
# ============================================================
set -e
cd "$(dirname "$0")"
REPO="$(pwd)"
PROD_API="https://narrative-production-2a1c.up.railway.app"

# --- 0) Boot intro (glitch "hello mithra" uplink theatre). ---
bash scripts/boot_intro.sh || true

echo "============================================================"
echo "   The Narrative - Beta (live data, no setup)"
echo "============================================================"
echo

# --- 1) Node check ---
if ! command -v node >/dev/null 2>&1; then
  echo "   Node.js is not installed. Install it, then run this again:"
  echo "       brew install node"
  echo "   (or download from https://nodejs.org)"
  echo
  read -n 1 -s -r -p "Press any key to close..."; exit 1
fi
echo "[1/3] Node.js found."

# --- 2) Point the frontend at the live backend (only if unconfigured). ---
if [ ! -f "web/.env" ]; then
  echo "[2/3] Configuring the app to use live data..."
  cat > web/.env <<EOF
# Auto-written by INSTALL_BETA_MAC.command - talks to the live backend.
VITE_API_TARGET=${PROD_API}
VITE_DEMO_MODE=false
# Optional: paste an AISStream key for live ships, then restart.
# VITE_AISSTREAM_KEY=
EOF
else
  echo "[2/3] Existing web/.env found - leaving it as-is."
fi

# --- 3) Install packages (first run only) and start the app. ---
echo "[3/3] Starting the app (http://localhost:5173)..."
cd web
[ -d node_modules ] || { echo "      Installing packages, one time..."; npm install; }

# Open the browser once the live backend answers (in the background).
(
  for _ in $(seq 1 30); do
    if curl -sf "${PROD_API}/health" >/dev/null 2>&1; then break; fi
    sleep 1
  done
  sleep 3
  open "http://localhost:5173"
) &

echo
echo "============================================================"
echo "   The Narrative is running.  Open:  http://localhost:5173"
echo
echo "     Email:    enterprise@narrative.dev"
echo "     Password: betatest1"
echo
echo "   Keep THIS window open. Press Ctrl+C to stop the app."
echo "   You are viewing LIVE shared data from the hosted backend."
echo "   (Aircraft may be blank on this path - that is expected.)"
echo "============================================================"
echo

npm run dev -- --port 5173 --strictPort
