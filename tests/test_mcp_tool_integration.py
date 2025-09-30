"""Tests for MCP tool integration with agents."""

from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio

from weaver_ai.agents.base import BaseAgent, Result
from weaver_ai.agents.tool_manager import AgentToolManager, ToolExecutionPlan
from weaver_ai.events import Event
from weaver_ai.tools import ToolRegistry
from weaver_ai.tools.base import Tool, ToolExecutionContext, ToolResult
from weaver_ai.tools.builtin import DocumentationTool, WebSearchTool


class ResearchAgent(BaseAgent):
    """Example research agent with tool support."""

    agent_type: str = "research"
    capabilities: list[str] = ["research", "analysis"]

    async def process(self, event: Event) -> Result:
        """Process research tasks using tools."""
        data = event.data if isinstance(event.data, dict) else {"task": str(event.data)}
        task = data.get("task", "")

        if not task:
            return Result(success=False, error="No task provided")

        # Use tool manager to select and execute tools
        if self.tool_registry:
            tool_manager = AgentToolManager(
                agent_id=self.agent_id,
                tool_registry=self.tool_registry,
                available_tools=self.available_tools,
            )

            # Select tools based on task
            selected_tools = tool_manager.select_tools_for_task(task)

            if "search" in task.lower() and "web_search" in selected_tools:
                # Execute web search
                result = await tool_manager.execute_single(
                    "web_search",
                    {"query": task, "max_results": 3},
                    {"workflow_id": event.metadata.get("workflow_id")},
                )

                return Result(
                    success=result.success,
                    data=result.data,
                    error=result.error,
                    workflow_id=event.metadata.get("workflow_id"),
                )

            elif "documentation" in task.lower() and "documentation" in selected_tools:
                # Extract library name from task
                library = "fastapi"  # Default for demo
                if "fastapi" in task.lower():
                    library = "fastapi"
                elif "django" in task.lower():
                    library = "django"

                result = await tool_manager.execute_single(
                    "documentation",
                    {"library": library, "topic": "getting started"},
                    {"workflow_id": event.metadata.get("workflow_id")},
                )

                return Result(
                    success=result.success,
                    data=result.data,
                    error=result.error,
                    workflow_id=event.metadata.get("workflow_id"),
                )

        # Fallback to basic processing
        return Result(
            success=True,
            data={"message": f"Processed task: {task}", "tools_used": []},
            workflow_id=event.metadata.get("workflow_id"),
        )


@pytest_asyncio.fixture
async def tool_registry():
    """Create a tool registry with test tools."""
    registry = ToolRegistry()

    # Register built-in tools
    await registry.register_tool(WebSearchTool())
    await registry.register_tool(DocumentationTool())

    return registry


@pytest_asyncio.fixture
async def research_agent(tool_registry):
    """Create a research agent with tools."""
    agent = ResearchAgent()

    # Initialize with tool support
    await agent.initialize(
        redis_url="redis://localhost:6379",
        tool_registry=tool_registry,
    )

    yield agent

    # Cleanup
    await agent.stop()


@pytest.mark.asyncio
async def test_agent_tool_discovery(tool_registry):
    """Test that agents can discover tools based on capabilities."""
    agent = ResearchAgent(capabilities=["research", "analysis"])

    await agent.initialize(
        redis_url="redis://localhost:6379",
        tool_registry=tool_registry,
    )

    # Check discovered tools
    assert "web_search" in agent.available_tools
    assert "documentation" in agent.available_tools

    # Check permissions
    assert agent.tool_permissions.get("web_search") is True
    assert agent.tool_permissions.get("documentation") is True

    await agent.stop()


@pytest.mark.asyncio
async def test_agent_web_search_tool(research_agent):
    """Test agent using web search tool."""
    event = Event(
        event_type="task",
        data={"task": "search for Python async programming tutorials"},
        metadata={"workflow_id": "test-123"},
    )

    result = await research_agent.process(event)

    assert result.success is True
    assert result.data is not None
    assert "results" in result.data
    assert len(result.data["results"]) > 0
    assert result.workflow_id == "test-123"


@pytest.mark.asyncio
async def test_agent_documentation_tool(research_agent):
    """Test agent using documentation tool."""
    event = Event(
        event_type="task",
        data={"task": "get documentation for FastAPI"},
        metadata={"workflow_id": "test-456"},
    )

    result = await research_agent.process(event)

    assert result.success is True
    assert result.data is not None
    assert "content" in result.data
    assert "FastAPI" in result.data["content"]
    assert result.workflow_id == "test-456"


@pytest.mark.asyncio
async def test_tool_manager_selection():
    """Test tool manager's tool selection."""
    registry = ToolRegistry()
    await registry.register_tool(WebSearchTool())
    await registry.register_tool(DocumentationTool())

    manager = AgentToolManager(
        agent_id="test-agent",
        tool_registry=registry,
        available_tools=["web_search", "documentation"],
    )

    # Test search task
    selected = manager.select_tools_for_task("search for Python tutorials")
    assert "web_search" in selected

    # Test documentation task
    selected = manager.select_tools_for_task("get API documentation")
    assert "documentation" in selected


@pytest.mark.asyncio
async def test_tool_parallel_execution():
    """Test parallel tool execution."""
    registry = ToolRegistry()
    await registry.register_tool(WebSearchTool())
    await registry.register_tool(DocumentationTool())

    manager = AgentToolManager(
        agent_id="test-agent",
        tool_registry=registry,
        available_tools=["web_search", "documentation"],
    )

    # Execute tools in parallel
    tools = [
        ("web_search", {"query": "Python async"}),
        ("documentation", {"library": "asyncio"}),
    ]

    results = await manager.execute_parallel(tools)

    assert len(results) == 2
    assert all(isinstance(r, ToolResult) for r in results)
    assert results[0].tool_name == "web_search"
    assert results[1].tool_name == "documentation"


@pytest.mark.asyncio
async def test_tool_sequential_execution():
    """Test sequential tool execution with context passing."""
    registry = ToolRegistry()
    await registry.register_tool(WebSearchTool())
    await registry.register_tool(DocumentationTool())

    manager = AgentToolManager(
        agent_id="test-agent",
        tool_registry=registry,
        available_tools=["web_search", "documentation"],
    )

    # Execute tools sequentially
    tools = [
        ("web_search", {"query": "FastAPI"}),
        ("documentation", {"library": "fastapi"}),
    ]

    results = await manager.execute_sequential(tools)

    assert len(results) == 2
    assert results[0].success is True
    assert results[1].success is True


@pytest.mark.asyncio
async def test_tool_execution_plan():
    """Test complex tool execution plan."""
    registry = ToolRegistry()
    await registry.register_tool(WebSearchTool())
    await registry.register_tool(DocumentationTool())

    manager = AgentToolManager(
        agent_id="test-agent",
        tool_registry=registry,
        available_tools=["web_search", "documentation"],
    )

    # Create execution plan
    plan = ToolExecutionPlan(
        sequential=["web_search"],
        parallel=[["documentation", "web_search"]],
    )

    results = await manager.execute_plan(
        plan,
        initial_args={"query": "Python", "library": "python"},
    )

    assert "sequential" in results
    assert "parallel" in results
    assert len(results["sequential"]) == 1
    assert len(results["parallel"]) == 1
    assert len(results["parallel"][0]) == 2


@pytest.mark.asyncio
async def test_tool_caching():
    """Test tool result caching."""
    registry = ToolRegistry()

    # Create a tool with caching enabled
    tool = WebSearchTool()
    tool.cache_enabled = True
    tool.cache_ttl = 10  # 10 seconds

    await registry.register_tool(tool)

    context = ToolExecutionContext(
        agent_id="test-agent",
        user_id="test-user",
    )

    # First execution
    result1 = await registry.execute_tool(
        "web_search",
        {"query": "Python"},
        context,
    )

    # Second execution (should be cached)
    result2 = await registry.execute_tool(
        "web_search",
        {"query": "Python"},
        context,
    )

    assert result1.success is True
    assert result2.success is True
    assert result2.cached is True


@pytest.mark.asyncio
async def test_tool_error_handling():
    """Test tool error handling."""
    registry = ToolRegistry()

    # Register a tool that will fail
    class FailingTool(Tool):
        name: str = "failing_tool"
        description: str = "A tool that always fails"

        async def execute(self, args, context):
            raise ValueError("Tool execution failed")

    await registry.register_tool(FailingTool())

    context = ToolExecutionContext(
        agent_id="test-agent",
        user_id="test-user",
    )

    result = await registry.execute_tool(
        "failing_tool",
        {},
        context,
    )

    assert result.success is False
    assert "Tool execution failed" in result.error


@pytest.mark.asyncio
async def test_tool_timeout():
    """Test tool execution timeout."""
    registry = ToolRegistry()

    # Register a slow tool
    class SlowTool(Tool):
        name: str = "slow_tool"
        description: str = "A slow tool"

        async def execute(self, args, context):
            await asyncio.sleep(5)  # Sleep longer than timeout
            return ToolResult(
                success=True,
                data={"message": "Done"},
                execution_time=5,
                tool_name=self.name,
            )

    await registry.register_tool(SlowTool())

    context = ToolExecutionContext(
        agent_id="test-agent",
        user_id="test-user",
        timeout=1.0,  # 1 second timeout
    )

    result = await registry.execute_tool(
        "slow_tool",
        {},
        context,
    )

    assert result.success is False
    assert "timed out" in result.error


@pytest.mark.asyncio
async def test_tool_statistics():
    """Test tool usage statistics."""
    registry = ToolRegistry()
    await registry.register_tool(WebSearchTool())

    context = ToolExecutionContext(
        agent_id="test-agent",
        user_id="test-user",
    )

    # Execute tool multiple times
    for i in range(3):
        await registry.execute_tool(
            "web_search",
            {"query": f"test query {i}"},
            context,
        )

    # Check statistics
    stats = registry.get_stats("web_search")
    assert stats["total_calls"] == 3
    assert stats["successful_calls"] == 3
    assert stats["failed_calls"] == 0
    assert stats["average_execution_time"] > 0


if __name__ == "__main__":
    # Run tests
    asyncio.run(test_agent_tool_discovery(None))
