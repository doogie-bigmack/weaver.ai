#!/usr/bin/env python3
"""
Orchestrator agent for multi-agent A2A workflows.

This agent demonstrates:
- Coordinating multiple agents via A2A protocol
- Starting workflows and tracking results
- Secure inter-agent communication with RSA signatures
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from weaver_ai.agents import BaseAgent, Result
from weaver_ai.events import Event


class OrchestratorAgent(BaseAgent):
    """Orchestrator that coordinates multi-agent workflows."""

    agent_type: str = "orchestrator"
    capabilities: list[str] = ["orchestration", "workflow:start"]

    async def process(self, event: Event) -> Result:
        """Process orchestration request.

        This agent kicks off workflows by publishing to the first capability.

        Args:
            event: Event containing workflow request

        Returns:
            Result with workflow status
        """
        print("[Orchestrator] Received orchestration request")
        print(f"[Orchestrator] Event type: {event.event_type}")
        print(f"[Orchestrator] Event data: {event.data}")

        # Extract workflow request
        if isinstance(event.data, dict):
            workflow_type = event.data.get("workflow_type", "research")
            query = event.data.get("query", "")
        else:
            workflow_type = "research"
            query = str(event.data)

        print(f"[Orchestrator] Starting workflow: {workflow_type}")
        print(f"[Orchestrator] Query: {query}")

        # For research workflow: search -> summarize
        if workflow_type == "research":
            # The workflow will automatically chain:
            # 1. This returns with next_capabilities=["search"]
            # 2. Search agent picks it up and returns with next_capabilities=["summarization"]
            # 3. Summarizer agent picks it up and completes (next_capabilities=[])

            return Result(
                success=True,
                data={
                    "workflow_type": workflow_type,
                    "query": query,
                    "status": "initiated",
                    "workflow_id": event.metadata.workflow_id,
                },
                next_capabilities=["search"],  # Start with search agent
                workflow_id=event.metadata.workflow_id,
            )

        return Result(
            success=False,
            error=f"Unknown workflow type: {workflow_type}",
            workflow_id=event.metadata.workflow_id,
        )


async def main(redis_url: str = "redis://localhost:6379", port: int = 8004):
    """Run orchestrator agent.

    Args:
        redis_url: Redis connection URL
        port: Port for agent (for identification)
    """
    print("=" * 60)
    print("Orchestrator Agent (A2A Multi-Agent)")
    print("=" * 60)
    print(f"Redis URL: {redis_url}")
    print(f"Port: {port}")
    print("Capabilities: orchestration, workflow:start")
    print("=" * 60)
    print()

    # Create and initialize agent (orchestrator doesn't need LLM)
    agent = OrchestratorAgent(agent_id=f"orchestrator-agent-{port}")

    print("Initializing agent...")
    await agent.initialize(redis_url=redis_url)

    print("Starting agent (listening for orchestration requests)...")
    await agent.start()

    print()
    print("✓ Orchestrator agent is running!")
    print("  Listening for A2A messages on:")
    print("    - tasks:orchestration")
    print("    - tasks:workflow_start")
    print()
    print("Workflow: orchestrator -> search -> summarizer")
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
    parser = argparse.ArgumentParser(
        description="Run orchestrator agent for A2A multi-agent workflows"
    )
    parser.add_argument(
        "--redis",
        default="redis://localhost:6379",
        help="Redis connection URL",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8004,
        help="Port number (for agent ID)",
    )

    args = parser.parse_args()

    asyncio.run(main(redis_url=args.redis, port=args.port))
