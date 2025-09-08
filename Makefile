.PHONY: help build test demo clean shell

help:
	@echo "Weaver AI - Docker Commands"
	@echo "============================"
	@echo "make build    - Build Docker image"
	@echo "make test     - Run tests in Docker"
	@echo "make demo     - Run demo in Docker"
	@echo "make shell    - Open shell in container"
	@echo "make clean    - Clean Docker containers"

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
