@echo off
setlocal enabledelayedexpansion
title The Narrative - Full Beta (Windows / Docker)

REM ============================================================
REM  The Narrative - FULL local beta for Windows (Path B, Docker)
REM  Self-contained: runs the whole backend (Postgres + Redis +
REM  API) in Docker plus the frontend. Live aircraft + ships work
REM  (the backend calls them from your own IP). Event data is a
REM  bundled snapshot. Portable - runs from wherever this folder is.
REM
REM  Prereq: Docker Desktop (https://www.docker.com/products/docker-desktop)
REM  First run pulls images + loads sample data (a few minutes).
REM ============================================================

REM Repo root = the folder this .bat lives in (portable, not hardcoded).
set "REPO=%~dp0"
if "%REPO:~-1%"=="\" set "REPO=%REPO:~0,-1%"
cd /d "%REPO%"

REM --- 0) Boot intro (glitch "hello mithra" uplink theatre). ---
powershell -NoProfile -ExecutionPolicy Bypass -File "%REPO%\scripts\boot_intro.ps1"

echo ============================================================
echo    The Narrative - Full Local Beta (Windows / Docker)
echo ============================================================
echo.

REM --- 1) Docker present + running? ---
where docker >nul 2>nul
if errorlevel 1 (
  echo    Docker Desktop is not installed. Install it, then run this again:
  echo        https://www.docker.com/products/docker-desktop
  echo.
  pause
  exit /b 1
)
docker info >nul 2>nul
if errorlevel 1 (
  echo [1/6] Starting Docker Desktop... (this can take a minute)
  start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" >nul 2>nul
  echo       waiting for the Docker engine...
  :waitdocker
  timeout /t 3 >nul
  docker info >nul 2>nul
  if errorlevel 1 goto waitdocker
)
echo [1/6] Docker is running.

REM --- 2) Config files the backend + frontend need (created once). ---
if not exist "%REPO%\.env" copy "%REPO%\.env.example" "%REPO%\.env" >nul
if not exist "%REPO%\web\.env" (
  >  "%REPO%\web\.env" echo # Local full-stack beta - talk to the LOCAL backend on :8000.
  >> "%REPO%\web\.env" echo VITE_DEMO_MODE=false
  >> "%REPO%\web\.env" echo # VITE_API_TARGET left blank => dev proxy targets localhost:8000.
  >> "%REPO%\web\.env" echo # Optional: paste an AISStream key for live ships, then restart.
  >> "%REPO%\web\.env" echo # VITE_AISSTREAM_KEY=
)
echo [2/6] Config ready.

REM --- 3) Database + cache ---
echo [3/6] Starting Postgres + Redis...
docker compose up -d postgres redis
echo       waiting for Postgres to accept connections...
:waitpg
docker compose exec -T postgres pg_isready -U narrative >nul 2>nul
if errorlevel 1 ( timeout /t 2 >nul & goto waitpg )

REM --- 4) Load the sample data only if the DB is empty ---
for /f "usebackq delims=" %%H in (`docker compose exec -T postgres psql -U narrative -d narrative -tAc "SELECT to_regclass('public.narrative_events') IS NOT NULL;" 2^>nul`) do set "HASTBL=%%H"
set "HASTBL=%HASTBL: =%"
if /i "%HASTBL%"=="t" (
  echo [4/6] Sample data already loaded.
) else (
  echo [4/6] Loading sample data ^(one time, ~1 min^)...
  docker compose exec -T postgres pg_restore -U narrative -d narrative --no-owner --clean --if-exists < "%REPO%\scripts\narrative.dump"
)

REM --- 5) Backend API (runs DB migrations on boot) ---
echo [5/6] Starting backend API ^(http://localhost:8000^)...
docker compose up -d api
echo       waiting for the backend to answer...
:waitapi
powershell -NoProfile -Command "try{ if((Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://localhost:8000/health).StatusCode -eq 200){exit 0} }catch{}; exit 1" >nul 2>nul
if errorlevel 1 ( timeout /t 3 >nul & goto waitapi )
echo       backend ready.

REM --- 6) Frontend (talks to the LOCAL backend) ---
echo [6/6] Starting the app ^(http://localhost:5173^)...
if not exist "%REPO%\web\node_modules" (
  echo       Installing packages, one time - this can take a minute...
  pushd "%REPO%\web" & call npm install & popd
)
start "" powershell -NoProfile -Command "Start-Sleep -Seconds 4; Start-Process 'http://localhost:5173'"

echo.
echo ============================================================
echo    Full beta running.  Open:  http://localhost:5173
echo       Email:    enterprise@narrative.dev
echo       Password: betatest1
echo.
echo    Keep THIS window open (Ctrl+C stops the app).
echo    Live aircraft + ships update in real time; event data is
echo    the bundled snapshot. To stop the backend later:  docker compose down
echo ============================================================
echo.
cd /d "%REPO%\web"
call npm run dev -- --port 5173 --strictPort
endlocal
