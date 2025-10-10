# Multi-Agent A2A Orchestration Example

This example demonstrates a **multi-agent research workflow** using the A2A (Agent-to-Agent) protocol with secure MCP tool integration.

## Architecture

```
Test Client
    ↓ (A2A/HTTP with RSA signatures)
Gateway (port 8005)
    ↓ (Redis pub/sub)
Orchestrator Agent
    ↓ (Redis: tasks:search)
Search Agent (with MCP web_search tool)
    ↓ (Redis: tasks:summarization)
Summarizer Agent (LLM-based)
    ↓ (Redis response)
Gateway → Test Client
```

## Components

### 1. **Orchestrator Agent** (`a2a_orchestrator_agent.py`)
- **Capability**: `orchestration`, `workflow:start`
- **Role**: Coordinates multi-agent workflows
- **Function**: Receives workflow requests and initiates agent chains

### 2. **Search Agent** (`a2a_search_agent.py`)
- **Capability**: `search:web`, `search`
- **Role**: Finds information using secure MCP tools
- **Features**:
  - Uses `WebSearchTool` from MCP with proper permissions
  - Falls back to LLM if tool unavailable
  - Returns structured search results

###3. **Summarizer Agent** (`a2a_summarizer_agent.py`)
- **Capability**: `summarization`, `summarize`
- **Role**: Condenses search results into summaries
- **Features**:
  - Uses OpenAI GPT-4 for real summarization
  - Processes search results from previous agent
  - Ends the workflow chain

## Security Features

### A2A Protocol Security
- **RSA Signature Verification**: All messages signed with RSA-2048 keys
- **Timestamp Validation**: 30-second window to prevent replay attacks
- **Public Key Registry**: Gateway validates sender identity

### MCP Tool Security
- **Scoped Permissions**: Tools require specific scopes (e.g., `tool:web_search`)
- **Execution Context**: Each tool call includes agent ID, session ID, user ID
- **Tool Registry**: Centralized registry with permission checks

## Quick Start

### 1. Start the Multi-Agent System

```bash
docker-compose -f docker-compose.multi-agent.yml up -d
```

This starts:
- Redis (port 6381)
- Orchestrator Agent
- Search Agent
- Summarizer Agent
- Gateway (port 8005)

### 2. Check Agent Status

```bash
docker-compose -f docker-compose.multi-agent.yml ps
```

All agents should show "Up" status.

### 3. View Agent Logs

```bash
# Orchestrator
docker logs orchestrator-agent --tail 20

# Search agent (with MCP tools)
docker logs search-agent --tail 20

# Summarizer
docker logs summarizer-agent --tail 20
```

### 4. Test the Workflow

Currently, test with the single translation agent:

```bash
python3 examples/a2a_test_client.py --endpoint http://localhost:8001
```

For multi-agent (needs a2a_client module installation):

```bash
python3 examples/a2a_multiagent_test.py --endpoint http://localhost:8005
```

## Workflow Example

**Request**: Research "artificial intelligence"

**Flow**:
1. Client sends A2A message to gateway with capability `orchestration`
2. Gateway verifies signature and routes to Orchestrator Agent
3. Orchestrator initiates workflow with `next_capabilities=["search"]`
4. Search Agent receives task, executes MCP `web_search` tool
5. Search Agent returns results with `next_capabilities=["summarization"]`
6. Summarizer Agent receives search results
7. Summarizer uses GPT-4 to create summary
8. Summarizer returns final result (no next_capabilities)
9. Gateway sends response back to client

## Configuration

### Environment Variables

Set in `.env`:

```bash
# Model Configuration
WEAVER_MODEL_PROVIDER=openai
WEAVER_MODEL_NAME=gpt-4
OPENAI_API_KEY=your-key-here

# Redis
REDIS_HOST=redis-multiagent
REDIS_PORT=6379

# A2A Security
WEAVER_A2A_SIGNING_PRIVATE_KEY_PEM=/app/keys/instance_a_private.pem
WEAVER_A2A_SIGNING_PUBLIC_KEY_PEM=/app/keys/instance_a_public.pem
```

### Generate RSA Keys

```bash
# Generate keys for testing
python3 scripts/generate_a2a_keys.py
```

This creates keys in `keys/` directory.

## Agent Capabilities

Agents automatically subscribe to Redis channels based on their capabilities:

- `orchestration` → `tasks:orchestration`
- `search:web` → `tasks:search_web`
- `search` → `tasks:search`
- `summarization` → `tasks:summarization`

## MCP Tools

### Available Tools

- `web_search`: Search the web (requires `tool:web_search` scope)
- More tools can be added to `weaver_ai/tools/builtin/`

### Tool Execution Example

```python
from weaver_ai.tools import ToolExecutionContext

context = ToolExecutionContext(
    agent_id="search-agent-8002",
    session_id="workflow-123",
    user_id="system",
    scopes=["tool:web_search"],  # Required permission
)

tool = tool_registry.get_tool("web_search")
result = await tool.execute(
    args={"query": "AI research", "max_results": 3},
    context=context,
)
```

## Monitoring

### Health Checks

```bash
# Gateway health
curl http://localhost:8005/health

# Agent card
curl http://localhost:8005/a2a/card
```

### Redis Monitoring

```bash
# Connect to Redis
docker exec -it redis-multiagent redis-cli

# Monitor pub/sub
PSUBSCRIBE tasks:*

# List keys
KEYS *
```

## Troubleshooting

### Agent Not Starting

Check logs:
```bash
docker logs search-agent
```

Common issues:
- Missing OPENAI_API_KEY
- Redis connection failed
- Import errors

### No Response from Workflow

1. Check all agents are running
2. Verify Redis connectivity
3. Check agent logs for errors
4. Ensure capabilities match channel names

### Signature Verification Failed

1. Verify public keys in `WEAVER_MCP_SERVER_PUBLIC_KEYS`
2. Check key format (PEM with escaped newlines)
3. Ensure sender_id matches registered key

## Development

### Adding New Agents

1. Create agent file in `examples/`
2. Inherit from `BaseAgent`
3. Define capabilities
4. Implement `process()` method
5. Add to `docker-compose.multi-agent.yml`

### Adding MCP Tools

1. Create tool in `weaver_ai/tools/builtin/`
2. Inherit from `Tool`
3. Define `input_schema` and `output_schema`
4. Implement `execute()` method
5. Register in `__init__.py`

## Performance

- **Agent Response Time**: ~100-500ms (LLM calls add 1-3s)
- **Redis Latency**: <10ms
- **Signature Verification**: <5ms
- **End-to-End Workflow**: ~3-5 seconds (with OpenAI GPT-4)

## Next Steps

1. Add more MCP tools (file operations, database access, etc.)
2. Implement workflow state persistence
3. Add agent health monitoring
4. Create web UI for workflow visualization
5. Add metrics and telemetry

## References

- [A2A Protocol Specification](https://a2a-protocol.org)
- [MCP (Model Context Protocol)](https://modelcontextprotocol.io)
- [Weaver AI Documentation](../README.md)
