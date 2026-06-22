#!/usr/bin/env bash
# Starts the Narrative API against the real WSL Postgres/Redis + real ingested data.
set -e
cd "$(dirname "$(readlink -f "$0")")/.."
source ~/nv-venv/bin/activate
exec uvicorn backend.main:app --host 0.0.0.0 --port 8000
