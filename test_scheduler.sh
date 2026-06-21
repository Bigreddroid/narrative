#!/bin/bash
cd "/mnt/c/Users/Varun/OneDrive/Desktop/Narrative v5"
source /opt/narrative-venv312/bin/activate
export PYTHONPATH="/mnt/c/Users/Varun/OneDrive/Desktop/Narrative v5"
python -m backend.scheduler 2>&1
