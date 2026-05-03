@echo off
REM ETL Pipeline API - Quick Start Script (Windows)

echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║      ETL Pipeline API - Quick Start (Windows)             ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Error: Python is not installed or not in PATH
    echo Please install Python 3.9+ from https://python.org
    pause
    exit /b 1
)

echo ✓ Python found
echo.

REM Set working directory
cd /d "%~dp0"

REM Check if virtual environment exists
if not exist "venv" (
    echo 📦 Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ❌ Error creating virtual environment
        pause
        exit /b 1
    )
    echo ✓ Virtual environment created
)

REM Activate virtual environment
echo 🔧 Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ❌ Error activating virtual environment
    pause
    exit /b 1
)
echo ✓ Virtual environment activated

REM Install dependencies
echo 📥 Installing dependencies...
pip install -q -r requirements.txt
if errorlevel 1 (
    echo ❌ Error installing dependencies
    pause
    exit /b 1
)
echo ✓ Dependencies installed

REM Check if .env exists
if not exist ".env" (
    echo 📋 Creating .env file from template...
    copy .env.example .env >nul
    echo ✓ .env file created (you may want to edit it)
)

REM Create uploads directory
if not exist "uploads" (
    echo 📁 Creating uploads directory...
    mkdir uploads
    echo ✓ Uploads directory created
)

REM Display information
echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║                 Ready to Start!                           ║
echo ╚════════════════════════════════════════════════════════════╝
echo.
echo 🚀 Starting ETL Pipeline API...
echo.
echo Access points:
echo   🌐 API              : http://localhost:8000
echo   📚 Swagger Docs     : http://localhost:8000/docs
echo   📖 ReDoc           : http://localhost:8000/redoc
echo   ❤️  Health Check   : http://localhost:8000/health
echo.
echo Press Ctrl+C to stop the server
echo.

REM Start the application
python -m uvicorn main:app --reload --port 8000

pause
