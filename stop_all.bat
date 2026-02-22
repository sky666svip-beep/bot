@echo off
echo [ChoiceBot] Stopping all services...

:: 1. Stop running processes
taskkill /F /IM python.exe /FI "WINDOWTITLE eq ChoiceBot-Server*" 2>nul
taskkill /F /IM python.exe 2>nul
taskkill /F /IM cloudflared.exe 2>nul

:: 2. Delete startup tasks
echo Deleting the startup task...
schtasks /Delete /TN "ChoiceBot-Server" /F 2>nul
schtasks /Delete /TN "ChoiceBot-Tunnel" /F 2>nul

echo.
echo  All services have been terminated, and the automatic startup on boot has been disabled.
pause
