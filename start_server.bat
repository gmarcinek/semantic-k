@echo off
REM Start Semantic Kernel Chat Server

echo Starting Semantic Kernel Chat Server...
echo.

REM Check if virtual environment exists
if not exist "venv\" (
    echo Virtual environment not found. Creating one...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Check if dependencies are installed
python -c "import fastapi" 2>nul
if errorlevel 1 (
    echo Installing dependencies...
    pip install -e .
)

REM Check if .env file exists
if not exist ".env" (
    echo .env file not found!
    echo Please create a .env file with your API keys.
    echo You can copy .env.example and fill in your keys.
    pause
    exit /b 1
)

echo.
echo Starting server on http://localhost:8000
echo Open your browser and navigate to http://localhost:8000
echo.
echo Press Ctrl+C to stop the server
echo.

REM Start the server
python -m uvicorn src.semantic_k.api_server:app --host 0.0.0.0 --port 8000 --reload
