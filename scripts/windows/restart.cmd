@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0manage.ps1" -Action Stop
if errorlevel 1 goto failed
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0manage.ps1" -Action Start
if errorlevel 1 goto failed
echo Auto-poke restarted. QQ and NapCat were left running.
pause
exit /b 0
:failed
echo Restart failed. See docs/windows.md and runtime.log.
pause
exit /b 1
