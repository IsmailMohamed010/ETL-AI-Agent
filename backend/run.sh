#!/bin/bash

# ETL Pipeline API - Quick Start Script (macOS/Linux)

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║      ETL Pipeline API - Quick Start (macOS/Linux)         ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed"
    echo "Please install Python 3.9+ from https://python.org or use:"
    echo "  macOS: brew install python3"
    echo "  Ubuntu: sudo apt install python3 python3-pip"
    exit 1
fi

echo "✓ Python found: $(python3 --version)"
echo ""

# Set working directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "❌ Error creating virtual environment"
        exit 1
    fi
    echo "✓ Virtual environment created"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate
if [ $? -ne 0 ]; then
    echo "❌ Error activating virtual environment"
    exit 1
fi
echo "✓ Virtual environment activated"

# Install dependencies
echo "📥 Installing dependencies..."
pip install -q -r requirements.txt
if [ $? -ne 0 ]; then
    echo "❌ Error installing dependencies"
    exit 1
fi
echo "✓ Dependencies installed"

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "📋 Creating .env file from template..."
    cp .env.example .env
    echo "✓ .env file created (you may want to edit it)"
fi

# Create uploads directory
if [ ! -d "uploads" ]; then
    echo "📁 Creating uploads directory..."
    mkdir -p uploads
    echo "✓ Uploads directory created"
fi

# Display information
echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                 Ready to Start!                           ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "🚀 Starting ETL Pipeline API..."
echo ""
echo "Access points:"
echo "  🌐 API              : http://localhost:8000"
echo "  📚 Swagger Docs     : http://localhost:8000/docs"
echo "  📖 ReDoc           : http://localhost:8000/redoc"
echo "  ❤️  Health Check   : http://localhost:8000/health"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start the application
python -m uvicorn main:app --reload --port 8000
