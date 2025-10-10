#!/usr/bin/env python3
"""
Summarization agent for A2A multi-agent orchestration.

This agent demonstrates:
- Receiving data from previous agent (search results)
- Summarizing content using LLM
- Completing the workflow (no next_capabilities)
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from weaver_ai.agents import BaseAgent, Result
from weaver_ai.events import Event


class SummarizerAgent(BaseAgent):
    """Summarization agent that condenses search results."""

    agent_type: str = "summarizer"
    capabilities: list[str] = ["summarization", "summarize"]

    async def process(self, event: Event) -> Result:
        """Process summarization request.

        Args:
            event: Event containing search results to summarize

        Returns:
            Result with summary (workflow ends here)
        """
        print("[Summarizer] Received summarization request")
        print(f"[Summarizer] Event type: {event.event_type}")
        data_keys = (
            list(event.data.keys()) if isinstance(event.data, dict) else "not a dict"
        )
        print(f"[Summarizer] Event data keys: {data_keys}")

        # Extract search results from event data
        if isinstance(event.data, dict):
            query = event.data.get("query", "")
            results = event.data.get("results", [])
        else:
            query = "unknown"
            results = []

        print(f"[Summarizer] Query: {query}")
        print(f"[Summarizer] Summarizing {len(results)} search results")

        # Create a summary using LLM
        if self.model_router and results:
            try:
                # Build prompt from search results
                results_text = "\n\n".join(
                    [
                        f"Result {i+1}:\n"
                        f"Title: {r.get('title', 'N/A')}\n"
                        f"Snippet: {r.get('snippet', 'N/A')}\n"
                        f"URL: {r.get('url', 'N/A')}"
                        for i, r in enumerate(results)
                    ]
                )

                prompt = (
                    f"You are a summarization agent. Summarize the following search results "
                    f"about '{query}' into a concise 2-3 paragraph summary. "
                    f"Focus on the key information and insights.\n\n"
                    f"{results_text}\n\n"
                    f"Summary:"
                )

                response = await self.model_router.generate(prompt=prompt)
                summary = response.text.strip()
            except Exception as e:
                print(
                    f"[Summarizer] LLM summarization failed: {e}, falling back to mock"
                )
                summary = (
                    f"Summary of {len(results)} results about '{query}': "
                    "[Mock summary - LLM failed]"
                )
        else:
            # Mock summary if no model router or no results
            summary = (
                f"Summary of {len(results)} results about '{query}': "
                "[Mock summary - No LLM available]"
            )

        print(f"[Summarizer] Summary generated ({len(summary)} chars)")

        # Return summary (no next_capabilities = workflow ends here)
        return Result(
            success=True,
            data={
                "query": query,
                "summary": summary,
                "source_count": len(results),
            },
            next_capabilities=[],  # Workflow ends here
            workflow_id=event.metadata.workflow_id,
        )


async def main(redis_url: str = "redis://localhost:6379", port: int = 8003):
    """Run summarizer agent.

    Args:
        redis_url: Redis connection URL
        port: Port for agent (for identification)
    """
    print("=" * 60)
    print("Summarizer Agent (A2A Multi-Agent)")
    print("=" * 60)
    print(f"Redis URL: {redis_url}")
    print(f"Port: {port}")
    print("Capabilities: summarization, summarize")
    print("=" * 60)
    print()

    # Create model router for LLM-based summarization
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
            print("⚠️  WARNING: OPENAI_API_KEY not found, will use mock summaries")
    else:
        print(f"⚠️  WARNING: Unsupported model provider: {settings.model_provider}")

    print()

    # Create and initialize agent
    agent = SummarizerAgent(agent_id=f"summarizer-agent-{port}")

    print("Initializing agent...")
    await agent.initialize(redis_url=redis_url, model_router=model_router)

    print("Starting agent (listening for summarization requests)...")
    await agent.start()

    print()
    print("✓ Summarizer agent is running!")
    print("  Listening for A2A messages on:")
    print("    - tasks:summarization")
    print("    - tasks:summarize")
    print()
    print("This agent receives output from search agent")
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
    parser = argparse.ArgumentParser(description="Run summarizer agent for A2A testing")
    parser.add_argument(
        "--redis",
        default="redis://localhost:6379",
        help="Redis connection URL",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8003,
        help="Port number (for agent ID)",
    )

    args = parser.parse_args()

    asyncio.run(main(redis_url=args.redis, port=args.port))
