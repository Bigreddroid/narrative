#!/usr/bin/env bash
# ============================================================
#  The Narrative — terminal analyst (mac/linux)
#  Ask the local ($0) AI analyst straight from your terminal.
#      ./analyst.sh "biggest risk to shipping right now"
#      ./analyst.sh --deep "how could a Hormuz closure hit me"
#      ./analyst.sh --image ./photo.jpg
#  Runs inside the api container (has DB + local models). The stack must be up
#  (start.sh / docker compose up).
# ============================================================
cd "$(dirname "$0")"
exec docker compose exec -T api python scripts/analyst.py "$@"
