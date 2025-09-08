#!/bin/bash

# Baseline performance testing script for Weaver AI

set -e

echo "========================================"
echo "Weaver AI - Baseline Performance Test"
echo "========================================"
echo ""

# Check if Weaver AI is running
echo "Checking if Weaver AI server is running..."
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health | grep -q "200"; then
    echo "✅ Server is running"
else
    echo "❌ Server is not running"
    echo ""
    echo "Please start the server first:"
    echo "  python -m weaver_ai.main --host 0.0.0.0 --port 8000"
    echo ""
    echo "Or in Docker:"
    echo "  docker-compose up weaver"
    exit 1
fi

# Install load testing dependencies if needed
if ! python -c "import locust" 2>/dev/null; then
    echo ""
    echo "Installing load testing dependencies..."
    pip install -e ".[load-test]"
fi

# Create results directory
mkdir -p load_tests/results

# Run the baseline tests
echo ""
echo "Starting baseline performance tests..."
echo "This will take approximately 10-15 minutes to complete."
echo ""

python load_tests/run_baseline.py

echo ""
echo "Baseline testing complete!"
echo "Results saved in: load_tests/results/"
