#!/usr/bin/env bash
# Dump the local Postgres (real ingested data) in custom format, ready to restore
# into Railway Postgres at migration time:
#
#   pg_restore --no-owner --no-acl --clean --if-exists \
#     -d "<RAILWAY_DATABASE_URL_without_+asyncpg>" scripts/narrative.dump
#
# Re-run this right before migrating so the snapshot is fresh. Output is
# gitignored (*.dump).
set -e
cd "$(dirname "$0")/.."
url=$(grep -E '^DATABASE_URL=' .env | cut -d= -f2-)
clean=$(python3 - "$url" <<'PY'
import sys, re
u = sys.argv[1].replace("+asyncpg", "")
print(re.sub(r"\?.*$", "", u))
PY
)
pg_dump -Fc --no-owner --no-acl "$clean" -f scripts/narrative.dump
echo "wrote scripts/narrative.dump ($(du -h scripts/narrative.dump | cut -f1))"
