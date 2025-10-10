#!/usr/bin/env python3
"""
Simple translator agent for A2A testing.

This agent demonstrates:
- Subscribing to capability-based Redis channels
- Processing A2A tasks
- Returning results via Redis

Usage:
    python examples/a2a_translator_agent.py --port 8001
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from weaver_ai.agents import BaseAgent, Result
from weaver_ai.events import Event


class TranslatorAgent(BaseAgent):
    """Simple English to Spanish translator agent."""

    agent_type: str = "translator"
    capabilities: list[str] = ["translation:en-es", "translation"]

    async def process(self, event: Event) -> Result:
        """Process translation request.

        Args:
            event: Event containing text to translate

        Returns:
            Result with translated text
        """
        print("[Translator] Received translation request")
        print(f"[Translator] Event type: {event.event_type}")
        print(f"[Translator] Event data: {event.data}")

        # Extract text from event data
        if isinstance(event.data, dict):
            text = event.data.get("text", "")
        else:
            text = str(event.data)

        print(f"[Translator] Translating: {text}")

        # Real translation using LLM
        if self.model_router:
            try:
                # Use LLM for actual translation
                prompt = (
                    f"Translate the following English text to Spanish. "
                    f"Only return the Spanish translation, nothing else:\n\n{text}"
                )
                response = await self.model_router.generate(prompt=prompt)
                translated = response.text.strip()
            except Exception as e:
                print(f"[Translator] LLM translation failed: {e}, falling back to mock")
                translated = f"[ES] {text}"
        else:
            # Mock translation (prepend [ES]) if no model router available
            translated = f"[ES] {text}"

        print(f"[Translator] Translation complete: {translated}")

        # Return result
        return Result(
            success=True,
            data={"translated": translated, "original": text},
            next_capabilities=[],  # No next capabilities (end of workflow)
            workflow_id=event.metadata.workflow_id,
        )


async def main(redis_url: str = "redis://localhost:6379", port: int = 8001):
    """Run translator agent.

    Args:
        redis_url: Redis connection URL
        port: Port for agent (for identification)
    """
    print("=" * 60)
    print("Translator Agent (A2A Test)")
    print("=" * 60)
    print(f"Redis URL: {redis_url}")
    print(f"Port: {port}")
    print("Capabilities: translation:en-es, translation")
    print("=" * 60)
    print()

    # Create model router for LLM-based translation
    import os

    from weaver_ai.models import ModelRouter, OpenAIAdapter
    from weaver_ai.settings import AppSettings

    settings = AppSettings()

    print(f"Model provider: {settings.model_provider}")
    print(f"Model name: {settings.model_name}")

    # Create router and add OpenAI model if configured
    model_router = ModelRouter(load_mock=False)

    if settings.model_provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            print(f"✓ Using OpenAI API key: {api_key[:10]}...")
            adapter = OpenAIAdapter(model=settings.model_name)
            model_router.register("default", adapter)
            model_router.default_model = "default"
        else:
            print("⚠️  WARNING: OPENAI_API_KEY not found, LLM translation will fail")
    else:
        print(f"⚠️  WARNING: Unsupported model provider: {settings.model_provider}")

    print()

    # Create and initialize agent
    agent = TranslatorAgent(agent_id=f"translator-agent-{port}")

    print("Initializing agent...")
    await agent.initialize(redis_url=redis_url, model_router=model_router)

    print("Starting agent (listening for translation requests)...")
    await agent.start()

    print()
    print("✓ Translator agent is running!")
    print("  Listening for A2A messages on:")
    print("    - tasks:translation_en_es")
    print("    - tasks:translation")
    print()
    print("Send test requests via A2A client or gateway endpoint")
    print("Press Ctrl+C to stop")
    print()

    try:
        # Keep agent running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print()
        print("Shutting down...")
        await agent.stop()
        print("✓ Agent stopped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run translator agent for A2A testing")
    parser.add_argument(
        "--redis",
        default="redis://localhost:6379",
        help="Redis connection URL",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="Port number (for agent ID)",
    )

    args = parser.parse_args()

    asyncio.run(main(redis_url=args.redis, port=args.port))
