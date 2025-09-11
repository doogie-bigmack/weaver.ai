.PHONY: help build test demo clean shell baseline baseline-ui baseline-run pentest-gpt validate

help:
	@echo "Weaver AI - Docker Commands"
	@echo "============================"
	@echo "make build       - Build Docker image"
	@echo "make test        - Run tests in Docker"
	@echo "make demo        - Run demo in Docker"
	@echo "make shell       - Open shell in container"
	@echo "make clean       - Clean Docker containers"
	@echo "make validate    - Run framework validation test"
	@echo "make pentest-gpt - Run penetration test with GPT"
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

# Framework Validation Testing

validate: build
	@echo "🔬 Running Weaver AI Framework Validation Test..."
	@echo "This test validates:"
	@echo "  ✓ ResultPublisher (Phase 1)"
	@echo "  ✓ Model Integration (Phase 2)"
	@echo "  ✓ Memory System"
	@echo "  ✓ Agent Coordination"
	@echo ""
	@docker run --rm -e OPENAI_API_KEY="$${OPENAI_API_KEY}" weaver-test:latest python3 run_framework_validation.py
	@echo "✅ Framework validation complete!"

validate-local:
	@echo "🔬 Running Framework Validation Locally (no Docker)..."
	@python3 run_framework_validation.py

# GPT Penetration Testing

pentest-gpt: build
	@echo "🔐 Running penetration test with GPT (GPT-5 ready)..."
	@if [ -z "$${OPENAI_API_KEY}" ]; then \
		echo "❌ Error: OPENAI_API_KEY environment variable is not set"; \
		echo "📝 Please run: export OPENAI_API_KEY='your-api-key-here'"; \
		exit 1; \
	fi
	@echo "✅ OPENAI_API_KEY is set"
	@echo "🤖 This test will automatically use GPT-5 when available"
	@echo "🚀 Starting penetration test..."
	@docker run --rm -e OPENAI_API_KEY="$${OPENAI_API_KEY}" weaver-test:latest python3 run_pentest_with_gpt5_ready.py
	@echo "✅ Penetration test complete!"

pentest-gpt-clean:
	@echo "🧹 Cleaning up penetration test services..."
	@docker-compose -f docker-compose.pentest.yml down -v
	@rm -rf pentest-results/
	@echo "✅ Cleanup complete"

# Powder Finder Penetration Testing

pentest-powder: build
	@echo "🎿 Running Powder Finder penetration test with GPT-5-2025-08-07..."
	@if [ -z "$${OPENAI_API_KEY}" ]; then \
		echo "⚠️  Warning: OPENAI_API_KEY not set, running in simulation mode"; \
		echo "📝 To use real models: export OPENAI_API_KEY='your-api-key-here'"; \
	else \
		echo "✅ OPENAI_API_KEY is set"; \
		echo "🤖 Attempting to use model: gpt-5-2025-08-07"; \
	fi
	@echo "🎯 Target: Powder Finder Application"
	@echo "🚀 Starting security assessment..."
	@docker run --rm -e OPENAI_API_KEY="$${OPENAI_API_KEY}" weaver-test:latest python3 run_powder_finder_pentest.py
	@echo "✅ Powder Finder penetration test complete!"

pentest-powder-local:
	@echo "🎿 Running Powder Finder penetration test locally..."
	@python3 run_powder_finder_pentest.py

pentest-detailed:
	@echo "🔍 Running DETAILED penetration test with attack logging..."
	@echo "📊 This test provides:"
	@echo "  • Exact URLs for each attack"
	@echo "  • Attack payloads and responses"
	@echo "  • Success/failure evidence"
	@python3 run_powder_finder_pentest_detailed.py
