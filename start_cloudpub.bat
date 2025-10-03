@echo off
chcp 65001
title CloudPub Info

echo ========================================
echo        CloudPub Tunnel Information
echo ========================================
echo.
echo INSTRUCTIONS:
echo 1. Make sure the web server is running (start_app.bat)
echo 2. Go to: https://cloudpub.ru/dashboard/
echo 3. Create a tunnel with these settings:
echo    - Local URL: http://localhost:8000
echo    - Protocol: HTTP
echo    - Port: 8000
echo.
echo 4. Your public URL will be like:
echo    https://chemically-oriented-anteater.cloudpub.ru/
echo.
echo 5. Share this URL to access your app from internet!
echo.
echo Current local URL: http://localhost:8000
echo.
pause