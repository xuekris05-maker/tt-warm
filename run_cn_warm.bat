@echo off
cd /d %~dp0
rem update script from GitHub (direct first, then via Clash); keep old copy if both fail
curl -fsSL --max-time 30 https://raw.githubusercontent.com/xuekris05-maker/tt-warm/main/cn_warm_local.py -o cn_warm_local.new || curl -fsSL --max-time 30 -x http://127.0.0.1:7897 https://raw.githubusercontent.com/xuekris05-maker/tt-warm/main/cn_warm_local.py -o cn_warm_local.new
if exist cn_warm_local.new for %%A in (cn_warm_local.new) do if %%~zA GTR 5000 (move /y cn_warm_local.new cn_warm_local.py >nul) else (del cn_warm_local.new)
for /f "delims=" %%i in ('where python') do (set PY=%%i& goto found)
:found
set PYTHONIOENCODING=utf-8
"%PY%" "%~dp0cn_warm_local.py" %*
