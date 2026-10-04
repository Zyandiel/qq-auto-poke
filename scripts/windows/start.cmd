@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"
if errorlevel 1 echo Startup failed. See docs/windows.md for setup and troubleshooting.
pause
