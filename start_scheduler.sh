#!/bin/bash
cd "/mnt/c/Users/Varun/OneDrive/Desktop/Narrative v5"
source /opt/narrative-venv312/bin/activate
export PYTHONPATH="/mnt/c/Users/Varun/OneDrive/Desktop/Narrative v5"
screen -dmS narrative-scheduler python -m backend.scheduler
echo "Scheduler started in screen session 'narrative-scheduler'"
echo "View logs: wsl -u root screen -r narrative-scheduler"
