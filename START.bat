@echo off
chcp 65001 >nul
title Bank Pricelist Comparison
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo.
    echo [ERROR] Python is not installed.
    echo Install Python from https://www.python.org/downloads/ and check "Add to PATH".
    echo.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo [First-time setup] Creating Python environment...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create venv.
        pause
        exit /b 1
    )
)

".venv\Scripts\python.exe" -c "import streamlit, pdfplumber, pandas, rapidfuzz" 2>nul
if errorlevel 1 (
    echo.
    echo [First-time setup] Installing dependencies... this takes 1-2 minutes.
    ".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Dependency installation failed.
        pause
        exit /b 1
    )
)

start "" /b cmd /c "timeout /t 4 >nul & start http://localhost:8501"

echo.
echo Starting server... browser will open automatically.
echo To stop: close this window.
echo.

".venv\Scripts\python.exe" -m streamlit run app.py --server.headless true --browser.gatherUsageStats false

pause
