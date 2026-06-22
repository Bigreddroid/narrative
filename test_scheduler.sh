#!/bin/bash
cd "$(dirname "$(readlink -f "$0")")"
source /opt/narrative-venv312/bin/activate
export PYTHONPATH="$PWD"
python -m backend.scheduler 2>&1
