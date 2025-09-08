#!/usr/bin/env python3
"""Demo script for Phase 3: Pydantic Agent Framework with Redis pub/sub.

This demo shows:
1. Multiple agents with different memory strategies
2. Redis-based pub/sub communication
3. Emergent workflow through capability matching
4. Memory persistence across agent restarts
"""

import asyncio
import sys
from datetime import datetime

from example_agents import (
    AnalysisResult,
    DataAnalystAgent,
    EchoAgent,
    Report,
    ReportGeneratorAgent,
    SalesData,
    ValidatorAgent,
    WorkflowCoordinatorAgent,
)
from weaver_ai.events import Event, EventMetadata
from weaver_ai.models import MockAdapter, ModelRouter
from weaver_ai.redis import RedisEventMesh


async def setup_agents(redis_url: str = "redis://localhost:6379"):
    """Setup and initialize agents.
    
    Returns:
        Tuple of (agents, mesh)
    """
    print("🚀 Setting up agents...")
    
    # Create model router with mock adapter
    router = ModelRouter()
    router.register_adapter("mock", MockAdapter())
    router.set_default("mock")
    
    # Create agents
    analyst = DataAnalystAgent()
    validator = ValidatorAgent()
    reporter = ReportGeneratorAgent()
    coordinator = WorkflowCoordinatorAgent()
    echo = EchoAgent()
    
    # Initialize all agents
    agents = [analyst, validator, reporter, coordinator, echo]
    for agent in agents:
        await agent.initialize(redis_url=redis_url, model_router=router)
        print(f"  ✅ Initialized {agent.agent_type} agent: {agent.agent_id[:8]}...")
    
    # Create shared mesh for direct publishing
    mesh = RedisEventMesh(redis_url)
    await mesh.connect()
    
    return agents, mesh


async def demonstrate_workflow(agents, mesh):
    """Demonstrate a complete workflow."""
    print("\n📊 Starting Sales Analysis Workflow")
    print("=" * 50)
    
    # Start all agents
    for agent in agents:
        await agent.start()
    print("  ✅ All agents started and listening")
    
    # Create sample sales data
    sales_data = SalesData(
        period="Q4 2024",
        revenue=2500000.00,
        units_sold=12500,
        region="North America",
        products=["CloudSync Pro", "DataVault Enterprise", "Analytics Suite"]
    )
    
    print(f"\n📥 Publishing sales data for {sales_data.period}")
    print(f"  Revenue: ${sales_data.revenue:,.2f}")
    print(f"  Units: {sales_data.units_sold:,}")
    
    # Publish initial task for coordinator
    workflow_id = await mesh.publish_task(
        capability="coordinate:workflow",
        task=sales_data,
        priority=1,
        workflow_id="demo_workflow_001"
    )
    
    print(f"  ✅ Published to coordinator (workflow: {workflow_id})")
    
    # Also publish directly for analysis
    await asyncio.sleep(1)  # Give coordinator time to start
    
    await mesh.publish_task(
        capability="analyze:sales",
        task=sales_data,
        priority=1,
        workflow_id=workflow_id
    )
    
    print("  ✅ Published to analyst")
    
    # Wait for processing
    print("\n⏳ Processing workflow...")
    await asyncio.sleep(3)
    
    # Check agent memories
    print("\n🧠 Checking Agent Memories:")
    print("-" * 40)
    
    for agent in agents:
        if agent.memory:
            memories = await agent.memory.recall(limit=3)
            if memories:
                print(f"\n{agent.agent_type.capitalize()} Agent Memory:")
                for mem in memories:
                    print(f"  • {mem.key}: {mem.memory_type} (importance: {mem.importance})")


async def demonstrate_memory_persistence(agents):
    """Demonstrate memory persistence across restarts."""
    print("\n💾 Testing Memory Persistence")
    print("=" * 50)
    
    # Store something in analyst's memory
    analyst = agents[0]
    test_key = "important_pattern"
    test_value = {
        "pattern": "Q4 sales spike",
        "confidence": 0.95,
        "occurrences": 3
    }
    
    print(f"  Storing pattern in analyst's memory: {test_key}")
    await analyst.memory.remember(
        key=test_key,
        value=test_value,
        memory_type="semantic",
        importance=1.0
    )
    
    # Persist memory
    await analyst.memory.persist()
    print("  ✅ Memory persisted to Redis")
    
    # Simulate restart - clear memory
    analyst.memory.clear()
    print("  🔄 Simulated restart - memory cleared")
    
    # Restore memory
    await analyst.memory.restore()
    print("  ✅ Memory restored from Redis")
    
    # Check if pattern is still there
    recalled = await analyst.memory.recall(query="pattern", memory_types=["semantic"])
    if recalled and any(test_key in r.key for r in recalled):
        print(f"  ✅ Pattern successfully recovered: {test_key}")
    else:
        print("  ❌ Pattern not found after restore")


async def demonstrate_pubsub_communication(mesh):
    """Demonstrate direct pub/sub communication."""
    print("\n📡 Testing Redis Pub/Sub Communication")
    print("=" * 50)
    
    # Subscribe to results channel
    received_events = []
    
    async def handler(event: Event):
        received_events.append(event)
        print(f"  📨 Received: {event.event_type} - {event.metadata.event_id[:8]}...")
    
    # Subscribe to multiple patterns
    await mesh.subscribe(
        patterns=["results:*", "channel:test"],
        handler=handler,
        agent_id="demo_subscriber"
    )
    
    print("  ✅ Subscribed to results:* and channel:test")
    
    # Publish test events
    event_id1 = await mesh.publish(
        channel="results:test",
        data={"message": "Test result 1"},
    )
    print(f"  📤 Published to results:test: {event_id1[:8]}...")
    
    event_id2 = await mesh.publish(
        channel="channel:test",
        data={"message": "Test message 2"},
    )
    print(f"  📤 Published to channel:test: {event_id2[:8]}...")
    
    # Wait for messages
    await asyncio.sleep(1)
    
    print(f"  ✅ Received {len(received_events)} events via pub/sub")


async def check_registry_stats(agents):
    """Check agent registry statistics."""
    print("\n📊 Agent Registry Statistics")
    print("=" * 50)
    
    if agents and agents[0].registry:
        stats = await agents[0].registry.get_stats()
        
        print(f"  Total agents: {stats['total_agents']}")
        print(f"  Online agents: {stats['online_agents']}")
        print(f"  Offline agents: {stats['offline_agents']}")
        
        if stats['capabilities']:
            print("\n  Capabilities:")
            for cap, count in stats['capabilities'].items():
                print(f"    • {cap}: {count} agents")


async def main():
    """Run the complete demo."""
    print("=" * 60)
    print("  Phase 3: Redis-based Multi-Agent Framework Demo")
    print("=" * 60)
    
    # Check Redis connection
    redis_url = "redis://localhost:6379"
    
    try:
        import redis.asyncio as aioredis
        redis = await aioredis.from_url(redis_url)
        await redis.ping()
        print(f"✅ Redis connected at {redis_url}")
        await redis.close()
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        print("\nPlease ensure Redis is running:")
        print("  docker run -d -p 6379:6379 redis:latest")
        sys.exit(1)
    
    try:
        # Setup agents
        agents, mesh = await setup_agents(redis_url)
        
        # Run demonstrations
        await demonstrate_pubsub_communication(mesh)
        await demonstrate_workflow(agents, mesh)
        await demonstrate_memory_persistence(agents)
        await check_registry_stats(agents)
        
        print("\n✨ Demo completed successfully!")
        
    except KeyboardInterrupt:
        print("\n⚠️ Demo interrupted")
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        print("\n🧹 Cleaning up...")
        for agent in agents:
            await agent.stop()
        await mesh.disconnect()
        print("  ✅ All agents stopped")


if __name__ == "__main__":
    asyncio.run(main())