"""Base classes for MCP tools."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ToolCapability(str, Enum):
    """Tool capability categories."""

    WEB_SEARCH = "web_search"
    DATABASE = "database"
    FILE_SYSTEM = "file_system"
    API_CALL = "api_call"
    CODE_EXECUTION = "code_execution"
    DOCUMENTATION = "documentation"
    ANALYSIS = "analysis"
    COMMUNICATION = "communication"
    COMPUTATION = "computation"


class ToolExecutionContext(BaseModel):
    """Context for tool execution."""

    agent_id: str
    workflow_id: Optional[str] = None
    user_id: str
    request_id: str = Field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timeout: float = 30.0  # seconds
    retry_count: int = 0
    max_retries: int = 3


class ToolResult(BaseModel):
    """Result from tool execution."""

    success: bool
    data: Any
    error: Optional[str] = None
    execution_time: float  # seconds
    metadata: Dict[str, Any] = Field(default_factory=dict)
    cached: bool = False
    tool_name: str
    tool_version: str = "1.0.0"

    def to_json(self) -> str:
        """Convert result to JSON string."""
        return json.dumps(self.model_dump(), default=str)


class Tool(ABC, BaseModel):
    """Abstract base class for all MCP tools."""

    name: str
    description: str
    version: str = "1.0.0"
    capabilities: List[ToolCapability] = Field(default_factory=list)
    required_scopes: List[str] = Field(default_factory=list)
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)

    # Runtime configuration
    enabled: bool = True
    rate_limit: Optional[int] = None  # requests per minute
    cost_per_call: float = 0.0  # for cost tracking
    requires_approval: bool = False

    # Caching configuration
    cache_enabled: bool = True
    cache_ttl: int = 300  # seconds

    class Config:
        arbitrary_types_allowed = True

    @abstractmethod
    async def execute(
        self, args: Dict[str, Any], context: ToolExecutionContext
    ) -> ToolResult:
        """Execute the tool with given arguments.

        Args:
            args: Tool-specific arguments
            context: Execution context

        Returns:
            ToolResult with execution outcome
        """
        pass

    def validate_args(self, args: Dict[str, Any]) -> bool:
        """Validate input arguments against schema.

        Args:
            args: Arguments to validate

        Returns:
            True if valid, raises ValueError if not
        """
        # Basic validation - can be overridden
        if self.input_schema:
            required = self.input_schema.get("required", [])
            for field in required:
                if field not in args:
                    raise ValueError(f"Missing required field: {field}")
        return True

    def get_cache_key(self, args: Dict[str, Any], context: ToolExecutionContext) -> str:
        """Generate cache key for the tool call.

        Args:
            args: Tool arguments
            context: Execution context

        Returns:
            Cache key string
        """
        # Simple cache key - can be overridden for more complex logic
        key_parts = [
            self.name,
            self.version,
            json.dumps(args, sort_keys=True),
            context.agent_id,
        ]
        return ":".join(key_parts)

    def get_metrics(self) -> Dict[str, Any]:
        """Get tool usage metrics.

        Returns:
            Dictionary of metrics
        """
        return {
            "name": self.name,
            "version": self.version,
            "enabled": self.enabled,
            "rate_limit": self.rate_limit,
            "cost_per_call": self.cost_per_call,
        }


class MCPTool(Tool):
    """Tool that wraps an MCP server endpoint."""

    mcp_server_id: str
    mcp_tool_name: str
    mcp_endpoint: Optional[str] = None

    async def execute(
        self, args: Dict[str, Any], context: ToolExecutionContext
    ) -> ToolResult:
        """Execute via MCP protocol.

        Args:
            args: Tool arguments
            context: Execution context

        Returns:
            ToolResult from MCP execution
        """
        # This will be implemented to call MCP server
        # For now, return a placeholder
        return ToolResult(
            success=True,
            data={"message": f"MCP tool {self.mcp_tool_name} executed"},
            execution_time=0.1,
            tool_name=self.name,
            tool_version=self.version,
        )
