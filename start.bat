@echo off
REM Start IFSCA Exam Prep System

echo.
echo ========================================
echo  IFSCA Exam Prep System - Startup
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

REM Check if .env exists
if not exist "backend\.env" (
    echo ERROR: .env file not found in backend folder
    echo Please copy .env.example to .env and add your Gemini API keys
    pause
    exit /b 1
)

REM Install dependencies (first time only)
if not exist "venv" (
    echo Installing dependencies...
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install -r backend\requirements.txt
) else (
    call venv\Scripts\activate.bat
)

REM Start backend server
echo.
echo Starting FastAPI server...
echo Server will be available at: http://localhost:8000
echo Frontend at: file:///D:\Exam_preparation\frontend\index.html
echo.
echo Press Ctrl+C to stop the server
echo.

cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
