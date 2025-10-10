# Multi-Agent Workflow Testing Guide

## Quick Test

The multi-agent research workflow is now operational! Here's how to test it:

### 1. Ensure all agents are running

```bash
docker-compose -f docker-compose.multi-agent.yml ps
```

All services should show "Up" status:
- redis-multiagent
- orchestrator-agent
- search-agent
- summarizer-agent
- gateway-multiagent

### 2. Check agent logs to see the workflow in action

Run this command and then trigger a workflow (next step):

```bash
# Terminal 1 - Watch all agent logs
docker logs -f orchestrator-agent &
docker logs -f search-agent &
docker logs -f summarizer-agent
```

### 3. Test the workflow directly via Redis

```bash
python3 examples/test_multiagent_direct.py
```

This will:
1. Publish a research request to the orchestrator
2. Orchestrator sends task to search agent
3. Search agent finds information and sends to summarizer
4. Summarizer generates final summary

### 4. Monitor the workflow

Watch the logs to see:

**Orchestrator logs:**
```
[Orchestrator] Received orchestration request
[Orchestrator] Starting workflow: research
```

**Search agent logs:**
```
[Search] Received search request
[Search] Searching for: artificial intelligence trends 2024
[Search] Returning 1 results
```

**Summarizer logs:**
```
[Summarizer] Received summarization request
[Summarizer] Summarizing 1 search results
[Summarizer] Summary generated
```

## Workflow Architecture

```
Test Client
    ↓ (Redis pub/sub: tasks:orchestration)
Orchestrator Agent
    ↓ (Redis pub/sub: tasks:search)
Search Agent
    ↓ (Redis pub/sub: tasks:summarization)
Summarizer Agent
    ↓ (Complete - summary generated)
```

## What's Working

✅ **Event-based agent chaining** - Agents communicate via Redis pub/sub
✅ **Capability-based routing** - Messages routed by agent capabilities
✅ **Workflow progression** - Orchestrator → Search → Summarizer chain works
✅ **MCP tool integration** - Search agent has secure tool access
✅ **Real LLM integration** - Summarizer uses OpenAI GPT-4

## Configuration

Agents use environment variables from `.env`:

```bash
# Required for real functionality
OPENAI_API_KEY=your-key-here
WEAVER_MODEL_PROVIDER=openai
WEAVER_MODEL_NAME=gpt-4

# Redis connection (handled by Docker)
REDIS_HOST=redis-multiagent
REDIS_PORT=6379
```

## Troubleshooting

### Workflow times out
- Check all agents are running: `docker-compose -f docker-compose.multi-agent.yml ps`
- Check Redis is accessible: `docker logs redis-multiagent`
- Restart agents: `docker-compose -f docker-compose.multi-agent.yml restart`

### Search agent uses mock results
- This is normal if `OPENAI_API_KEY` is not set
- Or if the LLM response can't be parsed as JSON
- Mock results still allow the workflow to complete

### No logs appearing
- Ensure you're using the correct Docker service names
- Try: `docker-compose -f docker-compose.multi-agent.yml logs -f`

## Next Steps

1. Add more complex workflows (e.g., multi-step research)
2. Implement workflow state persistence
3. Add metrics and monitoring
4. Create HTTP API endpoints for workflow initiation
5. Build web UI for workflow visualization
