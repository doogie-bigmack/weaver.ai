#!/usr/bin/env python3
"""
Demo: SailPoint MCP + OpenAI GPT Integration

This script demonstrates how to use real LLM capabilities with the SailPoint MCP tool.
Set your OpenAI API key as an environment variable before running:
    export OPENAI_API_KEY='sk-proj-...'
"""

import asyncio
import os

from pydantic import BaseModel

from weaver_ai.models.openai_adapter import OpenAIAdapter
from weaver_ai.models.router import ModelRouter
from weaver_ai.tools import ToolRegistry
from weaver_ai.tools.builtin.sailpoint import SailPointIIQTool


class Query(BaseModel):
    text: str


async def main():
    print("\n🚀 SailPoint + GPT Demo")
    print("=" * 40)

    # Check API key
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key or api_key == "sk-proj-...":
        print("\n⚠️  Please set your OpenAI API key:")
        print("   export OPENAI_API_KEY='your-actual-key'")
        print("\nOr enter it now (it won't be saved):")
        api_key = input("API Key: ").strip()
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
        else:
            return

    print("✅ API key configured")

    # Setup
    router = ModelRouter()
    router.register("gpt-4o-mini", OpenAIAdapter("gpt-4o-mini"))

    # Quick test
    print("\n🧪 Testing GPT...")
    result = await router.generate(
        "Say 'Ready!' in 1 word", model="gpt-4o-mini", max_tokens=5
    )
    print(f"   GPT: {result.text}")

    if "unavailable" in result.model:
        print("   ❌ GPT not working - check API key")
        return

    # Get SailPoint data
    print("\n📊 SailPoint Data (Mock):")
    tool = SailPointIIQTool()
    registry = ToolRegistry()
    await registry.register_tool(tool)

    # Execute tool
    from weaver_ai.tools import ToolExecutionContext

    ctx = ToolExecutionContext(agent_id="demo", workflow_id="test")
    result = await tool.execute({"action": "count_users_and_roles"}, ctx)

    if result.success:
        data = result.data
        print(f"   Users: {data['users']['total']} ({data['users']['active']} active)")
        print(f"   Roles: {data['roles']['total']}")

        # Use GPT to analyze
        print("\n🤖 GPT Analysis:")
        prompt = f"In 2 sentences, analyze: {data['summary']}"
        gpt_result = await router.generate(prompt, model="gpt-4o-mini", max_tokens=100)
        print(f"   {gpt_result.text}")
        print(f"\n✅ Demo complete! ({gpt_result.tokens_used} tokens used)")
    else:
        print(f"   ❌ Tool failed: {result.error}")


if __name__ == "__main__":
    asyncio.run(main())
