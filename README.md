# Weaver AI 🕸️

[![CI Pipeline](https://github.com/doogie-bigmack/weaver.ai/actions/workflows/ci.yml/badge.svg)](https://github.com/doogie-bigmack/weaver.ai/actions/workflows/ci.yml)
[![Security Scan](https://github.com/doogie-bigmack/weaver.ai/actions/workflows/security.yml/badge.svg)](https://github.com/doogie-bigmack/weaver.ai/actions/workflows/security.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**The easiest way to build secure, production-ready AI agent systems.**

Weaver AI is a developer-friendly framework that makes building enterprise-grade multi-agent systems as simple as writing Python functions. Built on the Model Context Protocol (MCP) and Agent-to-Agent (A2A) standards with built-in security, observability, and compliance.

## 🎯 Why Weaver AI?

✨ **Write agents in 10 lines** - Simple decorator-based API
🔒 **Enterprise security built-in** - JWT auth, RBAC, rate limiting, audit trails
📊 **Production ready** - Observability, health checks, graceful shutdown
🔗 **Multi-agent orchestration** - Chain agents with automatic type-based routing
🛠️ **MCP & A2A compliant** - Standard protocols for tools and agent communication
✅ **Tamper-evident logging** - Cryptographically signed audit trails for compliance

---

## 📋 Table of Contents

- [Quick Start](#-quick-start)
- [Installation](#-installation)
- [Your First Agent](#-your-first-agent)
- [Configuration](#-configuration)
- [Development Setup](#-development-setup)
- [Testing](#-testing)
- [Deployment](#-deployment)
  - [Docker](#docker-deployment)
  - [Kubernetes](#kubernetes-deployment)
  - [Production Checklist](#production-checklist)
- [Security](#-security)
- [Monitoring](#-monitoring)
- [API Reference](#-api-reference)
- [Contributing](#-contributing)

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.12+** ([Download](https://www.python.org/downloads/))
- **Git** ([Download](https://git-scm.com/downloads))
- **API Key** from OpenAI, Anthropic, or Groq

### 5-Minute Setup

```bash
# 1. Clone and install
git clone https://github.com/doogie-bigmack/weaver.ai.git
cd weaver.ai
pip install -e .

# 2. Configure environment
export OPENAI_API_KEY="your-api-key-here"
export WEAVER_MODEL_PROVIDER="openai"
export WEAVER_MODEL_NAME="gpt-4"

# 3. Run your first agent
python examples/simple_agent.py
```

**That's it!** You now have a running AI agent system. 🎉

---

## 📦 Installation

### Option 1: Basic Installation

```bash
git clone https://github.com/doogie-bigmack/weaver.ai.git
cd weaver.ai
pip install -e .
```

### Option 2: Development Installation (Recommended)

```bash
git clone https://github.com/doogie-bigmack/weaver.ai.git
cd weaver.ai

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install with development dependencies
pip install -e .[dev]

# Set up pre-commit hooks
pre-commit install
```

### Option 3: Docker Installation

```bash
git clone https://github.com/doogie-bigmack/weaver.ai.git
cd weaver.ai

# Build and run
docker build -t weaver:latest .
docker run -p 8000:8000 --env-file .env weaver:latest
```

---

## 🤖 Your First Agent

### Example 1: Simple Calculator Agent

```python
from weaver_ai.simple import agent, run

@agent(model="gpt-4")
async def calculator(expression: str) -> float:
    """A simple calculator agent."""
    return eval(expression)  # Note: Use ast.literal_eval in production

# Run it
result = await run(calculator, "2 + 2")
print(result)  # Output: 4.0
```

### Example 2: Multi-Agent Customer Support

```python
from weaver_ai.simple import agent, flow
from typing import Literal

@agent(model="gpt-4")
async def classifier(text: str) -> Literal["technical", "billing", "general"]:
    """Classify customer inquiries."""
    pass

@agent(model="gpt-3.5-turbo")
async def tech_support(query: str) -> str:
    """Handle technical support queries."""
    return f"Technical solution for: {query}"

@agent(model="gpt-3.5-turbo")
async def billing_support(query: str) -> str:
    """Handle billing queries."""
    return f"Billing information for: {query}"

# Create multi-agent flow
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
print(response)
```

### Example 3: HTTP API Server

```python
from weaver_ai.simple import agent, serve

@agent(model="gpt-4", tools=["web_search", "documentation"])
async def assistant(message: str) -> str:
    """A helpful AI assistant with tool access."""
    pass

# Start HTTP server
if __name__ == "__main__":
    serve(assistant, port=8000)
    # Now accessible at http://localhost:8000/ask
```

---

## ⚙️ Configuration

### Step 1: Environment Variables

Weaver AI uses environment variables for configuration. Create a `.env` file:

```bash
# Copy the example
cp .env.example .env

# Edit with your settings
nano .env  # or vim, code, etc.
```

### Step 2: Essential Configuration

**Minimum Required:**

```bash
# Model Provider (choose one)
OPENAI_API_KEY=sk-proj-...                    # For OpenAI (GPT-4, GPT-3.5)
ANTHROPIC_API_KEY=sk-ant-...                  # For Anthropic (Claude)
GROQ_API_KEY=gsk_...                          # For Groq (fast inference)

# Select your provider
WEAVER_MODEL_PROVIDER=openai                  # or "anthropic", "groq", "stub"
WEAVER_MODEL_NAME=gpt-4                       # or "claude-3-opus-20240229"
```

**Security (Production):**

```bash
# Authentication
WEAVER_AUTH_MODE=jwt                          # Use "api_key" for simple auth
WEAVER_ALLOWED_API_KEYS=key1,key2             # For api_key mode
WEAVER_JWT_PUBLIC_KEY="<your-rsa-public-key>" # For JWT mode

# Rate Limiting
WEAVER_RATELIMIT_RPS=10                       # Requests per second per user
WEAVER_RATELIMIT_BURST=20                     # Burst capacity

# Security Features
WEAVER_PII_REDACT=true                        # Redact PII (SSN, credit cards, etc.)
WEAVER_URL_ALLOWLIST=["https://api.example.com"]  # Allowed external URLs
WEAVER_REQUEST_TIMEOUT_MS=30000               # Request timeout (30 seconds)
```

**Telemetry & Monitoring:**

```bash
# Observability (Logfire)
WEAVER_TELEMETRY_ENABLED=true
WEAVER_TELEMETRY_SERVICE_NAME=weaver-ai
WEAVER_TELEMETRY_ENVIRONMENT=production
WEAVER_LOGFIRE_TOKEN=<your-logfire-token>
WEAVER_LOGFIRE_SEND_TO_CLOUD=true

# Signed Audit Trails (NEW - Tamper-evident logs)
WEAVER_TELEMETRY_SIGNING_ENABLED=true
WEAVER_TELEMETRY_SIGNING_KEY="<your-rsa-private-key-pem>"
WEAVER_TELEMETRY_VERIFICATION_KEY="<your-rsa-public-key-pem>"

# Audit Logging
WEAVER_AUDIT_PATH=/var/log/weaver/audit.log
```

**Redis (Multi-Agent Communication):**

```bash
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=<your-redis-password>
REDIS_DB=0
```

### Step 3: Load Environment Variables

```bash
# Option 1: Export from .env file (recommended)
export $(cat .env | grep -v '^#' | xargs)

# Option 2: Use with Docker
docker run --env-file .env weaver:latest

# Option 3: Use with Kubernetes
kubectl create secret generic weaver-config --from-env-file=.env
```

### Complete Environment Variable Reference

<details>
<summary><b>Click to expand full environment variable list</b></summary>

#### Model Configuration
```bash
WEAVER_MODEL_PROVIDER          # Model provider: openai, anthropic, vllm, tgi, stub
WEAVER_MODEL_NAME              # Model name: gpt-4, claude-3-opus-20240229, etc.
WEAVER_MODEL_ENDPOINT          # Custom model endpoint (optional)
WEAVER_MODEL_API_KEY           # API key for model provider (optional if using env vars)
```

#### Telemetry Settings
```bash
WEAVER_TELEMETRY_ENABLED           # Enable/disable telemetry (default: true)
WEAVER_TELEMETRY_SERVICE_NAME      # Service name (default: weaver-ai)
WEAVER_TELEMETRY_ENVIRONMENT       # Environment: development, staging, production
WEAVER_LOGFIRE_TOKEN               # Logfire API token
WEAVER_LOGFIRE_SEND_TO_CLOUD       # Send telemetry to cloud (default: false)
WEAVER_TELEMETRY_SIGNING_ENABLED   # Sign security events (default: true)
WEAVER_TELEMETRY_SIGNING_KEY       # RSA private key for signing (PEM format)
WEAVER_TELEMETRY_VERIFICATION_KEY  # RSA public key for verification (PEM format)
```

#### Security & Authentication
```bash
WEAVER_AUTH_MODE                   # Auth mode: api_key or jwt
WEAVER_ALLOWED_API_KEYS            # Comma-separated list of API keys
WEAVER_JWT_PUBLIC_KEY              # RSA public key for JWT validation
WEAVER_RATELIMIT_RPS               # Requests per second (default: 5)
WEAVER_RATELIMIT_BURST             # Burst capacity (default: 10)
WEAVER_REQUEST_MAX_TOKENS          # Max tokens per request (default: 4096)
WEAVER_REQUEST_TIMEOUT_MS          # Request timeout in ms (default: 25000)
WEAVER_REQUEST_MAX_TOOLS           # Max tools per request (default: 3)
WEAVER_AUDIT_PATH                  # Audit log file path (default: ./audit.log)
WEAVER_URL_ALLOWLIST               # JSON list of allowed URL patterns
WEAVER_URL_DENYLIST                # JSON list of denied URL patterns
WEAVER_PII_REDACT                  # Enable PII redaction (default: true)
```

#### A2A Protocol (Agent-to-Agent)
```bash
WEAVER_A2A_SIGNING_PRIVATE_KEY_PEM # Private key for A2A message signing
WEAVER_A2A_SIGNING_PUBLIC_KEY_PEM  # Public key for A2A verification
WEAVER_MCP_SERVER_PUBLIC_KEYS      # JSON dict of MCP server public keys
```

#### Redis Configuration
```bash
REDIS_HOST                         # Redis host (default: localhost)
REDIS_PORT                         # Redis port (default: 6379)
REDIS_PASSWORD                     # Redis password (optional)
REDIS_DB                           # Redis database number (default: 0)
```

</details>

---

## 🛠️ Development Setup

### Step 1: Clone and Install

```bash
# Clone repository
git clone https://github.com/doogie-bigmack/weaver.ai.git
cd weaver.ai

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install development dependencies
pip install -e .[dev]
```

### Step 2: Configure for Development

```bash
# Copy example environment
cp .env.example .env

# Add minimum configuration for development
cat >> .env << EOF
OPENAI_API_KEY=your-openai-api-key
WEAVER_MODEL_PROVIDER=openai
WEAVER_MODEL_NAME=gpt-4
WEAVER_AUTH_MODE=api_key
WEAVER_ALLOWED_API_KEYS=dev-key-123
EOF

# Load environment
export $(cat .env | grep -v '^#' | xargs)
```

### Step 3: Set Up Pre-commit Hooks

```bash
# Install hooks
pre-commit install

# Run manually (optional)
pre-commit run --all-files
```

### Step 4: Run Development Server

```bash
# Option 1: Using the CLI
python -m weaver_ai.main --host 0.0.0.0 --port 8000 --reload

# Option 2: Using uvicorn directly
uvicorn weaver_ai.gateway:app --reload --log-level debug

# Option 3: Using Docker
docker-compose up --build
```

### Step 5: Access API Documentation

```bash
# Open in browser
open http://localhost:8000/docs          # Swagger UI
open http://localhost:8000/redoc         # ReDoc
```

### Step 6: Code Quality Tools

```bash
# Linting
ruff check .                             # Check for issues
ruff check . --fix                       # Auto-fix issues

# Formatting
black .                                  # Format all files
black --check .                          # Check formatting

# Type checking
mypy weaver_ai --ignore-missing-imports

# Security scanning
pip-audit                                # Check dependencies
bandit -r weaver_ai                      # Check code security

# Generate SBOM (Software Bill of Materials)
cyclonedx-bom -o sbom/sbom.json
```

---

## 🧪 Testing

### Run All Tests

```bash
# Run all tests with coverage
pytest --cov=weaver_ai --cov-report=term-missing

# Run all tests with HTML coverage report
pytest --cov=weaver_ai --cov-report=html
open htmlcov/index.html

# Run in parallel (faster)
pytest -n auto
```

### Run Specific Tests

```bash
# Test simple API
pytest tests/unit/test_signed_telemetry.py -v

# Test security features
pytest tests/test_security_* -v

# Test integration workflows
pytest tests/integration/ -v

# Test specific function
pytest -k "test_sign_event" -v
```

### Run with Markers

```bash
# Skip slow tests
pytest -m "not slow"

# Only security tests
pytest -m security

# Only integration tests
pytest -m integration
```

### Write Your Own Tests

```python
# tests/test_my_feature.py
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

---

## 🚀 Deployment

### Docker Deployment

#### Step 1: Build Image

```bash
# Build production image
docker build -t weaver:latest .

# Or build with specific tag
docker build -t weaver:v1.0.0 .
```

#### Step 2: Run Container

```bash
# Run with environment file
docker run -d \
  --name weaver-prod \
  --restart unless-stopped \
  -p 8000:8000 \
  --env-file .env.production \
  -v /var/log/weaver:/var/log/weaver \
  weaver:latest

# Check logs
docker logs -f weaver-prod

# Check health
curl http://localhost:8000/health
```

#### Step 3: Docker Compose (Multi-Service)

```yaml
# docker-compose.yml
version: '3.8'

services:
  weaver:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env.production
    depends_on:
      - redis
    volumes:
      - ./logs:/var/log/weaver
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --requirepass ${REDIS_PASSWORD}
    restart: unless-stopped

volumes:
  redis_data:
```

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Scale services
docker-compose up -d --scale weaver=3

# Stop services
docker-compose down
```

### Kubernetes Deployment

#### Step 1: Create Configuration Secret

```bash
# Create secret from environment file
kubectl create secret generic weaver-config \
  --from-env-file=.env.production

# Or create from individual values
kubectl create secret generic weaver-config \
  --from-literal=OPENAI_API_KEY='your-key' \
  --from-literal=WEAVER_MODEL_PROVIDER='openai' \
  --from-literal=WEAVER_MODEL_NAME='gpt-4'
```

#### Step 2: Deploy Application

The project includes complete Kubernetes manifests in the `k8s/` directory:

```bash
# Apply all manifests
kubectl apply -f k8s/

# Or apply specific components
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml
```

#### Step 3: Verify Deployment

```bash
# Check deployment status
kubectl get deployments -n weaver-ai
kubectl get pods -n weaver-ai
kubectl get services -n weaver-ai

# Check logs
kubectl logs -f deployment/weaver-ai -n weaver-ai

# Check health
kubectl port-forward svc/weaver-ai 8000:8000 -n weaver-ai
curl http://localhost:8000/health
```

#### Step 4: Configure Ingress (Optional)

```yaml
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: weaver-ai
  namespace: weaver-ai
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
  - hosts:
    - api.yourdomain.com
    secretName: weaver-tls
  rules:
  - host: api.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: weaver-ai
            port:
              number: 8000
```

```bash
# Apply ingress
kubectl apply -f k8s/ingress.yaml

# Check ingress
kubectl get ingress -n weaver-ai
```

#### Step 5: Horizontal Pod Autoscaling

```bash
# Enable autoscaling based on CPU
kubectl autoscale deployment weaver-ai \
  --namespace weaver-ai \
  --cpu-percent=70 \
  --min=2 \
  --max=10

# Check HPA status
kubectl get hpa -n weaver-ai
```

#### Step 6: Update Deployment

```bash
# Update image
kubectl set image deployment/weaver-ai \
  weaver-ai=weaver:v1.1.0 \
  -n weaver-ai

# Rollback if needed
kubectl rollout undo deployment/weaver-ai -n weaver-ai

# Check rollout status
kubectl rollout status deployment/weaver-ai -n weaver-ai
```

### Production Checklist

Before deploying to production, ensure:

#### Security
- [ ] All secrets stored in secure vault (AWS Secrets Manager, HashiCorp Vault, K8s Secrets)
- [ ] TLS/SSL certificates configured
- [ ] JWT keys are RSA 2048-bit or stronger
- [ ] API keys are unique and rotated regularly
- [ ] Rate limiting enabled (`WEAVER_RATELIMIT_RPS`)
- [ ] PII redaction enabled (`WEAVER_PII_REDACT=true`)
- [ ] URL allowlist configured (`WEAVER_URL_ALLOWLIST`)
- [ ] Audit logging configured (`WEAVER_AUDIT_PATH`)
- [ ] Signed telemetry enabled (`WEAVER_TELEMETRY_SIGNING_ENABLED=true`)

#### Performance
- [ ] Redis configured for multi-agent communication
- [ ] Appropriate resource limits set (CPU, memory)
- [ ] Horizontal pod autoscaling configured (K8s)
- [ ] Request timeout set (`WEAVER_REQUEST_TIMEOUT_MS`)
- [ ] Connection pooling configured

#### Monitoring
- [ ] Telemetry enabled (`WEAVER_TELEMETRY_ENABLED=true`)
- [ ] Health checks configured
- [ ] Log aggregation set up (ELK, Splunk, CloudWatch)
- [ ] Alerting configured for:
  - High error rates
  - Authentication failures
  - Rate limit violations
  - High latency (p99 > threshold)

#### Reliability
- [ ] Health endpoints exposed (`/health`, `/ready`)
- [ ] Graceful shutdown configured
- [ ] Backup and disaster recovery plan
- [ ] Multi-region deployment (if required)
- [ ] Circuit breakers configured for external APIs

#### Compliance
- [ ] Audit logs retained per compliance requirements
- [ ] Signed telemetry for tamper-evident logs
- [ ] Data retention policies configured
- [ ] GDPR/SOX/HIPAA controls enabled (if applicable)

---

## 🔒 Security

### Built-in Security Features

Weaver AI includes enterprise-grade security out of the box:

#### 1. Authentication & Authorization
- **JWT Authentication**: Secure token-based authentication
- **API Key Auth**: Simple bearer token authentication
- **RBAC**: Role-based access control for tools and endpoints
- **Scope-based Permissions**: Fine-grained capability control

```python
# Example: Require authentication
from weaver_ai.security.auth import authenticate
from weaver_ai.settings import AppSettings

settings = AppSettings(auth_mode="jwt", jwt_public_key="...")
user = authenticate(request.headers, settings)
```

#### 2. Rate Limiting
- **Token bucket algorithm**: Smooth rate limiting with burst support
- **Per-user quotas**: Individual limits per authenticated user
- **Redis-backed**: Distributed rate limiting across instances

```bash
# Configure rate limits
WEAVER_RATELIMIT_RPS=10      # 10 requests per second
WEAVER_RATELIMIT_BURST=20    # Allow bursts up to 20
```

#### 3. Input/Output Guards
- **Content filtering**: Block malicious or inappropriate content
- **URL allowlist/denylist**: Control external API access
- **PII redaction**: Automatic masking of sensitive data
- **Size limits**: Prevent abuse with request/response limits

```bash
# Enable PII redaction
WEAVER_PII_REDACT=true

# Configure URL filtering
WEAVER_URL_ALLOWLIST='["https://api.safe-domain.com"]'
WEAVER_URL_DENYLIST='["https://malicious.com"]'
```

#### 4. Audit Logging & Signed Telemetry
- **Comprehensive audit trails**: Log all security events
- **Cryptographically signed logs**: Tamper-evident audit trails (NEW!)
- **Non-repudiation**: Cryptographic proof of actions
- **Compliance ready**: GDPR, SOX, HIPAA, PCI DSS

```bash
# Enable signed telemetry
WEAVER_TELEMETRY_SIGNING_ENABLED=true
WEAVER_TELEMETRY_SIGNING_KEY="<rsa-private-key-pem>"
WEAVER_TELEMETRY_VERIFICATION_KEY="<rsa-public-key-pem>"
```

**Generate RSA keys for signing:**
```bash
# Generate key pair
openssl genrsa -out signing_key.pem 2048
openssl rsa -in signing_key.pem -pubout -out verify_key.pem

# Use in environment
export WEAVER_TELEMETRY_SIGNING_KEY="$(cat signing_key.pem)"
export WEAVER_TELEMETRY_VERIFICATION_KEY="$(cat verify_key.pem)"
```

#### 5. A2A Protocol Security
- **Message signing**: HMAC-SHA256 for agent-to-agent messages
- **Nonce tracking**: Prevent replay attacks
- **Timestamp validation**: Detect stale messages

```bash
# Configure A2A signing
WEAVER_A2A_SIGNING_PRIVATE_KEY_PEM="<your-private-key>"
WEAVER_A2A_SIGNING_PUBLIC_KEY_PEM="<your-public-key>"
```

### Security Best Practices

1. **Key Management**
   - Store secrets in secure vault (AWS Secrets Manager, HashiCorp Vault)
   - Rotate keys quarterly
   - Use different keys per environment
   - Never commit secrets to version control

2. **Network Security**
   - Always use TLS/HTTPS in production
   - Configure firewall rules to restrict access
   - Use VPC/private networks for internal services
   - Enable network policies in Kubernetes

3. **Monitoring**
   - Monitor authentication failures
   - Alert on rate limit violations
   - Track privilege escalation attempts
   - Audit tool usage patterns

4. **Compliance**
   - Enable signed telemetry for audit trails
   - Configure PII redaction
   - Set up log retention policies
   - Regular security audits

### Reporting Security Issues

**DO NOT** open public issues for security vulnerabilities.

Email: security@example.com

We'll respond within 24 hours and work with you on a fix.

---

## 📊 Monitoring

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

# Check readiness (includes dependency checks)
curl http://localhost:8000/ready
```

### Observability with Logfire

Weaver AI uses [Pydantic Logfire](https://docs.pydantic.dev/logfire/) for comprehensive observability:

```bash
# Enable telemetry
export WEAVER_TELEMETRY_ENABLED=true
export WEAVER_TELEMETRY_SERVICE_NAME=weaver-ai
export WEAVER_LOGFIRE_TOKEN=<your-token>
export WEAVER_LOGFIRE_SEND_TO_CLOUD=true
```

**Automatic Instrumentation:**
- FastAPI endpoints
- Redis operations
- HTTP requests (httpx)
- System metrics (CPU, memory, disk)

**Custom Spans:**
```python
from weaver_ai.telemetry import start_span

async def my_function():
    with start_span("my_operation", user_id="123"):
        # Your code here
        pass
```

### Key Metrics to Monitor

**Performance:**
- Request latency (p50, p95, p99)
- Agent execution time
- Tool usage frequency
- Cache hit rates

**Security:**
- Authentication failures
- Rate limit violations
- Policy violations
- Privilege escalation attempts

**Reliability:**
- Error rates by endpoint
- Model API failures
- Redis connection health
- Resource utilization (CPU, memory)

### Dashboards

Access your Logfire dashboard at: https://logfire.pydantic.dev

**Key Dashboards:**
1. **Request Overview**: Latency, throughput, errors
2. **Security Events**: Auth failures, policy violations
3. **Agent Performance**: Execution times, tool usage
4. **System Health**: CPU, memory, Redis health

---

## 📖 API Reference

### Simple API

#### `@agent` Decorator

Create an agent with a simple decorator:

```python
from weaver_ai.simple import agent

@agent(
    model="gpt-4",              # Model to use
    cache=False,                # Enable result caching
    cache_ttl=3600,             # Cache TTL in seconds
    retry=3,                    # Number of retry attempts
    timeout=30.0,               # Timeout in seconds
    fallback=None,              # Fallback function if agent fails
    tools=["web_search"],       # Available MCP tools
    permissions=["read"]        # Required permissions
)
async def my_agent(input: str) -> str:
    """Agent description."""
    pass
```

#### Flow Builder

Chain multiple agents together:

```python
from weaver_ai.simple import flow

# Linear chain
my_flow = flow("name").chain(agent1, agent2, agent3)

# Conditional routing
my_flow = flow("name").chain(classifier).route({
    "option1": agent1,
    "option2": agent2
})

# Parallel execution
my_flow = flow("name").parallel(agent1, agent2, agent3)

# Complex composition
my_flow = (
    flow("pipeline")
    .chain(preprocessor)
    .parallel(analyzer1, analyzer2)
    .chain(aggregator)
    .route({"success": finalizer, "error": error_handler})
)
```

#### Execution Functions

```python
from weaver_ai.simple import run, serve

# Async execution
result = await run(agent_or_flow, input_data)

# HTTP server
serve(agent_or_flow, port=8000, host="0.0.0.0")
```

### Core API

#### BaseAgent (Advanced)

For full control, use the `BaseAgent` class:

```python
from weaver_ai.agents import BaseAgent
from weaver_ai.events import Event

class MyAgent(BaseAgent):
    agent_type = "custom"
    capabilities = ["data_processing", "analysis"]

    async def process(self, event: Event) -> Result:
        # Your logic here
        return Result(
            success=True,
            data={"result": "..."},
            next_capabilities=["reporting"]
        )

# Initialize
agent = MyAgent()
await agent.initialize(redis_url="redis://localhost")
await agent.start()
```

### REST API Endpoints

When running as HTTP server:

#### POST /ask
Ask a question to the agent:

```bash
curl -X POST http://localhost:8000/ask \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is 2+2?"}'
```

#### GET /health
Health check endpoint:

```bash
curl http://localhost:8000/health
```

#### GET /docs
Interactive API documentation (Swagger UI):

```bash
open http://localhost:8000/docs
```

---

## 🏗️ Architecture

### Project Structure

```
weaver_ai/
├── simple/                  # 🎯 Simple API (START HERE)
│   ├── __init__.py         # Public exports: agent, run, serve, flow
│   ├── decorators.py       # @agent decorator
│   ├── flow.py             # Flow builder
│   └── runners.py          # run() and serve() functions
│
├── agents/                  # 🤖 Agent Framework
│   ├── base.py             # BaseAgent with memory & capabilities
│   ├── capabilities.py     # Capability management
│   ├── publisher.py        # Result publishing
│   └── tool_manager.py     # Tool integration
│
├── tools/                   # 🛠️ MCP Tool Framework
│   ├── base.py             # Tool base classes
│   ├── registry.py         # Tool registry
│   └── builtin/            # Built-in tools
│       ├── web_search.py
│       ├── documentation.py
│       └── database.py
│
├── models/                  # 🔄 Model Adapters
│   ├── router.py           # Multi-provider routing
│   ├── openai_adapter.py   # OpenAI integration
│   ├── anthropic_adapter.py # Anthropic integration
│   └── cached.py           # Caching layer
│
├── redis/                   # 📡 Redis Communication
│   ├── mesh.py             # Event mesh for agent communication
│   ├── queue.py            # Work queue
│   └── registry.py         # Agent registry
│
├── memory/                  # 💾 Agent Memory
│   ├── core.py             # Memory management
│   └── strategies.py       # Memory retention strategies
│
├── security/                # 🔒 Security Modules
│   ├── auth.py             # Authentication (JWT, API keys)
│   ├── rbac.py             # Authorization (RBAC)
│   ├── policy.py           # Input/output guards
│   ├── ratelimit.py        # Rate limiting
│   └── audit.py            # Audit logging
│
├── gateway.py               # 🌐 FastAPI application
├── a2a.py                   # 🤝 A2A protocol
├── mcp.py                   # 📋 MCP implementation
├── telemetry.py             # 📊 Observability (Logfire)
├── settings.py              # ⚙️ Configuration
└── policies/                # 📜 Policy definitions
    ├── roles.yaml          # Role definitions
    ├── tools.yaml          # Tool access policies
    └── guardrails.yaml     # Content policies
```

### Data Flow

```
User Request
    ↓
FastAPI Gateway (auth, rate limit)
    ↓
Agent Orchestrator
    ↓
┌─────────┴─────────┐
↓                   ↓
Tools (MCP)    LLM (Router)
↓                   ↓
└─────────┬─────────┘
    ↓
Verification & Metrics
    ↓
Response (with guards)
```

---

## 🤝 Contributing

We welcome contributions! Here's how to get started:

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
   black .                  # Format code
   ruff check .             # Lint code
   pytest                   # Run tests
   mypy weaver_ai           # Type check
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
   - `perf:` Performance
   - `chore:` Maintenance

6. **Push and create Pull Request**
   ```bash
   git push origin feature/amazing-feature
   ```

### Code Style

- Python 3.12+ with type hints
- Black for formatting (line length: 88)
- Ruff for linting
- Google-style docstrings
- pytest for testing

### Adding Features

#### New Tool

```python
# weaver_ai/tools/builtin/my_tool.py
from weaver_ai.tools import Tool, ToolCapability, ToolResult

class MyTool(Tool):
    name: str = "my_tool"
    description: str = "Does something useful"
    capabilities: list[ToolCapability] = [ToolCapability.COMPUTATION]
    required_scopes: list[str] = ["tool:my_tool"]

    async def execute(self, context, **kwargs) -> ToolResult:
        # Implementation
        return ToolResult(success=True, data={"result": "..."})
```

#### New Endpoint

```python
# weaver_ai/gateway.py
@app.post("/my-endpoint")
async def my_endpoint(request: Request):
    user = enforce_limit(request)  # Auth + rate limit
    # Your logic
    return {"status": "ok"}
```

---

## 📚 Advanced Usage

### Custom Model Integration

```python
from weaver_ai.simple import agent

# Use any OpenAI-compatible endpoint
@agent(
    model="llama-3-70b",
    api_base="http://localhost:11434/v1",  # Ollama
    api_key="not-needed"
)
async def local_agent(prompt: str) -> str:
    """Agent using local LLM."""
    pass
```

### Tool Integration

```python
from weaver_ai.simple import agent

@agent(
    model="gpt-4",
    tools=["python_eval", "web_search", "database", "documentation"]
)
async def research_agent(query: str) -> dict:
    """Agent with multiple tool access."""
    # Tools automatically available via MCP
    pass
```

### Caching

```python
from weaver_ai.simple import agent

@agent(
    model="gpt-4",
    cache=True,         # Enable caching
    cache_ttl=3600      # 1 hour TTL
)
async def expensive_agent(data: str) -> str:
    """Results cached for 1 hour."""
    pass
```

### Error Handling

```python
from weaver_ai.simple import agent, run

@agent(model="gpt-4", retry=3, timeout=30.0)
async def reliable_agent(input: str) -> str:
    """Automatic retry on failure."""
    pass

@agent(model="gpt-3.5-turbo")
async def fallback_agent(input: str) -> str:
    """Fallback implementation."""
    pass

@agent(model="gpt-4", fallback=fallback_agent)
async def main_agent(input: str) -> str:
    """Main agent with fallback."""
    pass

# Handle errors
try:
    result = await run(main_agent, "input")
except Exception as e:
    print(f"Error: {e}")
```

---

## 📝 Examples

Check the `examples/` directory for more:

- `examples/simple_agent.py` - Basic agent
- `examples/multi_agent.py` - Multi-agent orchestration
- `examples/tool_usage.py` - Using MCP tools
- `examples/signed_telemetry_demo.py` - Signed audit trails
- `examples/production_setup.py` - Production configuration

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Built on [Pydantic Agents](https://github.com/pydantic/pydantic-ai)
- Implements [Model Context Protocol](https://modelcontextprotocol.io/)
- Follows [A2A Protocol](https://github.com/a2a-protocol/a2a) specification
- Observability via [Pydantic Logfire](https://docs.pydantic.dev/logfire/)

---

## 📧 Support

- **Documentation**: [docs/](docs/)
- **Issues**: [GitHub Issues](https://github.com/doogie-bigmack/weaver.ai/issues)
- **Discussions**: [GitHub Discussions](https://github.com/doogie-bigmack/weaver.ai/discussions)
- **Security**: security@example.com

---

## 🗺️ Roadmap

### Recently Added ✅
- **Signed Telemetry** - Cryptographically signed audit trails for compliance
- **Logfire Integration** - Modern observability with Pydantic Logfire
- **Kubernetes Support** - Production-ready K8s manifests

### Coming Soon 🔜
- **API Key Expiry** - Automated key rotation (Phase 1)
- **Short-lived JWT Tokens** - 15-minute TTL with refresh (Phase 2)
- **OAuth2 Support** - Standard workload identity (Phase 2)
- **Mutual Attestation** - Agent-to-agent identity verification (Phase 3)
- **Enhanced A2A Protocol** - Full envelope validation (Phase 4)
- **mTLS Support** - Certificate-based mutual auth (Phase 5)

See [Security Roadmap](docs/SIGNED_TELEMETRY_IMPLEMENTATION.md) for details.

---

**Made with ❤️ by the Weaver AI Team**

⭐ Star us on GitHub if you find this useful!
