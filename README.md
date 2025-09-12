# Weaver AI 🕸️

[![CI Pipeline](https://github.com/doogie-bigmack/weaver.ai/actions/workflows/ci.yml/badge.svg)](https://github.com/doogie-bigmack/weaver.ai/actions/workflows/ci.yml)
[![Security Scan](https://github.com/doogie-bigmack/weaver.ai/actions/workflows/security.yml/badge.svg)](https://github.com/doogie-bigmack/weaver.ai/actions/workflows/security.yml)
[![Release](https://github.com/doogie-bigmack/weaver.ai/actions/workflows/release.yml/badge.svg)](https://github.com/doogie-bigmack/weaver.ai/actions/workflows/release.yml)
[![Pre-commit](https://github.com/doogie-bigmack/weaver.ai/actions/workflows/pre-commit.yml/badge.svg)](https://github.com/doogie-bigmack/weaver.ai/actions/workflows/pre-commit.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A developer-friendly, A2A-compliant agent framework that makes building secure multi-agent systems as simple as writing Python functions. Built on Pydantic Agents and Model Context Protocol (MCP) with enterprise-grade security, observability, and verification.

## ✨ Features

- **🚀 Simple API**: Define agents in <20 lines of code with decorators
- **🔗 Multi-Agent Orchestration**: Chain agents together with automatic type-based routing
- **🔒 Enterprise Security**: Built-in authentication, RBAC, rate limiting, and audit logging
- **🎯 A2A Protocol Compliant**: Full Agent-to-Agent communication protocol support
- **🛠️ MCP Integration**: Model Context Protocol for standardized tool management
- **📊 Observable**: OpenTelemetry integration with comprehensive metrics
- **✅ Verifiable**: Output validation and groundedness checking
- **🐳 Production Ready**: Docker support, health checks, and graceful shutdown

## 🚀 Quick Start

### Installation

```bash
# Install from source
git clone https://github.com/doogie-bigmack/weaver.ai.git
cd weaver.ai
pip install -e .

# Or install with development dependencies
pip install -e .[dev]
```

### Your First Agent in 10 Lines

```python
from weaver_ai.simple import agent, run

@agent(model="gpt-4")
async def calculator(expression: str) -> float:
    """A simple calculator agent."""
    return eval(expression)  # Note: Use ast.literal_eval in production

# Run the agent
result = await run(calculator, "2 + 2")
print(result)  # Output: 4.0
```

### Multi-Agent Orchestration

```python
from weaver_ai.simple import agent, flow
from typing import Literal

@agent(model="gpt-4")
async def classifier(text: str) -> Literal["technical", "billing", "general"]:
    """Classify customer inquiries."""
    # Classification logic here
    return "technical"

@agent(model="gpt-3.5-turbo")
async def tech_support(query: str) -> str:
    """Handle technical support queries."""
    return f"Technical solution for: {query}"

@agent(model="gpt-3.5-turbo")
async def billing_support(query: str) -> str:
    """Handle billing queries."""
    return f"Billing information for: {query}"

# Create a multi-agent flow
support_flow = (
    flow("customer_support")
    .chain(classifier)
    .route({
        "technical": tech_support,
        "billing": billing_support,
        "general": lambda x: "Please contact support@example.com"
    })
)

# Run the flow
response = await support_flow.run("My API key isn't working")
print(response)  # Output: "Technical solution for: My API key isn't working"
```

### Serve as HTTP API

```python
from weaver_ai.simple import agent, serve

@agent(model="gpt-4")
async def assistant(message: str) -> str:
    """A helpful assistant."""
    return f"I can help with: {message}"

# Start HTTP server on port 8000
if __name__ == "__main__":
    serve(assistant, port=8000)
    # Now accessible at http://localhost:8000/ask
```

## 🛠️ Development Setup

### Prerequisites

- Python 3.12 or higher
- pip and virtualenv
- Git
- Docker (optional, for containerized development)

### Step 1: Clone and Install

```bash
# Clone the repository
git clone https://github.com/doogie-bigmack/weaver.ai.git
cd weaver.ai

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode with all dependencies
pip install -e .[dev]
```

### Step 2: Configure Environment

Weaver AI uses environment variables for configuration. We provide a comprehensive `.env.example` file as a template.

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your configuration
# IMPORTANT: Add your API keys for the model providers you plan to use
nano .env  # or use your preferred editor
```

**Essential Environment Variables:**

```bash
# At minimum, you need to configure one model provider:

# For OpenAI models (GPT-4, GPT-3.5, etc.)
OPENAI_API_KEY=your-openai-api-key-here

# For Anthropic models (Claude)
ANTHROPIC_API_KEY=your-anthropic-api-key-here

# For Groq (fast inference)
GROQ_API_KEY=your-groq-api-key-here

# Set your preferred model provider
WEAVER_MODEL_PROVIDER=openai  # or "anthropic", "groq", "stub" (for testing)
WEAVER_MODEL_NAME=gpt-4       # or "claude-3-opus-20240229", etc.

# For production deployments, configure security:
WEAVER_AUTH_MODE=api_key
WEAVER_ALLOWED_API_KEYS=your-secure-api-key-1,your-secure-api-key-2
```

**Loading Environment Variables:**

```bash
# Option 1: Export from .env file (recommended for development)
export $(cat .env | grep -v '^#' | xargs)

# Option 2: Use python-dotenv (automatic with the framework)
# The framework automatically loads .env if present

# Option 3: Set individually for testing
export OPENAI_API_KEY="your-key"
export WEAVER_MODEL_PROVIDER="openai"
```

**Security Notes:**
- Never commit `.env` files with real credentials to version control
- The `.env` file is already in `.gitignore` for your protection
- Use different API keys for development, staging, and production
- Consider using a secrets management service for production deployments

### Step 3: Set Up Pre-commit Hooks

```bash
# Install pre-commit hooks for code quality
pre-commit install

# Run hooks manually (optional)
pre-commit run --all-files
```

### Step 4: Run Tests

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=weaver_ai --cov-report=term-missing

# Run specific test categories
pytest tests/test_simple_api.py  # Test simple API
pytest tests/test_security_*     # Test security features
pytest -v                         # Verbose output
```

### Step 5: Code Quality Checks

```bash
# Linting
ruff check .

# Formatting
black .

# Type checking
mypy weaver_ai --ignore-missing-imports

# Security scanning
pip-audit
bandit -r weaver_ai

# Generate SBOM
cyclonedx-bom -o sbom/sbom.json
```

### Step 6: Run the Development Server

```bash
# Start the server with hot reload
python -m weaver_ai.main --host 0.0.0.0 --port 8000 --reload

# Or use uvicorn directly
uvicorn weaver_ai.gateway:app --reload --log-level debug

# Access the API documentation
open http://localhost:8000/docs
```

## 📚 API Documentation

### Simple API Reference

#### `@agent` Decorator
```python
@agent(
    model="gpt-4",           # Model to use
    cache=False,             # Enable caching
    retry=3,                 # Retry attempts
    timeout=30.0,            # Timeout in seconds
    fallback=None,           # Fallback function
    tools=["calculator"]     # Available tools
)
async def my_agent(input: str) -> str:
    """Agent description."""
    pass
```

#### Flow Builder
```python
# Linear chain
flow = flow("name").chain(agent1, agent2, agent3)

# Conditional routing
flow = flow("name").chain(classifier).route({
    "option1": agent1,
    "option2": agent2
})

# Parallel execution
flow = flow("name").parallel(agent1, agent2, agent3)

# Complex composition
flow = (
    flow("name")
    .chain(preprocessor)
    .parallel(analyzer1, analyzer2)
    .chain(aggregator)
    .route({"success": finalizer, "error": error_handler})
)
```

#### Execution Functions
```python
# Async execution
result = await run(agent_or_flow, input_data)

# HTTP server
serve(agent_or_flow, port=8000, host="0.0.0.0")
```

## 🏗️ Project Structure

```
weaver_ai/
├── simple/              # Simple API for developers
│   ├── __init__.py     # Public API exports
│   ├── decorators.py   # @agent decorator
│   ├── flow.py         # Flow builder
│   └── runners.py      # run() and serve() functions
├── gateway.py          # FastAPI application
├── agent.py            # Core orchestrator
├── a2a.py              # A2A protocol implementation
├── mcp.py              # Model Context Protocol
├── tools.py            # Tool framework
├── security/           # Security modules
│   ├── auth.py         # Authentication
│   ├── rbac.py         # Role-based access control
│   ├── policy.py       # Input/output guards
│   └── ratelimit.py    # Rate limiting
└── policies/           # Policy configurations
    ├── roles.yaml      # Role definitions
    └── tools.yaml      # Tool access policies
```

## 🧪 Testing

### Running Tests

```bash
# Run all tests with coverage
pytest --cov=weaver_ai --cov-report=html

# Run specific test files
pytest tests/test_simple_api.py

# Run tests in parallel
pytest -n auto

# Run with markers
pytest -m "not integration"  # Skip integration tests
pytest -m security           # Only security tests
```

### Writing Tests

```python
# tests/test_my_agent.py
import pytest
from weaver_ai.simple import agent, run

@agent(model="gpt-4")
async def my_agent(x: int) -> int:
    return x * 2

@pytest.mark.asyncio
async def test_my_agent():
    result = await run(my_agent, 5)
    assert result == 10
```

## 🐳 Docker Development

### Build and Run

```bash
# Build development image
docker build -f Dockerfile.test -t weaver-dev .

# Run tests in container
docker run --rm weaver-dev

# Build production image
docker build -t weaver:latest .

# Run production server with environment file
docker run -p 8000:8000 \
  --env-file .env \
  weaver:latest
```

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'
services:
  weaver:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env  # Load all environment variables from .env file
    volumes:
      - ./weaver_ai:/app/weaver_ai  # Hot reload for development
```

```bash
# Start all services
docker-compose up

# Run in background
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## 🚀 Production Deployment

### Environment Configuration

1. **Set up production environment file:**
   ```bash
   # Copy and configure for production
   cp .env.example .env.production

   # Edit with production values
   # - Use strong, unique API keys
   # - Enable security features
   # - Configure monitoring
   ```

2. **Essential production settings:**
   ```bash
   # Security
   WEAVER_AUTH_MODE=jwt
   WEAVER_JWT_PUBLIC_KEY="your-rsa-public-key"
   WEAVER_PII_REDACT=true

   # Performance
   WEAVER_RATELIMIT_RPS=10
   WEAVER_REQUEST_TIMEOUT_MS=30000

   # Monitoring
   WEAVER_TELEMETRY_ENABLED=true
   WEAVER_TELEMETRY_ENDPOINT=https://your-telemetry-collector.com
   WEAVER_AUDIT_PATH=/var/log/weaver/audit.log

   # Production database
   REDIS_HOST=your-redis-host.com
   REDIS_PASSWORD=your-redis-password
   ```

3. **Deploy with Docker:**
   ```bash
   # Build optimized production image
   docker build -t weaver:prod --target production .

   # Run with production config
   docker run -d \
     --name weaver-prod \
     --restart unless-stopped \
     -p 8000:8000 \
     --env-file .env.production \
     -v /var/log/weaver:/var/log/weaver \
     weaver:prod
   ```

4. **Deploy with Kubernetes:**
   ```bash
   # Create secret from env file
   kubectl create secret generic weaver-config --from-env-file=.env.production

   # Apply deployment
   kubectl apply -f k8s/deployment.yaml
   ```

5. **Health checks:**
   ```bash
   # Check service health
   curl http://your-domain.com/health

   # Check readiness
   curl http://your-domain.com/ready
   ```

### Security Checklist

- [ ] All API keys are unique and strong
- [ ] JWT keys are RSA 2048-bit or stronger
- [ ] TLS/SSL is configured for all endpoints
- [ ] Rate limiting is enabled
- [ ] Audit logging is configured
- [ ] PII redaction is enabled
- [ ] URL allowlist/denylist is configured
- [ ] Regular security updates are scheduled
- [ ] Secrets are managed via secure service (AWS Secrets Manager, Vault, etc.)

### Monitoring

Monitor these key metrics in production:
- Request latency (p50, p95, p99)
- Error rates by endpoint
- Rate limit violations
- Authentication failures
- Model API usage and costs
- Memory and CPU utilization

## 🤝 Contributing

We welcome contributions! Please follow these guidelines:

### Development Workflow

1. **Fork the repository**
2. **Create a feature branch**
   ```bash
   git checkout -b feature/amazing-feature
   ```

3. **Make your changes**
   - Write clean, documented code
   - Add tests for new features
   - Update documentation

4. **Run quality checks**
   ```bash
   # Format code
   black .

   # Check linting
   ruff check .

   # Run tests
   pytest

   # Type checking
   mypy weaver_ai
   ```

5. **Commit your changes**
   ```bash
   git commit -m "feat: Add amazing feature"
   ```

   Follow [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat:` New feature
   - `fix:` Bug fix
   - `docs:` Documentation
   - `test:` Testing
   - `refactor:` Code refactoring
   - `perf:` Performance improvements
   - `chore:` Maintenance

6. **Push and create Pull Request**
   ```bash
   git push origin feature/amazing-feature
   ```

### Code Style

- **Python 3.12+** with type hints
- **Black** for formatting (line length: 88)
- **Ruff** for linting
- **Google-style** docstrings
- **pytest** for testing

### Adding New Features

#### Creating a New Tool

```python
# weaver_ai/tools.py
class MyTool(Tool):
    name = "my_tool"
    description = "Does something useful"
    required_scopes = ["tool:my_tool"]

    def call(self, **kwargs):
        # Implementation
        return {"result": "success"}
```

#### Adding a New Endpoint

```python
# weaver_ai/gateway.py
@app.post("/my-endpoint")
async def my_endpoint(request: Request):
    user = enforce_limit(request)  # Auth + rate limit
    # Your logic here
    return {"status": "ok"}
```

## 📖 Advanced Usage

### Custom Model Integration

```python
from weaver_ai.simple import agent

# Use any OpenAI-compatible endpoint
@agent(
    model="local-llm",
    api_base="http://localhost:11434/v1",  # e.g., Ollama
    api_key="not-needed"
)
async def local_agent(prompt: str) -> str:
    """Agent using local LLM."""
    return f"Processed: {prompt}"
```

### Tool Integration

```python
from weaver_ai.simple import agent

@agent(
    model="gpt-4",
    tools=["python_eval", "web_search", "database"]
)
async def research_agent(query: str) -> dict:
    """Agent with access to multiple tools."""
    # Tools are automatically available via MCP
    return {"findings": "..."}
```

### Caching and Performance

```python
from weaver_ai.simple import agent

@agent(
    model="gpt-4",
    cache=True,          # Enable result caching
    cache_ttl=3600,      # Cache for 1 hour
    timeout=10.0         # 10 second timeout
)
async def expensive_agent(data: str) -> str:
    """Cached agent for expensive operations."""
    pass
```

### Error Handling

```python
from weaver_ai.simple import agent, run

@agent(model="gpt-4", retry=3)
async def reliable_agent(input: str) -> str:
    """Agent with automatic retry."""
    pass

@agent(model="gpt-4")
async def fallback_agent(input: str) -> str:
    """Fallback implementation."""
    pass

# Use with fallback
@agent(
    model="gpt-4",
    fallback=fallback_agent
)
async def main_agent(input: str) -> str:
    """Agent with fallback."""
    pass

# Handle errors explicitly
try:
    result = await run(main_agent, "input")
except Exception as e:
    print(f"Error: {e}")
```

## 🔒 Security

Weaver AI includes enterprise-grade security features:

- **JWT Authentication**: Secure token-based auth
- **RBAC**: Fine-grained role-based access control
- **Rate Limiting**: Configurable request throttling
- **Input/Output Guards**: Content filtering and validation
- **Audit Logging**: Comprehensive security event tracking
- **PII Redaction**: Automatic sensitive data masking

For security issues, please email security@example.com instead of using issue tracker.

## 📊 Monitoring and Observability

### Metrics

The framework exposes metrics via OpenTelemetry:

```python
# Enable telemetry
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4317"
export OTEL_SERVICE_NAME="weaver-ai"
```

Key metrics:
- Request latency (p50, p95, p99)
- Agent execution time
- Tool usage frequency
- Error rates
- Cache hit rates

### Health Checks

```bash
# Check service health
curl http://localhost:8000/health

# Response
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime": 3600
}
```

## 🚢 Deployment

### Production Checklist

- [ ] Set secure `JWT_SECRET`
- [ ] Configure rate limits
- [ ] Enable PII redaction if needed
- [ ] Set up monitoring/alerting
- [ ] Configure log aggregation
- [ ] Review security policies
- [ ] Set up backup strategy
- [ ] Configure auto-scaling

### Environment Variables

```bash
# Required
JWT_SECRET=<secure-random-string>

# Optional
PII_REDACT=true              # Enable PII redaction
RATE_LIMIT_RPM=60            # Requests per minute
LOG_LEVEL=INFO               # Logging level
TELEMETRY_ENABLED=true       # Enable telemetry
CACHE_REDIS_URL=redis://localhost:6379  # Redis for caching
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built on [Pydantic Agents](https://github.com/pydantic/pydantic-ai)
- Implements [Model Context Protocol](https://modelcontextprotocol.io/)
- Follows [A2A Protocol](https://github.com/a2a-protocol/a2a) specification

## 📧 Support

- **Documentation**: [docs/](docs/)
- **Issues**: [GitHub Issues](https://github.com/doogie-bigmack/weaver.ai/issues)
- **Discussions**: [GitHub Discussions](https://github.com/doogie-bigmack/weaver.ai/discussions)
- **Security**: security@example.com

---

Made with ❤️ by the Weaver AI Team
