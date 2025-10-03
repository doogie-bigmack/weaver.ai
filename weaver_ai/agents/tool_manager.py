"""Tool management for agents."""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel, Field

from ..tools import ToolExecutionContext, ToolRegistry, ToolResult


class ToolSelectionStrategy(BaseModel):
    """Strategy for selecting tools based on task."""

    task_keywords: dict[str, list[str]] = Field(default_factory=dict)
    capability_mapping: dict[str, list[str]] = Field(default_factory=dict)

    def select_tools(self, task: str, available_tools: list[str]) -> list[str]:
        """Select tools based on task description.

        Args:
            task: Task description
            available_tools: List of available tool names

        Returns:
            List of selected tool names
        """
        selected = []
        task_lower = task.lower()

        # Check for keyword matches
        for tool, keywords in self.task_keywords.items():
            if tool in available_tools:
                if any(keyword in task_lower for keyword in keywords):
                    selected.append(tool)

        return selected


class ToolExecutionPlan(BaseModel):
    """Execution plan for multiple tools."""

    sequential: list[str] = Field(default_factory=list)
    parallel: list[list[str]] = Field(default_factory=list)
    conditional: dict[str, dict[str, Any]] = Field(default_factory=dict)


class AgentToolManager:
    """Manages tool execution for agents."""

    def __init__(
        self,
        agent_id: str,
        tool_registry: ToolRegistry,
        available_tools: list[str] | None = None,
    ):
        """Initialize tool manager.

        Args:
            agent_id: Agent identifier
            tool_registry: Tool registry instance
            available_tools: List of available tool names
        """
        self.agent_id = agent_id
        self.tool_registry = tool_registry
        self.available_tools = available_tools or []
        self.execution_history: list[dict[str, Any]] = []
        self.selection_strategy = self._default_strategy()

    def _default_strategy(self) -> ToolSelectionStrategy:
        """Create default tool selection strategy.

        Returns:
            Default selection strategy
        """
        return ToolSelectionStrategy(
            task_keywords={
                "web_search": ["search", "find", "look up", "google", "web"],
                "documentation": ["docs", "documentation", "api", "reference", "guide"],
                "python_eval": ["calculate", "compute", "math", "evaluate"],
            },
            capability_mapping={
                "research": ["web_search", "documentation"],
                "analysis": ["python_eval", "data_analyzer"],
                "coding": ["code_executor", "syntax_checker"],
            },
        )

    async def execute_single(
        self,
        tool_name: str,
        args: dict[str, Any],
        context: dict[str, Any] | None = None,
        check_permissions: bool = False,
    ) -> ToolResult:
        """Execute a single tool.

        Args:
            tool_name: Name of the tool
            args: Tool arguments
            context: Optional execution context
            check_permissions: Whether to check RBAC permissions (default: False)

        Returns:
            Tool execution result
        """
        if tool_name not in self.available_tools:
            return ToolResult(
                success=False,
                data=None,
                error=f"Tool {tool_name} not available",
                execution_time=0,
                tool_name=tool_name,
            )

        exec_context = ToolExecutionContext(
            agent_id=self.agent_id,
            workflow_id=context.get("workflow_id") if context else None,
            user_id=context.get("user_id", "system") if context else "system",
            metadata=context or {},
        )

        result = await self.tool_registry.execute_tool(
            tool_name=tool_name,
            args=args,
            context=exec_context,
            check_permissions=check_permissions,
        )

        # Record execution
        self.execution_history.append(
            {
                "tool": tool_name,
                "args": args,
                "success": result.success,
                "execution_time": result.execution_time,
            }
        )

        return result

    async def execute_parallel(
        self,
        tools: list[tuple[str, dict[str, Any]]],
        context: dict[str, Any] | None = None,
        check_permissions: bool = False,
    ) -> list[ToolResult]:
        """Execute multiple tools in parallel.

        Args:
            tools: List of (tool_name, args) tuples
            context: Optional execution context
            check_permissions: Whether to check RBAC permissions (default: False)

        Returns:
            List of tool results
        """
        tasks = [
            self.execute_single(tool_name, args, context, check_permissions)
            for tool_name, args in tools
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to ToolResult
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                tool_name = tools[i][0]
                processed_results.append(
                    ToolResult(
                        success=False,
                        data=None,
                        error=str(result),
                        execution_time=0,
                        tool_name=tool_name,
                    )
                )
            else:
                processed_results.append(result)

        return processed_results

    async def execute_sequential(
        self,
        tools: list[tuple[str, dict[str, Any]]],
        context: dict[str, Any] | None = None,
        stop_on_error: bool = True,
        check_permissions: bool = False,
    ) -> list[ToolResult]:
        """Execute tools sequentially.

        Args:
            tools: List of (tool_name, args) tuples
            context: Optional execution context
            stop_on_error: Stop execution on first error
            check_permissions: Whether to check RBAC permissions (default: False)

        Returns:
            List of tool results
        """
        results = []

        for tool_name, args in tools:
            # Pass previous result as context if available
            if results and results[-1].success:
                if context is None:
                    context = {}
                context["previous_result"] = results[-1].data

            result = await self.execute_single(
                tool_name, args, context, check_permissions
            )
            results.append(result)

            if not result.success and stop_on_error:
                break

        return results

    async def execute_plan(
        self,
        plan: ToolExecutionPlan,
        initial_args: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a complex tool execution plan.

        Args:
            plan: Execution plan
            initial_args: Initial arguments for tools
            context: Optional execution context

        Returns:
            Combined results from all tool executions
        """
        results = {
            "sequential": [],
            "parallel": [],
            "conditional": [],
        }

        # Execute sequential tools
        if plan.sequential:
            seq_tools = [(tool, initial_args or {}) for tool in plan.sequential]
            results["sequential"] = await self.execute_sequential(seq_tools, context)

        # Execute parallel tool groups
        for parallel_group in plan.parallel:
            par_tools = [(tool, initial_args or {}) for tool in parallel_group]
            group_results = await self.execute_parallel(par_tools, context)
            results["parallel"].append(group_results)

        # Handle conditional executions
        for condition_key, _condition_spec in plan.conditional.items():
            # This would implement conditional logic
            # For now, just note it's not implemented
            results["conditional"].append(
                {
                    "condition": condition_key,
                    "status": "not_implemented",
                }
            )

        return results

    def select_tools_for_task(
        self,
        task: str,
        max_tools: int = 3,
    ) -> list[str]:
        """Select appropriate tools for a task.

        Args:
            task: Task description
            max_tools: Maximum number of tools to select

        Returns:
            List of selected tool names
        """
        selected = self.selection_strategy.select_tools(task, self.available_tools)

        # Limit to max_tools
        if len(selected) > max_tools:
            selected = selected[:max_tools]

        return selected

    def get_execution_stats(self) -> dict[str, Any]:
        """Get execution statistics.

        Returns:
            Execution statistics
        """
        if not self.execution_history:
            return {
                "total_executions": 0,
                "successful": 0,
                "failed": 0,
                "average_time": 0,
            }

        successful = sum(1 for h in self.execution_history if h["success"])
        failed = len(self.execution_history) - successful
        avg_time = sum(h["execution_time"] for h in self.execution_history) / len(
            self.execution_history
        )

        return {
            "total_executions": len(self.execution_history),
            "successful": successful,
            "failed": failed,
            "average_time": avg_time,
            "by_tool": self._stats_by_tool(),
        }

    def _stats_by_tool(self) -> dict[str, dict[str, Any]]:
        """Get statistics grouped by tool.

        Returns:
            Stats by tool
        """
        by_tool = {}

        for entry in self.execution_history:
            tool = entry["tool"]
            if tool not in by_tool:
                by_tool[tool] = {
                    "executions": 0,
                    "successful": 0,
                    "failed": 0,
                    "total_time": 0,
                }

            by_tool[tool]["executions"] += 1
            if entry["success"]:
                by_tool[tool]["successful"] += 1
            else:
                by_tool[tool]["failed"] += 1
            by_tool[tool]["total_time"] += entry["execution_time"]

        # Calculate averages
        for tool_stats in by_tool.values():
            if tool_stats["executions"] > 0:
                tool_stats["average_time"] = (
                    tool_stats["total_time"] / tool_stats["executions"]
                )

        return by_tool
