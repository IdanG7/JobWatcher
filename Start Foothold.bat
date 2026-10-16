@echo off
setlocal
title Foothold
chcp 65001 >nul
pushd "%~dp0"
if errorlevel 1 goto :missing
if not exist "runtime\python.exe" goto :missing
if not exist "app\portable_start.py" goto :missing
"runtime\python.exe" -u "app\portable_start.py" %*
set "jobwatch_exit=%errorlevel%"
popd
if not "%jobwatch_exit%"=="0" pause
exit /b %jobwatch_exit%
:missing
echo Please extract the entire Foothold ZIP first, then open Start Foothold.bat
echo from the extracted folder. Keep the app and runtime folders beside this file.
pause
exit /b 1
