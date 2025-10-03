# Claude Development Guidelines for Weaver AI

## Project Context

Weaver AI is an A2A-compliant agent framework with dual API design:
- **Simple API** (`weaver_ai/simple/`): Developer-friendly `@agent` decorator for creating agents in <20 lines
- **Core Infrastructure**: Enterprise-grade multi-agent orchestration with security, RBAC, MCP tool integration, and Redis-based event mesh

The framework implements capability-based agents that communicate via Redis, supports MCP (Model Context Protocol) for standardized tool management, and includes comprehensive security controls, telemetry, and verification systems.

## Architecture Overview

### Two-Level API Design

**1. Simple API** (Recommended for most use cases):
- Developers write async functions and decorate with `@agent`
- Framework handles all orchestration, security, and protocol details
- Type-based routing for multi-agent flows
- Example: `@agent(model="gpt-4") async def my_agent(input: str) -> str`

**2. Core Infrastructure** (For advanced scenarios):
- `BaseAgent` class with capability-based routing
- Redis event mesh for inter-agent communication
- Manual control over memory, tools, and publishing
- Use when you need: distributed agents, custom capabilities, or fine-grained control

### Multi-Agent Communication Flow

```
User Request → Gateway (auth/rate limit) → Agent Orchestrator
                                              ↓
                                         Execute Agent
                                              ↓
                                    ┌─────────┴─────────┐
                                    ↓                   ↓
                              Tools (MCP)          LLM (Router)
                                    ↓                   ↓
                                    └─────────┬─────────┘
                                              ↓
                                     Verification & Metrics
                                              ↓
                                      Response (with guards)
```

For capability-based agents:
```
Event → Redis Event Mesh → Subscribed Agents (by capability)
                                    ↓
                            Agent.process(event)
                                    ↓
                            Result with next_capabilities
                                    ↓
                            Published to Redis → Next Agent
```

### Key Architectural Patterns

**1. Capability-Based Routing**: Agents subscribe to capabilities (e.g., "data_processing", "analysis"). Events are routed based on required capabilities.

**2. MCP Tool Integration**: All tools follow Model Context Protocol for standardized discovery, execution, and security.

**3. Security Layers**:
   - Gateway: Authentication & rate limiting
   - Policy Engine: Input/output guards
   - RBAC: Capability-based permissions
   - Audit: All actions logged

**4. Type-Safe Flows**: Simple API uses Python type hints for automatic routing between agents.

**5. Redis-Based Event Mesh**: Agents communicate asynchronously via Redis pub/sub for scalable multi-agent orchestration.

## Key Commands

### Development
```bash
# Install development dependencies
pip install -e .[dev]

# Run tests
pytest
pytest -v  # verbose
pytest tests/test_security_*  # run security tests
pytest tests/unit/  # run unit tests
pytest tests/test_simple_api.py  # test simple API
pytest -k "test_name"  # run specific test

# Code quality
ruff check .          # linting
black .               # formatting
mypy weaver_ai        # type checking
pip-audit             # security audit

# Generate SBOM
cyclonedx-bom -o sbom/sbom.json

# Run the service
python -m weaver_ai.main --host 0.0.0.0 --port 8000
```

## Code Style & Conventions

### Python Standards
- **Python Version**: 3.12+
- **Type Hints**: Required for all functions
- **Docstrings**: Google style for public APIs
- **Imports**: Use `from __future__ import annotations`
- **Testing**: pytest with fixtures
- **Formatting**: Black with default settings
- **Linting**: Ruff for code quality

### Project Structure
```
weaver_ai/
├── simple/              # Simple API for developers
│   ├── decorators.py   # @agent decorator
│   ├── flow.py         # Flow builder
│   └── runners.py      # run() and serve()
├── agents/             # Agent framework
│   ├── base.py         # BaseAgent with memory & capabilities
│   ├── decorators.py   # Agent decorators
│   ├── capabilities.py # Capability management
│   ├── publisher.py    # Result publishing
│   └── tool_manager.py # Tool integration
├── tools/              # MCP tool framework
│   ├── base.py         # Tool base classes
│   ├── registry.py     # Tool registry
│   └── builtin/        # Built-in tools
│       ├── web_search.py
│       ├── documentation.py
│       └── sailpoint.py
├── models/             # Model adapters
│   ├── router.py       # Model routing
│   ├── openai_adapter.py
│   ├── anthropic_adapter.py
│   └── cached.py       # Caching layer
├── redis/              # Redis communication
│   ├── mesh.py         # Event mesh
│   ├── queue.py        # Work queue
│   └── registry.py     # Agent registry
├── memory/             # Agent memory
│   ├── core.py         # Memory management
│   └── strategies.py   # Memory strategies
├── security/           # Security modules
│   ├── auth.py         # Authentication
│   ├── rbac.py         # Authorization
│   ├── policy.py       # Guardrails
│   ├── ratelimit.py    # Rate limiting
│   └── audit.py        # Audit logging
├── gateway.py          # FastAPI application
├── agent.py            # Core orchestrator (legacy)
├── a2a.py              # A2A protocol
├── mcp.py              # MCP implementation
├── verifier.py         # Output validation
├── settings.py         # Configuration
├── legacy_tools.py     # Legacy tool code
└── policies/           # Policy definitions
    ├── roles.yaml
    ├── tools.yaml
    └── guardrails.yaml

tests/
├── unit/               # Unit tests
├── test_simple_api.py  # Simple API tests
└── test_security_*     # Security tests

docs/                   # Documentation
```

## Security Considerations

### Always Implement
1. **Input Validation**: Validate all external inputs
2. **Authentication**: Check auth on all endpoints
3. **Authorization**: Enforce RBAC for tool access
4. **Rate Limiting**: Apply to all user-facing endpoints
5. **Audit Logging**: Log security-relevant events
6. **Cryptography**: Use JWT for signing, validate signatures
7. **Nonce Tracking**: Prevent replay attacks

### Never Do
1. Don't expose internal errors to users
2. Don't log sensitive data (PII, tokens)
3. Don't bypass security checks for convenience
4. Don't use eval() or exec() on user input
5. Don't store secrets in code

## Testing Guidelines

### Test Coverage Requirements
- Minimum 80% code coverage
- 100% coverage for security modules
- All public APIs must have tests
- Integration tests for critical paths

### Test Patterns
```python
# Use fixtures for reusable components
@pytest.fixture
def mcp_server():
    return MCPServer("test", "secret")

# Test both success and failure cases
def test_auth_valid_token():
    # Test valid authentication

def test_auth_invalid_token():
    # Test rejection of invalid tokens

# Use parametrize for multiple scenarios
@pytest.mark.parametrize("input,expected", [
    ("2+2", 4),
    ("10-5", 5),
])
def test_calculation(input, expected):
    # Test multiple cases
```

## Common Tasks

### Creating a Simple Agent
The recommended way to create agents is using the Simple API:

```python
from weaver_ai.simple import agent, run

@agent(model="gpt-4")
async def my_agent(input: str) -> str:
    """Agent description."""
    return f"Processed: {input}"

# Run the agent
result = await run(my_agent, "hello")
```

With configuration:
```python
@agent(
    model="gpt-4",
    cache=True,
    retry=3,
    timeout=30.0,
    permissions=["read", "write"],
    tools=["web_search", "documentation"]
)
async def advanced_agent(query: str) -> dict:
    """Advanced agent with tools."""
    return {"result": "..."}
```

### Creating Multi-Agent Flows
```python
from weaver_ai.simple import agent, flow

@agent(model="gpt-4")
async def classifier(text: str) -> Literal["tech", "sales"]:
    """Classify inquiries."""
    pass

@agent(model="gpt-3.5-turbo")
async def tech_handler(query: str) -> str:
    """Handle technical queries."""
    pass

# Build flow with routing
support_flow = (
    flow("support")
    .chain(classifier)
    .route({
        "tech": tech_handler,
        "sales": sales_handler
    })
)

result = await support_flow.run("My API isn't working")
```

### Adding a New MCP Tool
1. Create tool class in `weaver_ai/tools/builtin/`:
```python
from weaver_ai.tools import Tool, ToolCapability, ToolExecutionContext, ToolResult
import time

class NewTool(Tool):
    name: str = "new_tool"
    description: str = "Tool description"
    version: str = "1.0.0"
    capabilities: list[ToolCapability] = [ToolCapability.COMPUTATION]
    required_scopes: list[str] = ["tool:new_tool"]

    async def execute(
        self,
        context: ToolExecutionContext,
        **kwargs
    ) -> ToolResult:
        """Execute the tool."""
        start = time.time()
        try:
            # Implementation
            result = {"output": "..."}
            return ToolResult(
                success=True,
                data=result,
                execution_time=time.time() - start,
                tool_name=self.name
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=str(e),
                execution_time=time.time() - start,
                tool_name=self.name
            )
```

2. Register in `weaver_ai/tools/builtin/__init__.py`
3. Add to `weaver_ai/policies/tools.yaml`
4. Write tests in `tests/test_new_tool.py`

### Creating a Capability-Based Agent
For advanced use cases, use `BaseAgent` with capabilities:

```python
from weaver_ai.agents import BaseAgent
from weaver_ai.events import Event

class CustomAgent(BaseAgent):
    agent_type = "custom"
    capabilities = ["data_processing", "analysis"]

    async def process(self, event: Event) -> Result:
        """Process incoming events."""
        # Your logic here
        return Result(
            success=True,
            data={"result": "..."},
            next_capabilities=["reporting"]
        )

# Initialize and start
agent = CustomAgent()
await agent.initialize(redis_url="redis://localhost")
await agent.start()
```

### Adding a New Gateway Endpoint
1. Add route in `gateway.py`:
```python
@app.post("/new_endpoint")
async def new_endpoint(request: Request):
    user = enforce_limit(request)  # Auth + rate limit
    # Implementation
    return response
```

2. Add request/response models in `weaver_ai/models/api.py`
3. Write tests in `tests/unit/test_gateway.py`
4. Update API documentation

### Implementing Security Policy
1. Define policy in appropriate YAML file
2. Load in gateway or agent
3. Apply via policy.input_guard() or policy.output_guard()
4. Add tests for policy enforcement

## Performance Optimization

### Key Metrics
- **Latency**: Track via telemetry
- **Throughput**: Monitor rate limits
- **Resource Usage**: Check memory/CPU
- **Cache Hit Rate**: For repeated operations

### Optimization Strategies
1. Use async/await for I/O operations
2. Implement caching for expensive operations
3. Batch operations where possible
4. Profile before optimizing

## Error Handling

### Standard Pattern
```python
try:
    # Operation
    result = perform_operation()
except SpecificError as e:
    # Log for debugging
    logger.error(f"Operation failed: {e}")
    # Return user-safe error
    raise HTTPException(
        status_code=400,
        detail="Operation failed"
    )
```

### Error Response Format
```python
class ErrorResponse(BaseModel):
    error: str
    message: str
    request_id: str | None = None
```

## Debugging Tips

### Useful Commands
```bash
# Watch logs
uvicorn weaver_ai.main:app --reload --log-level debug

# Test specific endpoint
curl -X POST http://localhost:8000/ask \
  -H "Authorization: Bearer token" \
  -H "Content-Type: application/json" \
  -d '{"query": "2+2"}'

# Profile performance
python -m cProfile -o profile.stats -m weaver_ai.main

# Check for security issues
bandit -r weaver_ai/
safety check
```

### Common Issues
1. **Import errors**: Check circular dependencies
2. **Auth failures**: Verify `WEAVER_` prefixed environment variables are set
3. **Rate limit errors**: Check `WEAVER_RATELIMIT_RPS` setting
4. **Tool not found**: Ensure tool is registered in `ToolRegistry` and available via MCP
5. **Policy violations**: Check `weaver_ai/policies/guardrails.yaml`
6. **Redis connection errors**: Verify Redis is running and `REDIS_HOST` is set
7. **Agent not receiving events**: Check capability matching and Redis event mesh connection

## Git Workflow

### Commit Messages
```
feat: Add new tool for data processing
fix: Correct JWT validation logic
docs: Update API documentation
test: Add tests for rate limiting
refactor: Simplify agent orchestration
perf: Optimize query processing
security: Fix authentication bypass
```

### Pre-commit Checks
- Formatting (black)
- Linting (ruff)
- Type checking (mypy)
- Security scanning (pip-audit)

## Environment Variables

All Weaver AI settings use the `WEAVER_` prefix (configured in `AppSettings`).

### Model Configuration
- `WEAVER_MODEL_PROVIDER`: Model provider (`openai`, `anthropic`, `vllm`, `tgi`, `stub`)
- `WEAVER_MODEL_NAME`: Model name (e.g., `gpt-4o`, `claude-3-opus-20240229`)
- `WEAVER_MODEL_ENDPOINT`: Custom model endpoint (optional)
- `WEAVER_MODEL_API_KEY`: API key for model provider (optional)

### Security
- `WEAVER_AUTH_MODE`: Authentication mode (`api_key` or `jwt`)
- `WEAVER_ALLOWED_API_KEYS`: Comma-separated list of allowed API keys
- `WEAVER_JWT_PUBLIC_KEY`: RSA public key for JWT validation
- `WEAVER_PII_REDACT`: Enable PII redaction (default: true)
- `WEAVER_A2A_SIGNING_PRIVATE_KEY_PEM`: Private key for A2A signing
- `WEAVER_A2A_SIGNING_PUBLIC_KEY_PEM`: Public key for A2A verification
- `WEAVER_MCP_SERVER_PUBLIC_KEYS`: JSON dict of MCP server public keys

### Rate Limiting & Performance
- `WEAVER_RATELIMIT_RPS`: Requests per second (default: 5)
- `WEAVER_RATELIMIT_BURST`: Burst limit (default: 10)
- `WEAVER_REQUEST_MAX_TOKENS`: Maximum tokens per request (default: 4096)
- `WEAVER_REQUEST_TIMEOUT_MS`: Request timeout in ms (default: 25000)
- `WEAVER_REQUEST_MAX_TOOLS`: Maximum tools per request (default: 3)

### URL Filtering
- `WEAVER_URL_ALLOWLIST`: JSON list of allowed URL patterns
- `WEAVER_URL_DENYLIST`: JSON list of denied URL patterns

### Monitoring
- `WEAVER_TELEMETRY_ENABLED`: Enable telemetry (default: false)
- `WEAVER_TELEMETRY_ENDPOINT`: OpenTelemetry endpoint
- `WEAVER_AUDIT_PATH`: Path to audit log file (default: `./audit.log`)

### Redis (for multi-agent orchestration)
- `REDIS_HOST`: Redis host (default: localhost)
- `REDIS_PORT`: Redis port (default: 6379)
- `REDIS_PASSWORD`: Redis password (optional)
- `REDIS_DB`: Redis database number (default: 0)

## Documentation

### Code Documentation
- Document all public APIs
- Include type hints
- Add examples for complex functions
- Explain security implications

### API Documentation
- FastAPI generates OpenAPI spec
- Access at http://localhost:8000/docs
- Keep endpoint descriptions updated

## Monitoring & Observability

### Key Metrics to Track
- Request latency (p50, p95, p99)
- Error rates by endpoint
- Tool usage frequency
- Authentication failures
- Rate limit violations
- Verification success rate

### Telemetry Integration
- OpenTelemetry for distributed tracing
- Structured logging with correlation IDs
- Metrics export to monitoring systems

## Future Enhancements

### Planned Features
1. Additional tool integrations
2. Multi-model routing strategies
3. Advanced caching layer
4. WebSocket support for streaming
5. Batch processing capabilities
6. Enhanced approval workflows

### Extension Points
- Custom model adapters
- Tool plugin system
- Policy engine enhancements
- Telemetry exporters

## Quick Reference

### File Locations
- **Main code**: `weaver_ai/`
- **Tests**: `tests/` (with `unit/` subdirectory)
- **Documentation**: `docs/`
- **Policies**: `weaver_ai/policies/`
- **Config**: `pyproject.toml`
- **Pre-commit**: `.pre-commit-config.yaml`

### Important Classes & Modules

**Simple API** (`weaver_ai/simple/`):
- `@agent` decorator: Create agents from async functions
- `flow()`: Build multi-agent workflows
- `run()`: Execute agents
- `serve()`: Run as HTTP server

**Core Infrastructure**:
- `BaseAgent` (`agents/base.py`): Capability-based agent with memory
- `AgentOrchestrator` (`agent.py`): Legacy core orchestration
- `ModelRouter` (`models/router.py`): Multi-provider model routing
- `AppSettings` (`settings.py`): Configuration with `WEAVER_` prefix
- `A2AEnvelope` (`a2a.py`): Agent-to-Agent message format

**MCP & Tools**:
- `Tool` (`tools/base.py`): Base class for MCP tools
- `ToolRegistry` (`tools/registry.py`): Tool registration and discovery
- `MCPServer/Client` (`mcp.py`): Model Context Protocol implementation
- Built-in tools: `web_search`, `documentation`, `sailpoint`

**Redis Communication**:
- `RedisEventMesh` (`redis/mesh.py`): Event-based agent communication
- `WorkQueue` (`redis/queue.py`): Task queue for agents
- `RedisAgentRegistry` (`redis/registry.py`): Agent discovery

**Memory & Caching**:
- `AgentMemory` (`memory/core.py`): Conversation memory management
- `MemoryStrategy` (`memory/strategies.py`): Memory retention strategies
- `CachedModel` (`models/cached.py`): Response caching layer

**Security Modules**:
- `auth.authenticate()`: Validate tokens with `WEAVER_` env vars
- `rbac.check_access()`: Check capability-based permissions
- `ratelimit.enforce()`: Apply rate limits with Redis backend
- `policy.input_guard()`: Validate input against guardrails
- `policy.output_guard()`: Sanitize output and redact PII

**Verification & Metrics**:
- `Verifier` (`verifier.py`): Output validation and groundedness checking
- `compute_reward()` (`reward.py`): Performance scoring
