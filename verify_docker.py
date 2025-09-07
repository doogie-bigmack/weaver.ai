#!/usr/bin/env python3
"""
Quick verification that the Event Mesh works in Docker.
Run this with: docker run --rm -v $(pwd):/app python:3.12-slim python /app/verify_docker.py
"""

import asyncio
import sys
sys.path.insert(0, '/app')

from weaver_ai.events import EventMesh
from pydantic import BaseModel


class TestEvent(BaseModel):
    message: str


async def verify():
    print("🐳 Verifying Event Mesh in Docker container...")
    
    # Create mesh
    mesh = EventMesh()
    
    # Test publish
    event_id = await mesh.publish(
        TestEvent,
        TestEvent(message="Hello from Docker!")
    )
    print(f"✅ Published event: {event_id}")
    
    # Test subscribe
    received = []
    
    async def subscriber():
        async for event in mesh.subscribe([TestEvent]):
            received.append(event)
            break
    
    # Start subscriber
    sub_task = asyncio.create_task(subscriber())
    await asyncio.sleep(0.1)
    
    # Publish another event
    await mesh.publish(TestEvent, TestEvent(message="Test 2"))
    
    # Wait for subscriber
    await sub_task
    
    # Verify
    assert len(received) == 1
    assert received[0].data.message == "Test 2"
    
    print("✅ Subscription works")
    
    # Check stats
    stats = mesh.get_stats()
    print(f"✅ Stats: {stats['total_events']} events, {stats['registered_types']} types")
    
    print("\n🎉 Event Mesh verified successfully in Docker!")
    return True


if __name__ == "__main__":
    asyncio.run(verify())