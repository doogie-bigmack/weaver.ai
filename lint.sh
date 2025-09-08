#!/bin/bash
# Quick linting script to run before commits

echo "🔍 Running linting checks..."

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run ruff check and fix
echo "Running ruff..."
ruff check . --fix
RUFF_STATUS=$?

# Run black formatting
echo "Running black..."
black .
BLACK_STATUS=$?

# Check if mypy is available and run it
if command -v mypy &> /dev/null; then
    echo "Running mypy..."
    mypy weaver_ai --ignore-missing-imports || true
fi

# Report results
if [ $RUFF_STATUS -eq 0 ] && [ $BLACK_STATUS -eq 0 ]; then
    echo "✅ All linting checks passed!"
    exit 0
else
    echo "⚠️  Some linting issues were auto-fixed. Please review the changes."
    exit 1
fi
