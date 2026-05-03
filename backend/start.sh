#!/bin/bash
# ETL Pipeline - Quick Start Guide
# Run this script to start the ETL Pipeline API server

echo "╔════════════════════════════════════════════════════════════╗"
echo "║         ETL Pipeline - Quick Start                          ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Check if Python is installed
if ! command -v python &> /dev/null; then
    echo "❌ Python is not installed. Please install Python 3.8+"
    exit 1
fi

echo "✅ Python found"
echo ""

# Check Python version
python_version=$(python --version 2>&1 | awk '{print $2}')
echo "📍 Python Version: $python_version"
echo ""

# Install dependencies
echo "📦 Installing dependencies..."
pip install -q -r requirements.txt

if [ $? -ne 0 ]; then
    echo "❌ Failed to install dependencies"
    exit 1
fi

echo "✅ Dependencies installed"
echo ""

# Run tests
echo "╔════════════════════════════════════════════════════════════╗"
echo "║              Running Test Suite (5 tests)                   ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

python test_pipeline.py

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Tests failed. Please check the output above."
    exit 1
fi

echo ""
echo "✅ All tests passed!"
echo ""

# Start the server
echo "╔════════════════════════════════════════════════════════════╗"
echo "║         Starting ETL Pipeline API Server                    ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "📍 Server will start at: http://localhost:8000"
echo "📍 Swagger UI: http://localhost:8000/docs"
echo "📍 ReDoc: http://localhost:8000/redoc"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

uvicorn main:app --reload --host 0.0.0.0 --port 8000
