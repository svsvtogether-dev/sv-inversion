@echo off
title SV Inversion x Conway Automaton - Gestion Autonoma
cd /d "%~dp0"

echo ========================================================
echo   SV INVERSION x CONWAY AUTOMATON (MODO SIMULACION)
echo ========================================================

set PYTHON_CMD=python
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
    set PYTHON_CMD="%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
) else if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    set PYTHON_CMD="%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
)

echo Usando: %PYTHON_CMD%
%PYTHON_CMD% main.py
pause
