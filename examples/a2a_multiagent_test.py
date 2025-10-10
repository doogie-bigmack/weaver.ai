#!/usr/bin/env python3
"""
Test client for multi-agent A2A orchestration.

This demonstrates:
- Sending workflow requests to orchestrator
- Automatic agent chaining (orchestrator -> search -> summarizer)
- Secure A2A communication with RSA signatures
- MCP tool usage across agents
"""

import argparse
import asyncio
from pathlib import Path

from weaver_ai.a2a import Budget
from weaver_ai.a2a_client import A2AClient


async def test_research_workflow(endpoint: str):
    """Test multi-agent research workflow.

    Workflow: Orchestrator -> Search Agent -> Summarizer Agent

    Args:
        endpoint: Gateway endpoint URL
    """
    print("=" * 60)
    print("Multi-Agent A2A Research Workflow Test")
    print("=" * 60)
    print()

    # Load keys
    keys_dir = Path("keys")
    private_key_path = keys_dir / "instance_b_private.pem"
    public_key_path = keys_dir / "instance_b_public.pem"
    receiver_public_key_path = keys_dir / "instance_a_public.pem"

    print(f"Using test keys from {private_key_path}")
    private_key = private_key_path.read_text()
    public_key = public_key_path.read_text()
    receiver_public_key = receiver_public_key_path.read_text()
    print()

    # Create A2A client
    client = A2AClient(
        sender_id="test-client",
        private_key=private_key,
        public_key=public_key,
        timeout=30.0,
    )

    # Register receiver's public key
    client.register_remote_agent("weaver-ai-agent", receiver_public_key)
    print("✓ Registered receiver's public key")
    print()

    # Test workflows
    test_cases = [
        {
            "name": "AI Research",
            "query": "artificial intelligence",
        },
        {
            "name": "Climate Change",
            "query": "climate change solutions",
        },
    ]

    for test_case in test_cases:
        print(f"Test: {test_case['name']}")
        print("-" * 60)

        try:
            # Send workflow request to orchestrator
            response = await client.send_message(
                endpoint=endpoint,
                receiver_id="weaver-ai-agent",
                capability="orchestration",
                payload={
                    "workflow_type": "research",
                    "query": test_case["query"],
                },
                budget=Budget(
                    tokens=4000,
                    time_ms=30000,  # 30 second timeout
                    tool_calls=10,
                ),
            )

            if response.success:
                print(
                    f"✓ Workflow completed! (took {response.execution_time_ms:.0f}ms)"
                )
                print()

                # Extract summary from final result
                if isinstance(response.data, dict):
                    if "summary" in response.data:
                        print("Summary:")
                        print(response.data["summary"])
                        print()
                        print(
                            f"Based on {response.data.get('source_count', 0)} sources"
                        )
                    elif "status" in response.data:
                        print(f"Status: {response.data['status']}")
                        print(f"Workflow ID: {response.data.get('workflow_id', 'N/A')}")
                    else:
                        print("Response data:")
                        print(response.data)
                else:
                    print("Response:", response.data)
            else:
                print(f"✗ Failed: {response.error}")

        except Exception as e:
            print(f"✗ Error: {e}")

        print()

    # Test agent card
    print("Test: Fetch Agent Card")
    print("-" * 60)
    try:
        card = await client.get_agent_card(endpoint)
        if card:
            print("✓ Agent card retrieved:")
            print(f"  Agent ID: {card.get('agent_id')}")
            print(f"  Name: {card.get('name')}")
            print(f"  Version: {card.get('version')}")
            print(f"  Capabilities: {len(card.get('capabilities', []))}")
        else:
            print("✗ Failed to fetch agent card")
    except Exception as e:
        print(f"✗ Error: {e}")

    print()
    print("=" * 60)
    print("Multi-agent test complete!")
    print("=" * 60)


async def main():
    """Run multi-agent test."""
    parser = argparse.ArgumentParser(description="Test multi-agent A2A orchestration")
    parser.add_argument(
        "--endpoint",
        default="http://localhost:8005",
        help="Gateway endpoint (default: http://localhost:8005)",
    )

    args = parser.parse_args()

    print()
    print("Multi-Agent Workflow Architecture:")
    print("  1. Test Client -> Gateway (A2A)")
    print("  2. Gateway -> Orchestrator Agent (Redis)")
    print("  3. Orchestrator -> Search Agent (Redis, uses MCP tools)")
    print("  4. Search Agent -> Summarizer Agent (Redis)")
    print("  5. Summarizer -> Gateway -> Test Client")
    print()

    await test_research_workflow(args.endpoint)


if __name__ == "__main__":
    asyncio.run(main())
