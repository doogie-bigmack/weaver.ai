#!/usr/bin/env python3
"""
Direct Redis test for multi-agent orchestration.

This bypasses the A2A HTTP layer and directly publishes to Redis channels
to test the agent-to-agent workflow.
"""

import asyncio
import json
from datetime import UTC, datetime
from uuid import uuid4

import redis.asyncio as aioredis


async def test_orchestrator_workflow():
    """Test the orchestrator -> search -> summarizer workflow."""
    print("=" * 60)
    print("Multi-Agent Workflow Test (Direct Redis)")
    print("=" * 60)
    print()

    # Connect to Redis
    redis_client = await aioredis.from_url(
        "redis://localhost:6381", decode_responses=True
    )

    workflow_id = uuid4().hex
    print(f"Workflow ID: {workflow_id}")
    print()

    # Create an event for the orchestrator
    current_year = datetime.now(UTC).year
    event_data = {
        "event_id": uuid4().hex,
        "event_type": "A2ATask",
        "workflow_id": workflow_id,
        "capability": "orchestration",
        "data": {
            "workflow_type": "research",
            "query": f"artificial intelligence trends {current_year}",
        },
        "metadata": {
            "workflow_id": workflow_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "source": "test-client",
        },
    }

    print("Step 1: Publishing to orchestrator...")
    print("Channel: tasks:orchestration")
    print(f"Query: {event_data['data']['query']}")
    print()

    # Publish to orchestrator channel
    await redis_client.publish("tasks:orchestration", json.dumps(event_data))

    print("✓ Message published to orchestrator")
    print()
    print("Monitoring workflow...")
    print("(The agents will process in sequence)")
    print()

    # Subscribe to workflow responses
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(f"workflow:{workflow_id}:response")

    print("Listening for workflow completion...")
    print("(This may take 5-10 seconds depending on the model)")
    print()

    # Wait for final response (timeout after 30 seconds)
    timeout = 30
    start_time = asyncio.get_event_loop().time()

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                result = json.loads(message["data"])

                print("✓ Workflow completed!")
                print()
                print("Final Result:")
                print("-" * 60)

                if isinstance(result, dict):
                    if "summary" in result:
                        print(f"Summary: {result['summary']}")
                        print(f"Sources: {result.get('source_count', 0)}")
                    else:
                        print(json.dumps(result, indent=2))
                else:
                    print(result)

                break

            # Check timeout
            if asyncio.get_event_loop().time() - start_time > timeout:
                print(f"⚠️  Timeout after {timeout}s - workflow may still be processing")
                break

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    finally:
        await pubsub.unsubscribe()
        await redis_client.close()

    print()
    print("=" * 60)
    print("Test complete!")
    print("=" * 60)


async def check_agents_registered():
    """Check which agents are registered in Redis."""
    print("=" * 60)
    print("Registered Agents")
    print("=" * 60)
    print()

    redis_client = await aioredis.from_url(
        "redis://localhost:6381", decode_responses=True
    )

    # Check for agent registrations
    agent_keys = await redis_client.keys("agents:*")

    if agent_keys:
        print(f"Found {len(agent_keys)} registered agents:")
        for key in agent_keys:
            agent_data = await redis_client.get(key)
            if agent_data:
                agent_info = json.loads(agent_data)
                print(f"\n  Agent: {agent_info.get('agent_id', 'unknown')}")
                print(f"  Type: {agent_info.get('agent_type', 'unknown')}")
                print(
                    f"  Capabilities: {', '.join(agent_info.get('capabilities', []))}"
                )
    else:
        print("No agents registered yet")
        print("(Agents register on startup)")

    await redis_client.close()
    print()


async def main():
    """Run tests."""
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--check-agents":
        await check_agents_registered()
    else:
        print()
        print("Note: This test requires all agents to be running:")
        print("  docker-compose -f docker-compose.multi-agent.yml ps")
        print()
        print("Starting workflow test in 2 seconds...")
        await asyncio.sleep(2)
        print()

        await test_orchestrator_workflow()


if __name__ == "__main__":
    asyncio.run(main())
