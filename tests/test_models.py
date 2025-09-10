"""Tests for model adapters and router."""

import asyncio

from weaver_ai.models import MockAdapter, ModelRouter


def test_mock_adapter():
    """Test mock adapter responses."""
    adapter = MockAdapter("test-mock")

    # Test hello
    response = asyncio.run(adapter.generate("Hello world"))
    assert "Hello" in response.text
    assert response.model == "test-mock"

    # Test math
    response = asyncio.run(adapter.generate("What is 10 + 5?"))
    assert "15" in response.text

    # Test analysis
    response = asyncio.run(adapter.generate("Analyze this data"))
    assert "Analysis" in response.text


def test_model_router():
    """Test model router functionality."""
    router = ModelRouter()

    # Default mock model should be registered
    assert "mock" in router.list_models()

    # Test with default model
    response = asyncio.run(router.generate("Test prompt"))
    assert response.text
    # Model name can be "mock" or "pooled-mock" depending on connection pooling
    assert response.model in ["mock", "pooled-mock"]

    # Register another mock model
    router.register("mock2", MockAdapter("mock2"))
    assert "mock2" in router.list_models()

    # Test with specific model
    response = asyncio.run(router.generate("Test", model_name="mock2"))
    assert response.model == "mock2"


def test_math_evaluation():
    """Test that math expressions work."""
    router = ModelRouter()

    # Test various math operations
    tests = [
        ("5 + 3", "8"),
        ("10 - 4", "6"),
        ("3 * 7", "21"),
        ("20 / 4", "5"),
    ]

    for expr, expected in tests:
        response = asyncio.run(router.generate(expr))
        assert expected in response.text, f"Failed for {expr}"


if __name__ == "__main__":
    test_mock_adapter()
    print("✅ Mock adapter tests passed")

    test_model_router()
    print("✅ Model router tests passed")

    test_math_evaluation()
    print("✅ Math evaluation tests passed")

    print("\n🎉 All model tests passed!")
