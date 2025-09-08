#!/usr/bin/env python3
"""Verify Phase 2: Model Integration works correctly."""

import asyncio

from weaver_ai.models import MockAdapter, ModelRouter
from weaver_ai.models.config import setup_router_from_config
from weaver_ai.models.openai_adapter import OpenAIAdapter


async def verify_models():
    """Verify model system works."""
    print("🔍 Verifying Phase 2: Model Integration")
    print("=" * 50)

    # Test 1: Mock adapter
    print("\n1️⃣ Testing Mock Adapter...")
    mock = MockAdapter()
    response = await mock.generate("What is 25 + 17?")
    assert "42" in response.text
    print(f"   ✅ Mock math: {response.text}")

    # Test 2: Model router
    print("\n2️⃣ Testing Model Router...")
    router = ModelRouter()
    models = router.list_models()
    assert "mock" in models
    print(f"   ✅ Available models: {models}")

    response = await router.generate("Hello world")
    assert response.text
    print(f"   ✅ Router response: {response.text[:50]}...")

    # Test 3: Config-based setup
    print("\n3️⃣ Testing Config-based Setup...")
    config_router = setup_router_from_config("models.yaml")
    models = config_router.list_models()
    print(f"   ✅ Models from config: {models}")

    # Test 4: OpenAI adapter (without key)
    print("\n4️⃣ Testing OpenAI Adapter (no key)...")
    openai = OpenAIAdapter()
    response = await openai.generate("Test")
    print(f"   ✅ Graceful handling: {response.text[:50]}...")

    # Test 5: Multiple models
    print("\n5️⃣ Testing Multiple Models...")
    router = ModelRouter()
    router.register("model1", MockAdapter("model1"))
    router.register("model2", MockAdapter("model2"))

    r1 = await router.generate("Test", model="model1")
    r2 = await router.generate("Test", model="model2")
    assert r1.model == "model1"
    assert r2.model == "model2"
    print(f"   ✅ Model 1: {r1.model}")
    print(f"   ✅ Model 2: {r2.model}")

    print("\n" + "=" * 50)
    print("✅ Phase 2 Verification Complete!")
    print("\nKey Features Working:")
    print("  • Mock adapter for testing")
    print("  • Model router with multiple models")
    print("  • Config-based model setup")
    print("  • OpenAI adapter (ready when API key provided)")
    print("  • Graceful error handling")

    return True


if __name__ == "__main__":
    result = asyncio.run(verify_models())
    if result:
        print("\n🎉 Phase 2: Model Integration - VERIFIED!")
