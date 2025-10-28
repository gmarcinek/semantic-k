@echo off
echo Starting Weather Chat Application...
echo.

REM Check if config.yml exists
if not exist "config.yml" (
    echo ERROR: config.yml not found!
    echo.
    echo Please ensure config.yml is in the current directory.
    echo.
    pause
    exit /b 1
)

REM Check if .env file exists
if not exist ".env" (
    echo ERROR: .env file not found!
    echo.
    echo Please create a .env file with your OpenAI API key:
    echo   1. Copy .env.example to .env
    echo   2. Add your OPENAI_API_KEY
    echo.
    echo Example:
    echo   copy .env.example .env
    echo   notepad .env
    echo.
    pause
    exit /b 1
)

REM Check if Python packages are installed
echo Checking dependencies...
python -c "import fastapi" 2>nul
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
)

echo.
echo Configuration loaded from config.yml
echo Starting server on http://localhost:8000
echo Open your browser and navigate to http://localhost:8000
echo.
echo Press Ctrl+C to stop the server
echo.

REM Start the server
python simple_server.py