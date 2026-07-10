@echo off
REM ============================================================
REM  The Narrative - one-click local demo launcher
REM  Opens two windows. KEEP BOTH OPEN during the presentation.
REM  Closing the API window shuts down WSL and stops the backend.
REM ============================================================

echo Starting The Narrative demo stack...
echo.

REM 1) Backend API in WSL (this window holds the WSL distro open = backend stays alive)
start "Narrative API (keep open)" wsl.exe -e bash -lc "bash '/mnt/c/Users/Varun/OneDrive/Desktop/Narrative v5/scripts/_run_api.sh'"

REM 2) Frontend (Vite) on Windows
start "Narrative Web (keep open)" cmd /k "cd /d \"C:\Users\Varun\OneDrive\Desktop\Narrative v5\web\" && npm run dev"

echo.
echo Two windows are starting:
echo   - "Narrative API"  -^> http://localhost:8000   (wait ~15s for "Application startup complete")
echo   - "Narrative Web"  -^> http://localhost:5173
echo.
echo Open http://localhost:5173 and log in:
echo   enterprise@narrative.dev  /  betatest1
echo.
echo Tip: ask one throwaway analyst question first to warm up the model (~90s cold).
echo Keep BOTH windows open for the whole demo.
pause
