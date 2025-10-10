"""A2A Router - Bridges HTTP A2A messages to Redis-based agents."""

from __future__ import annotations

import asyncio
from typing import Any

from weaver_ai.a2a import A2AEnvelope
from weaver_ai.events import Event, EventMetadata
from weaver_ai.redis import RedisEventMesh


class A2ARoutingError(Exception):
    """Error routing A2A message to agent."""

    pass


class A2ARouter:
    """Routes A2A messages from HTTP to Redis-based agents.

    This router acts as a bridge between:
    - External HTTP A2A messages (from internet)
    - Internal Redis events (to your agents)

    Workflow:
    1. Receive A2A envelope via HTTP
    2. Convert to Redis Event
    3. Publish to appropriate capability channel
    4. Wait for agent result
    5. Convert result back to A2A format
    6. Return to caller
    """

    def __init__(self, redis_mesh: RedisEventMesh):
        """Initialize A2A router.

        Args:
            redis_mesh: Redis event mesh for agent communication
        """
        self.mesh = redis_mesh
        self.pending_requests: dict[str, asyncio.Future] = {}
        self.result_channel = "a2a_results"

    async def start(self):
        """Start listening for results from agents."""
        if not self.mesh._connected:
            await self.mesh.connect()

        # Subscribe to result channel (use channel: prefix for direct subscription)
        await self.mesh.subscribe(
            patterns=[f"channel:{self.result_channel}"],
            handler=self._handle_result,
            agent_id="a2a_router",
        )

    async def stop(self):
        """Stop router and cancel pending requests."""
        # Cancel all pending requests
        for future in self.pending_requests.values():
            if not future.done():
                future.cancel()
        self.pending_requests.clear()

    async def route_message(self, envelope: A2AEnvelope) -> dict[str, Any]:
        """Route A2A message to appropriate agent via Redis.

        Args:
            envelope: A2A message envelope

        Returns:
            Result dictionary from agent

        Raises:
            A2ARoutingError: If routing fails
            asyncio.TimeoutError: If agent doesn't respond in time
        """
        # Extract capability from envelope
        if not envelope.capabilities:
            raise A2ARoutingError("No capabilities specified in A2A message")

        capability = envelope.capabilities[0].name  # Use first capability

        # Create Redis event from A2A envelope
        event = self._convert_to_event(envelope, capability)

        # Create future to wait for result
        result_future: asyncio.Future = asyncio.Future()
        self.pending_requests[envelope.request_id] = result_future

        try:
            # Publish to Redis channel for this capability
            channel = f"tasks:{capability.replace(':', '_')}"
            # Publish Event directly (not wrapping it again)
            await self.mesh.redis.publish(channel, event.model_dump_json())

            # Wait for result with timeout
            timeout_seconds = envelope.budget.time_ms / 1000.0
            result = await asyncio.wait_for(result_future, timeout=timeout_seconds)

            return result

        except TimeoutError as e:
            raise A2ARoutingError(
                f"Agent did not respond within {timeout_seconds}s timeout"
            ) from e

        except Exception as e:
            raise A2ARoutingError(f"Failed to route message: {e}") from e

        finally:
            # Cleanup
            self.pending_requests.pop(envelope.request_id, None)

    def _convert_to_event(self, envelope: A2AEnvelope, capability: str) -> Event:
        """Convert A2A envelope to Redis Event.

        Args:
            envelope: A2A envelope
            capability: Capability name

        Returns:
            Redis Event
        """
        return Event(
            event_type="A2ATask",
            data=envelope.payload,
            metadata=EventMetadata(
                event_id=envelope.request_id,
                source_agent=envelope.sender_id,
                timestamp=envelope.created_at,
                workflow_id=envelope.request_id,
                metadata={
                    "capability": capability,
                    "budget": envelope.budget.model_dump(),
                    "a2a_sender": envelope.sender_id,
                    "a2a_receiver": envelope.receiver_id,
                },
            ),
        )

    async def _handle_result(self, event: Event):
        """Handle result from agent.

        Args:
            event: Result event from agent
        """
        # Extract request ID from event metadata
        request_id = event.metadata.workflow_id

        if not request_id:
            # No workflow ID, can't match to request
            return

        # Find pending request
        future = self.pending_requests.get(request_id)
        if not future or future.done():
            return

        # Resolve future with result
        try:
            # Extract result data from event
            if hasattr(event.data, "model_dump"):
                result_data = event.data.model_dump()
            elif isinstance(event.data, dict):
                result_data = event.data
            else:
                result_data = {"result": str(event.data)}

            future.set_result(result_data)

        except Exception as e:
            future.set_exception(e)

    async def get_available_capabilities(self) -> list[str]:
        """Get list of available capabilities from registered agents.

        Returns:
            List of capability names
        """
        # This would query the Redis agent registry
        # For now, return empty list (to be implemented)
        return []
