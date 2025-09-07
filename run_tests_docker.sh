#!/bin/bash
# Run tests in Docker container

echo "🐳 Running Weaver AI tests in Docker..."
echo "========================================="

# Build the test image
echo "📦 Building Docker image..."
docker build -f Dockerfile.test -t weaver-test:latest . || exit 1

echo ""
echo "🧪 Running unit tests..."
echo "------------------------"
docker run --rm weaver-test:latest python -m pytest tests/unit/test_event_mesh.py -v --tb=short

echo ""
echo "🎭 Running demo..."
echo "-----------------"
docker run --rm weaver-test:latest python demo_event_mesh.py

echo ""
echo "✅ Docker tests complete!"