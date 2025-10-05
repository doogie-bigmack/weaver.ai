# Weaver AI - Architecture Documentation

**Version:** 1.1.0
**Last Updated:** 2025-10-05
**Status:** Active Development

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Principles](#architecture-principles)
3. [System Context](#system-context)
4. [Container Architecture](#container-architecture)
5. [Component Architecture](#component-architecture)
6. [Data Architecture](#data-architecture)
7. [Security Architecture](#security-architecture)
8. [Deployment Architecture](#deployment-architecture)
9. [Quality Attributes](#quality-attributes)
10. [Architecture Decision Records](#architecture-decision-records)

## System Overview

### Purpose

Weaver AI is an A2A-compliant (Agent-to-Agent) multi-agent orchestration framework designed to enable developers to build secure, scalable, and observable AI agent systems with minimal boilerplate code.

### Key Capabilities

- **Simple Agent Creation**: Define agents using Python decorators in <20 lines of code
- **Multi-Agent Orchestration**: Capability-based routing and Redis event mesh for distributed agents
- **Enterprise Security**: JWT/API key authentication, RBAC, rate limiting, PII redaction, audit logging
- **Signed Telemetry**: Cryptographically signed audit trails for tamper-evident compliance (GDPR, SOX, HIPAA, PCI DSS)
- **MCP Integration**: Model Context Protocol for standardized tool management and execution
- **Type-Safe Flows**: Automatic agent routing based on Python type hints
- **Production Ready**: Docker support, health checks, telemetry, graceful shutdown

### Technology Stack

| Layer | Technology |
|-------|-----------|
| **Language** | Python 3.12+ |
| **Web Framework** | FastAPI (ASGI) |
| **Agent Framework** | Pydantic AI |
| **Communication** | Redis (pub/sub, event mesh) |
| **Protocols** | A2A, MCP (Model Context Protocol) |
| **LLM Providers** | OpenAI, Anthropic, Groq, vLLM, TGI |
| **Validation** | Pydantic v2 |
| **Observability** | OpenTelemetry |
| **Testing** | pytest, pytest-asyncio |
| **Containerization** | Docker, Docker Compose |

## Architecture Principles

### 1. Developer Experience First
- **Minimal Boilerplate**: Simple `@agent` decorator API hides complexity
- **Type Safety**: Leverage Python type hints for automatic routing and validation
- **Progressive Disclosure**: Start simple, add complexity only when needed

### 2. Security by Default
- All endpoints require authentication and rate limiting
- Input/output validation and sanitization at every boundary
- PII redaction enabled by default
- Comprehensive audit logging for compliance

### 3. Composability
- Agents are composable functions that can be chained, routed, or parallelized
- Tool integration via standardized MCP protocol
- Model-agnostic design supports multiple LLM providers

### 4. Distributed Architecture
- Redis event mesh enables horizontal scaling of agents
- Capability-based routing for automatic agent discovery
- Stateless HTTP gateway for scalability

### 5. Observable and Verifiable
- OpenTelemetry integration for distributed tracing
- Output verification and groundedness checking
- Comprehensive metrics for performance monitoring

## System Context

### External Actors

1. **Developers**: Build agents using Simple API or BaseAgent class
2. **End Users**: Interact via HTTP API or integrated applications
3. **Administrators**: Manage security policies, monitor system health
4. **LLM Providers**: OpenAI, Anthropic, Groq, self-hosted models
5. **External Tools**: Web search, databases, SailPoint IIQ, custom integrations

### System Boundary

```
┌─────────────────────────────────────────────────────────────┐
│                        Weaver AI                             │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Simple API  │  │   Gateway    │  │  Redis Mesh  │     │
│  │  (@agent)    │  │   (FastAPI)  │  │   (Events)   │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│         │                  │                  │             │
│         └──────────────────┼──────────────────┘             │
│                            │                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Agents     │  │  MCP Tools   │  │   Security   │     │
│  │ (Capability) │  │  (Registry)  │  │   (RBAC)     │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
         │                  │                  │
         ↓                  ↓                  ↓
   LLM Providers      External APIs     Identity Provider
```

### Integration Points

- **HTTP API**: RESTful endpoints for client applications
- **LLM APIs**: OpenAI, Anthropic, Groq APIs for model inference
- **Redis**: Event mesh, work queues, agent registry
- **MCP Servers**: External tool integrations (SailPoint, custom tools)
- **Telemetry**: OpenTelemetry collectors for monitoring

## Container Architecture

See [container-architecture.md](./container-architecture.md) for detailed C4 Container diagram.

### Key Containers

#### 1. API Gateway (FastAPI)
- **Responsibility**: HTTP endpoint management, authentication, rate limiting
- **Technology**: FastAPI (ASGI), Uvicorn
- **Scaling**: Horizontal (stateless)
- **Port**: 8000

#### 2. Agent Orchestrator
- **Responsibility**: Agent lifecycle, tool execution, verification
- **Technology**: Python, Pydantic AI
- **Scaling**: Vertical (CPU-bound for LLM calls)

#### 3. Redis Event Mesh
- **Responsibility**: Event pub/sub, work queues, agent registry
- **Technology**: Redis 7+
- **Scaling**: Redis Cluster for high availability
- **Port**: 6379

#### 4. MCP Tool Registry
- **Responsibility**: Tool discovery, execution, permission management
- **Technology**: Python, MCP SDK
- **Scaling**: Embedded in agent processes

## Component Architecture

See [component-architecture.md](./component-architecture.md) for detailed diagrams.

### Layer 1: Simple API (`weaver_ai/simple/`)

Entry point for developers to create agents with minimal code.

- **decorators.py**: `@agent` decorator, metadata extraction
- **flow.py**: Flow builder for chaining/routing agents
- **runners.py**: `run()` and `serve()` execution functions

### Layer 2: Agent Framework (`weaver_ai/agents/`)

Core agent implementation with capability-based routing.

- **base.py**: `BaseAgent` with memory, capabilities, event processing
- **capabilities.py**: Capability matching and constraint evaluation
- **publisher.py**: Result publishing to Redis event mesh
- **tool_manager.py**: Tool permission and execution management

### Layer 3: Tools (`weaver_ai/tools/`)

MCP-compliant tool framework.

- **base.py**: Tool base classes, execution context, results
- **registry.py**: Tool discovery and registration
- **builtin/**: Web search, documentation, SailPoint tools

### Layer 4: Models (`weaver_ai/models/`)

LLM provider adapters and routing.

- **router.py**: Multi-provider model routing
- **openai_adapter.py**: OpenAI API integration
- **anthropic_adapter.py**: Anthropic Claude integration
- **cached.py**: Response caching layer

### Layer 5: Redis Communication (`weaver_ai/redis/`)

Distributed agent communication.

- **mesh.py**: Event pub/sub mesh for agent coordination
- **queue.py**: Work queue for task distribution
- **registry.py**: Agent discovery and heartbeat

### Layer 6: Security (`weaver_ai/security/`)

Comprehensive security controls.

- **auth.py**: JWT/API key authentication
- **rbac.py**: Role-based access control
- **policy.py**: Input/output guards, PII redaction
- **ratelimit.py**: Token bucket rate limiting
- **audit.py**: Audit event logging
- **telemetry.py**: Cryptographic signing for tamper-evident logs

### Layer 7: Memory (`weaver_ai/memory/`)

Agent conversation memory management.

- **core.py**: Memory storage and retrieval
- **strategies.py**: Retention strategies (sliding window, summary)

## Data Architecture

### Data Flow: Simple API Request

```
1. User Code: @agent decorated function
2. Decorator: Extract type hints, create agent metadata
3. run(): Instantiate agent, initialize connections
4. Agent: Process input with LLM and tools
5. Verifier: Validate output for groundedness
6. Return: Response to user code
```

### Data Flow: HTTP API Request

```
1. Client: POST /ask with QueryRequest
2. Gateway: Authenticate, rate limit
3. Policy: Input guard (blocked content, PII check)
4. Orchestrator: Execute agent with tools
5. Verifier: Output validation
6. Policy: Output guard (PII redaction)
7. Gateway: Return QueryResponse
8. Audit: Log request/response
```

### Data Flow: Capability-Based Agent

```
1. Event: Published to Redis channel (capability:data_processing)
2. Mesh: Distribute to subscribed agents
3. Agent: Process event, execute tools
4. Result: Publish with next_capabilities
5. Mesh: Route to next agent
6. Registry: Update agent heartbeat
```

### Data Storage

| Data Type | Storage | Retention |
|-----------|---------|-----------|
| **Agent Memory** | Redis (in-memory) | Session-based |
| **Agent Registry** | Redis (hash) | TTL-based heartbeat |
| **Work Queue** | Redis (list) | Until processed |
| **Audit Logs** | File system | Configurable |
| **Metrics** | OpenTelemetry | External collector |
| **Cache** | Redis (string) | TTL-based |

## Security Architecture

See [security-architecture.md](./security-architecture.md) for detailed threat model.

### Security Layers

```
┌─────────────────────────────────────────────────┐
│  Layer 1: Transport Security (TLS)              │
├─────────────────────────────────────────────────┤
│  Layer 2: Authentication (JWT/API Key)          │
├─────────────────────────────────────────────────┤
│  Layer 3: Rate Limiting (Token Bucket)          │
├─────────────────────────────────────────────────┤
│  Layer 4: Input Validation (Pydantic)           │
├─────────────────────────────────────────────────┤
│  Layer 5: Authorization (RBAC)                  │
├─────────────────────────────────────────────────┤
│  Layer 6: Policy Guards (Content Filter)        │
├─────────────────────────────────────────────────┤
│  Layer 7: PII Redaction (Output Sanitization)   │
├─────────────────────────────────────────────────┤
│  Layer 8: Audit Logging (Compliance)            │
└─────────────────────────────────────────────────┘
```

### Authentication Modes

1. **API Key** (`WEAVER_AUTH_MODE=api_key`)
   - Header: `Authorization: Bearer <api-key>`
   - Validation: Against `WEAVER_ALLOWED_API_KEYS`
   - Use Case: Development, service-to-service

2. **JWT** (`WEAVER_AUTH_MODE=jwt`)
   - Header: `Authorization: Bearer <jwt-token>`
   - Validation: RSA public key verification
   - Use Case: Production, user-facing applications

### RBAC Model

- **Roles**: Defined in `policies/roles.yaml`
- **Scopes**: Capability-based permissions (e.g., `tool:web_search`)
- **Enforcement**: Pre-execution checks for tool access

### Tool Security

| Tool | Sensitivity | Rate Limit | Approval Required |
|------|------------|------------|-------------------|
| python_eval | low | 100/min | No |
| web_search | low | 60/min | No |
| database_query | high | 30/min | Yes |
| code_execution | high | 10/min | Yes |
| sailpoint_iiq | high | 30/min | No |

## Deployment Architecture

### Development Environment

```yaml
services:
  weaver-dev:
    build: .
    ports: ["8000:8000"]
    volumes: [".:/app"]
    environment:
      - WEAVER_MODEL_PROVIDER=stub
      - WEAVER_AUTH_MODE=api_key
```

### Production Environment

```yaml
services:
  weaver-api:
    image: weaver:prod
    replicas: 3
    ports: ["8000:8000"]
    environment:
      - WEAVER_MODEL_PROVIDER=openai
      - WEAVER_AUTH_MODE=jwt
      - WEAVER_TELEMETRY_ENABLED=true

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes: [redis-data:/data]
```

### Kubernetes Deployment

- **Deployment**: 3+ replicas for high availability
- **Service**: LoadBalancer for external access
- **ConfigMap**: Environment configuration
- **Secret**: API keys, JWT keys
- **PersistentVolume**: Redis data, audit logs

## Quality Attributes

### Performance

- **Target Latency**: <500ms (p95) for simple queries
- **Throughput**: 100+ requests/second per gateway instance
- **Caching**: Response caching reduces redundant LLM calls by 40%

### Scalability

- **Horizontal**: Stateless gateway scales to N instances
- **Vertical**: Agent processes scale with CPU for LLM workload
- **Redis**: Cluster mode for multi-node scaling

### Reliability

- **Availability**: 99.9% uptime target
- **Retry Logic**: Exponential backoff for LLM API failures
- **Circuit Breaker**: Fail fast for degraded services
- **Graceful Degradation**: Fallback agents for error handling

### Security

- **Authentication**: Mandatory for all endpoints
- **Encryption**: TLS 1.3 for transport
- **Audit**: 100% coverage of security events
- **Compliance**: GDPR-ready PII redaction

### Maintainability

- **Code Coverage**: 80%+ test coverage
- **Type Safety**: 100% type hints with mypy validation
- **Documentation**: Comprehensive inline and external docs
- **Modularity**: Clear separation of concerns across layers

## Architecture Decision Records

See [adr/](./adr/) directory for all ADRs.

### Key Decisions

- [ADR-001: Dual API Design](./adr/001-dual-api-design.md)
- [ADR-002: Redis Event Mesh](./adr/002-redis-event-mesh.md)
- [ADR-003: MCP Tool Protocol](./adr/003-mcp-tool-protocol.md)
- [ADR-004: Capability-Based Routing](./adr/004-capability-based-routing.md) (placeholder)
- [ADR-005: Security-First Design](./adr/005-security-first-design.md) (placeholder)
- [ADR-006: Cryptographic Signing for Audit Trails](./adr/006-signed-telemetry.md) (NEW)

## References

- [C4 Model Documentation](https://c4model.com/)
- [A2A Protocol Specification](https://github.com/a2a-protocol/a2a)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [Pydantic AI](https://github.com/pydantic/pydantic-ai)
- [FastAPI](https://fastapi.tiangolo.com/)
