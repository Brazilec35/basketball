@echo off
chcp 65001
title Basketball App - Full Setup

echo ========================================
echo    Basketball Parser - Complete Setup
echo ========================================
echo.

cd /d "%~dp0"

echo Step 1: Starting Web Server...
start "Basketball Web Server" start_app.bat

echo Waiting for web server to start...
timeout /t 10 /nobreak

echo Step 2: Starting Data Parser...
start "Basketball Parser" start_parser.bat

echo Step 3: CloudPub Setup Instructions...
start "CloudPub Info" start_cloudpub.bat

echo.
echo ========================================
echo          SETUP COMPLETE!
echo ========================================
echo.
echo 1. Web Server: http://localhost:8000
echo 2. Parser: Running in background
echo 3. Check CloudPub window for public access
echo.
echo Press any key to close this window...
pause >nul