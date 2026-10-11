@echo off
chcp 65001 >nul
cd /d %~dp0
rem 先经 Clash 拉最新脚本，失败再直连，都失败就用本地旧版
curl -fsSL --max-time 30 -x http://127.0.0.1:7897 https://raw.githubusercontent.com/xuekris05-maker/tt-warm/main/tiktok_warm_local.py -o tiktok_warm_local.new || curl -fsSL --max-time 30 https://raw.githubusercontent.com/xuekris05-maker/tt-warm/main/tiktok_warm_local.py -o tiktok_warm_local.new
if exist tiktok_warm_local.new for %%A in (tiktok_warm_local.new) do if %%~zA GTR 5000 (move /y tiktok_warm_local.new tiktok_warm_local.py >nul) else (del tiktok_warm_local.new)
for /f "delims=" %%i in ('where python') do (set PY=%%i& goto found)
:found
"%PY%" "%~dp0tiktok_warm_local.py" %*
