#!/usr/bin/env python3
"""Simple Q&A Agent - Hello World Example.

This example demonstrates the simplest possible agent workflow:
a single agent that answers questions using an LLM.
"""

import asyncio

from pydantic import BaseModel

from weaver_ai import Workflow
from weaver_ai.agents import BaseAgent, agent
from weaver_ai.events import Event


class Question(BaseModel):
    """A question to be answered."""

    text: str
    context: str = ""


class Answer(BaseModel):
    """An answer to a question."""

    question: str
    answer: str
    confidence: float = 1.0


@agent(agent_type="qa_bot", capabilities=["answer:questions"])
class QABot(BaseAgent):
    """Simple question answering agent."""

    async def process(self, event: Event) -> Answer:
        """Process a question and return an answer.

        Args:
            event: Event containing a Question

        Returns:
            Answer with the response
        """
        # Extract question from event
        if isinstance(event.data, Question):
            question = event.data
        elif isinstance(event.data, str):
            question = Question(text=event.data)
        else:
            question = Question(text=str(event.data))

        # Use the model router to get an answer
        if self.model_router:
            response = await self.model_router.generate(
                f"Question: {question.text}\nContext: {question.context}\n\nAnswer:"
            )
            answer_text = response.text
        else:
            # Fallback for testing without model
            answer_text = f"This is a mock answer to: {question.text}"

        return Answer(question=question.text, answer=answer_text, confidence=0.95)


async def main():
    """Run the simple Q&A example."""
    print("=" * 60)
    print("Simple Q&A Agent Example")
    print("=" * 60)

    # Create a simple workflow with one agent
    workflow = Workflow("simple_qa").add_agent(QABot)

    # Example 1: Simple string question
    print("\n1. Simple string question:")
    print("   Question: What is the capital of France?")

    result = await workflow.run("What is the capital of France?")

    if isinstance(result, Answer):
        print(f"   Answer: {result.answer}")
        print(f"   Confidence: {result.confidence}")

    # Example 2: Question with context
    print("\n2. Question with context:")
    question = Question(
        text="What is the main product?",
        context="Our company specializes in AI-powered data analytics.",
    )
    print(f"   Question: {question.text}")
    print(f"   Context: {question.context}")

    result = await workflow.run(question)

    if isinstance(result, Answer):
        print(f"   Answer: {result.answer}")

    # Example 3: With observability enabled
    print("\n3. With observability enabled:")

    workflow_with_obs = (
        Workflow("qa_with_observability")
        .add_agent(QABot)
        .with_observability(True)
        .with_timeout(30)
    )

    result = await workflow_with_obs.run("How does photosynthesis work?")

    if isinstance(result, Answer):
        print(f"   Question: {result.question}")
        print(f"   Answer: {result.answer[:100]}...")  # Truncate long answer

    print("\n" + "=" * 60)
    print("Example completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    # Run the example
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExample interrupted by user")
    except Exception as e:
        print(f"\nError running example: {e}")
        import traceback

        traceback.print_exc()
