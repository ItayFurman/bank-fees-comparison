@echo off
chcp 65001 >nul
title Deploy to Streamlit Cloud
cd /d "%~dp0"

echo ==========================================================
echo   Deploy to Streamlit Community Cloud (free + share online)
echo ==========================================================
echo.

REM Verify git is installed
where git >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Git is not installed.
    echo Install from https://git-scm.com/download/win then run again.
    pause
    exit /b 1
)

echo Step 1: Checking git status...
git status >nul 2>&1
if errorlevel 1 (
    echo Initializing git repository...
    git init -b main
    git config user.email "you@example.com"
    git config user.name "Bank Compliance User"
)

REM Check if GitHub remote is configured
git remote get-url origin >nul 2>nul
if errorlevel 1 (
    echo.
    echo Step 2: Setting up GitHub remote
    echo.
    echo You need a GitHub account and a new empty repository.
    echo 1. Go to https://github.com/new
    echo 2. Repository name: bank-fees-comparison
    echo 3. Make it public ^(required for free Streamlit Cloud^)
    echo 4. DO NOT add README/license/gitignore
    echo 5. Click Create repository
    echo.
    set /p GH_USER="Enter your GitHub username: "
    if "%GH_USER%"=="" (
        echo [ERROR] Username required.
        pause
        exit /b 1
    )
    git remote add origin https://github.com/%GH_USER%/bank-fees-comparison.git
    echo Remote added.
)

echo.
echo Step 3: Committing latest changes
git add app.py requirements.txt .gitignore .streamlit/ src/ docs/ pdfs/.gitkeep START.bat DOWNLOAD_PRICELISTS.bat DEPLOY_TO_CLOUD.bat scripts/ 2>nul
git commit -m "Update deployment" 2>nul

echo.
echo Step 4: Pushing to GitHub
echo You will be prompted for GitHub credentials (use a Personal Access Token, not password)
echo Generate token at: https://github.com/settings/tokens/new (scope: repo)
echo.
git push -u origin main

if errorlevel 1 (
    echo.
    echo [WARNING] Push failed. Common fixes:
    echo - Verify GitHub username is correct
    echo - Use a Personal Access Token instead of password
    echo - Repository must exist and be empty
    pause
    exit /b 1
)

echo.
echo ==========================================================
echo   GitHub push successful!
echo ==========================================================
echo.
echo NEXT STEP (manual, 2 minutes):
echo.
echo 1. Open https://share.streamlit.io in your browser
echo 2. Sign in with GitHub
echo 3. Click "New app"
echo 4. Repository: ^<your-username^>/bank-fees-comparison
echo 5. Branch: main
echo 6. Main file path: app.py
echo 7. Click "Deploy"
echo.
echo Within 2 minutes you'll have a public URL to share.
echo.
echo Optional - enable LLM agent:
echo - In Streamlit Cloud: Settings -^> Secrets -^>
echo   ANTHROPIC_API_KEY = "sk-ant-..."
echo - Get key at: https://console.anthropic.com
echo.
pause
