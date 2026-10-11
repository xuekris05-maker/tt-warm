@echo off
chcp 65001 >nul
cd /d %~dp0
rem 先拉最新脚本（国内直连优先，失败再走 Clash），都失败就用本地旧版
curl -fsSL --max-time 30 https://raw.githubusercontent.com/xuekris05-maker/tt-warm/main/cn_warm_local.py -o cn_warm_local.new || curl -fsSL --max-time 30 -x http://127.0.0.1:7897 https://raw.githubusercontent.com/xuekris05-maker/tt-warm/main/cn_warm_local.py -o cn_warm_local.new
if exist cn_warm_local.new for %%A in (cn_warm_local.new) do if %%~zA GTR 5000 (move /y cn_warm_local.new cn_warm_local.py >nul) else (del cn_warm_local.new)
for /f "delims=" %%i in ('where python') do (set PY=%%i& goto found)
:found
"%PY%" "%~dp0cn_warm_local.py" %*
