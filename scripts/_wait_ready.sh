#!/usr/bin/env bash
# Wait until the local Postgres (:5432, user 'narrative') and Redis are ready.
# Used by the plug-and-play launchers so the API only starts once its
# dependencies accept connections. Exits 0 when ready, 1 on timeout.
for i in $(seq 1 40); do
  if pg_isready -h 127.0.0.1 -p 5432 -U narrative >/dev/null 2>&1 \
     && redis-cli ping >/dev/null 2>&1; then
    echo "READY"
    exit 0
  fi
  sleep 1
done
echo "TIMEOUT"
exit 1
