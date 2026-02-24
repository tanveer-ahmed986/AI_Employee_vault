@echo off
title AI Employee — Silver Tier
echo ================================================
echo   AI Employee Orchestrator — Silver Tier
echo   Starting all watchers and scheduler...
echo ================================================
echo.

cd /d "%~dp0"

:: Run via UV (virtual environment managed by UV)
uv run python orchestrator.py

pause
