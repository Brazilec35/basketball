@echo off
chcp 65001
title Install Dependencies

echo ========================================
echo    Installing Python Dependencies
echo ========================================
echo.

cd /d "%~dp0"

echo Creating virtual environment...
python -m venv venv

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing packages...
pip install fastapi uvicorn selenium websockets jinja2 python-multipart

echo.
echo Creating requirements.txt...
pip freeze > requirements.txt

echo.
echo Dependencies installed successfully!
echo.
pause
