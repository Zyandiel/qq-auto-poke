@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" -Check
if errorlevel 1 echo Check failed. See docs/windows.md for setup and troubleshooting.
pause
