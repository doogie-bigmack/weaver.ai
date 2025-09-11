# Simplification Comparison: Test Agent Boilerplate

## The Problem

In `test_security_pentest_workflow.py`, we have agents that inherit from `BaseAgent` which brings unnecessary complexity for test/demo agents that just return mock data.

## Original (Overcomplicated) Approach

```python
from weaver_ai.agents import BaseAgent
from weaver_ai.memory import AgentMemory, MemoryStrategy

class ReconAgent(BaseAgent):
    """Reconnaissance agent for initial target discovery."""

    agent_type: str = "recon"
    capabilities: list[str] = ["security.recon", "network.scan"]

    async def scan_target(self, target: str, publisher: ResultPublisher) -> Dict[str, Any]:
        # ... mock data generation ...

        # Memory storage would go here in production

        # Publish result
        result = await publisher.publish(...)
        return {"result_id": result.metadata.result_id, "data": recon_data}

class PenTestOrchestrator:
    def __init__(self, publisher: ResultPublisher):
        self.publisher = publisher
        self.agents: dict[str, BaseAgent] = {}

    async def setup_agents(self):
        """Initialize all agents."""
        # Create memory strategy for security agents
        security_memory = MemoryStrategy(
            short_term_size=1000,
            long_term_size=10000,
            short_term_ttl=7200,
            long_term_ttl=86400,
        )

        # Initialize agents
        self.agents["recon"] = ReconAgent(
            agent_id="recon_agent_001",
            memory_strategy=security_memory,
        )
        await self.agents["recon"].initialize()
        # ... more agent initialization ...
```

### Problems with this approach:
1. **Unnecessary inheritance** - BaseAgent brings memory, model routing, Redis connections
2. **Complex initialization** - Memory strategies, agent initialization, orchestrator setup
3. **Unused features** - These test agents don't actually use memory or models
4. **Verbose setup** - Lots of boilerplate for simple mock agents

## Simplified Approach

```python
class SimpleReconAgent:
    """Lightweight recon agent for testing."""

    def __init__(self, agent_id: str = "recon_agent"):
        self.agent_id = agent_id

    async def scan(self, target: str, publisher: ResultPublisher) -> dict[str, Any]:
        """Perform reconnaissance."""
        data = {
            "target": target,
            "open_ports": [22, 80, 443, 3306],
            "services": {"22": "SSH", "80": "HTTP", "443": "HTTPS", "3306": "MySQL"},
            "technologies": ["nginx", "PHP", "MySQL", "WordPress"],
        }

        result = await publisher.publish(
            agent_id=self.agent_id,
            data=data,
            capabilities_required=["security.read"],
            workflow_id="pentest",
        )
        return {"result_id": result.metadata.result_id, "data": data}

# Direct usage - no orchestrator needed
async def run_simple_pentest(target: str, publisher: ResultPublisher) -> dict[str, Any]:
    results = {}

    # Phase 1: Recon
    recon = SimpleReconAgent()
    recon_result = await recon.scan(target, publisher)
    results["recon"] = recon_result

    # Phase 2: Vulnerability Scan
    vuln_scanner = SimpleVulnScanner()
    vuln_result = await vuln_scanner.scan(recon_result["result_id"], publisher)
    results["vulnerabilities"] = vuln_result

    # Phase 3: Report
    reporter = SimpleReporter()
    report_result = await reporter.generate_report("pentest", publisher)
    results["report"] = report_result

    return results
```

### Benefits of simplified approach:
1. **No unnecessary inheritance** - Simple classes with just what's needed
2. **Direct instantiation** - No complex initialization or orchestrator
3. **Clear purpose** - Obviously just for testing/demo
4. **Less code** - ~50% reduction in boilerplate

## When to Use Each Approach

### Use BaseAgent when:
- Building production agents that need memory
- Agents that use LLM models for processing
- Need Redis integration for distributed systems
- Want full agent lifecycle management
- Building reusable agent components

### Use Simple Classes when:
- Writing tests or demos
- Agents just return mock/static data
- Don't need memory or model capabilities
- Want clear, readable test code
- Building proof-of-concept workflows

## Key Insight

The `BaseAgent` class is powerful for production agents that need:
- Memory management
- Model routing
- Redis integration
- Lifecycle management
- Error handling

But for **test agents that just publish mock data**, all this infrastructure is unnecessary overhead. Simple classes that just have an `agent_id` and methods to generate/publish data are much cleaner and easier to understand.

## Recommendation

1. Keep the full `test_security_pentest_workflow.py` as an example of production agent patterns
2. Use `test_security_pentest_workflow_simple.py` for actual testing
3. In documentation, show both patterns and explain when to use each
4. For unit tests, always prefer the simple approach

This separation makes it clear that:
- `BaseAgent` is for production agents with real functionality
- Simple classes are fine for testing and demos
- The ResultPublisher works with both approaches equally well
