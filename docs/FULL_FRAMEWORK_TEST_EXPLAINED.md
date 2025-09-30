# Full Framework Test Explained: What You Can Learn

## Overview

The `test_full_pentest_workflow.py` demonstrates the **complete Weaver AI framework** in action. Unlike the simplified test with mock data, this shows how production agents work with all framework features.

## Key Learning Points

### 1. **Real Agent Architecture**

```python
class ReconAgent(BaseAgent):
    agent_type: str = "reconnaissance"
    capabilities: list[str] = ["network.scan", "security.recon", "target.analysis"]
```

**What this teaches:**
- Agents inherit from `BaseAgent` to get memory, model routing, and lifecycle management
- `agent_type` identifies the agent's role
- `capabilities` define what the agent can do (used for discovery and authorization)

### 2. **Memory Integration**

```python
# Store in short-term memory
if self.memory:
    memory_item = {
        "timestamp": datetime.now().isoformat(),
        "target": target,
        "model_guidance": model_guidance,
        "action": "recon_initiated"
    }
    await self.memory.add_item(memory_item, item_type="short_term")

# Search memory for patterns
similar_targets = await self.memory.search("target reconnaissance", limit=3)
```

**What this teaches:**
- Agents have both short-term (working) and long-term (persistent) memory
- Memory helps agents learn from past experiences
- Search enables agents to find relevant past information

### 3. **Model Integration**

```python
if self.model_router:
    prompt = f"""Analyze this target for security testing: {target}

    Provide a reconnaissance strategy including:
    1. What ports would you check?
    2. What technologies might this site use?
    """

    response = await self.model_router.generate(prompt)
    model_guidance = response.text
```

**What this teaches:**
- Agents use LLMs to make intelligent decisions
- The `ModelRouter` abstracts model selection (can use GPT-4, Llama, etc.)
- Models enhance agent capabilities but aren't required

### 4. **Result Sharing via ResultPublisher**

```python
# Publish results with access control
result = await publisher.publish(
    agent_id=self.agent_id,
    data=recon_data,
    capabilities_required=["security.read"],  # Who can access
    workflow_id="pentest",                    # Group results
    ttl_seconds=3600,                         # Auto-expire
    tags={"phase": "reconnaissance"}           # Metadata
)

# Another agent retrieves results
recon_result = await publisher.retrieve(
    recon_result_id,
    agent_capabilities=self.capabilities  # Must have permission
)
```

**What this teaches:**
- Agents share results securely through `ResultPublisher`
- Capability-based access control prevents unauthorized access
- Results are organized by workflow and expire automatically
- Lineage tracking shows parent-child relationships

### 5. **Workflow Orchestration**

```python
class PenTestCoordinator:
    async def setup_agents(self):
        # Configure memory strategies
        recon_memory = MemoryStrategy(
            short_term_size=100,
            long_term_size=1000,
            short_term_ttl=1800,
            long_term_ttl=86400
        )

        # Initialize agents
        self.agents["recon"] = ReconAgent(
            agent_id="recon_001",
            memory_strategy=recon_memory
        )
        await self.agents["recon"].initialize(model_router=model_router)
```

**What this teaches:**
- Memory strategies can be customized per agent type
- Agents must be initialized before use
- The coordinator manages agent lifecycle and workflow

### 6. **Error Handling & Resilience**

```python
try:
    response = await self.model_router.generate(prompt)
    model_analysis = response.text
except Exception as e:
    model_analysis = f"Model error: {e}"
    # Continue without model - graceful degradation
```

**What this teaches:**
- Agents continue working even if models fail
- Graceful degradation is built-in
- Each component is optional (memory, models, etc.)

## The Complete Flow

### Phase 1: Reconnaissance
1. Agent uses model to plan reconnaissance strategy
2. Stores request in short-term memory
3. Performs reconnaissance (gathering data)
4. Stores results in long-term memory for learning
5. Publishes results for other agents

### Phase 2: Vulnerability Analysis
1. Retrieves recon results (with permission check)
2. Uses model to analyze vulnerabilities
3. Combines model insights with rule-based detection
4. Calculates risk scores
5. Stores patterns in memory
6. Publishes vulnerability report

### Phase 3: Exploit Testing
1. Retrieves vulnerability report
2. Uses model to plan safe testing approach
3. Simulates tests (never actual exploits)
4. Validates vulnerabilities
5. Publishes test results

### Phase 4: Report Generation
1. Collects all workflow results
2. Uses model to synthesize findings
3. Generates executive summary
4. Provides recommendations
5. Stores report in memory

## Configuration Options

### Memory Strategies

```python
# Minimal memory for simple agents
minimal_memory = MemoryStrategy(
    short_term_size=10,
    long_term_size=100,
    short_term_ttl=300,    # 5 minutes
    long_term_ttl=3600     # 1 hour
)

# Large memory for analysis agents
analysis_memory = MemoryStrategy(
    short_term_size=1000,
    long_term_size=10000,
    short_term_ttl=7200,   # 2 hours
    long_term_ttl=604800   # 1 week
)
```

### Model Configuration

```python
# Use mock model (no API needed)
model_router = ModelRouter()  # Uses MockAdapter

# Use Groq (fast and cheap)
if os.getenv("GROQ_API_KEY"):
    model_router.add_model(
        name="groq_llama",
        adapter_type="openai-compatible",
        base_url="https://api.groq.com/openai/v1",
        api_key=os.getenv("GROQ_API_KEY"),
        model="llama3-8b-8192"
    )

# Use OpenAI
if os.getenv("OPENAI_API_KEY"):
    model_router.add_model(
        name="gpt4",
        adapter_type="openai-compatible",
        base_url="https://api.openai.com/v1",
        api_key=os.getenv("OPENAI_API_KEY"),
        model="gpt-4-turbo-preview"
    )
```

## Running the Test

### With Mock Components (No Redis/API needed)
```python
# The demo at the bottom uses mocked Redis and MockAdapter
python3 tests/integration/test_full_pentest_workflow.py
```

### With Real Redis
```bash
# Start Redis
redis-server

# Run with pytest
pytest tests/integration/test_full_pentest_workflow.py -v
```

### With Real Models
```bash
# Set API key for Groq (cheap) or OpenAI
export GROQ_API_KEY="your-key"

# Run test
python3 tests/integration/test_full_pentest_workflow.py
```

## Performance Metrics

The test tracks performance:
```python
self.performance_metrics = {
    "total_time": total_time,
    "recon_time": recon_time,      # ~0.5s with mock
    "vuln_time": vuln_time,        # ~0.3s with mock
    "exploit_time": exploit_time,   # ~0.2s with mock
    "report_time": report_time,     # ~0.3s with mock
    "model_used": self.use_model,
    "agents_used": len(self.agents)
}
```

## What Makes This "Real"

1. **Full Agent Lifecycle**: Agents are properly initialized with memory and models
2. **Memory Persistence**: Agents store and retrieve information
3. **Model Integration**: Agents use LLMs for intelligent decisions
4. **Secure Result Sharing**: ResultPublisher with access control
5. **Error Handling**: Graceful degradation when components fail
6. **Performance Tracking**: Metrics for optimization
7. **Workflow Orchestration**: Complete multi-agent coordination

## Key Differences from Simple Test

| Feature | Simple Test | Full Test |
|---------|------------|-----------|
| **Agent Base** | Plain classes | Inherit from BaseAgent |
| **Memory** | None | Short-term & long-term |
| **Models** | None | ModelRouter integration |
| **Initialization** | Direct instantiation | Proper lifecycle |
| **Error Handling** | Basic | Comprehensive |
| **Performance** | Not tracked | Full metrics |
| **Learning** | None | Memory-based patterns |

## When to Use This Pattern

Use the full framework when you need:
- **Production agents** with real intelligence
- **Memory** for learning and context
- **Model integration** for decision-making
- **Secure multi-agent** workflows
- **Performance tracking** and optimization
- **Error resilience** and graceful degradation

## Summary

This test demonstrates that Weaver AI is a complete framework for building intelligent, memory-enabled agents that can:
- Learn from experience
- Make intelligent decisions using LLMs
- Share results securely
- Work together in complex workflows
- Handle errors gracefully
- Track performance

The pen testing workflow is just one example - the same patterns apply to any multi-agent system you want to build!
