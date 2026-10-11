@echo off
chcp 65001 >nul
cd /d %~dp0
for /f "delims=" %%i in ('where python') do (set PY=%%i& goto found)
:found
"%PY%" -m pip install -q requests
if not exist cn_warm_local.py curl -fsSL --max-time 30 -x http://127.0.0.1:7897 https://raw.githubusercontent.com/xuekris05-maker/tt-warm/main/cn_warm_local.py -o cn_warm_local.py
schtasks /create /f /tn "CN_warm_2110" /sc daily /st 21:10 /tr "\"%~dp0run_cn_warm.bat\""
schtasks /create /f /tn "CN_warm_2340" /sc daily /st 23:40 /tr "\"%~dp0run_cn_warm.bat\""
echo 已登记每天 21:10 / 23:40 国内养号（抖音/小红书/闲鱼），每次运行前自动从 GitHub 更新脚本。
echo 现在先试跑一次，约 15 分钟，结果写在 cn_local_log.txt
call "%~dp0run_cn_warm.bat" --now
pause
