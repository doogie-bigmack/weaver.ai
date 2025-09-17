"""Configuration-based model setup."""

import os

import yaml

from .mock import MockAdapter
from .openai_adapter import OpenAIAdapter
from .router import ModelRouter


def setup_router_from_config(config_path: str = "models.yaml") -> ModelRouter:
    """Set up model router from configuration file with BYOK support.

    Example config:
    ```yaml
    models:
      - name: mock
        type: mock

      - name: gpt3
        type: openai
        model: gpt-3.5-turbo
        requires_key: OPENAI_API_KEY

      - name: gpt4
        type: openai
        model: gpt-4
        requires_key: OPENAI_API_KEY

      - name: claude-3-opus
        type: anthropic
        model: claude-3-opus-20240229
        requires_key: ANTHROPIC_API_KEY

    default: mock
    fallback: mock
    ```
    """
    router = ModelRouter()

    # Always register mock as fallback
    router.register("mock", MockAdapter("mock"))

    # If no config file, just use mock
    if not os.path.exists(config_path):
        router.default_model = "mock"
        return router

    with open(config_path) as f:
        config = yaml.safe_load(f)

    for model_config in config.get("models", []):
        name = model_config["name"]
        model_type = model_config["type"]

        # Check if API key is required and available (BYOK)
        if requires_key := model_config.get("requires_key"):
            api_key = os.getenv(requires_key)
            if not api_key:
                # Skip this model if no key provided (BYOK principle)
                continue

        if model_type == "mock":
            adapter = MockAdapter(name)
        elif model_type == "openai":
            # Only create if API key exists
            api_key = os.getenv(model_config.get("requires_key", "OPENAI_API_KEY"))
            if api_key:
                model = model_config.get("model", "gpt-3.5-turbo")
                adapter = OpenAIAdapter(model)
            else:
                continue  # Skip if no API key
        elif model_type == "anthropic":
            # Only create if API key exists
            api_key = os.getenv(model_config.get("requires_key", "ANTHROPIC_API_KEY"))
            if api_key:
                from ..models.anthropic_adapter import AnthropicAdapter

                model = model_config.get("model", "claude-3-sonnet-20240229")
                adapter = AnthropicAdapter(model)
            else:
                continue  # Skip if no API key
        else:
            continue  # Skip unknown types

        router.register(name, adapter)

    # Set default model (prefer config default, then mock as fallback)
    router.default_model = config.get("default", "mock")

    # Ensure default model exists, otherwise fall back to mock
    if router.default_model not in router.models:
        router.default_model = config.get("fallback", "mock")

    return router
