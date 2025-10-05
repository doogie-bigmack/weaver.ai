# C4 Model Diagrams - Weaver AI

This document contains C4 model diagrams for Weaver AI architecture using Mermaid notation.

## Level 1: System Context Diagram

Shows how Weaver AI fits into the broader ecosystem and its interactions with external systems.

```mermaid
graph TB
    subgraph "External Actors"
        DEV[Developer<br/>Builds agents with @agent decorator]
        USER[End User<br/>Consumes agent services via API]
        ADMIN[Administrator<br/>Manages policies and monitors]
    end

    subgraph "Weaver AI System"
        WEAVER[Weaver AI<br/>Multi-agent orchestration framework]
    end

    subgraph "External Systems"
        OPENAI[OpenAI API<br/>GPT-4, GPT-3.5]
        ANTHROPIC[Anthropic API<br/>Claude models]
        GROQ[Groq API<br/>Fast inference]
        REDIS[Redis<br/>Event mesh & caching]
        TOOLS[External Tools<br/>Web search, databases, SailPoint]
        OTEL[OpenTelemetry Collector<br/>Metrics & traces]
    end

    DEV -->|Creates agents| WEAVER
    USER -->|HTTP requests| WEAVER
    ADMIN -->|Configures policies| WEAVER

    WEAVER -->|LLM inference| OPENAI
    WEAVER -->|LLM inference| ANTHROPIC
    WEAVER -->|LLM inference| GROQ
    WEAVER -->|Event pub/sub| REDIS
    WEAVER -->|Tool execution| TOOLS
    WEAVER -->|Telemetry| OTEL

    style WEAVER fill:#1168bd,stroke:#0b4884,color:#ffffff
    style DEV fill:#08427b,stroke:#052e56,color:#ffffff
    style USER fill:#08427b,stroke:#052e56,color:#ffffff
    style ADMIN fill:#08427b,stroke:#052e56,color:#ffffff
```

## Level 2: Container Diagram

Shows the high-level containers (applications, services) that make up Weaver AI.

```mermaid
graph TB
    subgraph "Weaver AI System"
        subgraph "API Layer"
            GATEWAY[API Gateway<br/>FastAPI<br/>Port 8000]
        end

        subgraph "Agent Layer"
            SIMPLE[Simple API<br/>@agent decorators<br/>Type-safe flows]
            ORCHESTRATOR[Agent Orchestrator<br/>Capability routing<br/>Tool execution]
            AGENTS[BaseAgent Instances<br/>Distributed agents<br/>Event processing]
        end

        subgraph "Infrastructure Layer"
            MCP[MCP Tool Registry<br/>Tool discovery<br/>Permission mgmt]
            MODELS[Model Router<br/>Multi-provider<br/>Response caching]
            SECURITY[Security Module<br/>Auth, RBAC<br/>Policy guards]
            MEMORY[Agent Memory<br/>Conversation state<br/>Redis-backed]
        end

        subgraph "Communication Layer"
            MESH[Redis Event Mesh<br/>Pub/sub channels<br/>Agent coordination]
            QUEUE[Work Queue<br/>Task distribution<br/>Priority handling]
            REGISTRY[Agent Registry<br/>Discovery<br/>Heartbeat]
        end
    end

    subgraph "External"
        USER[User/Client]
        LLM[LLM Providers<br/>OpenAI/Anthropic/Groq]
        REDIS_EXT[Redis Server<br/>Port 6379]
        TOOLS_EXT[External Tools<br/>MCP Servers]
    end

    USER -->|HTTP POST /ask| GATEWAY
    GATEWAY -->|Auth & Rate Limit| SECURITY
    GATEWAY -->|Route request| ORCHESTRATOR

    SIMPLE -.->|Creates instances| AGENTS
    ORCHESTRATOR -->|Execute| AGENTS

    AGENTS -->|Use tools| MCP
    AGENTS -->|LLM calls| MODELS
    AGENTS -->|Store context| MEMORY
    AGENTS -->|Publish events| MESH
    AGENTS -->|Subscribe to| MESH
    AGENTS -->|Register| REGISTRY

    MCP -->|External calls| TOOLS_EXT
    MODELS -->|API calls| LLM
    MEMORY -->|Store/retrieve| REDIS_EXT
    MESH -->|Pub/sub| REDIS_EXT
    QUEUE -->|Task queue| REDIS_EXT
    REGISTRY -->|Discovery| REDIS_EXT

    style GATEWAY fill:#1168bd,stroke:#0b4884,color:#ffffff
    style SIMPLE fill:#1168bd,stroke:#0b4884,color:#ffffff
    style ORCHESTRATOR fill:#1168bd,stroke:#0b4884,color:#ffffff
    style AGENTS fill:#1168bd,stroke:#0b4884,color:#ffffff
    style MCP fill:#438dd5,stroke:#2e6295,color:#ffffff
    style MODELS fill:#438dd5,stroke:#2e6295,color:#ffffff
    style SECURITY fill:#438dd5,stroke:#2e6295,color:#ffffff
    style MEMORY fill:#438dd5,stroke:#2e6295,color:#ffffff
    style MESH fill:#85bbf0,stroke:#5d82a8,color:#000000
    style QUEUE fill:#85bbf0,stroke:#5d82a8,color:#000000
    style REGISTRY fill:#85bbf0,stroke:#5d82a8,color:#000000
```

## Level 3: Component Diagram - Simple API

Detailed view of the Simple API layer components.

```mermaid
graph TB
    subgraph "Simple API (weaver_ai/simple/)"
        DECORATOR[decorators.py<br/>@agent decorator<br/>Type extraction<br/>Metadata attachment]
        FLOW[flow.py<br/>Flow builder<br/>Chain/Route/Parallel<br/>Type-based routing]
        RUNNERS[runners.py<br/>run() executor<br/>serve() HTTP server<br/>Async execution]
    end

    subgraph "Agent Framework (weaver_ai/agents/)"
        BASE[base.py<br/>BaseAgent class<br/>Capability matching<br/>Event processing]
        WRAPPER[SimpleAgentWrapper<br/>Function -> Agent<br/>Auto initialization<br/>Type routing]
    end

    subgraph "Core Infrastructure"
        ROUTER[ModelRouter<br/>LLM calls]
        MCPCLIENT[MCPClient<br/>Tool execution]
        EVENTMESH[RedisEventMesh<br/>Event distribution]
    end

    USER[Developer Code<br/>@agent decorated function] -->|Decorate| DECORATOR
    DECORATOR -->|Create metadata| WRAPPER
    DECORATOR -->|Extract types| FLOW

    USER -->|Build workflow| FLOW
    FLOW -->|Chain agents| WRAPPER

    USER -->|Execute| RUNNERS
    RUNNERS -->|Instantiate| WRAPPER
    WRAPPER -->|Inherits from| BASE

    BASE -->|LLM inference| ROUTER
    BASE -->|Tool calls| MCPCLIENT
    BASE -->|Publish/subscribe| EVENTMESH

    style DECORATOR fill:#1168bd,stroke:#0b4884,color:#ffffff
    style FLOW fill:#1168bd,stroke:#0b4884,color:#ffffff
    style RUNNERS fill:#1168bd,stroke:#0b4884,color:#ffffff
    style WRAPPER fill:#438dd5,stroke:#2e6295,color:#ffffff
    style BASE fill:#438dd5,stroke:#2e6295,color:#ffffff
```

## Level 3: Component Diagram - Security Architecture

Detailed view of security components and enforcement points.

```mermaid
graph TB
    subgraph "Security Layer (weaver_ai/security/)"
        AUTH[auth.py<br/>JWT validation<br/>API key check<br/>User context]
        RBAC[rbac.py<br/>Role loading<br/>Scope checking<br/>Permission enforcement]
        POLICY[policy.py<br/>Input guards<br/>Output guards<br/>PII redaction]
        RATELIMIT[ratelimit.py<br/>Token bucket<br/>Per-user limits<br/>Redis-backed]
        AUDIT[audit.py<br/>Event logging<br/>Structured logs<br/>Compliance]
        TELEMETRY[telemetry.py<br/>Signed events<br/>RSA-256 signatures<br/>Non-repudiation]
    end

    subgraph "Policy Definitions"
        ROLES[roles.yaml<br/>user: tool:python_eval<br/>admin: admin:all]
        TOOLS[tools.yaml<br/>Tool permissions<br/>Rate limits<br/>Approval flags]
        GUARDS[guardrails.yaml<br/>Blocked content<br/>URL filters<br/>PII patterns]
    end

    subgraph "Request Flow"
        REQUEST[Incoming Request]
        GATEWAY[Gateway Handler]
        AGENT[Agent Execution]
        RESPONSE[Response]
    end

    REQUEST -->|1. Authenticate| AUTH
    AUTH -->|Load roles| ROLES
    AUTH -->|2. Rate limit| RATELIMIT
    RATELIMIT -->|3. Validate input| POLICY
    POLICY -->|Load guards| GUARDS
    POLICY -->|4. Check permissions| RBAC
    RBAC -->|Load permissions| TOOLS
    RBAC -->|5. Execute| AGENT
    AGENT -->|6. Sanitize output| POLICY
    POLICY -->|7. Log event| AUDIT
    AUDIT -->|8. Sign event| TELEMETRY
    TELEMETRY -->|9. Return| RESPONSE

    style AUTH fill:#1168bd,stroke:#0b4884,color:#ffffff
    style RBAC fill:#1168bd,stroke:#0b4884,color:#ffffff
    style POLICY fill:#1168bd,stroke:#0b4884,color:#ffffff
    style RATELIMIT fill:#1168bd,stroke:#0b4884,color:#ffffff
    style AUDIT fill:#1168bd,stroke:#0b4884,color:#ffffff
    style TELEMETRY fill:#1168bd,stroke:#0b4884,color:#ffffff
```

## Level 3: Component Diagram - MCP Tools

Detailed view of MCP tool framework.

```mermaid
graph TB
    subgraph "MCP Tool Framework (weaver_ai/tools/)"
        BASE[base.py<br/>Tool abstract class<br/>ToolExecutionContext<br/>ToolResult]
        REGISTRY[registry.py<br/>ToolRegistry<br/>Discovery<br/>Permission check]

        subgraph "Built-in Tools (builtin/)"
            WEB[web_search.py<br/>Internet search<br/>Result parsing]
            DOCS[documentation.py<br/>Doc retrieval<br/>Context extraction]
            SAIL[sailpoint.py<br/>IIQ integration<br/>Identity operations]
        end
    end

    subgraph "MCP Protocol (weaver_ai/mcp.py)"
        SERVER[MCPServer<br/>Tool registration<br/>JWT signing<br/>Nonce tracking]
        CLIENT[MCPClient<br/>Tool invocation<br/>Signature verify<br/>Result handling]
    end

    subgraph "External MCP Servers"
        EXT_MCP[External MCP Tools<br/>Custom integrations<br/>Third-party services]
    end

    REGISTRY -->|Register| WEB
    REGISTRY -->|Register| DOCS
    REGISTRY -->|Register| SAIL

    BASE -->|Implements| WEB
    BASE -->|Implements| DOCS
    BASE -->|Implements| SAIL

    SERVER -->|Expose tools| REGISTRY
    CLIENT -->|Call tools| SERVER
    CLIENT -->|External call| EXT_MCP

    AGENT[BaseAgent] -->|Request tool| CLIENT
    CLIENT -->|Execute| BASE
    BASE -->|Return| AGENT

    style BASE fill:#1168bd,stroke:#0b4884,color:#ffffff
    style REGISTRY fill:#1168bd,stroke:#0b4884,color:#ffffff
    style SERVER fill:#438dd5,stroke:#2e6295,color:#ffffff
    style CLIENT fill:#438dd5,stroke:#2e6295,color:#ffffff
    style WEB fill:#85bbf0,stroke:#5d82a8,color:#000000
    style DOCS fill:#85bbf0,stroke:#5d82a8,color:#000000
    style SAIL fill:#85bbf0,stroke:#5d82a8,color:#000000
```

## Level 3: Component Diagram - Redis Event Mesh

Detailed view of distributed agent communication.

```mermaid
graph TB
    subgraph "Redis Communication (weaver_ai/redis/)"
        MESH[mesh.py<br/>RedisEventMesh<br/>Publish/subscribe<br/>Channel routing]
        QUEUE[queue.py<br/>WorkQueue<br/>Task priority<br/>Dead letter queue]
        REGISTRY[registry.py<br/>AgentRegistry<br/>Heartbeat<br/>Discovery]
    end

    subgraph "Event Flow"
        AGENT1[Agent A<br/>capability: data_processing]
        AGENT2[Agent B<br/>capability: analysis]
        AGENT3[Agent C<br/>capability: reporting]
    end

    subgraph "Redis Channels"
        CH_DATA[Channel: capability:data_processing]
        CH_ANALYSIS[Channel: capability:analysis]
        CH_REPORT[Channel: capability:reporting]
    end

    AGENT1 -->|Register| REGISTRY
    AGENT2 -->|Register| REGISTRY
    AGENT3 -->|Register| REGISTRY

    AGENT1 -->|Subscribe| MESH
    MESH -->|Listen| CH_DATA

    AGENT1 -->|Publish result<br/>next_cap: analysis| MESH
    MESH -->|Route| CH_ANALYSIS
    CH_ANALYSIS -->|Deliver| AGENT2

    AGENT2 -->|Publish result<br/>next_cap: reporting| MESH
    MESH -->|Route| CH_REPORT
    CH_REPORT -->|Deliver| AGENT3

    QUEUE -->|Task distribution| AGENT1
    QUEUE -->|Task distribution| AGENT2

    style MESH fill:#1168bd,stroke:#0b4884,color:#ffffff
    style QUEUE fill:#1168bd,stroke:#0b4884,color:#ffffff
    style REGISTRY fill:#1168bd,stroke:#0b4884,color:#ffffff
    style AGENT1 fill:#438dd5,stroke:#2e6295,color:#ffffff
    style AGENT2 fill:#438dd5,stroke:#2e6295,color:#ffffff
    style AGENT3 fill:#438dd5,stroke:#2e6295,color:#ffffff
```

## Data Flow Diagram - HTTP Request

Shows the end-to-end data flow for an HTTP API request.

```mermaid
sequenceDiagram
    participant Client
    participant Gateway
    participant Auth
    participant RateLimit
    participant Policy
    participant Orchestrator
    participant Agent
    participant ModelRouter
    participant LLM
    participant MCPClient
    participant Tool
    participant Verifier
    participant Audit
    participant Telemetry

    Client->>Gateway: POST /ask {query, user_id}
    Gateway->>Auth: Authenticate(headers)
    Auth-->>Gateway: UserContext

    Gateway->>RateLimit: Enforce(user_id)
    RateLimit-->>Gateway: OK (or 429)

    Gateway->>Policy: InputGuard(query)
    Policy-->>Gateway: Sanitized query

    Gateway->>Orchestrator: ask(query, user_id)
    Orchestrator->>Agent: Execute

    alt Tool required
        Agent->>MCPClient: call_tool(name, args)
        MCPClient->>Tool: execute(context)
        Tool-->>MCPClient: ToolResult
        MCPClient-->>Agent: Result
    end

    Agent->>ModelRouter: generate(query)
    ModelRouter->>LLM: API call
    LLM-->>ModelRouter: Response
    ModelRouter-->>Agent: Generated text

    Agent->>Verifier: verify(query, answer)
    Verifier-->>Agent: Verification result

    Agent-->>Orchestrator: answer, citations, metrics
    Orchestrator->>Policy: OutputGuard(answer)
    Policy-->>Orchestrator: Redacted answer

    Orchestrator->>Audit: Log(request, response)

    alt Signing enabled
        Audit->>Telemetry: log_security_event(action, user_id, detail)
        Telemetry->>Telemetry: Compute SHA-256 hash
        Telemetry->>Telemetry: Sign with RSA private key
        Telemetry-->>Audit: SignedEvent with signature
    end

    Orchestrator-->>Gateway: QueryResponse
    Gateway-->>Client: 200 OK {answer, citations}
```

## Deployment Diagram

Shows the physical deployment architecture.

```mermaid
graph TB
    subgraph "Production Kubernetes Cluster"
        subgraph "Namespace: weaver-ai"
            subgraph "API Tier"
                POD1[Gateway Pod 1<br/>weaver:prod<br/>CPU: 2, Mem: 4Gi]
                POD2[Gateway Pod 2<br/>weaver:prod<br/>CPU: 2, Mem: 4Gi]
                POD3[Gateway Pod 3<br/>weaver:prod<br/>CPU: 2, Mem: 4Gi]
            end

            LB[LoadBalancer Service<br/>External IP<br/>Port 443]

            subgraph "Data Tier"
                REDIS_MASTER[Redis Master<br/>redis:7-alpine<br/>Mem: 8Gi]
                REDIS_REPLICA1[Redis Replica 1]
                REDIS_REPLICA2[Redis Replica 2]
            end

            subgraph "Configuration"
                CONFIG[ConfigMap<br/>Environment vars]
                SECRET[Secret<br/>API keys, JWT keys]
            end

            subgraph "Storage"
                PV_REDIS[PersistentVolume<br/>Redis data<br/>100Gi]
                PV_LOGS[PersistentVolume<br/>Audit logs<br/>50Gi]
            end
        end
    end

    subgraph "External Services"
        INTERNET[Internet]
        OTEL[OpenTelemetry Collector<br/>Metrics & Traces]
        OPENAI_EXT[OpenAI API]
        ANTHROPIC_EXT[Anthropic API]
    end

    INTERNET -->|HTTPS| LB
    LB -->|Round-robin| POD1
    LB -->|Round-robin| POD2
    LB -->|Round-robin| POD3

    POD1 -->|Read| CONFIG
    POD1 -->|Read| SECRET
    POD2 -->|Read| CONFIG
    POD2 -->|Read| SECRET
    POD3 -->|Read| CONFIG
    POD3 -->|Read| SECRET

    POD1 -->|Pub/sub| REDIS_MASTER
    POD2 -->|Pub/sub| REDIS_MASTER
    POD3 -->|Pub/sub| REDIS_MASTER

    REDIS_MASTER -->|Replicate| REDIS_REPLICA1
    REDIS_MASTER -->|Replicate| REDIS_REPLICA2
    REDIS_MASTER -->|Persist| PV_REDIS

    POD1 -->|Write| PV_LOGS
    POD2 -->|Write| PV_LOGS
    POD3 -->|Write| PV_LOGS

    POD1 -->|Telemetry| OTEL
    POD2 -->|Telemetry| OTEL
    POD3 -->|Telemetry| OTEL

    POD1 -->|LLM calls| OPENAI_EXT
    POD1 -->|LLM calls| ANTHROPIC_EXT

    style LB fill:#1168bd,stroke:#0b4884,color:#ffffff
    style POD1 fill:#438dd5,stroke:#2e6295,color:#ffffff
    style POD2 fill:#438dd5,stroke:#2e6295,color:#ffffff
    style POD3 fill:#438dd5,stroke:#2e6295,color:#ffffff
    style REDIS_MASTER fill:#85bbf0,stroke:#5d82a8,color:#000000
```

## Notes

- All diagrams use Mermaid syntax and can be rendered in GitHub, GitLab, or documentation tools
- For interactive editing, use [Mermaid Live Editor](https://mermaid.live/)
- Diagrams follow C4 model color conventions:
  - **Blue (#1168bd)**: Primary system containers
  - **Light Blue (#438dd5)**: Secondary containers
  - **Lightest Blue (#85bbf0)**: Supporting infrastructure
  - **Dark Blue (#08427b)**: External actors

## Diagram Maintenance

When updating these diagrams:

1. Keep consistent with actual code changes
2. Update version number in architecture README
3. Review with architecture team
4. Export PNG versions for presentations if needed
5. Ensure Mermaid syntax remains valid

## Recent Updates

**2025-10-05**: Added signed telemetry to security component diagram and HTTP request sequence diagram
- Added `telemetry.py` to Security Layer
- Added signing flow to HTTP request sequence
- Documents cryptographic signing for tamper-evident audit trails
