# Weaver AI Agent Architecture

## Overview

Weaver AI is an A2A-compliant agent framework that implements secure, observable, and verifiable agent interactions using Pydantic Agents and Model Context Protocol (MCP).

## Core Components

### 1. Agent Orchestrator (`agent.py`)
- **Purpose**: Central coordinator for agent operations
- **Key Responsibilities**:
  - Query processing and routing
  - Tool invocation management
  - Metrics collection (latency, groundedness, verification)
  - Reward computation for agent performance
- **Integration Points**:
  - Model Router for LLM interactions
  - MCP Client for tool execution
  - Verifier for output validation
  - RBAC for access control

### 2. Gateway Layer (`gateway.py`)
- **Purpose**: FastAPI-based HTTP interface
- **Endpoints**:
  - `/health` - Health check
  - `/whoami` - User authentication verification
  - `/ask` - Main query endpoint
- **Security Features**:
  - Authentication enforcement
  - Rate limiting
  - Input/output guardrails
  - PII redaction support

### 3. A2A Protocol (`a2a.py`)
- **Purpose**: Agent-to-Agent communication protocol
- **Features**:
  - Envelope-based messaging with request tracking
  - Capability declarations
  - Budget constraints (tokens, time, tool calls)
  - Cryptographic signing and verification
  - Replay attack prevention via nonce tracking
  - Timestamp validation with configurable skew

### 4. MCP Integration (`mcp.py`)
- **Purpose**: Model Context Protocol implementation for tool management
- **Components**:
  - `MCPServer`: Tool registry and execution
  - `MCPClient`: Secure tool invocation
  - `ToolSpec`: Tool metadata and schema definitions
- **Security**: JWT-based request/response signing

### 5. Tool System (`tools.py`)
- **Purpose**: Extensible tool framework
- **Current Tools**:
  - `PythonEvalTool`: Safe arithmetic expression evaluation
- **Extension Points**:
  - Abstract `Tool` base class
  - Schema generation support
  - Scope-based access control

## Security Architecture

### Authentication & Authorization
- **Authentication** (`security/auth.py`):
  - Bearer token validation
  - User context extraction
  - Session management

- **RBAC** (`security/rbac.py`):
  - Role-based access control
  - Tool-level permissions
  - Policy-based authorization

- **Rate Limiting** (`security/ratelimit.py`):
  - User-level request throttling
  - Configurable limits via settings

### Policy Framework
- **Input Guards** (`security/policy.py`):
  - Query validation
  - Injection attack prevention
  - Content filtering

- **Output Guards**:
  - Response sanitization
  - PII redaction
  - Content compliance

- **Approval Workflows** (`security/approval.py`):
  - Multi-stage approval chains
  - Audit trail generation

### Audit & Telemetry
- **Audit Logging** (`security/audit.py`):
  - Request/response tracking
  - Security event logging
  - Compliance reporting

- **Telemetry** (`telemetry.py`):
  - OpenTelemetry integration
  - Performance metrics
  - Distributed tracing

## Model Routing

### Router Architecture (`model_router.py`)
- **Purpose**: Abstract interface for model selection and invocation
- **Current Implementation**: `StubModel` for testing
- **Extension Points**:
  - Custom routing logic
  - Model-specific adapters
  - Load balancing strategies

## Verification System

### Verifier (`verifier.py`)
- **Purpose**: Output validation and quality assurance
- **Metrics**:
  - Groundedness score
  - Tool requirement detection
  - Success/failure classification
- **Integration**: Feeds into reward computation

### Reward System (`reward.py`)
- **Purpose**: Agent performance evaluation
- **Factors**:
  - Verification results
  - Response latency
  - Resource utilization

## Configuration

### Settings Management (`settings.py`)
- **AppSettings**: Central configuration class
- **Environment Variables**:
  - `JWT_SECRET`: Authentication key
  - `PII_REDACT`: Enable PII redaction
  - `RATE_LIMIT_RPM`: Requests per minute limit

### Policy Files
- `policies/roles.yaml`: Role definitions and permissions
- `policies/tools.yaml`: Tool access policies
- `policies/guardrails.yaml`: Input/output filtering rules

## Testing Architecture

### Test Coverage
- **Unit Tests**:
  - A2A envelope signing/verification
  - Agent math operations
  - MCP client/server interaction
  - Security components (auth, RBAC, rate limiting)
  - Guardrail policies

- **Integration Tests**:
  - Gateway smoke tests
  - End-to-end request flow

### Test Execution
```bash
pytest                    # Run all tests
pytest tests/test_*.py   # Run specific test file
pytest -v                # Verbose output
```

## Development Workflow

### Setup
1. Install dependencies: `pip install -e .[dev]`
2. Configure pre-commit hooks: `pre-commit install`
3. Run tests: `pytest`

### Code Quality
- **Linting**: `ruff check .`
- **Formatting**: `black .`
- **Type Checking**: `mypy weaver_ai`
- **Security Scanning**: `pip-audit`

### Running the Service
```bash
python -m weaver_ai.main --host 0.0.0.0 --port 8000
```

## Extension Points

### Adding New Tools
1. Create tool class inheriting from `Tool`
2. Implement `call()` method
3. Define input/output schemas
4. Register with MCP server
5. Add required scopes to policies

### Custom Model Integration
1. Implement `ModelRouter` interface
2. Add model-specific configuration
3. Update settings for model selection
4. Implement retry/fallback logic

### Security Policies
1. Define policies in YAML format
2. Add to appropriate policy file
3. Update RBAC roles if needed
4. Test with security test suite

## Architecture Principles

1. **Security First**: All operations authenticated and authorized
2. **Observable**: Comprehensive telemetry and audit logging
3. **Verifiable**: Output validation and groundedness checking
4. **Extensible**: Plugin architecture for tools and models
5. **Compliant**: A2A protocol adherence
6. **Testable**: Comprehensive test coverage
7. **Configurable**: Environment-based configuration
