"""Base agent class with memory and capability support."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from weaver_ai.events import Event
from weaver_ai.memory import AgentMemory, MemoryStrategy
from weaver_ai.models import ModelRouter
from weaver_ai.redis import RedisAgentRegistry, RedisEventMesh, WorkQueue
from weaver_ai.redis.queue import Task
from weaver_ai.redis.registry import AgentInfo


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

    # State
    _running: bool = False
    _tasks: list[asyncio.Task] = []

    class Config:
        arbitrary_types_allowed = True

    async def initialize(
        self,
        redis_url: str = "redis://localhost:6379",
        model_router: ModelRouter | None = None,
    ):
        """Initialize agent connections and memory.

        Args:
            redis_url: Redis connection URL
            model_router: Optional model router for LLM access
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
            # Create event from task
            event = Event(
                event_type="Task",
                data=task,
                metadata={
                    "task_id": task.task_id,
                    "workflow_id": task.workflow_id,
                },
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
                    workflow_id=result.workflow_id
                    or source_event.metadata.get("workflow_id"),
                )
        else:
            # Publish to results channel
            channel = f"results:{self.agent_type}"
            await self.mesh.publish(
                channel=channel,
                data=result,
            )

    async def process(self, event: Event) -> Result:
        """Process an event - override in subclasses.

        Args:
            event: Event to process

        Returns:
            Processing result
        """
        raise NotImplementedError("Subclasses must implement process()")

    async def can_process(self, event: Event) -> bool:
        """Check if agent can handle this event.

        Args:
            event: Event to check

        Returns:
            True if agent can process
        """
        # Check if event type matches capabilities
        event_type = event.event_type.lower()

        for capability in self.capabilities:
            if ":" in capability:
                action, subject = capability.split(":", 1)
                if action in event_type or subject in event_type:
                    return True
            elif capability in event_type:
                return True

        return False
