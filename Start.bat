@echo off
title YouTube Automation Dashboard
echo ==============================================
echo   YouTube Automation Dashboard
echo ==============================================
echo.

cd /d "%~dp0"

REM Check Python
echo Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found
    pause
    exit /b 1
)
python --version
echo.

REM Install packages
echo Installing required packages...
pip install --upgrade flask selenium webdriver-manager psutil requests yt-dlp playwright bgutil-ytdlp-pot-provider
echo.

REM Install Playwright browsers
echo Checking Playwright browsers...
python -c "from playwright.sync_api import sync_playwright; sync_playwright().start().stop()" 2>nul
if errorlevel 1 (
    echo Installing Playwright Chromium...
    playwright install chromium
)
echo.

REM Check if Node.js server exists and start it
if exist "bgutil-ytdlp-pot-provider\server\build\main.js" (
    echo Starting PO Token HTTP Server on port 4416...
    start "PO Token Server" /min cmd /c "cd bgutil-ytdlp-pot-provider\server && node build/main.js --port 4416"
    timeout /t 3 /nobreak >nul
    echo Server started.
) else (
    echo WARNING: PO token server not found. Install from: https://github.com/Brainicism/bgutil-ytdlp-pot-provider
)
echo.

REM Launch dashboard
echo Starting Dashboard...
echo.
echo Dashboard will open at http://127.0.0.1:5000
echo.

python YTDash.py

pause