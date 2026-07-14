#!/usr/bin/env bash
# ============================================================
#  Package the FRONTEND-ONLY distributable (IP-protected demo).
#
#  Produces ./dist-frontend/ containing ONLY the thin Node frontend + the
#  Path-A installers, which talk to the hosted backend. The backend source
#  (the actual IP: consequence engine, workers, algorithms) is NEVER included,
#  so a recipient cannot read or reverse-engineer it — they only get the React
#  app, which the browser sees anyway.
#
#  Hand someone the produced dist-frontend/ folder (or a zip of it), NOT the
#  repo. It fails loudly if any real secret would ship.
#
#  Usage:  bash scripts/package_frontend.sh
# ============================================================
set -euo pipefail
cd "$(dirname "$0")/.."
REPO="$(pwd)"
OUT="$REPO/dist-frontend"

echo "==> Cleaning $OUT"
rm -rf "$OUT"
mkdir -p "$OUT/web" "$OUT/scripts"

echo "==> Copying frontend source (excluding node_modules / build / secrets)"
# web/ sans the heavy/regenerable and secret bits. node_modules is reinstalled
# by the installer; web/.env (may hold a real VITE_ key) is deliberately dropped
# — the installer writes a fresh keyless one pointed at the hosted backend.
tar -C "$REPO/web" \
    --exclude=node_modules \
    --exclude=dist \
    --exclude=.env \
    --exclude=.env.local \
    -cf - . | tar -C "$OUT/web" -xf -

echo "==> Copying installers + boot intro (no backend, no compose, no dumps)"
cp "$REPO/INSTALL_BETA_WIN.bat"     "$OUT/"
cp "$REPO/INSTALL_BETA_MAC.command" "$OUT/"
cp "$REPO/scripts/boot_intro.ps1"   "$OUT/scripts/"
cp "$REPO/scripts/boot_intro.sh"    "$OUT/scripts/"

cat > "$OUT/README.md" <<'EOF'
# The Narrative — Demo (live data, no setup)

A thin local frontend that connects to our hosted backend. No Docker, no
database, no source to configure — just Node.

## Run it
- **Windows:** double-click `INSTALL_BETA_WIN.bat`
- **macOS:** double-click `INSTALL_BETA_MAC.command` (if blocked: right-click → Open)

Requires Node.js LTS (`winget install OpenJS.NodeJS.LTS` / `brew install node`).
First run installs packages (~1 min), then opens http://localhost:5173.

## Log in
- Email: `enterprise@narrative.dev`
- Password: `betatest1`

You are viewing live shared data from the hosted backend.
EOF

# ---- Secret guard: refuse to ship if any real key slipped in ----------------
echo "==> Scanning bundle for secrets"
# Anthropic (sk-ant-), Voyage (pa-...), AISStream 40-hex, generic private keys.
if grep -rIEl \
     -e 'sk-ant-[A-Za-z0-9_-]{20,}' \
     -e 'pa-[A-Za-z0-9_-]{30,}' \
     -e 'VITE_AISSTREAM_KEY=[0-9a-f]{40}' \
     -e 'BEGIN [A-Z ]*PRIVATE KEY' \
     "$OUT" ; then
  echo "!! SECRET DETECTED in dist-frontend — aborting. Remove it and re-run." >&2
  rm -rf "$OUT"
  exit 1
fi

# Also assert the backend never leaked in.
if [ -d "$OUT/backend" ] || ls "$OUT"/*.dump >/dev/null 2>&1 || [ -f "$OUT/docker-compose.yml" ]; then
  echo "!! Backend/compose/dump found in bundle — aborting." >&2
  rm -rf "$OUT"; exit 1
fi

echo "==> OK. Clean frontend-only bundle at: $OUT"
echo "    Contents: web/ (no node_modules), installers, boot intro, README."
echo "    Zip it and hand it out — backend source is NOT included."
