# Phase 4: Developer Experience Guide

## What's New in Phase 4

Phase 4 introduces a powerful, developer-friendly workflow API that makes it incredibly easy to build multi-agent systems. With just a few lines of code, you can create complex workflows that automatically route data between agents based on types.

### Key Features

1. **Fluent Workflow API** - Chain methods to build workflows programmatically
2. **Automatic Type-Based Routing** - Agents automatically connect based on input/output types
3. **Configurable Error Handling** - Per-agent error strategies (retry, fail-fast, skip)
4. **Observability & Intervention** - Monitor and dynamically modify workflows
5. **Simple Agent Definition** - Use the `@agent` decorator for minimal boilerplate

## Quick Start

### 1. Simple Q&A Agent

The simplest possible agent - answers questions using an LLM:

```python
from weaver_ai import Workflow
from weaver_ai.agents import BaseAgent, agent
from weaver_ai.events import Event

@agent(agent_type="qa_bot", capabilities=["answer:questions"])
class QABot(BaseAgent):
    async def process(self, event: Event) -> str:
        # Use the model router to generate an answer
        if self.model_router:
            response = await self.model_router.generate(event.data)
            return response.text
        return f"Answer to: {event.data}"

# Create and run the workflow
workflow = Workflow("simple_qa").add_agent(QABot)
answer = await workflow.run("What is the capital of France?")
print(answer.result)  # "Paris"
```

### 2. Multi-Agent Pipeline

Build powerful pipelines where agents automatically connect:

```python
from pydantic import BaseModel
from weaver_ai import Workflow
from weaver_ai.agents import BaseAgent, agent

# Define data models
class ResearchRequest(BaseModel):
    topic: str

class ResearchData(BaseModel):
    topic: str
    findings: list[str]

class Analysis(BaseModel):
    insights: list[str]
    recommendations: list[str]

# Define agents
@agent(agent_type="researcher", memory_strategy="analyst")
class Researcher(BaseAgent):
    async def process(self, event: Event) -> ResearchData:
        request = event.data
        # Research logic here
        return ResearchData(
            topic=request.topic,
            findings=["finding1", "finding2"]
        )

@agent(agent_type="analyst")
class Analyst(BaseAgent):
    async def process(self, event: Event) -> Analysis:
        data = event.data
        # Analysis logic here
        return Analysis(
            insights=["insight1"],
            recommendations=["recommendation1"]
        )

# Create workflow - agents automatically connect!
workflow = (
    Workflow("research_pipeline")
    .add_agents(Researcher, Analyst)
    .with_observability(True)
    .with_error_handling("retry", max_retries=3)
)

result = await workflow.run(ResearchRequest(topic="AI Safety"))
```

## Core Concepts

### Workflow Class

The `Workflow` class provides a fluent API for building agent pipelines:

```python
workflow = (
    Workflow("my_workflow")
    .add_agents(Agent1, Agent2, Agent3)  # Add multiple agents
    .with_error_handling("retry", max_retries=3)  # Configure error handling
    .with_observability(True)  # Enable progress tracking
    .with_intervention(True)  # Allow external intervention
    .with_timeout(60)  # Set timeout in seconds
)
```

### Agent Discovery

Agents automatically connect based on their input/output types:

1. **Automatic Routing**: If Agent A outputs `DataX` and Agent B accepts `DataX`, they connect automatically
2. **Manual Override**: You can override automatic routing with custom rules

```python
workflow.add_route(
    when=lambda result: result.confidence < 0.5,
    from_agent="analyst",
    to_agent="reviewer",
    priority=10
)
```

### Error Handling Strategies

Configure how each agent handles errors:

- **`retry`**: Retry with exponential backoff (default)
- **`fail_fast`**: Stop workflow on first error
- **`skip`**: Skip failed agent and continue

```python
workflow.add_agent(
    CriticalAgent,
    error_handling="fail_fast"  # This agent must succeed
).add_agent(
    OptionalAgent,
    error_handling="skip"  # This agent can fail
)
```

### Memory Strategies

Agents can have different memory configurations:

```python
@agent(memory_strategy="analyst")  # Large memory for analysis
class DataAnalyst(BaseAgent):
    pass

@agent(memory_strategy="minimal")  # Minimal memory footprint
class SimpleProcessor(BaseAgent):
    pass
```

Available strategies:
- `analyst`: Large memory for data analysis
- `coordinator`: Track many agents
- `validator`: Quick validation tasks
- `minimal`: Minimal memory usage

## Advanced Features

### Observability

Enable observability to track workflow progress:

```python
workflow = Workflow("observable").with_observability(True)

# Progress events are published to Redis event mesh
# Subscribe to "workflow.progress" events to monitor
```

### Intervention

Allow external agents to modify workflow routing:

```python
workflow = Workflow("intervene").with_intervention(True)

# External agents can inject routing changes
# Useful for quality control and human-in-the-loop
```

### Type-Based Router

The `TypeBasedRouter` analyzes agent signatures to build routing graphs:

```python
from weaver_ai.agents.discovery import TypeBasedRouter

router = TypeBasedRouter()
router.register_agent("agent1", agent_instance)

# Find agent that can process a type
next_agent = router.find_agent_for_type(DataType)

# Get workflow path between types
path = router.get_workflow_path(InputType, OutputType)
```

## Testing Your Workflows

```python
import pytest
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
async def test_my_workflow():
    workflow = Workflow("test").add_agent(MyAgent)

    with patch('weaver_ai.workflow.RedisEventMesh') as mock_mesh:
        mock_mesh.return_value.connect = AsyncMock()

        result = await workflow.run(test_input)

        assert result.state == WorkflowState.COMPLETED
        assert result.result == expected_output
```

## Best Practices

1. **Use Type Hints**: Always type hint your agent process methods for automatic routing
2. **Handle Errors Gracefully**: Choose appropriate error strategies for each agent
3. **Monitor Workflows**: Enable observability for production workflows
4. **Test Thoroughly**: Test both individual agents and complete workflows
5. **Document Data Models**: Use Pydantic models with clear documentation

## Examples

See the `examples/` directory for complete working examples:

- `01_simple_qa.py` - Basic Q&A agent
- `02_analysis_pipeline.py` - Multi-agent analysis pipeline

## API Reference

### Workflow Methods

- `add_agent(agent_class, **config)` - Add a single agent
- `add_agents(*agent_classes)` - Add multiple agents
- `add_route(when, from_agent, to_agent, priority)` - Add custom routing
- `with_error_handling(strategy, **options)` - Set error handling
- `with_observability(enabled)` - Enable/disable observability
- `with_intervention(enabled)` - Enable/disable intervention
- `with_timeout(seconds)` - Set execution timeout
- `with_model_router(router)` - Set model router
- `run(input_data)` - Execute the workflow

### Error Strategies

- `RetryWithBackoff` - Retry with exponential backoff
- `FailFast` - Fail immediately on error
- `SkipOnError` - Skip and continue
- `CircuitBreaker` - Circuit breaker pattern
- `AdaptiveRetry` - Adjust retries based on success rate
- `TimeoutStrategy` - Execute with timeout

## Migration from Phase 3

If you're upgrading from Phase 3:

1. Replace manual agent orchestration with `Workflow` class
2. Use `@agent` decorator instead of manual BaseAgent subclassing
3. Let type-based routing handle agent connections
4. Configure error handling per agent instead of globally

## Troubleshooting

### Common Issues

**Q: Agents aren't connecting automatically**
A: Ensure your agents have proper type hints on their process methods

**Q: Workflow times out**
A: Increase timeout with `.with_timeout()` or optimize agent processing

**Q: Memory errors with large data**
A: Use appropriate memory strategies for your agents

## Next Steps

- Explore the examples to see workflows in action
- Build your own multi-agent pipeline
- Enable observability to monitor your workflows
- Contribute your own examples and improvements!
