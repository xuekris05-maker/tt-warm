@echo off
cd /d %~dp0
set RAW=https://raw.githubusercontent.com/xuekris05-maker/tt-warm/main
curl -fsSL --max-time 30 %RAW%/watchdog.py -o watchdog.py || curl -fsSL --max-time 30 -x http://127.0.0.1:7897 %RAW%/watchdog.py -o watchdog.py
if not exist watchdog.py (echo [ERROR] download watchdog.py failed & pause & exit /b)
if not exist relay.py (echo [ERROR] put this file in the tiktok-relay folder, next to relay.py & pause & exit /b)
for /f "delims=" %%i in ('where python') do (set PY=%%i& goto found)
:found
set PYW=%PY:python.exe=pythonw.exe%
if not exist "%PYW%" set PYW=%PY%
"%PY%" -m pip install -q psutil aiohttp
rem --- autostart at logon (no admin needed) ---
set VBS=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\kris_relay_watchdog.vbs
> "%VBS%" echo CreateObject("WScript.Shell").Run """%PYW%"" ""%~dp0watchdog.py""", 0, False
rem --- never sleep / hibernate on AC power ---
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
rem --- close old start.bat windows, watchdog takes over ---
taskkill /f /fi "WINDOWTITLE eq relay*" >nul 2>&1
taskkill /f /fi "WINDOWTITLE eq ngrok*" >nul 2>&1
taskkill /f /im ngrok.exe >nul 2>&1
wscript "%VBS%"
echo Waiting 90s for relay + ngrok to come up...
timeout /t 90 /nobreak >nul
type watchdog_log.txt
echo.
echo OK: watchdog installed. It starts with Windows, restarts relay/ngrok if they die,
echo and keeps the PC awake. You no longer need start.bat. Keep AdsPower profiles open.
pause
