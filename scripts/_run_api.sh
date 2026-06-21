#!/usr/bin/env bash
# Starts the Narrative API against the real WSL Postgres/Redis + real ingested data.
set -e
cd "/mnt/c/Users/Varun/OneDrive/Desktop/Narrative v5"
source ~/nv-venv/bin/activate
exec uvicorn backend.main:app --host 0.0.0.0 --port 8000
