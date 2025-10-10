#!/usr/bin/env python3
"""
Test client for A2A communication.

This script demonstrates sending A2A messages to remote agents.

Usage:
    # Test with default settings
    python examples/a2a_test_client.py

    # Test with custom endpoint
    python examples/a2a_test_client.py --endpoint http://localhost:8001

    # Test with ngrok
    python examples/a2a_test_client.py --endpoint https://abc123.ngrok.io
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from weaver_ai.a2a import Budget
from weaver_ai.a2a_client import A2AClient


async def test_translation(
    endpoint: str,
    sender_id: str,
    private_key: str,
    public_key: str,
    receiver_public_key: str | None = None,
):
    """Test translation via A2A.

    Args:
        endpoint: Remote agent endpoint
        sender_id: Your agent ID
        private_key: Your private key (PEM)
        public_key: Your public key (PEM)
        receiver_public_key: Receiver's public key for verification
    """
    print("=" * 60)
    print("A2A Translation Test")
    print("=" * 60)
    print(f"Endpoint: {endpoint}")
    print(f"Sender ID: {sender_id}")
    print("=" * 60)
    print()

    # Create client
    client = A2AClient(
        sender_id=sender_id,
        private_key=private_key,
        public_key=public_key,
        timeout=10.0,
    )

    # Register receiver's public key if provided
    if receiver_public_key:
        client.register_remote_agent("translator-agent", receiver_public_key)
        print("✓ Registered receiver's public key")
    else:
        print("⚠ No receiver public key provided (response won't be verified)")

    print()

    # Test 1: Simple translation
    print("Test 1: Simple translation")
    print("-" * 60)

    try:
        result = await client.send_message(
            endpoint=endpoint,
            receiver_id="translator-agent",
            capability="translation:en-es",
            payload={"text": "Hello, world!"},
            budget=Budget(tokens=1000, time_ms=5000, tool_calls=1),
        )

        if result.success:
            print(f"✓ Success! (took {result.execution_time_ms:.0f}ms)")
            print(f"  Original: {result.data.get('original')}")
            print(f"  Translated: {result.data.get('translated')}")
        else:
            print(f"✗ Failed: {result.error}")

    except Exception as e:
        print(f"✗ Error: {e}")

    print()

    # Test 2: Longer text
    print("Test 2: Longer text translation")
    print("-" * 60)

    try:
        result = await client.send_message(
            endpoint=endpoint,
            receiver_id="translator-agent",
            capability="translation:en-es",
            payload={"text": "The quick brown fox jumps over the lazy dog"},
            budget=Budget(tokens=2000, time_ms=5000, tool_calls=1),
        )

        if result.success:
            print(f"✓ Success! (took {result.execution_time_ms:.0f}ms)")
            print(f"  Translated: {result.data.get('translated')}")
        else:
            print(f"✗ Failed: {result.error}")

    except Exception as e:
        print(f"✗ Error: {e}")

    print()

    # Test 3: Get agent card
    print("Test 3: Fetch agent card")
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
            print("✗ Failed to retrieve agent card")

    except Exception as e:
        print(f"✗ Error: {e}")

    print()
    print("=" * 60)
    print("Test complete!")
    print("=" * 60)


async def main():
    """Run A2A test client."""
    parser = argparse.ArgumentParser(description="Test A2A communication")
    parser.add_argument(
        "--endpoint",
        default="http://localhost:8001",
        help="Remote agent endpoint",
    )
    parser.add_argument(
        "--sender-id",
        default="test-client",
        help="Your agent ID",
    )
    parser.add_argument(
        "--private-key",
        help="Path to your private key file",
    )
    parser.add_argument(
        "--public-key",
        help="Path to your public key file",
    )
    parser.add_argument(
        "--receiver-public-key",
        help="Path to receiver's public key file",
    )

    args = parser.parse_args()

    # Load keys
    if args.private_key:
        private_key = Path(args.private_key).read_text()
    else:
        # Use default test keys from keys/instance_b (client keys)
        keys_dir = Path(__file__).parent.parent / "keys"
        private_key_path = keys_dir / "instance_b_private.pem"

        if private_key_path.exists():
            private_key = private_key_path.read_text()
            print("Using test keys from keys/instance_b_private.pem")
        else:
            print("ERROR: No keys found!")
            print("  Generate keys with: python scripts/generate_a2a_keys.py")
            return
        print()

    if args.public_key:
        public_key = Path(args.public_key).read_text()
    else:
        # Use default test keys from keys/instance_b (client keys)
        keys_dir = Path(__file__).parent.parent / "keys"
        public_key_path = keys_dir / "instance_b_public.pem"

        if public_key_path.exists():
            public_key = public_key_path.read_text()
        else:
            print("ERROR: No public key found!")
            print("  Generate keys with: python scripts/generate_a2a_keys.py")
            return

    receiver_public_key = None
    if args.receiver_public_key:
        receiver_public_key = Path(args.receiver_public_key).read_text()
    else:
        # Use instance_a public key (gateway/translator agent)
        keys_dir = Path(__file__).parent.parent / "keys"
        receiver_key_path = keys_dir / "instance_a_public.pem"

        if receiver_key_path.exists():
            receiver_public_key = receiver_key_path.read_text()
            print("Using receiver's public key from keys/instance_a_public.pem")
            print()

    # Run test
    await test_translation(
        endpoint=args.endpoint,
        sender_id=args.sender_id,
        private_key=private_key,
        public_key=public_key,
        receiver_public_key=receiver_public_key,
    )


if __name__ == "__main__":
    asyncio.run(main())
