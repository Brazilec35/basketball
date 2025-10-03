@echo off
chcp 65001
title Basketball Web Server

echo ========================================
echo    Basketball Parser - Web Server
echo ========================================
echo.

cd /d "%~dp0"

echo Checking Python...
python --version
if errorlevel 1 (
    echo ERROR: Python not found! Please install Python 3.9+
    pause
    exit /b 1
)

echo Checking virtual environment...
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing dependencies...
pip install -r requirements.txt

echo.
echo Starting FastAPI server...
echo Web interface: http://localhost:8000
echo.
uvicorn web_app:app --host 0.0.0.0 --port 8000 --reload

pause