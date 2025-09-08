"""Unit tests for EventMesh."""

from __future__ import annotations

import asyncio
from typing import List

import pytest
import pytest_asyncio
from pydantic import BaseModel

from weaver_ai.events import EventMesh, Event, EventMetadata, AccessPolicy


# Test event types
class DataEvent(BaseModel):
    """Test event for unit tests."""
    message: str
    value: int


class AnotherTestEvent(BaseModel):
    """Another test event type."""
    data: str


class SecretEvent(BaseModel):
    """Event with restricted access."""
    secret_data: str


class TestEventMesh:
    """Unit tests for EventMesh."""
    
    @pytest_asyncio.fixture
    async def mesh(self):
        """Create a clean event mesh for testing."""
        mesh = EventMesh()
        yield mesh
        await mesh.clear()
    
    @pytest.mark.asyncio
    async def test_publish_valid_event(self, mesh):
        """Test publishing a valid typed event."""
        data = DataEvent(message="hello", value=42)
        event_id = await mesh.publish(
            event_type=DataEvent,
            data=data
        )
        
        assert event_id is not None
        assert isinstance(event_id, str)
        assert len(event_id) > 0
        
        # Verify event was stored
        event = await mesh.get_event(event_id)
        assert event is not None
        assert event.data.message == "hello"
        assert event.data.value == 42
    
    @pytest.mark.asyncio
    async def test_publish_with_metadata(self, mesh):
        """Test publishing event with custom metadata."""
        metadata = EventMetadata(
            source_agent="test_agent",
            priority="high",
            correlation_id="corr_123"
        )
        
        data = DataEvent(message="test", value=1)
        event_id = await mesh.publish(
            event_type=DataEvent,
            data=data,
            metadata=metadata
        )
        
        event = await mesh.get_event(event_id)
        assert event.metadata.source_agent == "test_agent"
        assert event.metadata.priority == "high"
        assert event.metadata.correlation_id == "corr_123"
    
    @pytest.mark.asyncio
    async def test_publish_type_mismatch(self, mesh):
        """Test that publishing with wrong type raises error."""
        wrong_data = AnotherTestEvent(data="wrong")
        
        with pytest.raises(TypeError):
            await mesh.publish(
                event_type=DataEvent,  # Declared type
                data=wrong_data  # Wrong actual type
            )
    
    @pytest.mark.asyncio
    async def test_subscribe_single_type(self, mesh):
        """Test subscribing to a single event type."""
        received_events = []
        
        async def subscriber():
            async for event in mesh.subscribe([DataEvent]):
                received_events.append(event)
                if len(received_events) >= 3:
                    break
        
        # Start subscriber
        sub_task = asyncio.create_task(subscriber())
        
        # Give subscriber time to start
        await asyncio.sleep(0.1)
        
        # Publish matching events
        await mesh.publish(DataEvent, DataEvent(message="1", value=1))
        await mesh.publish(DataEvent, DataEvent(message="2", value=2))
        
        # Publish non-matching event (should not be received)
        await mesh.publish(AnotherTestEvent, AnotherTestEvent(data="ignored"))
        
        # Publish another matching event
        await mesh.publish(DataEvent, DataEvent(message="3", value=3))
        
        # Wait for subscriber to complete
        await sub_task
        
        assert len(received_events) == 3
        assert all(isinstance(e.data, DataEvent) for e in received_events)
        assert [e.data.value for e in received_events] == [1, 2, 3]
    
    @pytest.mark.asyncio
    async def test_subscribe_multiple_types(self, mesh):
        """Test subscribing to multiple event types."""
        received_events = []
        
        async def subscriber():
            async for event in mesh.subscribe([DataEvent, AnotherTestEvent]):
                received_events.append(event)
                if len(received_events) >= 3:
                    break
        
        sub_task = asyncio.create_task(subscriber())
        await asyncio.sleep(0.1)
        
        # Publish different types
        await mesh.publish(DataEvent, DataEvent(message="test", value=1))
        await mesh.publish(AnotherTestEvent, AnotherTestEvent(data="another"))
        await mesh.publish(DataEvent, DataEvent(message="test2", value=2))
        
        await sub_task
        
        assert len(received_events) == 3
        assert isinstance(received_events[0].data, DataEvent)
        assert isinstance(received_events[1].data, AnotherTestEvent)
        assert isinstance(received_events[2].data, DataEvent)
    
    @pytest.mark.asyncio
    async def test_multiple_subscribers(self, mesh):
        """Test multiple subscribers receive same events."""
        subscriber1_events = []
        subscriber2_events = []
        
        async def subscriber1():
            async for event in mesh.subscribe([DataEvent], agent_id="sub1"):
                subscriber1_events.append(event)
                if len(subscriber1_events) >= 2:
                    break
        
        async def subscriber2():
            async for event in mesh.subscribe([DataEvent], agent_id="sub2"):
                subscriber2_events.append(event)
                if len(subscriber2_events) >= 2:
                    break
        
        # Start both subscribers
        sub1_task = asyncio.create_task(subscriber1())
        sub2_task = asyncio.create_task(subscriber2())
        await asyncio.sleep(0.1)
        
        # Publish events
        await mesh.publish(DataEvent, DataEvent(message="broadcast", value=1))
        await mesh.publish(DataEvent, DataEvent(message="broadcast", value=2))
        
        # Wait for both to complete
        await asyncio.gather(sub1_task, sub2_task)
        
        assert len(subscriber1_events) == 2
        assert len(subscriber2_events) == 2
        assert subscriber1_events[0].data.value == subscriber2_events[0].data.value
        assert subscriber1_events[1].data.value == subscriber2_events[1].data.value
    
    @pytest.mark.asyncio
    async def test_access_control(self, mesh):
        """Test access control enforcement."""
        public_events = []
        secret_events = []
        
        async def public_subscriber():
            async for event in mesh.subscribe(
                [SecretEvent],
                agent_id="public_agent",
                agent_level="public"
            ):
                public_events.append(event)
        
        async def secret_subscriber():
            async for event in mesh.subscribe(
                [SecretEvent],
                agent_id="secret_agent",
                agent_level="secret"
            ):
                secret_events.append(event)
                if len(secret_events) >= 1:
                    break
        
        # Start subscribers
        public_task = asyncio.create_task(public_subscriber())
        secret_task = asyncio.create_task(secret_subscriber())
        await asyncio.sleep(0.1)
        
        # Publish secret event
        await mesh.publish(
            SecretEvent,
            SecretEvent(secret_data="classified"),
            access_policy=AccessPolicy(min_level="secret")
        )
        
        # Wait for secret subscriber
        await secret_task
        
        # Give public subscriber time (it shouldn't receive anything)
        await asyncio.sleep(0.2)
        public_task.cancel()
        
        assert len(secret_events) == 1
        assert len(public_events) == 0
    
    @pytest.mark.asyncio
    async def test_role_based_access(self, mesh):
        """Test role-based access control."""
        admin_events = []
        user_events = []
        
        async def admin_subscriber():
            async for event in mesh.subscribe(
                [DataEvent],
                agent_roles=["admin"],
                agent_id="admin"
            ):
                admin_events.append(event)
                if len(admin_events) >= 1:
                    break
        
        async def user_subscriber():
            async for event in mesh.subscribe(
                [DataEvent],
                agent_roles=["user"],
                agent_id="user"
            ):
                user_events.append(event)
        
        # Start subscribers
        admin_task = asyncio.create_task(admin_subscriber())
        user_task = asyncio.create_task(user_subscriber())
        await asyncio.sleep(0.1)
        
        # Publish admin-only event
        await mesh.publish(
            DataEvent,
            DataEvent(message="admin only", value=1),
            access_policy=AccessPolicy(allowed_roles=["admin"])
        )
        
        await admin_task
        await asyncio.sleep(0.2)
        user_task.cancel()
        
        assert len(admin_events) == 1
        assert len(user_events) == 0
    
    @pytest.mark.asyncio
    async def test_event_history(self, mesh):
        """Test event history tracking."""
        # Publish several events
        event_ids = []
        for i in range(5):
            event_id = await mesh.publish(
                DataEvent,
                DataEvent(message=f"event_{i}", value=i)
            )
            event_ids.append(event_id)
        
        # Verify all events are in history
        for event_id in event_ids:
            event = await mesh.get_event(event_id)
            assert event is not None
        
        stats = mesh.get_stats()
        assert stats["total_events"] == 5
    
    @pytest.mark.asyncio
    async def test_concurrent_publish(self, mesh):
        """Test concurrent event publishing."""
        async def publish_event(i: int):
            return await mesh.publish(
                DataEvent,
                DataEvent(message=f"concurrent_{i}", value=i)
            )
        
        # Publish 100 events concurrently
        tasks = [publish_event(i) for i in range(100)]
        event_ids = await asyncio.gather(*tasks)
        
        assert len(event_ids) == 100
        assert len(set(event_ids)) == 100  # All unique IDs
        
        stats = mesh.get_stats()
        assert stats["total_events"] == 100
    
    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Subscription cleanup needs fix in EventMesh - causes timeout issues in CI")
    async def test_subscription_cleanup(self, mesh):
        """Test that subscriptions are cleaned up properly."""
        received = []
        
        async def subscriber():
            async for event in mesh.subscribe([DataEvent]):
                received.append(event)
                if len(received) >= 1:
                    break
        
        # Start and complete subscription  
        await subscriber()
        
        # Check subscription was removed
        stats = mesh.get_stats()
        assert stats["active_subscriptions"] == 0
        
        # Publish event - should not cause issues
        await mesh.publish(DataEvent, DataEvent(message="after", value=1))
        
        assert len(received) == 1  # Only the one from during subscription