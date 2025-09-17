"""Tool registry for managing available tools."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime
from typing import Any

from ..mcp import MCPClient, MCPServer
from ..security.rbac import check_access
from .base import Tool, ToolCapability, ToolExecutionContext, ToolResult


class ToolRegistry:
    """Central registry for all available tools."""

    def __init__(self):
        """Initialize the tool registry."""
        self._tools: dict[str, Tool] = {}
        self._capability_map: dict[ToolCapability, set[str]] = defaultdict(set)
        self._mcp_clients: dict[str, MCPClient] = {}
        self._cache: dict[str, ToolResult] = {}
        self._usage_stats: dict[str, dict[str, Any]] = defaultdict(dict)
        self._lock = asyncio.Lock()

    async def register_tool(self, tool: Tool) -> None:
        """Register a tool in the registry.

        Args:
            tool: Tool instance to register
        """
        async with self._lock:
            if tool.name in self._tools:
                raise ValueError(f"Tool {tool.name} already registered")

            self._tools[tool.name] = tool

            # Update capability mapping
            for capability in tool.capabilities:
                self._capability_map[capability].add(tool.name)

            # Initialize usage stats
            self._usage_stats[tool.name] = {
                "total_calls": 0,
                "successful_calls": 0,
                "failed_calls": 0,
                "total_execution_time": 0.0,
                "average_execution_time": 0.0,
                "last_used": None,
            }

    async def unregister_tool(self, tool_name: str) -> None:
        """Unregister a tool from the registry.

        Args:
            tool_name: Name of the tool to unregister
        """
        async with self._lock:
            if tool_name not in self._tools:
                return

            tool = self._tools[tool_name]

            # Remove from capability mapping
            for capability in tool.capabilities:
                self._capability_map[capability].discard(tool_name)

            # Remove tool
            del self._tools[tool_name]

            # Clear cache entries for this tool
            cache_keys_to_remove = [
                key for key in self._cache.keys() if key.startswith(f"{tool_name}:")
            ]
            for key in cache_keys_to_remove:
                del self._cache[key]

    def get_tool(self, tool_name: str) -> Tool | None:
        """Get a tool by name.

        Args:
            tool_name: Name of the tool

        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(tool_name)

    def get_tools_by_capability(self, capability: ToolCapability) -> list[Tool]:
        """Get all tools with a specific capability.

        Args:
            capability: Tool capability to filter by

        Returns:
            List of tools with the capability
        """
        tool_names = self._capability_map.get(capability, set())
        return [self._tools[name] for name in tool_names if name in self._tools]

    def list_tools(self, enabled_only: bool = True) -> list[Tool]:
        """List all registered tools.

        Args:
            enabled_only: Only return enabled tools

        Returns:
            List of tools
        """
        tools = list(self._tools.values())
        if enabled_only:
            tools = [t for t in tools if t.enabled]
        return tools

    async def execute_tool(
        self,
        tool_name: str,
        args: dict[str, Any],
        context: ToolExecutionContext,
        check_permissions: bool = True,
    ) -> ToolResult:
        """Execute a tool with the given arguments.

        Args:
            tool_name: Name of the tool to execute
            args: Tool arguments
            context: Execution context
            check_permissions: Whether to check RBAC permissions

        Returns:
            ToolResult from execution
        """
        tool = self.get_tool(tool_name)
        if not tool:
            return ToolResult(
                success=False,
                data=None,
                error=f"Tool {tool_name} not found",
                execution_time=0,
                tool_name=tool_name,
            )

        if not tool.enabled:
            return ToolResult(
                success=False,
                data=None,
                error=f"Tool {tool_name} is disabled",
                execution_time=0,
                tool_name=tool_name,
            )

        # Check permissions if required
        if check_permissions and tool.required_scopes:
            from pathlib import Path

            from ..security.auth import UserContext

            # Create UserContext from execution context
            user_context = UserContext(user_id=context.user_id)

            roles_path = Path("weaver_ai/policies/roles.yaml")
            for scope in tool.required_scopes:
                try:
                    check_access(user_context, scope, roles_path=roles_path)
                except Exception as e:
                    return ToolResult(
                        success=False,
                        data=None,
                        error=f"Permission denied: {str(e)}",
                        execution_time=0,
                        tool_name=tool_name,
                    )

        # Check cache if enabled
        if tool.cache_enabled:
            cache_key = tool.get_cache_key(args, context)
            if cache_key in self._cache:
                cached_result = self._cache[cache_key]
                cached_result.cached = True
                return cached_result

        # Validate arguments
        try:
            tool.validate_args(args)
        except ValueError as e:
            return ToolResult(
                success=False,
                data=None,
                error=f"Invalid arguments: {str(e)}",
                execution_time=0,
                tool_name=tool_name,
            )

        # Execute tool with timeout
        import time

        start_time = time.time()

        try:
            result = await asyncio.wait_for(
                tool.execute(args, context),
                timeout=context.timeout,
            )
            execution_time = time.time() - start_time
            result.execution_time = execution_time

            # Update usage stats
            await self._update_stats(tool_name, result)

            # Cache successful result if enabled
            if tool.cache_enabled and result.success:
                cache_key = tool.get_cache_key(args, context)
                self._cache[cache_key] = result

                # Schedule cache expiration
                asyncio.create_task(self._expire_cache(cache_key, tool.cache_ttl))

            return result

        except TimeoutError:
            execution_time = time.time() - start_time
            result = ToolResult(
                success=False,
                data=None,
                error=f"Tool execution timed out after {context.timeout}s",
                execution_time=execution_time,
                tool_name=tool_name,
            )
            await self._update_stats(tool_name, result)
            return result

        except Exception as e:
            execution_time = time.time() - start_time
            result = ToolResult(
                success=False,
                data=None,
                error=f"Tool execution failed: {str(e)}",
                execution_time=execution_time,
                tool_name=tool_name,
            )
            await self._update_stats(tool_name, result)
            return result

    async def _update_stats(self, tool_name: str, result: ToolResult) -> None:
        """Update usage statistics for a tool.

        Args:
            tool_name: Name of the tool
            result: Execution result
        """
        async with self._lock:
            stats = self._usage_stats[tool_name]
            stats["total_calls"] += 1

            if result.success:
                stats["successful_calls"] += 1
            else:
                stats["failed_calls"] += 1

            stats["total_execution_time"] += result.execution_time
            stats["average_execution_time"] = (
                stats["total_execution_time"] / stats["total_calls"]
            )
            stats["last_used"] = datetime.now().isoformat()

    async def _expire_cache(self, cache_key: str, ttl: int) -> None:
        """Expire a cache entry after TTL.

        Args:
            cache_key: Cache key to expire
            ttl: Time to live in seconds
        """
        await asyncio.sleep(ttl)
        self._cache.pop(cache_key, None)

    def get_stats(self, tool_name: str | None = None) -> dict[str, Any]:
        """Get usage statistics.

        Args:
            tool_name: Specific tool name or None for all

        Returns:
            Usage statistics
        """
        if tool_name:
            return self._usage_stats.get(tool_name, {})
        return dict(self._usage_stats)

    async def register_mcp_server(
        self, server_id: str, server: MCPServer, client: MCPClient
    ) -> None:
        """Register an MCP server and its tools.

        Args:
            server_id: Unique server identifier
            server: MCP server instance
            client: MCP client for the server
        """
        async with self._lock:
            self._mcp_clients[server_id] = client

            # TODO: Discover and register tools from MCP server
            # This would involve querying the server for available tools
            # and creating MCPTool instances for each


# Global registry instance
global_tool_registry = ToolRegistry()
