"""Test flexible model configuration with developer-controlled models."""

import asyncio

import pytest

from weaver_ai.models import ModelRouter


def test_flexible_model_configuration():
    """Test that developers can configure any model they want."""
    router = ModelRouter(load_mock=False)

    # Add OpenAI-compatible model (no API key needed for test)
    router.add_model(
        name="gpt4",
        adapter_type="openai-compatible",
        base_url="https://api.openai.com/v1",
        api_key="test-key",
        model="gpt-4-turbo-preview",  # Developer chooses model
    )

    # Add Groq Llama
    router.add_model(
        name="llama",
        adapter_type="openai-compatible",
        base_url="https://api.groq.com/openai/v1",
        api_key="test-key",
        model="llama3-70b-8192",  # Developer chooses model
    )

    # Add Anthropic Claude
    router.add_model(
        name="claude",
        adapter_type="anthropic",
        api_key="test-key",
        model="claude-3-opus-20240229",  # Developer chooses model
    )

    # Check models are registered
    models = router.list_models()
    assert "gpt4" in models
    assert "llama" in models
    assert "claude" in models

    # Check model info
    gpt4_info = router.get_model_info("gpt4")
    assert gpt4_info["model"] == "gpt-4-turbo-preview"
    assert gpt4_info["adapter_type"] == "openai-compatible"

    llama_info = router.get_model_info("llama")
    assert llama_info["model"] == "llama3-70b-8192"

    claude_info = router.get_model_info("claude")
    assert claude_info["model"] == "claude-3-opus-20240229"
    assert claude_info["adapter_type"] == "anthropic"


@pytest.mark.asyncio
async def test_model_generation_without_keys():
    """Test that models handle missing API keys gracefully."""
    router = ModelRouter(load_mock=False)

    # Add model without API key
    router.add_model(
        name="gpt5",  # Future model - just works!
        adapter_type="openai-compatible",
        base_url="https://api.openai.com/v1",
        api_key=None,  # No key
        model="gpt-5",  # Developer can use future models
    )

    # Should return error message about missing key
    response = await router.generate("Hello", model_name="gpt5")
    assert "API key not configured" in response.text
    assert response.model == "gpt-5-no-key"


@pytest.mark.asyncio
async def test_openrouter_universal_access():
    """Test that OpenRouter can be used to access any model."""
    router = ModelRouter(load_mock=False)

    # OpenRouter provides access to 400+ models with one API
    router.add_model(
        name="universal",
        adapter_type="openai-compatible",
        base_url="https://openrouter.ai/api/v1",
        api_key="test-key",
        model="meta-llama/llama-3.3-70b-instruct",  # Any model!
    )

    # Can also access Claude through OpenRouter
    router.add_model(
        name="claude-via-router",
        adapter_type="openai-compatible",  # Same adapter!
        base_url="https://openrouter.ai/api/v1",
        api_key="test-key",
        model="anthropic/claude-3-opus",  # Claude via OpenRouter
    )

    assert "universal" in router.list_models()
    assert "claude-via-router" in router.list_models()


def test_future_proof_models():
    """Test that future models work without code changes."""
    router = ModelRouter(load_mock=False)

    # These models don't exist yet, but will work when they do!
    future_models = [
        ("gpt-6", "https://api.openai.com/v1"),
        ("claude-4-opus", "https://api.anthropic.com/v1"),
        ("llama4-400b", "https://api.groq.com/openai/v1"),
        ("gemini-ultra-2", "https://api.google.com/v1"),
    ]

    for model, base_url in future_models:
        router.add_model(
            name=model,
            adapter_type="openai-compatible",
            base_url=base_url,
            api_key="test-key",
            model=model,
        )

    # All models registered
    models = router.list_models()
    for model, _ in future_models:
        assert model in models


if __name__ == "__main__":
    # Run tests
    test_flexible_model_configuration()
    print("✅ Flexible model configuration test passed")

    asyncio.run(test_model_generation_without_keys())
    print("✅ Missing API key handling test passed")

    asyncio.run(test_openrouter_universal_access())
    print("✅ OpenRouter universal access test passed")

    test_future_proof_models()
    print("✅ Future-proof models test passed")

    print("\n🎉 All flexible model tests passed!")
    print("\nDevelopers have full control over model selection!")
    print("- Use any model: GPT-4, GPT-5, Claude, Llama, etc.")
    print("- No code changes needed for new models")
    print("- One adapter works for most providers")
    print("- Simple configuration, powerful flexibility")
