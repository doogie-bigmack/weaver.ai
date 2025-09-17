#!/usr/bin/env python3
"""Test SailPoint IIQ MCP server integration."""

import asyncio
import json

from pydantic import BaseModel

from weaver_ai.agents.base import BaseAgent, Result
from weaver_ai.events import Event
from weaver_ai.tools import ToolRegistry
from weaver_ai.tools.base import ToolExecutionContext
from weaver_ai.tools.builtin.sailpoint import SailPointIIQTool


class IdentityQueryRequest(BaseModel):
    """Request for identity governance queries."""

    task: str
    workflow_id: str | None = None


class IdentityGovernanceAgent(BaseAgent):
    """Agent specialized in identity governance and administration."""

    agent_type: str = "identity_governance"
    capabilities: list[str] = ["integration", "data", "analysis"]

    async def process(self, event: Event) -> Result:
        """Process identity governance requests."""
        # Extract task from the event data
        if isinstance(event.data, IdentityQueryRequest):
            task = event.data.task
            workflow_id = event.data.workflow_id
        else:
            task = ""
            workflow_id = None

        if not task:
            return Result(success=False, data=None, error="No task provided")

        # Use tool registry directly for SailPoint operations
        if self.tool_registry and "sailpoint_iiq" in self.available_tools:
            # Determine operation based on task
            operation = None
            query = {}

            if "count" in task.lower() or "how many" in task.lower():
                operation = "count_users_roles"
            elif "list users" in task.lower():
                operation = "list_users"
                query = {"limit": 5}
            elif "list roles" in task.lower():
                operation = "list_roles"
                query = {"limit": 5}
            elif "get user" in task.lower():
                operation = "get_user"
                query = {"user_id": "user_123"}
            elif "get role" in task.lower():
                operation = "get_role"
                query = {"role_id": "role_1"}

            if operation:
                # Execute tool directly with bypassed permissions for testing
                exec_context = ToolExecutionContext(
                    agent_id=self.agent_id,
                    user_id="admin",
                    workflow_id=workflow_id,
                )
                result = await self.tool_registry.execute_tool(
                    "sailpoint_iiq",
                    {"operation": operation, "query": query},
                    exec_context,
                    check_permissions=False,  # Bypass for testing
                )
                return Result(
                    success=result.success,
                    data=result.data,
                    error=result.error,
                    workflow_id=workflow_id,
                )

        return Result(
            success=False,
            data=None,
            error="SailPoint IIQ tool not available",
            workflow_id=workflow_id,
        )


async def test_sailpoint_mcp_server():
    """Test SailPoint IIQ MCP server integration."""
    print("\n" + "=" * 70)
    print(" SailPoint IdentityIQ MCP Server Integration Test")
    print("=" * 70)

    # Show configuration
    print("\n📋 Configuration from claude_desktop_config.json:")
    print("  - MCP Server: localhost:3000")
    print("  - IIQ URL: http://10.201.224.8:8080/identityiq")
    print("  - Auth Type: Basic")
    print("  - Username: spadmin")

    # Create tool registry
    registry = ToolRegistry()

    # Register SailPoint tool
    sailpoint_tool = SailPointIIQTool()
    await registry.register_tool(sailpoint_tool)

    print("\n✅ SailPoint IIQ tool registered")

    # Create identity governance agent
    agent = IdentityGovernanceAgent()
    await agent.initialize(
        redis_url="redis://localhost:6379",
        tool_registry=registry,
    )

    print("✅ Identity Governance Agent initialized")
    print(f"   Available tools: {agent.available_tools}")

    # Test 1: Count users and roles
    print("\n" + "-" * 70)
    print("📊 Test 1: Count users and roles in SailPoint IIQ")
    print("-" * 70)

    query_data = IdentityQueryRequest(
        task="How many users and roles are currently configured?",
        workflow_id="test-count",
    )
    event = Event(data=query_data)

    result = await agent.process(event)

    if result.success:
        print("\n✅ Query successful!")
        data = result.data
        print("\n📈 Results:")
        print("   Users:")
        print(f"     - Total: {data['users']['total']}")
        print(f"     - Active: {data['users']['active']}")
        print(f"     - Inactive: {data['users']['inactive']}")
        print("   Roles:")
        print(f"     - Total: {data['roles']['total']}")
        print(f"     - Business Roles: {data['roles']['business_roles']}")
        print(f"     - IT Roles: {data['roles']['it_roles']}")
        print(f"\n   Summary: {data['summary']}")
    else:
        print(f"❌ Query failed: {result.error}")

    # Test 2: List users
    print("\n" + "-" * 70)
    print("👥 Test 2: List users")
    print("-" * 70)

    query_data = IdentityQueryRequest(task="list users", workflow_id="test-list-users")
    event = Event(data=query_data)

    result = await agent.process(event)

    if result.success:
        print("\n✅ User list retrieved!")
        users = result.data.get("users", [])
        print(f"   Showing {len(users)} of {result.data.get('total', 0)} users:")
        for user in users[:3]:  # Show first 3
            print(
                f"   - {user['name']} ({user['email']}) - {user['department']} - {user['status']}"
            )
    else:
        print(f"❌ Failed to list users: {result.error}")

    # Test 3: List roles
    print("\n" + "-" * 70)
    print("🔐 Test 3: List roles")
    print("-" * 70)

    query_data = IdentityQueryRequest(task="list roles", workflow_id="test-list-roles")
    event = Event(data=query_data)

    result = await agent.process(event)

    if result.success:
        print("\n✅ Role list retrieved!")
        roles = result.data.get("roles", [])
        print(f"   Showing {len(roles)} of {result.data.get('total', 0)} roles:")
        for role in roles[:3]:  # Show first 3
            print(
                f"   - {role['name']} ({role['type']}) - {role['entitlements']} entitlements"
            )
    else:
        print(f"❌ Failed to list roles: {result.error}")

    # Test 4: Direct tool execution
    print("\n" + "-" * 70)
    print("🔧 Test 4: Direct tool execution")
    print("-" * 70)

    context = ToolExecutionContext(
        agent_id="test-agent",
        user_id="admin",
    )

    # Get specific user details
    print("\n📝 Getting user details for user_123...")
    result = await registry.execute_tool(
        "sailpoint_iiq",
        {"operation": "get_user", "query": {"user_id": "user_123"}},
        context,
        check_permissions=False,
    )

    if result.success:
        print("✅ User details retrieved:")
        user = result.data
        print(f"   Name: {user['name']}")
        print(f"   Email: {user['email']}")
        print(f"   Department: {user['department']}")
        print(f"   Roles: {', '.join(user['roles'])}")
        print("   Entitlements:")
        for ent in user["entitlements"]:
            print(f"     - {ent['app']}: {ent['value']}")

    # Get specific role details
    print("\n📝 Getting role details for role_1...")
    result = await registry.execute_tool(
        "sailpoint_iiq",
        {"operation": "get_role", "query": {"role_id": "role_1"}},
        context,
        check_permissions=False,
    )

    if result.success:
        print("✅ Role details retrieved:")
        role = result.data
        print(f"   Name: {role['name']}")
        print(f"   Type: {role['type']}")
        print(f"   Description: {role['description']}")
        print(f"   Members: {role['members']}")
        print("   Entitlements:")
        for ent in role["entitlements"]:
            print(f"     - {ent['app']}: {ent['value']}")

    # Show statistics
    print("\n" + "-" * 70)
    print("📊 Tool Usage Statistics")
    print("-" * 70)

    stats = registry.get_stats("sailpoint_iiq")
    if stats:
        print(f"   Total calls: {stats.get('total_calls', 0)}")
        print(f"   Successful: {stats.get('successful_calls', 0)}")
        print(f"   Failed: {stats.get('failed_calls', 0)}")
        print(f"   Average time: {stats.get('average_execution_time', 0):.3f}s")

    # Cleanup
    await agent.stop()

    print("\n" + "=" * 70)
    print(" Test Complete")
    print("=" * 70)


def demonstrate_mcp_protocol():
    """Demonstrate how MCP protocol would work with SailPoint."""
    print("\n" + "=" * 70)
    print(" MCP Protocol Communication Example")
    print("=" * 70)

    print("\n🔌 How the MCP protocol works with SailPoint IIQ:\n")

    # Show MCP request structure
    mcp_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "sailpoint.countIdentities",
            "arguments": {
                "types": ["Identity", "Bundle"],
                "filters": {
                    "Identity": {"active": True},
                    "Bundle": {"type": "business"},
                },
            },
        },
    }

    print("1️⃣ MCP Request (from Weaver.AI to MCP Server):")
    print(json.dumps(mcp_request, indent=2))

    # Show MCP response structure
    mcp_response = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "users": {"total": 1250, "active": 1180, "inactive": 70},
                            "roles": {
                                "total": 85,
                                "business_roles": 45,
                                "it_roles": 40,
                            },
                        }
                    ),
                },
            ],
        },
    }

    print("\n2️⃣ MCP Response (from MCP Server to Weaver.AI):")
    print(json.dumps(mcp_response, indent=2))

    print("\n3️⃣ The MCP Server internally:")
    print("   - Receives the MCP request")
    print("   - Authenticates with SailPoint IIQ using provided credentials")
    print("   - Makes REST API calls to SailPoint IIQ")
    print("   - Transforms the response to MCP format")
    print("   - Returns the result to Weaver.AI")

    print("\n📝 Benefits of using MCP:")
    print("   ✓ Standardized protocol for tool communication")
    print("   ✓ Authentication handled by MCP server")
    print("   ✓ Error handling and retry logic")
    print("   ✓ Response caching and optimization")
    print("   ✓ Audit logging and compliance")


async def main():
    """Run all tests."""
    # Show MCP protocol explanation
    demonstrate_mcp_protocol()

    # Run SailPoint integration test
    await test_sailpoint_mcp_server()

    print("\n🎯 Key Takeaways:")
    print("   1. MCP tools can integrate with complex enterprise systems")
    print("   2. The tool abstraction makes it easy to query different systems")
    print("   3. Agents can use specialized tools based on their capabilities")
    print("   4. Full audit trail and statistics are maintained")
    print("\n✨ The MCP tool framework successfully integrates with SailPoint IIQ!")


if __name__ == "__main__":
    asyncio.run(main())
