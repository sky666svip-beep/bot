@echo off
echo [ChoiceBot] 正在终止所有服务...

:: 1. 停止当前运行的进程
taskkill /F /IM python.exe /FI "WINDOWTITLE eq ChoiceBot-Server*" 2>nul
taskkill /F /IM python.exe 2>nul
taskkill /F /IM cloudflared.exe 2>nul

:: 2. 删除开机自启任务
echo 正在删除开机自启任务...
schtasks /Delete /TN "ChoiceBot-Server" /F 2>nul
schtasks /Delete /TN "ChoiceBot-Tunnel" /F 2>nul

echo.
echo ✅ 所有服务已停止，开机自启已取消。
pause
