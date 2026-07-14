@echo off
REM ============================================================
REM   The Narrative - terminal analyst (Windows / CMD)
REM   Ask the local ($0) AI analyst straight from your terminal:
REM       analyst.cmd "biggest risk to shipping right now"
REM       analyst.cmd --deep "how could a Hormuz closure hit me"
REM       analyst.cmd --image .\photo.jpg
REM   Runs inside the api container. The stack must be up (start.cmd).
REM ============================================================
setlocal
cd /d "%~dp0"
docker compose exec -T api python scripts/analyst.py %*
endlocal
