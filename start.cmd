@echo off
REM ============================================================
REM   The Narrative - one-command launcher (Windows / CMD)
REM   Plays the "hello mithra" boot intro, then brings the whole
REM   stack up with docker compose. Double-click it, or run from
REM   cmd: start.cmd   (pass -d to run in the background)
REM ============================================================
setlocal
cd /d "%~dp0"

REM Punk "hacker uplink" greeting - hello mithra (PowerShell renders the VT art).
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\boot_intro.ps1"

echo.
echo ^>^> booting the narrative - docker compose up
echo.
docker compose up %*

endlocal
