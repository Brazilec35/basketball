@echo off
chcp 65001
title Basketball Parser

echo ========================================
echo    Basketball Parser - Data Parser
echo ========================================
echo.

cd /d "%~dp0"

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Starting basketball parser...
echo This will collect live match data...
echo.

python app.py

pause
