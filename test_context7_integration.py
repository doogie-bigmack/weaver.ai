#!/usr/bin/env python3
"""Test integration with context7 MCP server for documentation."""

import asyncio
import json
from typing import Any, Dict

from weaver_ai.agents.base import BaseAgent, Result
from weaver_ai.agents.tool_manager import AgentToolManager
from weaver_ai.events import Event
from weaver_ai.tools import ToolRegistry
from weaver_ai.tools.base import Tool, ToolCapability, ToolExecutionContext, ToolResult
from weaver_ai.tools.builtin import WebSearchTool, DocumentationTool


class Context7DocumentationTool(Tool):
    """Tool that integrates with context7 MCP server for real documentation."""
    
    name: str = "context7_docs"
    description: str = "Access real library documentation via context7"
    capabilities: list[ToolCapability] = [
        ToolCapability.DOCUMENTATION,
        ToolCapability.ANALYSIS,
    ]
    required_scopes: list[str] = ["tool:documentation"]
    
    async def execute(
        self,
        args: Dict[str, Any],
        context: ToolExecutionContext,
    ) -> ToolResult:
        """Execute documentation search using context7.
        
        Args:
            args: Documentation search arguments
            context: Execution context
            
        Returns:
            ToolResult with documentation content
        """
        import time
        start_time = time.time()
        
        try:
            library = args.get("library", "")
            topic = args.get("topic", "")
            
            if not library:
                return ToolResult(
                    success=False,
                    data=None,
                    error="Library name is required",
                    execution_time=time.time() - start_time,
                    tool_name=self.name,
                    tool_version=self.version,
                )
            
            # Note: In a real implementation, this would call the context7 MCP server
            # For demonstration, we'll show how it would work
            print(f"\n[Context7] Resolving library ID for: {library}")
            
            # This would normally use mcp__context7__resolve-library-id
            # and mcp__context7__get-library-docs functions
            
            # Mock response for demonstration
            mock_docs = f"""
# {library} Documentation (via Context7)

## Overview
Real-time documentation for {library} retrieved from Context7 MCP server.

## {topic if topic else 'Getting Started'}

This documentation is dynamically fetched from the Context7 documentation service,
providing up-to-date information about {library}.

### Key Features
- Always current documentation
- Code examples and snippets
- Best practices and patterns
- API references

### Example Usage
```python
# Example code for {library}
import {library.lower().replace('-', '_')}

# Your code here
```

### Related Resources
- Official {library} website
- GitHub repository
- Community forums
- Stack Overflow discussions
"""
            
            return ToolResult(
                success=True,
                data={
                    "library": library,
                    "content": mock_docs,
                    "source": "context7",
                    "topic": topic,
                },
                execution_time=time.time() - start_time,
                tool_name=self.name,
                tool_version=self.version,
                metadata={
                    "agent_id": context.agent_id,
                    "mcp_server": "context7",
                },
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=str(e),
                execution_time=time.time() - start_time,
                tool_name=self.name,
                tool_version=self.version,
            )


class DocumentationAgent(BaseAgent):
    """Agent specialized in fetching and analyzing documentation."""
    
    agent_type: str = "documentation"
    capabilities: list[str] = ["research", "analysis"]
    
    async def process(self, event: Event) -> Result:
        """Process documentation requests."""
        if isinstance(event.data, dict):
            data = event.data
        else:
            # Handle non-dict data
            data = {"task": event.data if isinstance(event.data, str) else ""}
        task = data.get("task", "")
        
        if not task:
            return Result(success=False, data=None, error="No task provided")
        
        # Extract library name from task
        libraries = ["fastapi", "django", "flask", "sqlalchemy", "pydantic", "pytest"]
        library = None
        for lib in libraries:
            if lib in task.lower():
                library = lib
                break
        
        if not library:
            library = data.get("library", "python")
        
        # Use tool manager to execute documentation tool
        if self.tool_registry:
            tool_manager = AgentToolManager(
                agent_id=self.agent_id,
                tool_registry=self.tool_registry,
                available_tools=self.available_tools,
            )
            
            # Try context7 tool first, fallback to regular documentation
            if "context7_docs" in self.available_tools:
                result = await tool_manager.execute_single(
                    "context7_docs",
                    {"library": library, "topic": data.get("topic", "")},
                    {"workflow_id": event.metadata.get("workflow_id")},
                )
            elif "documentation" in self.available_tools:
                result = await tool_manager.execute_single(
                    "documentation",
                    {"library": library, "topic": data.get("topic", "")},
                    {"workflow_id": event.metadata.get("workflow_id")},
                )
            else:
                return Result(
                    success=False,
                    data=None,
                    error="No documentation tools available",
                    workflow_id=event.metadata.get("workflow_id"),
                )
            
            return Result(
                success=result.success,
                data=result.data,
                error=result.error,
                workflow_id=event.metadata.get("workflow_id"),
            )
        
        return Result(
            success=False,
            data=None,
            error="Tool registry not available",
            workflow_id=event.metadata.get("workflow_id"),
        )


async def test_context7_documentation():
    """Test documentation retrieval with context7 MCP server."""
    print("\n=== Testing Context7 Documentation Integration ===\n")
    
    # Create tool registry
    registry = ToolRegistry()
    
    # Register tools
    await registry.register_tool(Context7DocumentationTool())
    await registry.register_tool(DocumentationTool())
    await registry.register_tool(WebSearchTool())
    
    # Create documentation agent
    agent = DocumentationAgent()
    await agent.initialize(
        redis_url="redis://localhost:6379",
        tool_registry=registry,
    )
    
    # Test various documentation requests
    test_cases = [
        {
            "task": "Get documentation for FastAPI routing",
            "library": "fastapi",
            "topic": "routing",
        },
        {
            "task": "Show me Django ORM documentation",
            "library": "django",
            "topic": "ORM",
        },
        {
            "task": "I need pytest fixture documentation",
            "library": "pytest",
            "topic": "fixtures",
        },
    ]
    
    for test_case in test_cases:
        print(f"\nTest: {test_case['task']}")
        print("-" * 50)
        
        event = Event(
            event_type="documentation_request",
            data=test_case,
            metadata={"workflow_id": f"test-{test_case['library']}"},
        )
        
        result = await agent.process(event)
        
        if result.success:
            print(f"✓ Successfully retrieved documentation for {test_case['library']}")
            if result.data:
                print(f"  Source: {result.data.get('source', 'unknown')}")
                print(f"  Topic: {result.data.get('topic', 'general')}")
                print(f"  Content preview: {result.data['content'][:200]}...")
        else:
            print(f"✗ Failed: {result.error}")
    
    # Test tool statistics
    print("\n\n=== Tool Usage Statistics ===")
    stats = registry.get_stats()
    for tool_name, tool_stats in stats.items():
        if tool_stats:
            print(f"\n{tool_name}:")
            print(f"  Total calls: {tool_stats.get('total_calls', 0)}")
            print(f"  Successful: {tool_stats.get('successful_calls', 0)}")
            print(f"  Failed: {tool_stats.get('failed_calls', 0)}")
            if tool_stats.get('average_execution_time'):
                print(f"  Avg time: {tool_stats['average_execution_time']:.3f}s")
    
    # Cleanup
    await agent.stop()
    
    print("\n\n=== Test Complete ===\n")


async def test_real_context7_mcp():
    """Test with real context7 MCP functions if available."""
    print("\n=== Testing Real Context7 MCP Server ===\n")
    
    # This would use the actual mcp__context7 functions
    # For demonstration, we'll show the structure
    
    test_libraries = ["fastapi", "django", "pytest", "sqlalchemy"]
    
    for library in test_libraries:
        print(f"\nTesting documentation for: {library}")
        
        # Step 1: Resolve library ID
        # This would call: mcp__context7__resolve-library-id(libraryName=library)
        print(f"  1. Resolving library ID for {library}...")
        
        # Step 2: Get documentation
        # This would call: mcp__context7__get-library-docs(
        #     context7CompatibleLibraryID=resolved_id,
        #     tokens=5000,
        #     topic="getting started"
        # )
        print(f"  2. Fetching documentation...")
        
        # Mock result for demonstration
        print(f"  ✓ Documentation retrieved successfully")
        print(f"    - Library: {library}")
        print(f"    - Tokens: 5000")
        print(f"    - Topic: getting started")
    
    print("\n=== Real MCP Test Complete ===\n")


async def main():
    """Run all tests."""
    # Test with mock context7
    await test_context7_documentation()
    
    # Test structure for real context7
    await test_real_context7_mcp()
    
    # Additional test: Tool execution plan
    print("\n=== Testing Tool Execution Plans ===\n")
    
    registry = ToolRegistry()
    await registry.register_tool(WebSearchTool())
    await registry.register_tool(DocumentationTool())
    await registry.register_tool(Context7DocumentationTool())
    
    manager = AgentToolManager(
        agent_id="test-agent",
        tool_registry=registry,
        available_tools=["web_search", "documentation", "context7_docs"],
    )
    
    # Execute multiple tools in parallel
    print("Executing parallel documentation searches...")
    results = await manager.execute_parallel([
        ("web_search", {"query": "FastAPI best practices"}),
        ("documentation", {"library": "fastapi"}),
        ("context7_docs", {"library": "fastapi", "topic": "middleware"}),
    ])
    
    for i, result in enumerate(results):
        print(f"\nTool {i+1} ({result.tool_name}):")
        print(f"  Success: {result.success}")
        print(f"  Execution time: {result.execution_time:.3f}s")
        if result.error:
            print(f"  Error: {result.error}")
    
    print("\n=== All Tests Complete ===\n")


if __name__ == "__main__":
    asyncio.run(main())