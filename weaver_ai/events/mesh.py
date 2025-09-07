"""Event mesh for agent communication.

The EventMesh provides a publish-subscribe system for agents to communicate
through typed events. It supports:
- Type-safe event publishing with Pydantic models
- Multiple concurrent subscribers
- Access control based on roles and levels
- Event history tracking for debugging
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from pydantic import BaseModel

from .models import AccessPolicy, Event, EventMetadata


class EventSubscription:
    """Represents an active subscription to events.
    
    Manages the delivery of events to a specific agent based on
    event types and access policies.
    """
    
    def __init__(
        self,
        event_types: list[type[BaseModel]],
        queue: asyncio.Queue,
        agent_id: str,
        agent_roles: list[str] | None = None,
        agent_level: str = "public"
    ):
        """Initialize a subscription.
        
        Args:
            event_types: List of Pydantic model types to subscribe to
            queue: Async queue for event delivery
            agent_id: Unique identifier for the subscribing agent
            agent_roles: Roles assigned to the agent for access control
            agent_level: Access level of the agent
        """
        self.event_types = set(event_types)
        self.queue = queue
        self.agent_id = agent_id
        self.agent_roles = agent_roles or []
        self.agent_level = agent_level
        self.active = True
    
    def matches(self, event: Event) -> bool:
        """Check if this subscription should receive an event.
        
        Args:
            event: The event to check
            
        Returns:
            True if the event matches type and access requirements
        """
        # Type must match
        if type(event.data) not in self.event_types:
            return False
        
        # Access must be allowed
        if not event.access_policy.can_access(self.agent_roles, self.agent_level):
            return False
        
        return True
    
    async def deliver(self, event: Event) -> None:
        """Deliver an event to the subscriber's queue.
        
        Args:
            event: The event to deliver
        """
        if self.active:
            await self.queue.put(event)
    
    def cancel(self) -> None:
        """Cancel this subscription."""
        self.active = False


class EventMesh:
    """In-memory event mesh for agent communication.
    
    Provides a simple publish-subscribe system where agents can:
    - Publish typed events with access controls
    - Subscribe to specific event types
    - Automatically receive events they have access to
    
    This implementation uses in-memory storage and is suitable
    for single-process applications. For distributed systems,
    replace with Redis or Kafka backend.
    """
    
    def __init__(self):
        """Initialize an empty event mesh."""
        self.subscriptions: list[EventSubscription] = []
        self.event_history: list[Event] = []
        self.event_types: set[type[BaseModel]] = set()
        self._lock = asyncio.Lock()
    
    async def publish(
        self,
        event_type: type[BaseModel],
        data: BaseModel,
        metadata: EventMetadata | None = None,
        access_policy: AccessPolicy | None = None
    ) -> str:
        """Publish an event to all matching subscribers.
        
        Args:
            event_type: The Pydantic model type of the event
            data: The event data (must be instance of event_type)
            metadata: Optional event metadata
            access_policy: Optional access control policy
            
        Returns:
            The unique event ID
            
        Raises:
            TypeError: If data is not an instance of event_type
        """
        # Validate type safety
        if not isinstance(data, event_type):
            raise TypeError(f"Data must be instance of {event_type.__name__}")
        
        # Create event with defaults
        event = Event(
            data=data,
            metadata=metadata or EventMetadata(),
            access_policy=access_policy or AccessPolicy()
        )
        
        # Store event atomically
        async with self._lock:
            self.event_history.append(event)
            self.event_types.add(event_type)
        
        # Deliver to all matching subscribers
        delivery_tasks = []
        for subscription in self.subscriptions:
            if subscription.matches(event):
                delivery_tasks.append(subscription.deliver(event))
        
        if delivery_tasks:
            await asyncio.gather(*delivery_tasks, return_exceptions=True)
        
        return event.metadata.event_id
    
    async def subscribe(
        self,
        event_types: list[type[BaseModel]],
        agent_id: str = "anonymous",
        agent_roles: list[str] | None = None,
        agent_level: str = "public"
    ) -> AsyncIterator[Event]:
        """Subscribe to events of specified types.
        
        Creates an async iterator that yields events as they are published.
        The subscription is automatically cleaned up when the iterator exits.
        
        Args:
            event_types: List of Pydantic model types to subscribe to
            agent_id: Unique identifier for the subscribing agent
            agent_roles: Roles for access control
            agent_level: Access level for the agent
            
        Yields:
            Events that match the subscription criteria
        """
        queue = asyncio.Queue()
        subscription = EventSubscription(
            event_types=event_types,
            queue=queue,
            agent_id=agent_id,
            agent_roles=agent_roles,
            agent_level=agent_level
        )
        
        # Register subscription
        async with self._lock:
            self.subscriptions.append(subscription)
        
        try:
            # Yield events as they arrive
            while subscription.active:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield event
                except TimeoutError:
                    # Check if still active periodically
                    continue
        finally:
            # Clean up on exit
            subscription.cancel()
            async with self._lock:
                if subscription in self.subscriptions:
                    self.subscriptions.remove(subscription)
    
    async def get_event(self, event_id: str) -> Event | None:
        """Retrieve a specific event by ID.
        
        Args:
            event_id: The unique event identifier
            
        Returns:
            The event if found, None otherwise
        """
        async with self._lock:
            for event in self.event_history:
                if event.metadata.event_id == event_id:
                    return event
        return None
    
    async def clear(self) -> None:
        """Clear all events and subscriptions.
        
        This method is primarily for testing. In production,
        consider implementing event expiration instead.
        """
        async with self._lock:
            self.event_history.clear()
            self.subscriptions.clear()
            self.event_types.clear()
    
    def get_stats(self) -> dict[str, int]:
        """Get current mesh statistics.
        
        Returns:
            Dictionary with total_events, active_subscriptions, and registered_types
        """
        return {
            "total_events": len(self.event_history),
            "active_subscriptions": len(self.subscriptions),
            "registered_types": len(self.event_types)
        }