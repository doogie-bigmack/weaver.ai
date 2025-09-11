"""Run the Weaver AI framework validation test with real GPT models."""

import asyncio
import json
import os

# Set up path
import sys
from datetime import datetime

sys.path.insert(0, ".")

from tests.integration.test_framework_validation import FrameworkValidator


async def run_validation_with_gpt():
    """Run framework validation with GPT models."""

    print("\n" + "=" * 70)
    print("WEAVER AI FRAMEWORK VALIDATION WITH GPT MODELS")
    print("=" * 70 + "\n")

    # Check for API key
    if os.getenv("OPENAI_API_KEY"):
        print(f"✅ OpenAI API key found: {os.getenv('OPENAI_API_KEY')[:10]}...")
    else:
        print("⚠️  No OpenAI API key found, will use mock models")

    # Create validator
    validator = FrameworkValidator()
    await validator.setup()

    # If API key exists, add real GPT model to router
    if os.getenv("OPENAI_API_KEY"):
        print("📡 Configuring real GPT model...")
        validator.model_router.add_model(
            name="gpt",
            adapter_type="openai-compatible",
            base_url="https://api.openai.com/v1",
            api_key=os.getenv("OPENAI_API_KEY"),
            model="gpt-3.5-turbo",  # Using 3.5 for cost efficiency in testing
        )
        print("✅ Configured GPT-3.5-turbo for testing")

    # Run validation
    print("\nStarting framework validation...\n")
    results = await validator.run_validation()

    # Save results to file
    results_file = "framework_validation_results.json"

    # Convert results to serializable format
    serializable_results = {}
    for component, component_results in results.items():
        serializable_results[component] = {}
        for test, result in component_results.items():
            serializable_results[component][test] = bool(result)

    with open(results_file, "w") as f:
        json.dump(
            {
                "timestamp": datetime.now().isoformat(),
                "model_used": (
                    "gpt-3.5-turbo" if os.getenv("OPENAI_API_KEY") else "mock"
                ),
                "results": serializable_results,
                "summary": {
                    "total_tests": sum(len(r) for r in results.values()),
                    "passed_tests": sum(
                        sum(1 for v in r.values() if v) for r in results.values()
                    ),
                },
            },
            f,
            indent=2,
        )

    print(f"\n📝 Results saved to {results_file}")

    # Print final summary
    print("\n" + "=" * 70)
    print("FRAMEWORK VALIDATION COMPLETE")
    print("=" * 70 + "\n")

    # Calculate overall success
    total = sum(len(r) for r in results.values())
    passed = sum(sum(1 for v in r.values() if v) for r in results.values())

    if passed == total:
        print("🎉 PERFECT SCORE! All framework components working correctly!")
        print("\n✅ Phase 1: ResultPublisher - VALIDATED")
        print("✅ Phase 2: Flexible Model Integration - VALIDATED")
        print("✅ Memory System - VALIDATED")
        print("✅ Agent Coordination - VALIDATED")
        print("\n🚀 The Weaver AI framework is ready for production use!")
    elif passed / total >= 0.8:
        print(f"✅ VALIDATION PASSED: {passed}/{total} tests successful")
        print("\nMost framework components are working correctly.")
        print("Review the detailed results above for any failures.")
    else:
        print(f"⚠️  VALIDATION NEEDS ATTENTION: Only {passed}/{total} tests passed")
        print("\nSeveral framework components need fixes.")
        print("Review the detailed results above to identify issues.")

    return results


if __name__ == "__main__":
    # Run the validation
    asyncio.run(run_validation_with_gpt())
