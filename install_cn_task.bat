@echo off
cd /d %~dp0
set RAW=https://raw.githubusercontent.com/xuekris05-maker/tt-warm/main
curl -fsSL --max-time 30 %RAW%/run_cn_warm.bat -o run_cn_warm.bat || curl -fsSL --max-time 30 -x http://127.0.0.1:7897 %RAW%/run_cn_warm.bat -o run_cn_warm.bat
curl -fsSL --max-time 30 %RAW%/cn_warm_local.py -o cn_warm_local.py || curl -fsSL --max-time 30 -x http://127.0.0.1:7897 %RAW%/cn_warm_local.py -o cn_warm_local.py
if not exist run_cn_warm.bat (echo [ERROR] download run_cn_warm.bat failed & pause & exit /b)
if not exist cn_warm_local.py (echo [ERROR] download cn_warm_local.py failed & pause & exit /b)
for /f "delims=" %%i in ('where python') do (set PY=%%i& goto found)
:found
"%PY%" -m pip install -q requests
schtasks /create /f /tn "CN_warm_2110" /sc daily /st 21:10 /tr "\"%~dp0run_cn_warm.bat\""
schtasks /create /f /tn "CN_warm_2340" /sc daily /st 23:40 /tr "\"%~dp0run_cn_warm.bat\""
echo.
echo OK: tasks set for 21:10 and 23:40 daily. Test run now (about 15 min), result goes to cn_local_log.txt
call "%~dp0run_cn_warm.bat" --now
pause
