@echo off
setlocal enabledelayedexpansion
title The Narrative - Beta (install ^& run)

REM ============================================================
REM  The Narrative - Beta installer for Windows (Path A)
REM  Runs a thin local frontend pointed at the LIVE hosted
REM  backend. No Docker, no Python, no database - just Node.
REM  Double-click this file. First run installs packages (~1 min).
REM ============================================================

REM Repo root = the folder this .bat lives in (portable, not hardcoded).
set "REPO=%~dp0"
if "%REPO:~-1%"=="\" set "REPO=%REPO:~0,-1%"

set "PROD_API=https://narrative-production-2a1c.up.railway.app"

REM --- 0) Boot intro (glitch "hello mithra" uplink theatre). ---
powershell -NoProfile -ExecutionPolicy Bypass -File "%REPO%\scripts\boot_intro.ps1"

echo ============================================================
echo    The Narrative - Beta  (live data, no setup)
echo ============================================================
echo.

REM --- 1) Node check ---
where node >nul 2>nul
if errorlevel 1 (
  echo    Node.js is not installed. Install the LTS build, then
  echo    double-click this file again:
  echo        winget install OpenJS.NodeJS.LTS
  echo    ^(or download from https://nodejs.org^)
  echo.
  pause
  exit /b 1
)
echo [1/3] Node.js found.

REM --- 2) Point the frontend at the live backend (only if unconfigured). ---
if not exist "%REPO%\web\.env" (
  echo [2/3] Configuring the app to use live data...
  >  "%REPO%\web\.env" echo # Auto-written by INSTALL_BETA_WIN.bat - talks to the live backend.
  >> "%REPO%\web\.env" echo VITE_API_TARGET=%PROD_API%
  >> "%REPO%\web\.env" echo VITE_DEMO_MODE=false
  >> "%REPO%\web\.env" echo # Optional: paste an AISStream key for live ships, then restart.
  >> "%REPO%\web\.env" echo # VITE_AISSTREAM_KEY=
) else (
  echo [2/3] Existing web\.env found - leaving it as-is.
)

REM --- 3) Install packages (first run only) and start the app. ---
echo [3/3] Starting the app  (http://localhost:5173)...
if not exist "%REPO%\web\node_modules" (
  echo       Installing packages, one time - this can take a minute...
  pushd "%REPO%\web"
  call npm install
  popd
)

start "Narrative Web (KEEP OPEN)" cmd /k "cd /d \"%REPO%\web\" && npm run dev -- --port 5173 --strictPort"

REM Wait for the LIVE backend to answer, then open the browser.
powershell -NoProfile -Command "$ok=$false; for($i=0;$i -lt 30;$i++){ try{ if((Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 '%PROD_API%/health').StatusCode -eq 200){ $ok=$true; break } }catch{}; Start-Sleep -Seconds 1 }; Start-Sleep -Seconds 3; Start-Process 'http://localhost:5173'"

echo.
echo ============================================================
echo    The Narrative is running.  Open:  http://localhost:5173
echo.
echo    Log in:
echo       Email:     enterprise@narrative.dev
echo       Password:  betatest1
echo.
echo    A window opened (Web) - KEEP IT OPEN while you use the beta.
echo    You are viewing LIVE shared data from the hosted backend.
echo    (Aircraft may be blank on this path - that is expected.)
echo ============================================================
echo.
echo Press any key to close THIS window (the app keeps running).
pause >nul
endlocal
