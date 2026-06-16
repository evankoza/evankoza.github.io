@echo off
REM ---- Launch the portfolio site locally on port 3210 ----
cd /d "%~dp0"
set PORT=3210

REM Open the browser shortly after the server boots
start "" /min cmd /c "timeout /t 2 >nul & start http://localhost:%PORT%"

echo Starting server at http://localhost:%PORT%  (press Ctrl+C to stop)

REM Prefer Node's "serve"; fall back to Python if Node isn't installed
where node >nul 2>nul
if %errorlevel%==0 (
  npx --yes serve -l %PORT%
  goto :eof
)

where python >nul 2>nul
if %errorlevel%==0 (
  python -m http.server %PORT%
  goto :eof
)

echo.
echo ERROR: Neither Node.js nor Python was found on your PATH.
echo Install Node.js from https://nodejs.org and try again.
pause
