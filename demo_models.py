#!/usr/bin/env python3
"""Demo of model integration with event mesh."""

import asyncio

from pydantic import BaseModel

from weaver_ai.events import EventMesh
from weaver_ai.models import ModelRouter


# Event types
class Question(BaseModel):
    """A question that needs answering."""

    text: str
    user_id: str


class Answer(BaseModel):
    """An answer from the model."""

    question: str
    answer: str
    model_used: str


async def question_answerer(mesh: EventMesh, router: ModelRouter):
    """Agent that answers questions using models."""
    print("🤖 Question Answerer Agent started")

    async for event in mesh.subscribe([Question], agent_id="answerer"):
        question = event.data
        print(f"  📝 Processing: {question.text}")

        # Use model to generate answer
        response = await router.generate(question.text)

        # Publish answer
        answer = Answer(
            question=question.text, answer=response.text, model_used=response.model
        )

        await mesh.publish(Answer, answer)
        print(f"  ✅ Answer generated using {response.model}")
        break  # Process one for demo


async def result_printer(mesh: EventMesh):
    """Agent that prints results."""
    print("🖨️  Result Printer Agent started")

    async for event in mesh.subscribe([Answer], agent_id="printer"):
        answer = event.data
        print("\n📊 RESULT:")
        print(f"   Question: {answer.question}")
        print(f"   Answer: {answer.answer}")
        print(f"   Model: {answer.model_used}")
        break


async def main():
    """Run the model integration demo."""
    print("=" * 60)
    print("Model Integration Demo")
    print("=" * 60)

    # Create components
    mesh = EventMesh()
    router = ModelRouter()  # Uses mock model by default

    # Start agents
    print("\n🚀 Starting agents...")
    answerer_task = asyncio.create_task(question_answerer(mesh, router))
    printer_task = asyncio.create_task(result_printer(mesh))

    await asyncio.sleep(0.5)

    # Test different types of questions
    questions = [
        Question(text="What is 15 + 27?", user_id="user1"),
        Question(text="Hello, how are you?", user_id="user2"),
        Question(text="Analyze the market trends", user_id="user3"),
    ]

    for q in questions[:1]:  # Process first question for demo
        print(f"\n❓ User asks: {q.text}")
        await mesh.publish(Question, q)

        # Wait for processing
        await asyncio.sleep(0.5)

    # Wait for agents to complete
    await asyncio.gather(answerer_task, printer_task)

    # Show available models
    print(f"\n📋 Available models: {router.list_models()}")

    print("\n✅ Model integration demo complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
