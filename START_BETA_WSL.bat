@echo off
setlocal enabledelayedexpansion
title The Narrative - Beta Launcher
set "REPO=C:\Users\Varun\OneDrive\Desktop\Narrative v5"

REM --- 0) Boot intro (glitch "hello mithra" uplink theatre). ---
powershell -NoProfile -ExecutionPolicy Bypass -File "%REPO%\scripts\boot_intro.ps1"

echo ============================================================
echo    The Narrative - Local Beta  (plug and play)
echo ============================================================
echo.

REM --- 1) Wake WSL. systemd auto-starts Postgres + Redis on boot. ---
echo [1/4] Starting database + cache (WSL Postgres 18 + Redis)...
wsl -d Ubuntu -e bash -lc "bash '/mnt/c/Users/Varun/OneDrive/Desktop/Narrative v5/scripts/_wait_ready.sh'"
if errorlevel 1 (
  echo.
  echo    ERROR: Postgres/Redis did not come up in WSL within 40s.
  echo    Open a WSL terminal ^(type: wsl^) and check:
  echo        pg_lsclusters      ^(cluster should say 'online'^)
  echo        redis-cli ping     ^(should say 'PONG'^)
  echo.
  pause
  exit /b 1
)
echo    Database + cache are up.
echo.

REM --- 2) Backend API in its own WSL window. KEEP OPEN = backend alive. ---
echo [2/4] Starting backend API  (http://localhost:8000)...
start "Narrative API (KEEP OPEN)" wsl -d Ubuntu -e bash -lc "bash '/mnt/c/Users/Varun/OneDrive/Desktop/Narrative v5/scripts/_run_api.sh'"

REM --- 3) Frontend (Vite) in its own window, pinned to port 5173. ---
echo [3/4] Starting frontend  (http://localhost:5173)...
start "Narrative Web (KEEP OPEN)" cmd /k "cd /d \"%REPO%\web\" && npm run dev -- --port 5173 --strictPort"

REM --- 4) Wait for the API to answer, then open the browser. ---
echo [4/4] Waiting for the backend to finish starting (~10-20s), then opening your browser...
powershell -NoProfile -Command "$ok=$false; for($i=0;$i -lt 45;$i++){ try{ if((Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://localhost:8000/health).StatusCode -eq 200){ $ok=$true; break } }catch{}; Start-Sleep -Seconds 1 }; if($ok){ Write-Host '    Backend is ready.' } else { Write-Host '    Backend still starting - open the browser manually in a moment.' }; Start-Process 'http://localhost:5173'"

echo.
echo ============================================================
echo    Beta is running.  Open:  http://localhost:5173
echo.
echo    Log in:
echo       Email:     enterprise@narrative.dev
echo       Password:  betatest1
echo.
echo    Two windows opened (API + Web) - KEEP BOTH OPEN while
echo    you use the beta. Closing the API window stops the backend.
echo.
echo    Tip: the world map shows live events, ships (AIS) and
echo    aircraft (OpenSky). Air needs ~15s for its first refresh.
echo ============================================================
echo.
echo Press any key to close THIS launcher window (the app keeps running).
pause >nul
endlocal
