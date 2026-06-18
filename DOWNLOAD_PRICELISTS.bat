@echo off
chcp 65001 >nul
title Download Bank Pricelists
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python is not installed.
    pause
    exit /b 1
)

set PYEXE=python
if exist ".venv\Scripts\python.exe" set PYEXE=.venv\Scripts\python.exe

echo === Downloading PDFs ===
%PYEXE% scripts\download_pricelists.py

echo.
echo === Downloading Excel files ===
%PYEXE% scripts\download_excel_pricelists.py

echo.
pause
