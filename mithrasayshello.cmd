@echo off
REM ============================================================
REM   mithrasayshello - one-command installer for The Narrative
REM   (Windows / CMD - double-click it, or run from a terminal)
REM
REM   Clones the project from git if needed, then boots the whole
REM   local stack ($0, keyless, local AI).
REM
REM   From a checkout you already have:
REM       git clone https://github.com/Bigreddroid/narrative.git
REM       cd narrative
REM       mithrasayshello.cmd
REM
REM   Pass extra docker args through, e.g.  mithrasayshello.cmd -d  (background).
REM ============================================================
setlocal
cd /d "%~dp0"

set "REPO_URL=https://github.com/Bigreddroid/narrative.git"
set "DIR_NAME=narrative"

echo.
echo   mithra says hello.  booting The Narrative...
echo.

REM ── 1. Docker must be installed and running ─────────────────────────────
where docker >nul 2>&1
if errorlevel 1 (
  echo !! Docker isn't installed. Get Docker Desktop:
  echo    https://www.docker.com/products/docker-desktop/  then re-run me.
  goto :fail
)
docker info >nul 2>&1
if errorlevel 1 (
  echo !! Docker is installed but not running. Open Docker Desktop, wait for
  echo    the whale icon to go steady, then re-run me.
  goto :fail
)

REM ── 2. Find (or fetch) the project ──────────────────────────────────────
if exist "docker-compose.yml" (
  echo ^>^> using the project in this folder
) else if exist "%DIR_NAME%\.git" (
  echo ^>^> found an existing clone in .\%DIR_NAME% - updating it
  git -C "%DIR_NAME%" pull --ff-only
  cd /d "%DIR_NAME%"
) else (
  where git >nul 2>&1
  if errorlevel 1 (
    echo !! git isn't installed. Install Git for Windows: https://git-scm.com/download/win
    echo    then re-run me.
    goto :fail
  )
  echo ^>^> cloning %REPO_URL% into .\%DIR_NAME%
  git clone --depth 1 "%REPO_URL%" "%DIR_NAME%"
  cd /d "%DIR_NAME%"
)

REM ── 3. Punk boot intro (PowerShell renders the VT art) ──────────────────
if exist "scripts\boot_intro.ps1" powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\boot_intro.ps1"

REM ── 4. Bring the whole stack up ─────────────────────────────────────────
echo.
echo ^>^> docker compose up - first run pulls images + local AI models (~10-20 min, once)
echo ^>^> when it settles, open  http://localhost:5173   (login: enterprise@narrative.dev / betatest1)
echo.
docker compose up %*
goto :eof

:fail
endlocal
exit /b 1
