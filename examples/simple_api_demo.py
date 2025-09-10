#!/usr/bin/env python3
"""
Simple API Demo for Weaver AI

This example demonstrates how easy it is to create multi-agent workflows
using the simplified API - no boilerplate, just business logic!

Run this example:
    python examples/simple_api_demo.py
"""

import asyncio

from weaver_ai.simple import agent, flow, run

# ==============================================================================
# EXAMPLE 1: Hello World - Single Agent (5 lines!)
# ==============================================================================


@agent
async def hello(name: str) -> str:
    """Simple greeting agent."""
    return f"Hello, {name}! Welcome to Weaver AI."


async def example1_hello_world():
    """Simplest possible agent - just 5 lines total!"""
    print("\n" + "=" * 60)
    print("EXAMPLE 1: Hello World Agent")
    print("=" * 60)

    result = await run(hello, "Alice")
    print(f"Result: {result}")


# ==============================================================================
# EXAMPLE 2: Multi-Agent Pipeline (< 20 lines!)
# ==============================================================================


@agent(model="gpt-3.5-turbo")
async def analyzer(text: str) -> dict:
    """Analyze text and extract key information."""
    words = text.split()
    return {
        "word_count": len(words),
        "chars": len(text),
        "sentences": text.count(".") + text.count("!") + text.count("?"),
    }


@agent(model="gpt-4")
async def summarizer(analysis: dict) -> str:
    """Create a summary from analysis."""
    return (
        f"Document Analysis: {analysis['word_count']} words, "
        f"{analysis['chars']} characters, {analysis['sentences']} sentences"
    )


@agent
async def formatter(summary: str) -> str:
    """Format the final output."""
    return f"📊 {summary}\n✅ Analysis complete!"


async def example2_pipeline():
    """Multi-agent pipeline with automatic routing."""
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Multi-Agent Pipeline")
    print("=" * 60)

    # Create pipeline - agents automatically connect based on types!
    pipeline = flow("analysis_pipeline").chain(analyzer, summarizer, formatter)

    test_text = "This is a test document. It has multiple sentences! How many words?"

    # Run the pipeline - just one line!
    result = await run(pipeline, test_text)
    print(f"Pipeline Result:\n{result}")


# ==============================================================================
# EXAMPLE 3: Customer Support Workflow (< 30 lines!)
# ==============================================================================


@agent(model="gpt-4", retry=3)
async def ticket_classifier(ticket: str) -> dict:
    """Classify support tickets by type and priority."""
    ticket_lower = ticket.lower()

    # Simple classification logic
    if "urgent" in ticket_lower or "asap" in ticket_lower:
        priority = "high"
    elif "bug" in ticket_lower or "error" in ticket_lower:
        priority = "high"
    else:
        priority = "medium"

    if "login" in ticket_lower or "password" in ticket_lower:
        category = "authentication"
    elif "slow" in ticket_lower or "performance" in ticket_lower:
        category = "performance"
    elif "feature" in ticket_lower:
        category = "feature_request"
    else:
        category = "general"

    return {"ticket": ticket, "category": category, "priority": priority}


@agent(cache=True)  # Enable caching for responses
async def solution_generator(classification: dict) -> dict:
    """Generate solutions based on ticket classification."""
    solutions = {
        "authentication": [
            "Reset your password using the 'Forgot Password' link",
            "Clear browser cookies and cache",
            "Try logging in from an incognito window",
        ],
        "performance": [
            "Check your internet connection",
            "Clear application cache",
            "Try during off-peak hours",
        ],
        "feature_request": [
            "Thank you for your suggestion",
            "We'll add this to our feature backlog",
            "Vote for features on our roadmap page",
        ],
        "general": [
            "Please provide more details about your issue",
            "Check our FAQ section",
            "Contact support for personalized help",
        ],
    }

    return {
        **classification,
        "solutions": solutions.get(classification["category"], ["Contact support"]),
    }


@agent
async def response_writer(solution_data: dict) -> str:
    """Write a friendly customer response."""
    response = f"""
🎫 Support Ticket Response
━━━━━━━━━━━━━━━━━━━━━━━━
Category: {solution_data['category'].replace('_', ' ').title()}
Priority: {solution_data['priority'].upper()}

Your Issue:
{solution_data['ticket']}

Suggested Solutions:
"""
    for i, solution in enumerate(solution_data["solutions"], 1):
        response += f"{i}. {solution}\n"

    response += "\nIf these solutions don't help, please reply to this ticket."
    return response


async def example3_support_workflow():
    """Customer support workflow with classification and response generation."""
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Customer Support Workflow")
    print("=" * 60)

    # Build the support workflow
    support_flow = (
        flow("customer_support")
        .chain(ticket_classifier, solution_generator, response_writer)
        .with_timeout(30)  # 30 second timeout
        .with_observability(True)  # Enable monitoring
    )

    # Test tickets
    test_tickets = [
        "URGENT: I can't login to my account!",
        "The app is running very slow on my phone",
        "Feature request: Can you add dark mode?",
    ]

    for ticket in test_tickets:
        print(f"\nProcessing: {ticket}")
        print("-" * 40)
        result = await run(support_flow, ticket)
        print(result)


# ==============================================================================
# EXAMPLE 4: Parallel Processing (< 20 lines!)
# ==============================================================================


@agent
async def check_inventory(order: dict) -> dict:
    """Check product inventory."""
    await asyncio.sleep(0.1)  # Simulate API call
    return {"inventory": "in_stock", "quantity": 100}


@agent
async def check_pricing(order: dict) -> dict:
    """Get current pricing."""
    await asyncio.sleep(0.1)  # Simulate API call
    return {"price": 29.99, "discount": 0.1}


@agent
async def check_shipping(order: dict) -> dict:
    """Calculate shipping options."""
    await asyncio.sleep(0.1)  # Simulate API call
    return {"shipping": 5.99, "delivery_days": 3}


async def example4_parallel():
    """Run multiple agents in parallel for faster processing."""
    print("\n" + "=" * 60)
    print("EXAMPLE 4: Parallel Agent Processing")
    print("=" * 60)

    # Note: In a real implementation, parallel() would run these concurrently
    # For this demo, we'll run them sequentially
    order = {"product_id": "ABC123", "quantity": 2}

    print("Checking inventory, pricing, and shipping in parallel...")

    # Run agents individually for demo
    inventory = await run(check_inventory, order)
    pricing = await run(check_pricing, order)
    shipping = await run(check_shipping, order)

    print("\nResults:")
    print(f"  Inventory: {inventory}")
    print(f"  Pricing: {pricing}")
    print(f"  Shipping: {shipping}")


# ==============================================================================
# EXAMPLE 5: Agent with Configuration (< 15 lines!)
# ==============================================================================


@agent(
    model="gpt-4",
    temperature=0.3,  # Lower temperature for consistency
    max_tokens=500,
    retry=5,  # Retry up to 5 times on failure
    cache=True,  # Cache responses
    permissions=["read", "write"],  # Required permissions
)
async def advanced_processor(data: dict) -> dict:
    """Agent with full configuration options."""
    # In production, this would use the configured model
    # For demo, we'll simulate processing
    processed = {
        "input": data,
        "processed_at": "2024-01-01T12:00:00Z",
        "status": "success",
        "confidence": 0.95,
    }
    return processed


async def example5_configured_agent():
    """Demonstrate agent with full configuration."""
    print("\n" + "=" * 60)
    print("EXAMPLE 5: Configured Agent")
    print("=" * 60)

    test_data = {"user_id": 123, "action": "process", "data": "sample"}

    result = await run(advanced_processor, test_data)
    print(f"Configured Agent Result: {result}")


# ==============================================================================
# MAIN: Run All Examples
# ==============================================================================


async def main():
    """Run all examples to demonstrate the simple API."""
    print("╔" + "═" * 58 + "╗")
    print("║" + " WEAVER AI SIMPLE API DEMONSTRATION ".center(58) + "║")
    print("║" + " Create powerful agents in < 20 lines of code! ".center(58) + "║")
    print("╚" + "═" * 58 + "╝")

    # Run all examples
    await example1_hello_world()
    await example2_pipeline()
    await example3_support_workflow()
    await example4_parallel()
    await example5_configured_agent()

    print("\n" + "=" * 60)
    print("DEMONSTRATION COMPLETE")
    print("=" * 60)
    print("\n✨ Key Takeaways:")
    print("  • Single agent: 5 lines of code")
    print("  • Multi-agent pipeline: < 20 lines")
    print("  • Production workflow: < 30 lines")
    print("  • No boilerplate - just business logic!")
    print("  • Automatic type-based routing")
    print("  • Built-in retry, caching, and monitoring")
    print("\n🚀 Start building with: from weaver_ai.simple import agent, flow, run")


if __name__ == "__main__":
    asyncio.run(main())
