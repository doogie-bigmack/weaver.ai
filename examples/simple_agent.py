#!/usr/bin/env python3
"""
Simple Agent Interaction Example for Weaver AI
Demonstrates basic multi-agent workflow with automatic type-based routing
"""

import asyncio

from pydantic import BaseModel

from weaver_ai import Workflow
from weaver_ai.agents import BaseAgent, agent
from weaver_ai.events import Event


# Step 1: Define data models for agent communication
class Question(BaseModel):
    """Input question from user"""

    query: str
    context: str = ""


class ResearchResult(BaseModel):
    """Research findings from web/database"""

    query: str
    sources: list[str]
    raw_data: dict


class Answer(BaseModel):
    """Final formatted answer"""

    question: str
    answer: str
    confidence: float
    citations: list[str]


# Step 2: Define specialized agents


@agent(
    agent_type="researcher",
    capabilities=["search", "data_gathering"],
    memory_strategy="analyst",
)
class ResearchAgent(BaseAgent):
    """Gathers information from various sources"""

    async def process(self, event: Event) -> ResearchResult:
        # Extract the question
        question: Question = event.data

        # Simulate research (in production, this would call real APIs/tools)
        print(f"🔍 Researching: {question.query}")

        # Mock research results
        sources = [
            "https://example.com/article1",
            "https://example.com/article2",
            "internal_database_record_123",
        ]

        raw_data = {
            "fact1": "Paris is the capital of France",
            "fact2": "Population is approximately 2.2 million",
            "fact3": "Known as the City of Light",
            "confidence_score": 0.95,
        }

        return ResearchResult(query=question.query, sources=sources, raw_data=raw_data)


@agent(agent_type="synthesizer", capabilities=["analysis", "summarization"])
class SynthesisAgent(BaseAgent):
    """Analyzes research and formulates answer"""

    async def process(self, event: Event) -> Answer:
        # Extract research results
        research: ResearchResult = event.data

        print(f"🧠 Synthesizing answer from {len(research.sources)} sources")

        # Analyze the raw data (simplified for demo)
        facts = list(research.raw_data.values())
        answer_text = f"Based on my research: {'. '.join(str(f) for f in facts[:3])}"

        # Extract confidence if available
        confidence = research.raw_data.get("confidence_score", 0.8)

        return Answer(
            question=research.query,
            answer=answer_text,
            confidence=confidence,
            citations=research.sources,
        )


@agent(agent_type="validator")
class QualityValidator(BaseAgent):
    """Optional agent that validates answer quality"""

    async def process(self, event: Event) -> Answer:
        answer: Answer = event.data

        print(f"✅ Validating answer (confidence: {answer.confidence:.2f})")

        # Simple validation logic
        if answer.confidence < 0.5:
            answer.answer = f"[Low confidence warning] {answer.answer}"

        # Could add fact-checking, bias detection, etc.
        return answer


# Step 3: Create and run the workflow


async def run_simple_example():
    """Demonstrate a simple multi-agent Q&A workflow"""

    print("=== Weaver AI Simple Agent Interaction ===\n")

    # Build the workflow with automatic routing
    workflow = (
        Workflow("question_answering")
        .add_agent(ResearchAgent)
        .add_agent(SynthesisAgent)
        .add_agent(QualityValidator, error_handling="skip")  # Optional validation
        .with_observability(True)  # Enable progress tracking
        .with_timeout(30)  # 30 second timeout
    )

    # Prepare a question
    question = Question(
        query="What is the capital of France?",
        context="User is asking about European geography",
    )

    print(f"📝 User Question: {question.query}\n")
    print("Starting agent workflow...\n")

    # Run the workflow - agents automatically connect based on types!
    # Flow: Question -> ResearchAgent -> SynthesisAgent -> QualityValidator -> Answer
    result = await workflow.run(question)

    # Display results
    print("\n=== Workflow Complete ===")
    print(f"Status: {result.state}")

    if result.state == "completed":
        final_answer: Answer = result.result
        print(f"\n💡 Answer: {final_answer.answer}")
        print(f"Confidence: {final_answer.confidence:.1%}")
        print(f"Sources: {len(final_answer.citations)} citations")

        # Show agent metrics
        print("\n📊 Performance Metrics:")
        for metric, value in result.metrics.items():
            print(f"  - {metric}: {value}")
    else:
        print(f"Error: {result.error}")


# Step 4: Advanced example with conditional routing


async def run_advanced_example():
    """Demonstrate conditional routing based on confidence"""

    print("\n=== Advanced Example: Conditional Routing ===\n")

    # Additional agent for low-confidence cases
    @agent(agent_type="deep_researcher")
    class DeepResearchAgent(BaseAgent):
        """Performs deeper research for low-confidence answers"""

        async def process(self, event: Event) -> Answer:
            answer: Answer = event.data
            print("🔬 Performing deep research due to low confidence...")

            # Enhance the answer
            answer.answer = f"[Enhanced] {answer.answer}"
            answer.confidence = min(answer.confidence + 0.3, 1.0)
            return answer

    # Build workflow with conditional routing
    workflow = (
        Workflow("advanced_qa")
        .add_agents(ResearchAgent, SynthesisAgent, QualityValidator)
        .add_agent(DeepResearchAgent)
        # Route to deep research if confidence is low
        .add_route(
            when=lambda result: isinstance(result, Answer) and result.confidence < 0.7,
            from_agent="synthesizer",
            to_agent="deep_researcher",
        )
    )

    # Test with a complex question
    complex_question = Question(
        query="What are the quantum mechanical implications of consciousness?",
        context="Philosophy of mind discussion",
    )

    result = await workflow.run(complex_question)
    print(f"Final confidence: {result.result.confidence:.1%}")


# Step 5: Example with error handling


async def run_error_handling_example():
    """Demonstrate error handling strategies"""

    print("\n=== Error Handling Example ===\n")

    @agent(agent_type="unreliable")
    class UnreliableAgent(BaseAgent):
        """Agent that sometimes fails"""

        async def process(self, event: Event) -> str:
            import random

            if random.random() < 0.5:
                raise Exception("Random failure!")
            return "Success"

    # Different error strategies
    workflow = (
        Workflow("error_demo")
        .add_agent(
            UnreliableAgent,
            instance_id="retry_agent",
            error_handling="retry",
            max_retries=3,
        )
        .add_agent(UnreliableAgent, instance_id="skip_agent", error_handling="skip")
    )

    result = await workflow.run("test")
    print(f"Workflow completed with status: {result.state}")


if __name__ == "__main__":
    # Run the examples
    asyncio.run(run_simple_example())
    # Uncomment to run additional examples:
    # asyncio.run(run_advanced_example())
    # asyncio.run(run_error_handling_example())
