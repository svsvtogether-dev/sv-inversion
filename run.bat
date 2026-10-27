@echo off
title SV Inversion - Bot de Trading 10 EUR
cd /d "%~dp0"

echo ========================================================
echo        Iniciando SV Inversion - Paper Trading
echo ========================================================

set PYTHON_CMD=python
where python >nul 2>nul
if %errorlevel% neq 0 (
    if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
        set PYTHON_CMD="%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    ) else if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
        set PYTHON_CMD="%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    ) else (
        echo [ERROR] No se encontro Python instalado en el sistema.
        pause
        exit /b 1
    )
)

echo Usando: %PYTHON_CMD%
%PYTHON_CMD% main.py
pause
