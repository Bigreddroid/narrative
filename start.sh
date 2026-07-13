#!/usr/bin/env bash
# ============================================================
#  The Narrative — one-command launcher (macOS / Linux / terminal)
#  Plays the "hello mithra" boot intro, then brings the whole
#  stack up with docker compose. Extra args pass through, e.g.
#      ./start.sh -d       (run in the background)
# ============================================================
set -e
cd "$(dirname "$0")"

# Punk "hacker uplink" greeting — hello mithra. Never blocks the launch.
bash scripts/boot_intro.sh || true

echo ""
echo ">> booting the narrative — docker compose up"
echo ""
exec docker compose up "$@"
