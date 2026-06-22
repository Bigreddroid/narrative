#!/bin/bash
cd "$(dirname "$(readlink -f "$0")")"
source /opt/narrative-venv312/bin/activate
export PYTHONPATH="$PWD"
screen -dmS narrative-scheduler python -m backend.scheduler
echo "Scheduler started in screen session 'narrative-scheduler'"
echo "View logs: wsl -u root screen -r narrative-scheduler"
