.PHONY: help build test demo clean shell baseline baseline-ui baseline-run

help:
	@echo "Weaver AI - Docker Commands"
	@echo "============================"
	@echo "make build       - Build Docker image"
	@echo "make test        - Run tests in Docker"
	@echo "make demo        - Run demo in Docker"
	@echo "make shell       - Open shell in container"
	@echo "make clean       - Clean Docker containers"
	@echo ""
	@echo "Performance Testing:"
	@echo "make baseline    - Start services for baseline testing"
	@echo "make baseline-ui - Start services with Locust web UI"
	@echo "make baseline-run - Run automated baseline tests"

build:
	@echo "🔨 Building Docker image..."
	@docker build -f Dockerfile.test -t weaver-test:latest .

test: build
	@echo "🧪 Running tests in Docker..."
	@docker run --rm weaver-test:latest

demo: build
	@echo "🎭 Running demo in Docker..."
	@docker run --rm weaver-test:latest python demo_event_mesh.py

shell: build
	@echo "🐚 Opening shell in container..."
	@docker run --rm -it weaver-test:latest /bin/bash

clean:
	@echo "🧹 Cleaning up Docker containers..."
	@docker rm -f $$(docker ps -aq --filter name=weaver) 2>/dev/null || true
	@echo "✅ Cleanup complete"

# Performance Testing Targets

baseline:
	@echo "🚀 Starting Weaver AI for baseline testing..."
	@docker-compose -f docker-compose.baseline.yml up -d redis weaver
	@echo "⏳ Waiting for services to be ready..."
	@sleep 10
	@echo "✅ Services ready! Weaver AI available at http://localhost:8000"
	@echo "📊 Run 'make baseline-run' to start automated tests"

baseline-ui:
	@echo "🚀 Starting Weaver AI with Locust UI..."
	@docker-compose -f docker-compose.baseline.yml up -d
	@echo "⏳ Waiting for services to be ready..."
	@sleep 15
	@echo "✅ Services ready!"
	@echo "🌐 Locust UI available at http://localhost:8089"
	@echo "🎯 Target host is already configured"

baseline-run:
	@echo "📊 Running automated baseline tests..."
	@docker-compose -f docker-compose.baseline.yml --profile run-baseline up baseline-runner
	@echo "✅ Baseline tests complete! Check load_tests/results/ for reports"

baseline-stop:
	@echo "🛑 Stopping baseline test services..."
	@docker-compose -f docker-compose.baseline.yml down
	@echo "✅ Services stopped"

baseline-logs:
	@echo "📜 Showing baseline test logs..."
	@docker-compose -f docker-compose.baseline.yml logs -f
