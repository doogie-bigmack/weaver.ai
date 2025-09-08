"""Redis-backed event mesh for distributed agent communication."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4

import redis.asyncio as aioredis
from pydantic import BaseModel, Field

from weaver_ai.events import AccessPolicy, Event, EventMetadata


class RedisEventMesh:
    """Redis-backed event mesh for production scale agent communication.
    
    Agents publish results to Redis channels, and other agents pick them up
    based on their subscribed capabilities.
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        """Initialize Redis event mesh.
        
        Args:
            redis_url: Redis connection URL
        """
        self.redis_url = redis_url
        self.redis: aioredis.Redis | None = None
        self.pubsub: aioredis.client.PubSub | None = None
        self.subscriptions: dict[str, list[dict]] = {}
        self._listeners: dict[str, asyncio.Task] = {}
        self._connected = False
        
    async def connect(self):
        """Connect to Redis."""
        if not self._connected:
            self.redis = await aioredis.from_url(self.redis_url, decode_responses=True)
            self.pubsub = self.redis.pubsub()
            self._connected = True
            
    async def disconnect(self):
        """Disconnect from Redis."""
        if self._connected:
            # Cancel all listeners
            for task in self._listeners.values():
                task.cancel()
            self._listeners.clear()
            
            # Close pubsub
            if self.pubsub:
                await self.pubsub.close()
                
            # Close Redis connection
            if self.redis:
                await self.redis.close()
                
            self._connected = False
    
    async def publish(
        self,
        channel: str | None,
        data: BaseModel,
        event_type: type[BaseModel] | None = None,
        metadata: EventMetadata | None = None,
        ttl: int | None = None,
    ) -> str:
        """Publish event to Redis channel.
        
        Args:
            channel: Channel to publish to. If None, auto-determined from event_type
            data: Event data to publish
            event_type: Type of the event (for auto-channel determination)
            metadata: Optional event metadata
            ttl: Optional TTL in seconds for storing event
            
        Returns:
            Event ID
        """
        if not self._connected:
            await self.connect()
            
        # Auto-determine channel from event type if not specified
        if not channel:
            if event_type:
                channel = f"results:{event_type.__name__.lower()}"
            else:
                channel = f"results:{data.__class__.__name__.lower()}"
        
        # Create event metadata if not provided
        if not metadata:
            metadata = EventMetadata()
            
        # Create event
        event = Event(
            event_type=data.__class__.__name__,
            data=data,
            metadata=metadata,
        )
        
        # Publish to Redis
        await self.redis.publish(channel, event.json())
        
        # Optional: Store in Redis with TTL for late subscribers
        if ttl:
            await self.redis.setex(
                f"event:{event.metadata.event_id}",
                ttl,
                event.json(),
            )
        
        return event.metadata.event_id
    
    async def subscribe(
        self,
        patterns: list[str],
        handler: Callable[[Event], Any],
        agent_id: str | None = None,
    ):
        """Subscribe to Redis channels/patterns.
        
        Args:
            patterns: List of channel patterns to subscribe to
            handler: Async function to handle received events  
            agent_id: Optional agent ID for tracking
        """
        if not self._connected:
            await self.connect()
            
        # Convert patterns to channel patterns
        channels = []
        for pattern in patterns:
            channel = self._pattern_to_channel(pattern)
            channels.append(channel)
            
            # Track subscription
            if channel not in self.subscriptions:
                self.subscriptions[channel] = []
            self.subscriptions[channel].append({
                "handler": handler,
                "agent_id": agent_id,
                "pattern": pattern,
            })
        
        # Subscribe in Redis
        await self.pubsub.psubscribe(*channels)
        
        # Start listener if not already running
        listener_key = f"{agent_id or 'anonymous'}_{id(handler)}"
        if listener_key not in self._listeners:
            self._listeners[listener_key] = asyncio.create_task(
                self._listen(handler, agent_id)
            )
    
    async def _listen(self, handler: Callable, agent_id: str | None):
        """Listen for messages and dispatch to handler.
        
        Args:
            handler: Function to handle events
            agent_id: Optional agent ID for logging
        """
        try:
            async for message in self.pubsub.listen():
                if message["type"] in ["pmessage", "message"]:
                    try:
                        # Parse event
                        event_data = message["data"]
                        if isinstance(event_data, str):
                            event = Event.parse_raw(event_data)
                            
                            # Call handler
                            if asyncio.iscoroutinefunction(handler):
                                await handler(event)
                            else:
                                handler(event)
                    except Exception as e:
                        # Log error but continue listening
                        print(f"Error handling message for agent {agent_id}: {e}")
        except asyncio.CancelledError:
            # Clean shutdown
            pass
    
    def _pattern_to_channel(self, pattern: str) -> str:
        """Convert capability pattern to Redis channel pattern.
        
        Args:
            pattern: Capability pattern (e.g., "analyze:sales")
            
        Returns:
            Redis channel pattern
        """
        if pattern.startswith("channel:"):
            # Direct channel subscription
            return pattern[8:]
        elif pattern.startswith("results:"):
            # Results channel
            return pattern
        elif pattern.startswith("tasks:"):
            # Task channel
            return pattern
        elif ":" in pattern:
            # Capability pattern: "analyze:sales" -> "results:*sales*"
            parts = pattern.split(":", 1)
            return f"results:*{parts[1]}*"
        else:
            # Default to results channel
            return f"results:{pattern}"
    
    async def publish_task(
        self,
        capability: str,
        task: BaseModel,
        priority: int = 0,
        workflow_id: str | None = None,
    ) -> str:
        """Publish a task for agents with specific capability.
        
        Args:
            capability: Required capability
            task: Task data
            priority: Task priority (higher = more important)
            workflow_id: Optional workflow ID for tracking
            
        Returns:
            Task ID
        """
        task_id = uuid4().hex
        channel = f"tasks:{capability.replace(':', '_')}"
        
        # Add task metadata
        task_event = {
            "task_id": task_id,
            "capability": capability,
            "priority": priority,
            "workflow_id": workflow_id,
            "data": task.dict(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        # Publish to task channel
        await self.redis.publish(channel, json.dumps(task_event))
        
        # Also add to priority queue
        queue_name = f"queue:{capability.replace(':', '_')}"
        await self.redis.zadd(
            queue_name,
            {json.dumps(task_event): -priority}  # Negative for high priority first
        )
        
        return task_id
    
    async def get_stats(self) -> dict[str, Any]:
        """Get mesh statistics.
        
        Returns:
            Statistics dictionary
        """
        if not self._connected:
            return {"connected": False}
            
        # Get channel info
        channels = await self.redis.pubsub_channels()
        
        return {
            "connected": True,
            "active_channels": len(channels),
            "channels": channels,
            "subscriptions": len(self.subscriptions),
            "active_listeners": len(self._listeners),
        }