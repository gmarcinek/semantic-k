#!/bin/bash

# Start Semantic Kernel Chat Server

echo "🚀 Starting Semantic Kernel Chat Server..."
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "⚠️  Virtual environment not found. Creating one..."
    python -m venv venv
fi

# Activate virtual environment
echo "📦 Activating virtual environment..."
source venv/bin/activate

# Check if dependencies are installed
if ! python -c "import fastapi" 2>/dev/null; then
    echo "📥 Installing dependencies..."
    pip install -e .
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found!"
    echo "Please create a .env file with your API keys."
    echo "You can copy .env.example and fill in your keys."
    exit 1
fi

echo ""
echo "✅ Starting server on http://localhost:8000"
echo "📱 Open your browser and navigate to http://localhost:8000"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start the server
python -m uvicorn src.semantic_k.api_server:app --host 0.0.0.0 --port 8000 --reload
