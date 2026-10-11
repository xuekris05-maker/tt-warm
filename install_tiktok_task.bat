@echo off
chcp 65001 >nul
cd /d %~dp0
for /f "delims=" %%i in ('where python') do (set PY=%%i& goto found)
:found
"%PY%" -m pip install -q requests
schtasks /create /f /tn "TikTok_warm_0000" /sc daily /st 00:00 /tr "\"%~dp0run_warm.bat\""
schtasks /create /f /tn "TikTok_warm_0500" /sc daily /st 05:00 /tr "\"%~dp0run_warm.bat\""
schtasks /create /f /tn "TikTok_warm_1100" /sc daily /st 11:00 /tr "\"%~dp0run_warm.bat\""
echo 已登记 0:00 / 5:00 / 11:00，每次运行前自动从 GitHub 更新脚本。
call "%~dp0run_warm.bat" --now
pause
