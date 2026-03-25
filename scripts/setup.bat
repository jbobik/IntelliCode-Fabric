@echo off
echo ============================================
echo   AI Code Partner — Setup Script (Windows)
echo ============================================

:: Check Python
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.9+
    exit /b 1
)

echo.
echo [1/5] Creating Python virtual environment...
cd /d "%~dp0\.."
python -m venv .venv
call .venv\Scripts\activate

echo.
echo [2/5] Installing Python dependencies...
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt

echo.
echo [3/5] Creating directories...
if not exist models mkdir models
if not exist data mkdir data

echo.
echo [4/5] Installing VS Code extension dependencies...
cd extension
where npm >nul 2>&1
if not errorlevel 1 (
    call npm install
    call npm run compile
    echo Extension compiled successfully!
) else (
    echo WARNING: npm not found. Install Node.js to build the extension.
)
cd ..

echo.
echo [5/5] Downloading embedding model...
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2'); print('Embedding model ready!')"

echo.
echo ============================================
echo   Setup Complete!
echo ============================================
echo.
echo Next steps:
echo   1. Activate venv:  .venv\Scripts\activate
echo   2. Start backend:  cd backend ^& python server.py
echo   3. Open VS Code:   code .
echo   4. Press F5 to launch extension in debug mode
echo.
pause