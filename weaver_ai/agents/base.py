"""Base agent class with memory and capability support."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from weaver_ai.events import Event, EventMetadata
from weaver_ai.mcp import MCPClient
from weaver_ai.memory import AgentMemory, MemoryStrategy
from weaver_ai.models import ModelRouter
from weaver_ai.redis import RedisAgentRegistry, RedisEventMesh, WorkQueue
from weaver_ai.redis.queue import Task
from weaver_ai.redis.registry import AgentInfo
from weaver_ai.tools import ToolExecutionContext, ToolRegistry


class Result(BaseModel):
    """Result from agent processing."""

    success: bool
    data: Any
    error: str | None = None
    next_capabilities: list[str] = []
    workflow_id: str | None = None


class BaseAgent(BaseModel):
    """Base agent with memory, capabilities, and Redis communication.

    Agents subscribe to Redis channels based on their capabilities and
    publish results for other agents to pick up.
    """

    # Identity
    agent_id: str = Field(default_factory=lambda: uuid4().hex)
    agent_type: str = "base"
    version: str = "1.0.0"

    # Capabilities
    capabilities: list[str] = []
    capability_constraints: dict[str, Any] = {}

    # Memory configuration
    memory_strategy: MemoryStrategy = Field(default_factory=MemoryStrategy)
    memory: AgentMemory | None = None

    # Runtime connections (excluded from serialization)
    mesh: RedisEventMesh | None = Field(None, exclude=True)
    model_router: ModelRouter | None = Field(None, exclude=True)
    registry: RedisAgentRegistry | None = Field(None, exclude=True)
    work_queue: WorkQueue | None = Field(None, exclude=True)

    # MCP Tool support
    mcp_client: MCPClient | None = Field(None, exclude=True)
    tool_registry: ToolRegistry | None = Field(None, exclude=True)
    available_tools: list[str] = Field(default_factory=list)
    tool_permissions: dict[str, bool] = Field(default_factory=dict)

    # State
    _running: bool = False
    _tasks: list[asyncio.Task] = []

    class Config:
        arbitrary_types_allowed = True

    async def initialize(
        self,
        redis_url: str = "redis://localhost:6379",
        model_router: ModelRouter | None = None,
        mcp_client: MCPClient | None = None,
        tool_registry: ToolRegistry | None = None,
    ):
        """Initialize agent connections and memory.

        Args:
            redis_url: Redis connection URL
            model_router: Optional model router for LLM access
            mcp_client: Optional MCP client for tool access
            tool_registry: Optional tool registry
        """
        # Setup Redis connections
        self.mesh = RedisEventMesh(redis_url)
        await self.mesh.connect()

        import redis.asyncio as aioredis

        redis_client = await aioredis.from_url(redis_url, decode_responses=True)

        self.registry = RedisAgentRegistry(redis_client)
        self.work_queue = WorkQueue(redis_client)

        # Setup model router
        self.model_router = model_router

        # Setup MCP and tools
        self.mcp_client = mcp_client
        self.tool_registry = tool_registry

        # Auto-discover available tools based on capabilities
        if self.tool_registry:
            await self._discover_tools()

        # Initialize memory
        self.memory = AgentMemory(
            strategy=self.memory_strategy,
            agent_id=self.agent_id,
            redis_client=redis_client,
        )
        await self.memory.initialize()

        # Register with registry
        await self._register()

    async def _register(self):
        """Register agent with registry."""
        if self.registry:
            info = AgentInfo(
                agent_id=self.agent_id,
                agent_type=self.agent_type,
                capabilities=self.capabilities,
                registered_at=datetime.now(UTC),
                metadata={
                    "version": self.version,
                    "constraints": self.capability_constraints,
                },
            )
            await self.registry.register(info)

    async def start(self):
        """Start agent - subscribe to channels and process tasks."""
        if self._running:
            return

        self._running = True

        # Subscribe to capability-based channels
        patterns = []
        for capability in self.capabilities:
            patterns.append(f"tasks:{capability.replace(':', '_')}")

        if patterns and self.mesh:
            await self.mesh.subscribe(
                patterns=patterns,
                handler=self._handle_event,
                agent_id=self.agent_id,
            )

        # Start heartbeat task
        self._tasks.append(asyncio.create_task(self._heartbeat_loop()))

        # Start work queue processor
        self._tasks.append(asyncio.create_task(self._process_queue()))

    async def stop(self):
        """Stop agent and cleanup."""
        self._running = False

        # Cancel tasks
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()

        # Unregister
        if self.registry:
            await self.registry.unregister(self.agent_id)

        # Disconnect
        if self.mesh:
            await self.mesh.disconnect()

        # Save memory
        if self.memory:
            await self.memory.persist()

    async def cleanup(self):
        """Cleanup alias for stop (for test compatibility)."""
        await self.stop()

    async def _heartbeat_loop(self):
        """Send periodic heartbeats."""
        while self._running:
            if self.registry:
                await self.registry.heartbeat(self.agent_id)
            await asyncio.sleep(15)  # Every 15 seconds

    async def _process_queue(self):
        """Process tasks from work queue."""
        if not self.work_queue:
            return

        # Queue names based on capabilities
        queue_names = [f"queue:{cap.replace(':', '_')}" for cap in self.capabilities]

        while self._running:
            try:
                # Pop task from queue
                task = await self.work_queue.pop_task(
                    queue_names=queue_names,
                    block=False,  # Non-blocking to allow shutdown
                )

                if task:
                    await self._process_task(task)
                else:
                    # No task available, wait a bit
                    await asyncio.sleep(0.5)

            except Exception as e:
                print(f"Error processing queue: {e}")
                await asyncio.sleep(1)

    async def _process_task(self, task: Task):
        """Process a task from the queue.

        Args:
            task: Task to process
        """
        try:
            # Create event from task - convert BaseModel to dict
            event = Event(
                event_type="Task",
                data=task.model_dump() if isinstance(task, BaseModel) else task,
                metadata=EventMetadata(
                    metadata={
                        "task_id": task.task_id,
                        "workflow_id": task.workflow_id,
                    }
                ),
            )

            # Process
            result = await self.process(event)

            # Publish result
            if self.mesh and result.success:
                # Determine next channel
                if result.next_capabilities:
                    for capability in result.next_capabilities:
                        await self.mesh.publish_task(
                            capability=capability,
                            task=result.data,
                            workflow_id=task.workflow_id,
                        )
                else:
                    # Publish as general result
                    await self.mesh.publish(
                        channel=f"results:{self.agent_type}",
                        data=result,
                    )

        except Exception as e:
            # Requeue on failure
            if self.work_queue:
                await self.work_queue.requeue_task(
                    task=task,
                    delay_seconds=5,
                )
            print(f"Error processing task {task.task_id}: {e}")

    async def _handle_event(self, event: Event):
        """Handle event from subscription.

        Args:
            event: Received event
        """
        try:
            result = await self.process(event)

            # Publish result if successful
            if self.mesh and result.success:
                await self._publish_result(result, event)

        except Exception as e:
            print(f"Error handling event: {e}")

    async def _publish_result(self, result: Result, source_event: Event):
        """Publish processing result.

        Args:
            result: Processing result
            source_event: Original event that triggered processing
        """
        if not self.mesh:
            return

        # Determine channel based on next capabilities
        if result.next_capabilities:
            # Publish tasks for next agents
            for capability in result.next_capabilities:
                await self.mesh.publish_task(
                    capability=capability,
                    task=result.data,
                    workflow_id=result.workflow_id or source_event.metadata.workflow_id,
                )
        else:
            # Workflow complete - publish to workflow response channel
            workflow_id = result.workflow_id or source_event.metadata.workflow_id

            # Create metadata with workflow_id for routing
            result_metadata = EventMetadata(
                workflow_id=workflow_id,
                correlation_id=source_event.metadata.correlation_id,
                parent_event_id=source_event.metadata.event_id,
            )

            # Publish to workflow-specific response channel for direct subscribers
            if workflow_id:
                await self.mesh.publish(
                    channel=f"workflow:{workflow_id}:response",
                    data=result,
                    metadata=result_metadata,
                )

            # Also publish to agent-type or A2A results channel for routers/monitors
            if source_event.event_type == "A2ATask":
                # Publish to A2A results channel for router
                channel = "a2a_results"
            else:
                # Publish to regular results channel
                channel = f"results:{self.agent_type}"

            await self.mesh.publish(
                channel=channel,
                data=result,
                metadata=result_metadata,
            )

    async def process(self, event: Event) -> Result:
        """Process an event - override in subclasses.

        Args:
            event: Event to process

        Returns:
            Processing result
        """
        raise NotImplementedError("Subclasses must implement process()")

    async def _discover_tools(self) -> None:
        """Discover available tools based on agent capabilities."""
        if not self.tool_registry:
            return

        from ..tools import ToolCapability

        # Map agent capabilities to tool capabilities
        capability_mapping = {
            "research": [ToolCapability.WEB_SEARCH, ToolCapability.DOCUMENTATION],
            "analysis": [ToolCapability.ANALYSIS, ToolCapability.COMPUTATION],
            "data": [ToolCapability.DATABASE, ToolCapability.FILE_SYSTEM],
            "integration": [ToolCapability.API_CALL],
            "coding": [ToolCapability.CODE_EXECUTION],
        }

        discovered_tools = set()

        # Find tools matching agent capabilities
        for agent_cap in self.capabilities:
            if agent_cap in capability_mapping:
                for tool_cap in capability_mapping[agent_cap]:
                    tools = self.tool_registry.get_tools_by_capability(tool_cap)
                    for tool in tools:
                        discovered_tools.add(tool.name)
                        self.tool_permissions[tool.name] = True

        self.available_tools = list(discovered_tools)

    async def execute_tool(
        self,
        tool_name: str,
        args: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a tool by name.

        Args:
            tool_name: Name of the tool to execute
            args: Tool arguments
            context: Optional execution context

        Returns:
            Tool execution result
        """
        if not self.tool_registry:
            return {"error": "No tool registry available"}

        if tool_name not in self.available_tools:
            return {"error": f"Tool {tool_name} not available"}

        if not self.tool_permissions.get(tool_name, False):
            return {"error": f"No permission to use tool {tool_name}"}

        # Create execution context
        exec_context = ToolExecutionContext(
            agent_id=self.agent_id,
            workflow_id=context.get("workflow_id") if context else None,
            user_id=context.get("user_id", "system") if context else "system",
            metadata=context or {},
        )

        # Execute tool
        result = await self.tool_registry.execute_tool(
            tool_name=tool_name,
            args=args,
            context=exec_context,
            check_permissions=True,
        )

        # Store in memory if successful
        if self.memory and result.success:
            # Note: add_tool_usage doesn't exist in AgentMemory yet
            # We'll need to add it or use existing memory methods
            await self.memory.add_event(
                Event(
                    event_type="tool_execution",
                    data={
                        "tool_name": tool_name,
                        "args": args,
                        "result": result.data,
                    },
                    metadata=EventMetadata(
                        metadata={"tool_execution_time": result.execution_time}
                    ),
                )
            )

        return result.model_dump()

    async def can_process(self, event: Event) -> bool:
        """Check if agent can handle this event.

        Args:
            event: Event to check

        Returns:
            True if agent can process
        """
        # Check if event type matches capabilities
        # event.event_type is now a string
        event_type_name = event.event_type.lower()

        for capability in self.capabilities:
            capability_lower = capability.lower()
            if ":" in capability_lower:
                # For action:subject format, match more precisely
                # Convert TestData -> test:data
                # This ensures test:data matches TestData but not OtherData
                action, subject = capability_lower.split(":", 1)
                # Check if event type name contains both parts
                # TestData -> testdata should match test:data
                # OtherData -> otherdata should NOT match test:data
                expected_name = (action + subject).lower()
                if event_type_name == expected_name:
                    return True
            elif capability_lower in event_type_name:
                return True

        return False
