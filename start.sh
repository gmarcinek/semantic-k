#!/bin/bash

echo "🚀 Starting Weather Chat Application..."
echo ""

# Check if config.yml exists
if [ ! -f "config.yml" ]; then
    echo "⚠️  ERROR: config.yml not found!"
    echo ""
    echo "Please ensure config.yml is in the current directory."
    echo ""
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  ERROR: .env file not found!"
    echo ""
    echo "Please create a .env file with your OpenAI API key:"
    echo "  1. Copy .env.example to .env"
    echo "  2. Add your OPENAI_API_KEY"
    echo ""
    echo "Example:"
    echo "  cp .env.example .env"
    echo "  nano .env  # or use your favorite editor"
    echo ""
    exit 1
fi

# Check if Python packages are installed
echo "📦 Checking dependencies..."
python3 -c "import fastapi" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "📥 Installing dependencies..."
    pip install -r requirements.txt
fi

echo ""
echo "✅ Configuration loaded from config.yml"
echo "✅ Starting server on http://localhost:8000"
echo "📱 Open your browser and navigate to http://localhost:8000"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start the server
python3 simple_server.py