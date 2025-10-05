# Architecture Documentation Index

Welcome to the Weaver AI architecture documentation. This comprehensive guide provides end-to-end coverage of the system's design, patterns, and operational procedures.

## Quick Navigation

### Getting Started
- [Main Architecture Overview](./README.md) - Start here for system overview and key concepts
- [C4 Model Diagrams](./c4-diagrams.md) - Visual architecture diagrams
- [Security Architecture](./security-architecture.md) - Security design and threat model

### Architecture Decisions
- [ADR Index](./adr/README.md) - All architecture decision records
- [ADR-001: Dual API Design](./adr/001-dual-api-design.md)
- [ADR-002: Redis Event Mesh](./adr/002-redis-event-mesh.md)
- [ADR-003: MCP Tool Protocol](./adr/003-mcp-tool-protocol.md)

### Deployment & Operations
- [Deployment Guide](./deployment-guide.md) - Docker and Kubernetes deployment
- Monitoring Guide (coming soon)
- Disaster Recovery Plan (coming soon)

## Documentation Structure

```
docs/architecture/
├── README.md                    # Main architecture overview
├── INDEX.md                     # This file
├── c4-diagrams.md              # C4 model diagrams (Mermaid)
├── security-architecture.md     # Security design and threat model
├── deployment-guide.md          # Deployment procedures
└── adr/                        # Architecture Decision Records
    ├── README.md               # ADR index and template
    ├── 001-dual-api-design.md
    ├── 002-redis-event-mesh.md
    ├── 003-mcp-tool-protocol.md
    ├── 004-capability-based-routing.md (placeholder)
    ├── 005-security-first-design.md (placeholder)
    └── 006-pydantic-validation.md (placeholder)
```

## Documentation by Audience

### For Developers

**Getting Started**:
1. Read [Main Architecture Overview](./README.md) - Understand system components
2. Review [C4 Diagrams](./c4-diagrams.md) - See component relationships
3. Study [ADR-001](./adr/001-dual-api-design.md) - Learn API design philosophy
4. Check [Simple API Examples](../../README.md#quick-start) - Start building

**Advanced Topics**:
- [Redis Event Mesh](./adr/002-redis-event-mesh.md) - Distributed agent communication
- [MCP Tools](./adr/003-mcp-tool-protocol.md) - Tool integration standard
- [Security Architecture](./security-architecture.md) - Security controls

### For DevOps Engineers

**Essential Reading**:
1. [Deployment Guide](./deployment-guide.md) - Complete deployment procedures
2. [Security Architecture](./security-architecture.md) - Security requirements
3. [C4 Deployment Diagram](./c4-diagrams.md#deployment-diagram) - Infrastructure topology

**Operational Tasks**:
- [Docker Deployment](./deployment-guide.md#docker-deployment)
- [Kubernetes Deployment](./deployment-guide.md#kubernetes-deployment)
- [Scaling Strategies](./deployment-guide.md#scaling-strategies)
- [Disaster Recovery](./deployment-guide.md#disaster-recovery)

### For Security Engineers

**Security Documentation**:
1. [Security Architecture](./security-architecture.md) - Complete security design
2. [Threat Model](./security-architecture.md#threat-model) - STRIDE analysis
3. [Security Controls](./security-architecture.md#security-controls) - Defense layers
4. [Audit & Compliance](./security-architecture.md#audit--compliance) - GDPR, SOC2, HIPAA

**Key Security Features**:
- Authentication: JWT & API Key
- Authorization: RBAC with capability-based permissions
- Input Validation: Pydantic schemas + policy guards
- Output Sanitization: PII redaction
- Audit Logging: Comprehensive event tracking

### For Architects

**High-Level Design**:
1. [System Context](./README.md#system-context) - External integrations
2. [Architecture Principles](./README.md#architecture-principles) - Design philosophy
3. [Quality Attributes](./README.md#quality-attributes) - Non-functional requirements
4. [All ADRs](./adr/README.md) - Decision history

**Key Design Patterns**:
- **Dual API**: Simple decorator + BaseAgent for progressive disclosure
- **Event Mesh**: Redis pub/sub for capability-based routing
- **MCP Tools**: Standardized tool integration protocol
- **Security Layers**: Defense-in-depth with 9 security layers
- **Type Safety**: Python type hints for automatic routing

## Key Concepts

### System Layers

```
┌─────────────────────────────────────┐
│  Layer 1: Simple API                │  ← Developer Interface
│  (@agent decorator, flow builder)   │
├─────────────────────────────────────┤
│  Layer 2: Agent Framework           │  ← Agent Lifecycle
│  (BaseAgent, capabilities, events)  │
├─────────────────────────────────────┤
│  Layer 3: Tools & Models            │  ← External Integration
│  (MCP tools, model routing)         │
├─────────────────────────────────────┤
│  Layer 4: Security & Policy         │  ← Security Controls
│  (Auth, RBAC, guards, audit)        │
├─────────────────────────────────────┤
│  Layer 5: Communication             │  ← Distributed Agents
│  (Redis mesh, queues, registry)     │
└─────────────────────────────────────┘
```

### Data Flow

**Simple API Request**:
```
User Code → @agent decorator → SimpleAgentWrapper → BaseAgent
→ ModelRouter → LLM API → Verifier → Response
```

**HTTP API Request**:
```
Client → Gateway (auth/rate limit) → Policy guards
→ Orchestrator → Agent → Tools/Models → Verifier
→ Policy guards (PII redaction) → Audit log → Response
```

**Capability-Based Agent**:
```
Event → Redis channel → Subscribed agents → Process
→ Publish result → Next capability → Next agent
```

## Architecture Diagrams

### C4 Model Hierarchy

1. **Level 1: System Context** - Weaver AI in ecosystem ([view](./c4-diagrams.md#level-1-system-context-diagram))
   - External actors: Developers, users, admins
   - External systems: LLM providers, tools, monitoring

2. **Level 2: Container Diagram** - High-level containers ([view](./c4-diagrams.md#level-2-container-diagram))
   - API Gateway, Simple API, Orchestrator
   - Redis Event Mesh, Work Queue, Registry
   - Security, Memory, MCP Tools

3. **Level 3: Component Diagrams** - Internal structure ([view](./c4-diagrams.md#level-3-component-diagram-simple-api))
   - Simple API components
   - Security architecture
   - MCP tools framework
   - Redis event mesh

4. **Deployment Diagram** - Physical infrastructure ([view](./c4-diagrams.md#deployment-diagram))
   - Kubernetes pods, services, storage
   - External dependencies

### Sequence Diagrams

- [HTTP Request Flow](./c4-diagrams.md#data-flow-diagram-http-request)
- Event Mesh Communication (see [ADR-002](./adr/002-redis-event-mesh.md))

## Technology Stack

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| **Language** | Python | 3.12+ | Application runtime |
| **Web Framework** | FastAPI | 0.115+ | HTTP API |
| **Agent Framework** | Pydantic AI | Latest | Agent orchestration |
| **Validation** | Pydantic | 2.8+ | Type safety |
| **Communication** | Redis | 7+ | Event mesh |
| **Protocols** | A2A, MCP | Latest | Standards compliance |
| **Observability** | OpenTelemetry | 1.26+ | Metrics & tracing |
| **Container** | Docker | 20.10+ | Packaging |
| **Orchestration** | Kubernetes | 1.28+ | Production deployment |

## Compliance & Standards

### Industry Standards
- **A2A Protocol**: Agent-to-Agent communication
- **MCP**: Model Context Protocol for tools
- **OpenTelemetry**: Observability standard
- **C4 Model**: Architecture documentation

### Security Compliance
- **GDPR**: Data protection and privacy
- **SOC 2 Type II**: Security controls
- **HIPAA**: Healthcare data protection (optional)

### Development Standards
- **PEP 8**: Python style guide
- **PEP 484**: Type hints
- **Google Style**: Docstring format
- **Conventional Commits**: Commit messages

## Metrics & SLIs

### Service Level Indicators

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Availability** | 99.9% | Uptime monitoring |
| **Latency (p95)** | <500ms | HTTP request duration |
| **Error Rate** | <0.1% | 5xx responses / total |
| **Throughput** | 100+ RPS | Requests per second |

### Key Performance Indicators

- **Agent Execution Time**: <2s (p95)
- **LLM API Latency**: <1s (p95)
- **Tool Execution Time**: <500ms (p95)
- **Cache Hit Rate**: >40%
- **Redis Latency**: <10ms (p99)

## Roadmap

### Completed (v1.0)
- ✅ Dual API design (Simple + BaseAgent)
- ✅ Redis event mesh
- ✅ MCP tool protocol
- ✅ Security-first architecture
- ✅ Comprehensive documentation

### In Progress (v1.1)
- 🚧 Monitoring and observability guide
- 🚧 Additional ADRs (004-006)
- 🚧 Performance optimization guide
- 🚧 Developer onboarding guide

### Planned (v1.2+)
- 📋 Multi-tenancy support
- 📋 GraphQL API
- 📋 WebSocket streaming
- 📋 Enhanced caching layer
- 📋 ML-based routing optimization

## Contributing to Documentation

### Adding New Documentation

1. **Architecture Changes**: Create ADR first
2. **Diagrams**: Use Mermaid for consistency
3. **Code Examples**: Test before documenting
4. **Review**: Get architecture team approval

### Documentation Standards

- **Format**: Markdown with Mermaid diagrams
- **Structure**: Follow existing templates
- **Links**: Use relative paths
- **Version**: Update dates and version numbers
- **Tone**: Technical, concise, objective

### Tools

- **Mermaid**: [Live Editor](https://mermaid.live/)
- **Markdown**: Any markdown previewer
- **PlantUML**: Alternative diagram tool (if needed)
- **Draw.io**: For complex diagrams

## Getting Help

### Internal Resources
- **Slack**: #weaver-ai-architecture
- **Wiki**: https://wiki.example.com/weaver-ai
- **Office Hours**: Tuesdays 2-3pm PT

### External Resources
- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: Architecture discussions
- **Documentation**: [docs/](../)

## Document Maintenance

### Review Schedule
- **Quarterly**: Full documentation review
- **Per Release**: Update version numbers and roadmap
- **As Needed**: ADRs when architectural decisions made

### Ownership
- **Lead Architect**: Overall architecture
- **DevOps Lead**: Deployment guides
- **Security Lead**: Security architecture
- **Development Team**: Code examples and guides

### Changelog

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2025-10-03 | 1.0.0 | Initial comprehensive architecture documentation | Architecture Team |

---

**Last Updated**: 2025-10-03
**Document Version**: 1.0.0
**Maintained By**: Weaver AI Architecture Team
