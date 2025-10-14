#!/usr/bin/env python3
"""Debug script to test A2A message flow."""

import asyncio
from datetime import UTC, datetime

from weaver_ai.a2a import A2AEnvelope, Budget, Capability
from weaver_ai.a2a_router import A2ARouter
from weaver_ai.agents import BaseAgent, Result
from weaver_ai.events import Event
from weaver_ai.redis import RedisEventMesh


class DebugTranslatorAgent(BaseAgent):
    """Debug translator agent with logging."""

    agent_type: str = "translator"
    capabilities: list[str] = ["translation:en-es", "translation"]

    async def process(self, event: Event) -> Result:
        """Process translation request."""
        print("\n[AGENT] ============================================")
        print("[AGENT] Received event!")
        print(f"[AGENT] Event type: {event.event_type}")
        print(f"[AGENT] Event data type: {type(event.data)}")
        print(f"[AGENT] Event data: {event.data}")
        print(f"[AGENT] Metadata workflow_id: {event.metadata.workflow_id}")
        print("[AGENT] ============================================\n")

        # Extract text
        if isinstance(event.data, dict):
            text = event.data.get("text", "")
        else:
            text = str(event.data)

        # Mock translation
        translated = f"[ES] {text}"

        result = Result(
            success=True,
            data={"translated": translated, "original": text},
            next_capabilities=[],
            workflow_id=event.metadata.workflow_id,
        )

        print(f"[AGENT] Returning result: {result}")
        return result


async def main():
    """Run debug test."""
    print("=" * 60)
    print("A2A Debug Test")
    print("=" * 60)

    # Setup Redis mesh
    mesh = RedisEventMesh("redis://localhost:6379")
    await mesh.connect()

    # Setup router
    router = A2ARouter(mesh)
    await router.start()
    print("✓ Router started")

    # Setup agent
    agent = DebugTranslatorAgent(agent_id="debug-translator")
    await agent.initialize(redis_url="redis://localhost:6379")
    await agent.start()
    print("✓ Agent started\n")

    # Wait for agent to subscribe
    await asyncio.sleep(2)

    # Create test A2A envelope
    envelope = A2AEnvelope(
        request_id="test-123",
        sender_id="test-client",
        receiver_id="debug-translator",
        created_at=datetime.now(UTC),
        nonce="test-nonce",
        capabilities=[Capability(name="translation:en-es", version="1.0")],
        budget=Budget(tokens=1000, time_ms=10000, tool_calls=1, cost_usd=0.01),
        payload={"text": "Hello, world!"},
        signature=None,
    )

    print("[TEST] Sending A2A message...")
    print(f"[TEST] Request ID: {envelope.request_id}")
    print(f"[TEST] Capability: {envelope.capabilities[0].name}")
    print(f"[TEST] Payload: {envelope.payload}\n")

    try:
        result = await router.route_message(envelope)
        print("\n[TEST] ✓ SUCCESS!")
        print(f"[TEST] Result: {result}")
    except Exception as e:
        print("\n[TEST] ✗ FAILED!")
        print(f"[TEST] Error: {e}")
        import traceback

        traceback.print_exc()

    # Cleanup
    await agent.stop()
    await router.stop()
    await mesh.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
