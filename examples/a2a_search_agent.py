#!/usr/bin/env python3
"""
Web search agent for A2A multi-agent orchestration.

This agent demonstrates:
- Searching for information on a topic
- Returning structured results
- Chaining to next agent via next_capabilities
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from weaver_ai.agents import BaseAgent, Result
from weaver_ai.events import Event


class SearchAgent(BaseAgent):
    """Web search agent that finds information on topics."""

    agent_type: str = "search"
    capabilities: list[str] = ["search:web", "search"]

    async def process(self, event: Event) -> Result:
        """Process search request using secure MCP tools.

        Args:
            event: Event containing search query

        Returns:
            Result with search results and next capability (summarization)
        """
        print("[Search] Received search request")
        print(f"[Search] Event type: {event.event_type}")
        print(f"[Search] Event data: {event.data}")

        # Extract query from event data
        # Handle both direct events and queue tasks
        query = ""
        if isinstance(event.data, dict):
            # Check if data contains nested data from queue Task
            if "data" in event.data and isinstance(event.data["data"], dict):
                query = event.data["data"].get("query", "")
            else:
                query = event.data.get("query", "")
        else:
            query = str(event.data)

        print(f"[Search] Searching for: {query}")

        # Use MCP web_search tool if available
        search_results = []

        if self.tool_registry and "web_search" in self.available_tools:
            print("[Search] Using secure MCP web_search tool")
            try:
                # Execute tool with proper context and permissions
                from weaver_ai.tools import ToolExecutionContext

                context = ToolExecutionContext(
                    agent_id=self.agent_id,
                    session_id=event.metadata.workflow_id or "test-session",
                    user_id="system",
                    scopes=["tool:web_search"],  # Required permission
                )

                tool = self.tool_registry.get_tool("web_search")
                result = await tool.execute(
                    args={"query": query, "max_results": 3},
                    context=context,
                )

                if result.success:
                    search_results = result.data.get("results", [])
                    print(f"[Search] MCP tool returned {len(search_results)} results")
                else:
                    print(f"[Search] MCP tool failed: {result.error}")
                    # Fall through to LLM fallback

            except Exception as e:
                print(f"[Search] MCP tool error: {e}, falling back to LLM")

        # Fallback to LLM if MCP tool not available or failed
        if not search_results and self.model_router and query:
            print("[Search] Using LLM to generate realistic search results")
            try:
                prompt = (
                    f"Generate 3 realistic web search results for: {query}\n\n"
                    f"Respond with ONLY a JSON array in this exact format:\n"
                    f'[{{"title": "Article Title", "snippet": "2-3 sentence summary", "url": "https://example.com/page"}}]\n\n'
                    f"Requirements:\n"
                    f"- Return ONLY the JSON array, no other text\n"
                    f"- Make the results relevant to the query\n"
                    f"- Use realistic URLs and titles\n"
                    f"- Each snippet should be 2-3 sentences\n"
                )
                response = await self.model_router.generate(
                    prompt=prompt,
                    max_tokens=800,  # Enough for 3 search results
                    temperature=0.7,
                )
                search_results_text = response.text.strip()

                # Remove markdown code blocks if present
                if search_results_text.startswith("```"):
                    lines = search_results_text.split("\n")
                    search_results_text = (
                        "\n".join(lines[1:-1])
                        if len(lines) > 2
                        else search_results_text
                    )

                # Try to parse as JSON
                import json

                try:
                    search_results = json.loads(search_results_text)
                    print(f"[Search] LLM generated {len(search_results)} results")
                except json.JSONDecodeError as e:
                    print(f"[Search] Failed to parse LLM response: {e}")
                    print(f"[Search] Response was: {search_results_text[:200]}")
                    search_results = []
            except Exception as e:
                print(f"[Search] LLM search failed: {e}")

        # Final fallback to mock results
        if not search_results:
            print("[Search] Using mock fallback results")
            search_results = [
                {
                    "title": f"Mock Result: {query}",
                    "snippet": f"This is a mock search result for: {query}",
                    "url": "https://example.com/mock",
                }
            ]

        print(f"[Search] Returning {len(search_results)} results")

        # Return results and specify next capability (summarization)
        return Result(
            success=True,
            data={
                "query": query,
                "results": search_results,
                "result_count": len(search_results),
            },
            next_capabilities=["summarization"],  # Chain to summarizer
            workflow_id=event.metadata.workflow_id,
        )


async def main(redis_url: str = "redis://localhost:6379", port: int = 8002):
    """Run search agent.

    Args:
        redis_url: Redis connection URL
        port: Port for agent (for identification)
    """
    print("=" * 60)
    print("Search Agent (A2A Multi-Agent)")
    print("=" * 60)
    print(f"Redis URL: {redis_url}")
    print(f"Port: {port}")
    print("Capabilities: search:web, search")
    print("=" * 60)
    print()

    # Create model router for LLM-based search
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
            print("⚠️  WARNING: OPENAI_API_KEY not found, search will use mock results")
    else:
        print(f"⚠️  WARNING: Unsupported model provider: {settings.model_provider}")

    print()

    # Setup MCP tools with permissions
    from weaver_ai.tools import global_tool_registry
    from weaver_ai.tools.builtin.web_search import WebSearchTool

    print("Setting up MCP tools...")

    # Register web search tool if not already registered
    try:
        web_search_tool = WebSearchTool()
        # We're in async context (main function)
        await global_tool_registry.register_tool(web_search_tool)
        print("✓ Registered web_search tool")
    except Exception as e:
        print(f"⚠️  Tool registration error: {e}")

    tools = global_tool_registry.list_tools()
    if isinstance(tools, dict):
        print(f"Available tools: {list(tools.keys())}")
    else:
        print(
            f"Available tools: {[t.name if hasattr(t, 'name') else str(t) for t in tools]}"
        )

    # Create and initialize agent
    agent = SearchAgent(agent_id=f"search-agent-{port}")

    print("Initializing agent...")
    await agent.initialize(
        redis_url=redis_url,
        model_router=model_router,
        tool_registry=global_tool_registry,
    )

    print("Starting agent (listening for search requests)...")
    await agent.start()

    print()
    print("✓ Search agent is running!")
    print("  Listening for A2A messages on:")
    print("    - tasks:search_web")
    print("    - tasks:search")
    print()
    print("Send test requests via A2A client or orchestrator")
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
    parser = argparse.ArgumentParser(description="Run search agent for A2A testing")
    parser.add_argument(
        "--redis",
        default="redis://localhost:6379",
        help="Redis connection URL",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8002,
        help="Port number (for agent ID)",
    )

    args = parser.parse_args()

    asyncio.run(main(redis_url=args.redis, port=args.port))
