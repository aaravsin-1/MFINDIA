@echo off
REM ===================================================================
REM  Paper-trading daily runner  (Windows Task Scheduler entrypoint)
REM  Fetches end-of-day NAVs, marks the portfolio to market, and
REM  rebalances when due. Schedule ~9:00 PM IST (AMFI publishes daily
REM  NAVs by ~8-9 PM). See README.md for the schtasks command.
REM
REM  If you use a virtualenv, replace `python` below with the full path
REM  to that venv's python.exe.
REM ===================================================================
setlocal
cd /d "%~dp0"

if not exist logs mkdir logs

REM dated log file (yyyy-MM-dd) via PowerShell for locale-independence
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set TODAY=%%i
set LOG=logs\paper_%TODAY%.log

echo ============================================================ >> "%LOG%"
echo  RUN STARTED %DATE% %TIME% >> "%LOG%"
echo ============================================================ >> "%LOG%"

python update_daily.py >> "%LOG%" 2>&1
set RC=%ERRORLEVEL%

echo ------------------------------------------------------------ >> "%LOG%"
echo  RUN FINISHED %DATE% %TIME%  (exit code %RC%) >> "%LOG%"
echo. >> "%LOG%"

endlocal
exit /b %RC%
