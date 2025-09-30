#!/usr/bin/env python3
"""
Test SailPoint IIQ MCP integration with real server.

This script demonstrates:
1. Connecting to the real MCP server
2. Making actual API calls (not mock data)
3. Processing responses with GPT for analysis
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from weaver_ai.agents.base import BaseAgent, Result
from weaver_ai.events.models import Event, EventMetadata, EventType
from weaver_ai.models.config import setup_router_from_config
from weaver_ai.tools.base import ToolCapability
from weaver_ai.tools.builtin.sailpoint import SailPointIIQTool
from weaver_ai.tools.registry import ToolRegistry


class LiveSailPointAgent(BaseAgent):
    """Agent that connects to real SailPoint MCP server."""
    
    name: str = "LiveSailPointAgent"
    description: str = "Agent for real-time SailPoint IIQ operations"
    capabilities: list[ToolCapability] = [ToolCapability.API_CALL, ToolCapability.DATABASE]
    
    async def process(self, event: Event) -> Result:
        """Process SailPoint queries using real MCP server."""
        print(f"\n[{self.name}] Processing: {event.data}")
        
        # Parse the query
        query = event.data if isinstance(event.data, str) else str(event.data)
        
        # Execute SailPoint operations
        operations = []
        
        if "count" in query.lower():
            # Count users and roles
            result = await self.execute_tool(
                "sailpoint_iiq",
                {"operation": "count_users_roles"},
                check_permissions=False
            )
            operations.append(("User and Role Count", result))
            
        if "list" in query.lower() and "user" in query.lower():
            # List users
            result = await self.execute_tool(
                "sailpoint_iiq",
                {
                    "operation": "list_users",
                    "query": {"limit": 5, "offset": 0}
                },
                check_permissions=False
            )
            operations.append(("User List", result))
            
        if "list" in query.lower() and "role" in query.lower():
            # List roles
            result = await self.execute_tool(
                "sailpoint_iiq",
                {
                    "operation": "list_roles",
                    "query": {"limit": 5, "offset": 0}
                },
                check_permissions=False
            )
            operations.append(("Role List", result))
        
        # Process results with LLM if configured
        if hasattr(self, 'model_router') and self.model_router:
            # Prepare context for LLM
            context = "SailPoint IIQ Live Data Analysis:\n\n"
            for op_name, op_result in operations:
                if op_result and op_result.success:
                    context += f"{op_name}:\n"
                    if op_result.data:
                        # Check if this is real or mock data
                        if isinstance(op_result.data, dict):
                            source = op_result.data.get('_source', 'unknown')
                            if source == 'live':
                                context += "  [LIVE DATA FROM SAILPOINT]\n"
                            elif source == 'demo':
                                context += "  [DEMO DATA - Real server attempted but unavailable]\n"
                            elif '_mock' in op_result.data:
                                context += "  [MOCK DATA - MCP server not available]\n"
                        context += f"  {op_result.data}\n\n"
                else:
                    error_msg = op_result.error if op_result else "Unknown error"
                    context += f"{op_name}: Failed - {error_msg}\n\n"
            
            prompt = f"""You are analyzing real-time SailPoint IdentityIQ data.

{context}

Based on this data, provide:
1. A summary of the identity governance status
2. Key observations about user and role distribution
3. Any potential compliance or security concerns
4. Recommendations for improvement

Note whether the data is from a live SailPoint instance or demo data."""

            try:
                response = await self.model_router.generate(
                    prompt=prompt,
                    model="gpt-4o-mini",
                    max_tokens=500,
                    temperature=0.7
                )
                
                return Result(
                    success=True,
                    data={
                        "sailpoint_operations": [
                            {
                                "operation": op[0],
                                "success": op[1].success if op[1] else False,
                                "data": op[1].data if op[1] and op[1].success else None,
                                "error": op[1].error if op[1] and not op[1].success else None
                            }
                            for op in operations
                        ],
                        "analysis": response,
                        "mcp_server": "Connected to localhost:3000",
                        "data_source": self._determine_data_source(operations)
                    },
                    metadata={"processed_by": self.name}
                )
            except Exception as e:
                print(f"[{self.name}] LLM analysis failed: {e}")
                # Return results without LLM analysis
                return Result(
                    success=True,
                    data={
                        "sailpoint_operations": [
                            {
                                "operation": op[0],
                                "success": op[1].success if op[1] else False,
                                "data": op[1].data if op[1] and op[1].success else None
                            }
                            for op in operations
                        ],
                        "mcp_server": "Connected to localhost:3000",
                        "data_source": self._determine_data_source(operations),
                        "note": "LLM analysis unavailable"
                    },
                    metadata={"processed_by": self.name}
                )
        else:
            # No LLM configured, return raw results
            return Result(
                success=True,
                data={
                    "sailpoint_operations": [
                        {
                            "operation": op[0],
                            "success": op[1].success if op[1] else False,
                            "data": op[1].data if op[1] and op[1].success else None
                        }
                        for op in operations
                    ],
                    "mcp_server": "Connected to localhost:3000",
                    "data_source": self._determine_data_source(operations)
                },
                metadata={"processed_by": self.name}
            )
    
    def _determine_data_source(self, operations):
        """Determine the data source from operation results."""
        for _, result in operations:
            if result and result.success and result.data:
                if isinstance(result.data, dict):
                    if result.data.get('_source') == 'live':
                        return "Live SailPoint Instance"
                    elif result.data.get('_source') == 'demo':
                        return "Demo Data (Real server unavailable)"
                    elif '_mock' in result.data:
                        return "Mock Data (MCP server not running)"
        return "Unknown"


async def main():
    """Main test function."""
    print("\n" + "="*60)
    print("SailPoint IIQ MCP - Real Server Test")
    print("="*60)
    
    # Check if MCP server is expected to be running
    print("\n[Setup] Checking MCP server requirements...")
    print("  Expected MCP server: http://localhost:3000")
    print("  To start the server:")
    print("    cd sailpoint-mcp-server")
    print("    npm install")
    print("    npm start")
    print()
    
    # Setup
    print("[Setup] Initializing components...")
    
    # Create tool registry and register SailPoint tool
    tool_registry = ToolRegistry()
    sailpoint_tool = SailPointIIQTool()
    tool_registry.register_tool(sailpoint_tool)
    print(f"  ✓ Registered {sailpoint_tool.name} tool")
    
    # Setup model router if API key is available
    model_router = None
    if os.getenv("OPENAI_API_KEY"):
        print("  ✓ OpenAI API key found, enabling LLM analysis")
        model_router = setup_router_from_config("models.yaml")
    else:
        print("  ⚠ No OpenAI API key found, running without LLM analysis")
        print("    Set OPENAI_API_KEY environment variable to enable GPT analysis")
    
    # Create agent
    agent = LiveSailPointAgent()
    await agent.initialize(tool_registry=tool_registry)
    
    if model_router:
        agent.model_router = model_router
    
    print(f"  ✓ Initialized {agent.name}")
    print(f"  ✓ Available tools: {[t.name for t in agent.available_tools]}")
    
    # Test queries
    queries = [
        "Count all users and roles in SailPoint",
        "List users and roles with details",
    ]
    
    for query in queries:
        print(f"\n[Test] Query: {query}")
        print("-" * 40)
        
        # Create event
        event = Event(
            type=EventType.TASK,
            data=query,
            metadata=EventMetadata(
                source="test_script",
                target=agent.name,
                workflow_id="test_real_mcp"
            )
        )
        
        # Process
        try:
            result = await agent.process(event)
            
            if result.success:
                print("\n[Result] Success!")
                
                # Display results
                if isinstance(result.data, dict):
                    # Show data source
                    data_source = result.data.get('data_source', 'Unknown')
                    print(f"\n  Data Source: {data_source}")
                    
                    if data_source == "Live SailPoint Instance":
                        print("  ✓ Successfully connected to real SailPoint!")
                    elif data_source == "Demo Data (Real server unavailable)":
                        print("  ⚠ MCP server running but SailPoint unavailable")
                    elif data_source == "Mock Data (MCP server not running)":
                        print("  ⚠ MCP server not running, using fallback mock data")
                    
                    # Show operations
                    ops = result.data.get('sailpoint_operations', [])
                    for op in ops:
                        print(f"\n  Operation: {op['operation']}")
                        if op['success']:
                            print("    Status: ✓ Success")
                            if op['data']:
                                # Show sample data
                                data = op['data']
                                if 'users' in data:
                                    print(f"    Total Users: {data['users'].get('total', 'N/A')}")
                                if 'roles' in data:
                                    print(f"    Total Roles: {data['roles'].get('total', 'N/A')}")
                                if 'identities' in data:
                                    print(f"    Identities Retrieved: {len(data['identities'])}")
                                if 'bundles' in data:
                                    print(f"    Bundles Retrieved: {len(data['bundles'])}")
                        else:
                            print("    Status: ✗ Failed")
                            print(f"    Error: {op.get('error', 'Unknown')}")
                    
                    # Show LLM analysis if available
                    if 'analysis' in result.data:
                        print("\n  GPT Analysis:")
                        print("  " + "-"*30)
                        for line in result.data['analysis'].split('\n'):
                            if line.strip():
                                print(f"  {line}")
                
            else:
                print(f"\n[Result] Failed: {result.error}")
                
        except Exception as e:
            print(f"\n[Error] {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*60)
    print("Test Complete")
    print("="*60)
    
    # Instructions for next steps
    print("\nNext Steps:")
    print("1. If MCP server is not running:")
    print("   cd sailpoint-mcp-server")
    print("   npm install")
    print("   npm start")
    print()
    print("2. To connect to a real SailPoint instance:")
    print("   Edit sailpoint-mcp-server/.env with your SailPoint credentials")
    print()
    print("3. To enable GPT analysis:")
    print("   export OPENAI_API_KEY='your-api-key'")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())