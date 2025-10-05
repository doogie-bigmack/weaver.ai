# ADR-001: Dual API Design (Simple API + BaseAgent)

**Status**: Accepted
**Date**: 2024-09-01
**Decision Makers**: Architecture Team
**Technical Story**: Initial framework design

## Context

When designing Weaver AI, we faced a fundamental question: **How can we make agent development accessible to Python developers while still supporting advanced distributed multi-agent use cases?**

### Forces at Play

1. **Developer Experience**: Most developers want to create agents quickly without learning complex frameworks
2. **Production Requirements**: Enterprise deployments need distributed agents, capability-based routing, and event-driven architectures
3. **Learning Curve**: Complex abstractions (event meshes, pub/sub) are difficult for beginners
4. **Flexibility**: Different use cases require different levels of control
5. **Migration Path**: Developers should be able to start simple and scale up as needed

### Constraints

- Python 3.12+ type system available for routing
- Pydantic AI as underlying agent framework
- Need to support both synchronous prototyping and async production
- Framework should "hide" complexity by default

## Decision

**We will provide two complementary APIs:**

### 1. Simple API (`weaver_ai/simple/`)

**Target Users**: Application developers, rapid prototyping, single-agent systems

**Key Features**:
- `@agent` decorator for function-to-agent transformation
- Automatic type extraction for routing
- `run()` and `serve()` for immediate execution
- `flow()` builder for chaining agents
- No explicit Redis/event mesh management
- Synchronous-feeling async API

**Example**:
```python
from weaver_ai.simple import agent, run

@agent(model="gpt-4")
async def summarizer(text: str) -> str:
    """Summarize the text."""
    return f"Summary: {text}"

result = await run(summarizer, "Long text...")
```

### 2. BaseAgent API (`weaver_ai/agents/base.py`)

**Target Users**: Framework developers, distributed systems, multi-agent orchestration

**Key Features**:
- Explicit `BaseAgent` class inheritance
- Capability-based routing and discovery
- Direct Redis event mesh access
- Memory management control
- Tool permission management
- Event processing and publishing

**Example**:
```python
from weaver_ai.agents import BaseAgent

class CustomAgent(BaseAgent):
    capabilities = ["data_processing"]

    async def process(self, event: Event) -> Result:
        # Custom processing logic
        return Result(
            success=True,
            data={"result": "..."},
            next_capabilities=["analysis"]
        )

agent = CustomAgent()
await agent.initialize(redis_url="redis://localhost")
await agent.start()
```

### Integration

- Simple API **wraps** BaseAgent via `SimpleAgentWrapper`
- Both share same infrastructure (security, tools, models)
- Developers can start with Simple API and migrate to BaseAgent when needed

## Consequences

### Positive

1. **Low Barrier to Entry**: Developers can create agents in <20 lines of code
2. **Progressive Disclosure**: Complexity only revealed when needed
3. **Type Safety**: Python type hints provide automatic routing
4. **Production Ready**: Both APIs use same battle-tested infrastructure
5. **Migration Path**: Easy upgrade from Simple to BaseAgent
6. **Flexibility**: Right tool for the right job

### Negative

1. **Maintenance Burden**: Two APIs to maintain and document
2. **Potential Confusion**: Developers may not know which API to use
3. **Feature Parity**: Need to ensure both APIs can access same capabilities
4. **Testing Complexity**: More test scenarios to cover
5. **Learning Curve**: Advanced users still need to learn BaseAgent eventually

### Neutral

1. **Code Duplication**: Some concepts expressed in both APIs
2. **Documentation Split**: Separate docs for each API level
3. **Community Fragmentation**: Two different ways to solve same problem

## Alternatives Considered

### Alternative 1: Single Simple API Only

**Description**: Only provide decorator-based API, hide all distributed features

**Pros**:
- Simplest for developers
- Single way to do things
- Smaller codebase

**Cons**:
- No path to distributed agents
- Can't support advanced use cases
- Forces premature abstraction decisions

**Why not chosen**: Too limiting for production use cases

### Alternative 2: Single BaseAgent API Only

**Description**: Require all developers to subclass BaseAgent

**Pros**:
- Single API to maintain
- Maximum flexibility
- Consistent patterns

**Cons**:
- High barrier to entry
- Verbose for simple cases
- Scares away casual users

**Why not chosen**: Too complex for majority of use cases

### Alternative 3: Configuration-Based Agents

**Description**: Define agents in YAML/JSON configuration files

**Pros**:
- No code for simple cases
- Declarative style
- Version control friendly

**Cons**:
- Limited expressiveness
- Debugging difficult
- Not Pythonic

**Why not chosen**: Doesn't leverage Python's type system and tooling

## Implementation Notes

### SimpleAgentWrapper Implementation

The bridge between Simple API and BaseAgent:

```python
# weaver_ai/simple/decorators.py:26-80
class SimpleAgentWrapper(BaseAgent):
    """Wrapper that converts simple functions into BaseAgent instances."""

    _func: Callable = None
    _config: dict[str, Any] = None
    _type_hints: dict = None

    def __init__(self, func: Callable, config: dict[str, Any], **kwargs):
        # Store function as class attribute (not Pydantic field)
        self.__class__._func = func
        self.__class__._config = config

        # Extract type hints for routing
        self.__class__._type_hints = get_type_hints(func)

        # Initialize BaseAgent with capabilities from config
        super().__init__(
            agent_type=config.get("agent_type", func.__name__),
            capabilities=config.get("capabilities", []),
            **kwargs
        )

    async def process(self, event: Event) -> Result:
        # Delegate to wrapped function
        result = await self._func(event.data)
        return Result(success=True, data=result)
```

### Type-Based Routing

```python
# weaver_ai/simple/flow.py:40-60
class Flow:
    def route(self, routes: dict[str, AgentFunc]) -> "Flow":
        """Route based on output type of previous agent."""
        for output_type, agent in routes.items():
            # Match agent input type to route key
            if agent._input_type == output_type:
                self._routes[output_type] = agent
        return self
```

### Migration Path

1. **Start Simple**: Use `@agent` for rapid development
2. **Add Complexity**: Use `flow()` for multi-agent workflows
3. **Scale Up**: Migrate to `BaseAgent` when you need:
   - Distributed agents across processes
   - Custom capability matching logic
   - Fine-grained memory control
   - Event-driven architecture

## References

- [Pydantic AI Documentation](https://ai.pydantic.dev/)
- [Python Decorators PEP 318](https://peps.python.org/pep-0318/)
- [Type Hints PEP 484](https://peps.python.org/pep-0484/)
- Internal: `docs/agents.md` (agent development guide)
