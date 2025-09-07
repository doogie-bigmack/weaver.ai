# Claude Development Guidelines for Weaver AI

## Project Context

Weaver AI is an experimental A2A-compliant agent framework implementing secure multi-agent orchestration with comprehensive security controls, telemetry, and verification systems.

## Key Commands

### Development
```bash
# Install development dependencies
pip install -e .[dev]

# Run tests
pytest
pytest -v  # verbose
pytest tests/test_security_*  # run security tests

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
├── main.py           # Entry point
├── gateway.py        # FastAPI application
├── agent.py          # Core orchestrator
├── a2a.py           # A2A protocol
├── mcp.py           # MCP implementation
├── tools.py         # Tool framework
├── verifier.py      # Output validation
├── reward.py        # Performance metrics
├── model_router.py  # Model abstraction
├── settings.py      # Configuration
├── telemetry.py     # Observability
├── security/        # Security modules
│   ├── auth.py      # Authentication
│   ├── rbac.py      # Authorization
│   ├── policy.py    # Guardrails
│   ├── ratelimit.py # Rate limiting
│   ├── approval.py  # Approval flows
│   └── audit.py     # Audit logging
└── policies/        # Policy definitions
    ├── roles.yaml
    ├── tools.yaml
    └── guardrails.yaml
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

### Adding a New Tool
1. Create tool class in `tools.py`:
```python
class NewTool(Tool):
    name = "new_tool"
    description = "Tool description"
    required_scopes = ["tool:new_tool"]
    
    def call(self, **kwargs):
        # Implementation
        return {"result": ...}
```

2. Register with MCP server
3. Add to policies/tools.yaml
4. Write tests in tests/test_new_tool.py

### Adding a New Endpoint
1. Add route in `gateway.py`:
```python
@app.post("/new_endpoint")
async def new_endpoint(request: Request):
    user = enforce_limit(request)  # Auth + rate limit
    # Implementation
    return response
```

2. Add request/response models in `models.py`
3. Write integration tests
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
2. **Auth failures**: Verify JWT_SECRET is set
3. **Rate limit errors**: Check RATE_LIMIT_RPM setting
4. **Tool not found**: Ensure tool is registered with MCP
5. **Policy violations**: Check guardrails.yaml

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

### Required
- `JWT_SECRET`: Authentication key (generate with `openssl rand -hex 32`)

### Optional
- `PII_REDACT`: Enable PII redaction (default: false)
- `RATE_LIMIT_RPM`: Requests per minute (default: 60)
- `LOG_LEVEL`: Logging verbosity (default: INFO)

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
- **Tests**: `tests/`
- **Policies**: `weaver_ai/policies/`
- **Config**: `pyproject.toml`
- **Pre-commit**: `.pre-commit-config.yaml`

### Important Classes
- `AgentOrchestrator`: Core orchestration
- `A2AEnvelope`: Message format
- `MCPServer/Client`: Tool management
- `Verifier`: Output validation
- `AppSettings`: Configuration

### Security Modules
- `auth.authenticate()`: Validate tokens
- `rbac.check_access()`: Check permissions
- `ratelimit.enforce()`: Apply rate limits
- `policy.input_guard()`: Validate input
- `policy.output_guard()`: Sanitize output